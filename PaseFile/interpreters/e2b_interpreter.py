import os
from typing import Any, ClassVar, Dict, List, Optional

from .base import BaseInterpreter
from .interpreter_error import InterpreterError
from .logger import get_logger


logger = get_logger(__name__)


class E2BInterpreter(BaseInterpreter):
    r"""E2B代码解释器实现。

    参数:
        require_confirm (bool, 可选): 如果为True，出于安全考虑，在运行代码字符串前会提示用户确认。
            （默认值：:obj:`True`）
    """

    _CODE_TYPE_MAPPING: ClassVar[Dict[str, Optional[str]]] = {
        "python": None,
        "py3": None,
        "python3": None,
        "py": None,
        "shell": "bash",
        "bash": "bash",
        "sh": "bash",
        "java": "java",
        "javascript": "js",
        "r": "r",
    }

    
    def __init__(
        self,
        require_confirm: bool = True,
    ) -> None:
        from e2b_code_interpreter import Sandbox

        self.require_confirm = require_confirm
        self._sandbox = Sandbox(api_key=os.environ.get("E2B_API_KEY"))

    def __del__(self) -> None:
        r"""E2BInterpreter类的析构函数。

        此方法确保当解释器被删除时，e2b沙箱会被终止。
        """
        if (
            hasattr(self, '_sandbox')
            and self._sandbox is not None
            and self._sandbox.is_running()
        ):
            self._sandbox.kill()

    def run(
        self,
        code: str,
        code_type: str,
    ) -> str:
        r"""在e2b沙箱中执行给定的代码。

        参数:
            code (str): 要执行的代码字符串。
            code_type (str): 要执行的代码类型（例如，'python'，'bash'）。

        返回:
            str: 执行代码输出的字符串表示。

        异常:
            InterpreterError: 如果`code_type`不受支持，或者在代码执行过程中发生任何运行时错误。
        """
        if code_type not in self._CODE_TYPE_MAPPING:
            raise InterpreterError(
                f"不支持的代码类型 {code_type}。"
                f"`{self.__class__.__name__}`仅支持"
                f"{', '.join(list(self._CODE_TYPE_MAPPING.keys()))}。"
            )
        # 打印代码以进行安全检查
        if self.require_confirm:
            logger.info(
                f"以下{code_type}代码将在您的e2b沙箱上运行：{code}"
            )
            while True:
                choice = input("是否运行代码？[Y/n]：").lower()
                if choice in ["y", "yes", "ye"]:
                    break
                elif choice not in ["no", "n"]:
                    continue
                raise InterpreterError(
                    "执行已停止：用户选择不运行代码。"
                    "此选择将停止当前操作以及任何后续代码执行。"
                )

        if self._CODE_TYPE_MAPPING[code_type] is None:
            execution = self._sandbox.run_code(code)
        else:
            execution = self._sandbox.run_code(
                code=code, language=self._CODE_TYPE_MAPPING[code_type]
            )

        if execution.text and execution.text.lower() != "none":
            return execution.text

        if execution.logs:
            if execution.logs.stdout:
                return ",".join(execution.logs.stdout)
            elif execution.logs.stderr:
                return ",".join(execution.logs.stderr)

        return str(execution.error)

    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。"""
        return list(self._CODE_TYPE_MAPPING.keys())

    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新*python*解释器的动作空间"""
        raise RuntimeError("E2B不支持`action_space`。")

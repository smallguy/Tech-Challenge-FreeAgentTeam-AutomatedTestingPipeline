from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseInterpreter(ABC):
    r"""代码解释器的抽象基类。"""

    @abstractmethod
    def run(self, code: str, code_type: str) -> str:
        r"""根据给定代码的类型执行该代码。

            参数:
                code (字符串): 待执行的代码内容。
                code_type (字符串): 代码类型，该值必须是 `supported_code_types()` 函数返回的
                    类型之一。

            返回值:
                字符串: 代码执行的结果。若执行失败，返回内容应包含足够信息，以便诊断并修正
                    相关问题。

            异常:
                InterpreterError: 当代码执行遇到可通过修改或重新生成代码解决的错误时触发。
        """
        pass

    @abstractmethod
    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。"""
        pass

    @abstractmethod
    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新*python*解释器的操作空间"""
        pass

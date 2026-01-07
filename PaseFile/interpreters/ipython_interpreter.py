import queue
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .base import BaseInterpreter
from .interpreter_error import InterpreterError

if TYPE_CHECKING:
    from jupyter_client import BlockingKernelClient, KernelManager

TIMEOUT = 30


class JupyterKernelInterpreter(BaseInterpreter):
    r"""一个用于在Jupyter内核中执行代码字符串的类。

    参数:
        require_confirm (bool, 可选): 如果为`True`，出于安全考虑，在运行代码字符串前会提示用户确认。默认为`True`。
        print_stdout (bool, 可选): 如果为`True`，会打印执行代码的标准输出。默认为`False`。
        print_stderr (bool, 可选): 如果为`True`，会打印执行代码的标准错误。默认为`True`。
    """

    def __init__(
        self,
        require_confirm: bool = True,
        print_stdout: bool = False,
        print_stderr: bool = True,
    ) -> None:
        self.require_confirm = require_confirm
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr

        self.kernel_manager: Optional[KernelManager] = None
        self.client: Optional[BlockingKernelClient] = None

    def __del__(self) -> None:
        r"""清理内核和客户端。"""

        if self.kernel_manager:
            self.kernel_manager.shutdown_kernel()
        if self.client:
            self.client.stop_channels()

    def _initialize_if_needed(self) -> None:
        r"""如果内核管理器和客户端尚未初始化，则对它们进行初始化。"""

        if self.kernel_manager is not None:
            return

        from jupyter_client.manager import start_new_kernel

        self.kernel_manager, self.client = start_new_kernel()

    @staticmethod
    def _clean_ipython_output(output: str) -> str:
        r"""从输出中移除ANSI转义序列。"""

        ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        return ansi_escape.sub('', output)

    def _execute(self, code: str, timeout: float) -> str:
        r"""在Jupyter内核中执行代码并返回结果。"""

        if not self.kernel_manager or not self.client:
            raise InterpreterError("Jupyter客户端未初始化。")

        self.client.execute(code)
        outputs = []
        while True:
            try:
                msg = self.client.get_iopub_msg(timeout=timeout)
                msg_content = msg["content"]
                msg_type = msg.get("msg_type", None)

                if msg_content.get("execution_state", None) == "idle":
                    break

                if msg_type == "error":
                    print(msg_content.keys())
                    print(msg_content)
                    traceback = "\n".join(msg_content["traceback"])
                    outputs.append(traceback)
                elif msg_type == "stream":
                    outputs.append(msg_content["text"])
                elif msg_type in ["execute_result", "display_data"]:
                    outputs.append(msg_content["data"]["text/plain"])
                    if "image/png" in msg_content["data"]:
                        outputs.append(
                            f"\n![image](data:image/png;base64,"
                            f"{msg_content['data']['image/png']})\n"
                        )
            except queue.Empty:
                outputs.append("超时")
                break
            except Exception as e:
                outputs.append(f"发生异常: {e!s}")
                break

        exec_result = "\n".join(outputs)
        return self._clean_ipython_output(exec_result)

    def run(self, code: str, code_type: str) -> str:
        r"""在Jupyter内核中执行给定的代码。

        参数:
            code (str): 要执行的代码字符串。
            code_type (str): 要执行的代码类型（例如，'python'，'bash'）。

        返回:
            str: 包含所执行代码的捕获结果的字符串。

        异常:
            InterpreterError: 当代码执行出现错误时抛出。
        """
        self._initialize_if_needed()

        if code_type == "bash":
            code = f"%%bash\n({code})"
        try:
            result = self._execute(code, timeout=TIMEOUT)
        except Exception as e:
            raise InterpreterError(f"执行失败: {e!s}")

        return result

    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。

        返回:
            List[str]: 支持的代码类型。
        """
        return ["python", "bash"]

    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新解释器的动作空间。

        参数:
            action_space (Dict[str, Any]): 表示新的或更新后的动作空间的字典。

        异常:
            RuntimeError: 始终抛出，因为`JupyterKernelInterpreter`不支持更新动作空间。
        """
        raise RuntimeError(
            "SubprocessInterpreter不支持`action_space`。"
        )
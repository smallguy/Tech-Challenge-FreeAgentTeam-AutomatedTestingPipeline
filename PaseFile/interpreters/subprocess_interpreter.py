import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from colorama import Fore

from .base import BaseInterpreter
from .interpreter_error import InterpreterError
from .logger import get_logger

logger = get_logger(__name__)


class SubprocessInterpreter(BaseInterpreter):
    r"""SubprocessInterpreter是一个用于在子进程中执行代码文件或代码字符串的类。

    这个类负责在子进程中执行不同脚本语言（目前支持Python和Bash）的代码，
    捕获它们的stdout和stderr流，并允许在执行代码字符串前进行用户确认。

    参数:
        require_confirm (bool, 可选): 如果为True，在运行代码字符串前提示用户确认以确保安全。
            （默认值: :obj:`True`）
        print_stdout (bool, 可选): 如果为True，打印执行代码的标准输出。（默认值: :obj:`False`）
        print_stderr (bool, 可选): 如果为True，打印执行代码的标准错误。（默认值: :obj:`True`）
        execution_timeout (int, 可选): 等待代码执行完成的最大时间（秒）。（默认值: :obj:`60`）
    """

    _CODE_EXECUTE_CMD_MAPPING: ClassVar[Dict[str, Dict[str, str]]] = {
        "python": {"posix": "python {file_name}", "nt": "python {file_name}"},
        "bash": {"posix": "bash {file_name}", "nt": "bash {file_name}"},
        "r": {"posix": "Rscript {file_name}", "nt": "Rscript {file_name}"},
    }

    _CODE_EXTENSION_MAPPING: ClassVar[Dict[str, str]] = {
        "python": "py",
        "bash": "sh",
        "r": "R",
    }

    _CODE_TYPE_MAPPING: ClassVar[Dict[str, str]] = {
        "python": "python",
        "py3": "python",
        "python3": "python",
        "py": "python",
        "shell": "bash",
        "bash": "bash",
        "sh": "bash",
        "r": "r",
        "R": "r",
    }

    def __init__(
        self,
        require_confirm: bool = True,
        print_stdout: bool = False,
        print_stderr: bool = True,
        execution_timeout: int = 60,
        workspace_dir: str | None = None,
    ) -> None:
        self.require_confirm = require_confirm
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self.execution_timeout = execution_timeout
        self.workspace_dir = workspace_dir

    def run_file(
        self,
        file: Path,
        code_type: str,
    ) -> str:
        r"""在子进程中执行代码文件并捕获其输出。

        参数:
            file (Path): 要运行的文件的路径对象。
            code_type (str): 要执行的代码类型（例如，'python'，'bash'）。

        返回:
            str: 包含所执行代码的捕获的标准输出和标准错误的字符串。
        """
        if not file.is_file():
            return f"{file} 不是一个文件。"
        code_type = self._check_code_type(code_type)
        if self._CODE_TYPE_MAPPING[code_type] == "python":
            # 对于Python代码，使用ast进行分析和修改
            import ast

            import astor

            with open(file, 'r', encoding='utf-8') as f:
                source = f.read()

            # 解析源代码
            try:
                tree = ast.parse(source)
                # 获取最后一个节点
                if tree.body:
                    last_node = tree.body[-1]
                    # 处理通常不会产生输出的表达式
                    # 例如：在REPL中，输入'1 + 2'应该显示'3'

                    if isinstance(last_node, ast.Expr):
                        # 只有当它不是已经是一个print调用时，才用print(repr())包装
                        if not (
                            isinstance(last_node.value, ast.Call)
                            and isinstance(last_node.value.func, ast.Name)
                            and last_node.value.func.id == 'print'
                        ):
                            # 转换AST，将表达式包装在print(repr())中
                            # 转换示例：
                            #   转换前：x + y
                            #   转换后：print(repr(x + y))
                            tree.body[-1] = ast.Expr(
                                value=ast.Call(
                                    # 创建print()函数调用
                                    func=ast.Name(id='print', ctx=ast.Load()),
                                    args=[
                                        ast.Call(
                                            # 创建repr()函数调用
                                            func=ast.Name(
                                                id='repr', ctx=ast.Load()
                                            ),
                                            # 将原始表达式作为参数传递给repr()
                                            args=[last_node.value],
                                            keywords=[],
                                        )
                                    ],
                                    keywords=[],
                                )
                            )
                    # 修复缺失的源位置
                    ast.fix_missing_locations(tree)
                    # 转换回源代码
                    modified_source = astor.to_source(tree)
                    # 创建包含修改后源代码的临时文件
                    temp_file = self._create_temp_file(modified_source, "py")
                    cmd = ["python", str(temp_file)]
            except (SyntaxError, TypeError, ValueError) as e:
                logger.warning(f"无法使用AST解析Python代码：{e}")
                platform_type = 'posix' if os.name != 'nt' else 'nt'
                cmd_template = self._CODE_EXECUTE_CMD_MAPPING[code_type][
                    platform_type
                ]
                base_cmd = cmd_template.split()[0]

                # 检查命令是否可用
                if not self._is_command_available(base_cmd):
                    raise InterpreterError(
                        f"未找到命令'{base_cmd}'。请确保它已安装并在您的PATH中可用。"
                    )

                cmd = [base_cmd, str(file)]
        else:
            # 对于非Python代码，使用标准执行方式
            platform_type = 'posix' if os.name != 'nt' else 'nt'
            cmd_template = self._CODE_EXECUTE_CMD_MAPPING[code_type][
                platform_type
            ]
            base_cmd = cmd_template.split()[0]  # 获取'python'，'bash'等

            # 检查命令是否可用
            if not self._is_command_available(base_cmd):
                raise InterpreterError(
                    f"未找到命令'{base_cmd}'。请确保它已安装并在您的PATH中可用。"
                )

            cmd = [base_cmd, str(file)]

        # 获取当前Python可执行文件的环境变量
        env = os.environ.copy()

        # 在Windows上，确保使用正确的Python可执行文件路径
        if os.name == 'nt':
            python_path = os.path.dirname(sys.executable)
            if 'PATH' in env:
                env['PATH'] = python_path + os.pathsep + env['PATH']
            else:
                env['PATH'] = python_path

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                shell=False,  # 为了安全，永远不要使用shell=True
                cwd=self.workspace_dir,  # 将工作目录设置为工作区
            )
            # 添加超时以防止进程挂起
            stdout, stderr = proc.communicate(timeout=self.execution_timeout)
            return_code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return_code = proc.returncode
            timeout_msg = (
                f"进程在{self.execution_timeout}秒后超时并被终止。"
            )
            stderr = f"{stderr}\n{timeout_msg}"

        # 如果创建了临时文件，则清理它
        temp_file_to_clean = locals().get('temp_file')
        if temp_file_to_clean is not None:
            try:
                if temp_file_to_clean.exists():
                    try:
                        temp_file_to_clean.unlink()
                    except PermissionError:
                        # 在Windows上，文件可能被锁定
                        logger.warning(
                            f"无法删除临时文件{temp_file_to_clean}（可能被锁定）"
                        )
            except Exception as e:
                logger.warning(f"清理临时文件失败：{e}")

        if self.print_stdout and stdout:
            print("======标准输出======")
            print(Fore.GREEN + stdout + Fore.RESET)
            print("====================")
        if self.print_stderr and stderr:
            print("======标准错误======")
            print(Fore.RED + stderr + Fore.RESET)
            print("====================")

        # 构建执行结果
        exec_result = ""
        if stdout:
            exec_result += stdout
        if stderr:
            exec_result += f"（标准错误：{stderr}）"
        if return_code != 0:
            error_msg = f"（执行失败，返回代码{return_code}）"
            if not stderr:
                exec_result += error_msg
            elif error_msg not in stderr:
                exec_result += error_msg
        return exec_result

    def run(
        self,
        code: str,
        code_type: str,
    ) -> str:
        r"""生成一个包含给定代码的临时文件，执行它，然后删除该文件。

        参数:
            code (str): 要执行的代码字符串。
            code_type (str): 要执行的代码类型（例如，'python'，'bash'）。

        返回:
            str: 包含所执行代码的捕获的标准输出和标准错误的字符串。

        抛出:
            InterpreterError: 如果用户拒绝运行代码或代码类型不受支持。
        """
        code_type = self._check_code_type(code_type)

        # 打印代码以供安全检查
        if self.require_confirm:
            logger.info(
                f"以下{code_type}代码将在您的计算机上运行：{code}"
            )
            while True:
                choice = input("运行代码吗？[Y/n]：").lower().strip()
                if choice in ["y", "yes", "ye", ""]:
                    break
                elif choice in ["no", "n"]:
                    raise InterpreterError(
                        "执行中止：用户选择不运行代码。此选择将停止当前操作和任何进一步的代码执行。"
                    )
                else:
                    print("请输入'y'或'n'。")

        temp_file_path = None
        temp_dir = None
        try:
            temp_file_path = self._create_temp_file(
                code=code, extension=self._CODE_EXTENSION_MAPPING[code_type]
            )
            temp_dir = temp_file_path.parent
            return self.run_file(temp_file_path, code_type)
        finally:
            # 清理临时文件和目录
            try:
                if temp_file_path and temp_file_path.exists():
                    try:
                        temp_file_path.unlink()
                    except PermissionError:
                        # 在Windows上，文件可能被锁定
                        logger.warning(
                            f"无法删除临时文件{temp_file_path}"
                        )

                if temp_dir and temp_dir.exists():
                    try:
                        import shutil

                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception as e:
                        logger.warning(f"无法删除临时目录：{e}")
            except Exception as e:
                logger.warning(f"清理过程中出错：{e}")

    def _create_temp_file(self, code: str, extension: str) -> Path:
        r"""创建一个包含给定代码和扩展名的临时文件。

        参数:
            code (str): 要写入临时文件的代码。
            extension (str): 要使用的文件扩展名。

        返回:
            Path: 所创建的临时文件的路径。
        """
        try:
            # 首先创建一个临时目录以确保我们有写入权限
            temp_dir = tempfile.mkdtemp()
            # 创建具有适当扩展名的文件路径
            file_path = Path(temp_dir) / f"temp_code.{extension}"

            # 使用适当的编码将代码写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            return file_path
        except Exception as e:
            # 如果创建失败，清理临时目录
            if 'temp_dir' in locals():
                try:
                    import shutil

                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
            logger.error(f"创建临时文件失败：{e}")
            raise

    def _check_code_type(self, code_type: str) -> str:
        if code_type not in self._CODE_TYPE_MAPPING:
            raise InterpreterError(
                f"不支持的代码类型{code_type}。目前`{self.__class__.__name__}`仅支持"
                f"{', '.join(self._CODE_EXTENSION_MAPPING.keys())}。"
            )
        return self._CODE_TYPE_MAPPING[code_type]

    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。"""
        return list(self._CODE_EXTENSION_MAPPING.keys())

    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新*python*解释器的动作空间"""
        raise RuntimeError(
            "SubprocessInterpreter不支持`action_space`。"
        )

    def _is_command_available(self, command: str) -> bool:
        r"""检查系统PATH中是否有某个命令可用。

        参数:
            command (str): 要检查的命令。

        返回:
            bool: 如果命令可用则为True，否则为False。
        """
        if os.name == 'nt':  # Windows
            # 在Windows上，使用where.exe查找命令
            try:
                with open(os.devnull, 'w') as devnull:
                    subprocess.check_call(
                        ['where', command],
                        stdout=devnull,
                        stderr=devnull,
                        shell=False,
                    )
                return True
            except subprocess.CalledProcessError:
                return False
        else:  # 类Unix系统
            # 在类Unix系统上，使用which查找命令
            try:
                with open(os.devnull, 'w') as devnull:
                    subprocess.check_call(
                        ['which', command],
                        stdout=devnull,
                        stderr=devnull,
                        shell=False,
                    )
                return True
            except subprocess.CalledProcessError:
                return False
import io
import shlex
import tarfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
import subprocess
from colorama import Fore

from .base import BaseInterpreter
from .interpreter_error import InterpreterError
from .logger import get_logger


def is_docker_running() -> bool:
    r"""检查    检查 Docker 守护进程是否正在运行。

    返回值:
        布尔值: 若 Docker 守护守护进程进程正在正在运行则返回 True，否则返回 False。
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
if TYPE_CHECKING:
    from docker.models.containers import Container

logger = get_logger(__name__)


class DockerInterpreter(BaseInterpreter):
    r"""
    用于在 Docker 容器中执行代码文件或代码字符串的类。

    该类负责在 Docker 容器内执行不同脚本语言（当前支持 Python 和 Bash）的代码，
    捕获其标准输出（stdout）和标准错误（stderr）流，并允许在执行代码字符串前由用户确认。

    参数:
        require_confirm (布尔值，可选): 若设为 True，为保障安全，会在运行代码字符串前提示用户确认。
            默认值为 True。
        print_stdout (布尔值，可选): 若设为 True，会打印已执行代码的标准输出。默认值为 False。
        print_stderr (布尔值，可选): 若设为 True，会打印已执行代码的标准错误。默认值为 True。
    """

    _CODE_EXECUTE_CMD_MAPPING: ClassVar[Dict[str, str]] = {
        "python": "python {file_name}",
        "bash": "bash {file_name}",
        "r": "Rscript {file_name}",
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
    ) -> None:
        self.require_confirm = require_confirm
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr

        # 延迟初始化容器
        self._container: Optional[Container] = None

    def __del__(self) -> None:
        r"""
        DockerInterpreter 类的析构方法。

        该方法确保当解释器实例被销毁时，对应的 Docker 容器会被移除。
        """
        if self._container is not None:
            self._container.remove(force=True)

    def _initialize_if_needed(self) -> None:
        if self._container is not None:
            return

        if not is_docker_running():
            raise InterpreterError(
                "Docker 守护进程未运行。请安装/启动 docker 后重试。"
            )

        import docker

        client = docker.from_env()

        # 构建包含 Python 和 R 的自定义镜像
        dockerfile_path = Path(__file__).parent / "docker"
        image_tag = "camel-interpreter:latest"
        try:
            client.images.get(image_tag)
        except docker.errors.ImageNotFound:
            logger.info("正在构建自定义解释器镜像...")
            client.images.build(
                path=str(dockerfile_path),
                tag=image_tag,
                rm=True,
            )

        self._container = client.containers.run(
            image_tag,
            detach=True,
            name=f"camel-interpreter-{uuid.uuid4()}",
            command="tail -f /dev/null",
        )

    def _create_file_in_container(self, content: str) -> Path:
        # 为文件获取一个随机名称
        filename = str(uuid.uuid4())
        # 在内存中创建一个 tar 文件
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(content)
            tar.addfile(tarinfo, io.BytesIO(content.encode('utf-8')))
        tar_stream.seek(0)

        # 将 tar 文件复制到容器中
        if self._container is None:
            raise InterpreterError(
                "容器未初始化。请尝试重新运行代码。"
            )
        self._container.put_archive("/tmp", tar_stream)
        return Path(f"/tmp/{filename}")

    def _run_file_in_container(
        self,
        file: Path,
        code_type: str,
    ) -> str:
        code_type = self._check_code_type(code_type)
        commands = shlex.split(
            self._CODE_EXECUTE_CMD_MAPPING[code_type].format(
                file_name=file.as_posix()
            )
        )
        if self._container is None:
            raise InterpreterError(
                "容器未初始化。请尝试重新运行代码。"
            )
        stdout, stderr = self._container.exec_run(
            commands,
            demux=True,
        ).output

        if self.print_stdout and stdout:
            print("======标准输出======")
            print(Fore.GREEN + stdout.decode() + Fore.RESET)
            print("====================")
        if self.print_stderr and stderr:
            print("======标准错误======")
            print(Fore.RED + stderr.decode() + Fore.RESET)
            print("====================")
        exec_result = f"{stdout.decode()}" if stdout else ""
        exec_result += f"(标准错误: {stderr.decode()})" if stderr else ""
        return exec_result

    def run(
        self,
        code: str,
        code_type: str,
    ) -> str:
        r"""
        在关联到当前解释器的 Docker 容器中执行给定代码，并捕获标准输出（stdout）和标准错误（stderr）流。

        参数:
            code (字符串): 待执行的代码字符串。
            code_type (字符串): 待执行代码的类型（例如：'python'、'bash'）。

        返回值:
            字符串: 包含已执行代码的捕获到的标准输出和标准错误信息的字符串。

        异常:
            InterpreterError: 触发场景包括：用户拒绝运行代码、代码类型不被支持、
                或 Docker API/容器执行过程中出现错误。
        """
        import docker.errors

        code_type = self._check_code_type(code_type)

        # 打印代码以进行安全检查
        if self.require_confirm:
            logger.info(
                f"以下 {code_type} 代码将在您的计算机上运行: {code}"
            )
            while True:
                choice = input("是否运行代码? [Y/n]:").lower()
                if choice in ["y", "yes", "ye", ""]:
                    break
                elif choice not in ["no", "n"]:
                    continue
                raise InterpreterError(
                    "执行已中止：用户选择不运行代码。"
                    "此选择将停止当前操作及任何后续代码执行。"
                )

        self._initialize_if_needed()

        try:
            temp_file_path = self._create_file_in_container(code)
            result = self._run_file_in_container(temp_file_path, code_type)
        except docker.errors.APIError as e:
            raise InterpreterError(
                f"由于 docker API 错误，执行已中止：{e.explanation}。"
                "此选择将停止当前操作及任何后续代码执行。"
            ) from e
        except docker.errors.DockerException as e:
            raise InterpreterError(
                f"由于 docker 异常，执行已中止：{e}。"
                "此选择将停止当前操作及任何后续代码执行。"
            ) from e
        return result

    def _check_code_type(self, code_type: str) -> str:
        if code_type not in self._CODE_TYPE_MAPPING:
            raise InterpreterError(
                f"不支持的代码类型 {code_type}。当前"
                f"`{self.__class__.__name__}` 仅支持"
                f"{', '.join(self._CODE_EXTENSION_MAPPING.keys())}。"
            )
        return self._CODE_TYPE_MAPPING[code_type]

    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。"""
        return list(self._CODE_EXTENSION_MAPPING.keys())

    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新 *python* 解释器的操作空间"""
        raise RuntimeError(
            "SubprocessInterpreter 不支持 " "`action_space`。"
        )
"""沙箱管理模块"""
import os
from pathlib import Path
from typing import List, Literal, Optional

from interpreters.interpreters import DockerInterpreter
from interpreters.interpreters import E2BInterpreter
from interpreters.interpreters import InternalPythonInterpreter
from interpreters.interpreters import JupyterKernelInterpreter
from interpreters.interpreters import SubprocessInterpreter

from validators import validate_imports
from constants import DEFAULT_IMPORT_WHITELIST
from utils import get_workspace_dir
from logger import get_logger

# 全局沙箱缓存
_task_sandboxes = {}

logger = get_logger(__name__)

class UnifiedWorkspaceSandbox:
    """
    具有扁平工作区结构和导入白名单验证的统一沙箱。
    
    🎯 关键特性:
        • 所有文件在单一工作区目录中
        • 跨执行保持持久环境
        • 支持终端命令
        • 文件覆盖行为（无版本控制）
        • 导入白名单验证以确保安全
    
    🔒 导入安全:
        • 根据白名单验证所有导入语句
        • 支持torch、transformers和其他ML库
        • 阻止未经授权的导入以确保安全
    """

    def __init__(
        self,
        workspace_dir: str,
        sandbox: Literal["internal_python", "jupyter", "docker", "subprocess", "e2b"] = "subprocess",
        *,
        verbose: bool = False,
        unsafe_mode: bool = False,
        import_whitelist: Optional[list[str]] = None,
        require_confirm: bool = False,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.verbose = verbose
        
        # 设置导入白名单
        self.import_whitelist = import_whitelist or DEFAULT_IMPORT_WHITELIST.copy()
        self.unsafe_mode = unsafe_mode  # 如果为True，跳过白名单验证
        self.require_confirm = require_confirm

        # 初始化解释器，确保使用正确的工作区目录
        self.interpreter = self._initialize_interpreter(sandbox, self.workspace_dir)

    def _initialize_interpreter(self, sandbox_type: str, work_dir: str):
        """初始化正确的解释器。"""
        
        # 注意：工作目录现在通过workspace_dir参数直接传递给SubprocessInterpreter，
        # 消除了大多数情况下对os.chdir()的需求。
        
        if sandbox_type == "internal_python":
            return SubprocessInterpreter(
                require_confirm=self.require_confirm,
                print_stdout=self.verbose,
                print_stderr=self.verbose,
                workspace_dir=work_dir,
            )
        elif sandbox_type == "jupyter":
            return JupyterKernelInterpreter(
                require_confirm=self.require_confirm,
                print_stdout=self.verbose,
                print_stderr=self.verbose,
            )
        elif sandbox_type == "docker":
            return DockerInterpreter(
                require_confirm=self.require_confirm,
                print_stdout=self.verbose,
                print_stderr=self.verbose,
            )
        elif sandbox_type == "e2b":
            return E2BInterpreter(require_confirm=self.require_confirm)
        
        # 默认使用SubprocessInterpreter
        return SubprocessInterpreter(
            require_confirm=self.require_confirm,
            print_stdout=self.verbose,
            print_stderr=self.verbose,
            workspace_dir=work_dir,
        )

    def execute_code(self, code: str, filename: str) -> str:
        """
        使用导入白名单验证执行Python代码并保存到指定文件名。
        
        🔧 执行过程:
            1. 根据白名单验证导入
            2. 切换到工作区目录
            3. 将代码写入指定文件名（覆盖现有文件）
            4. 在持久环境中执行代码
            5. 返回带有验证信息的执行结果
        
        🔒 白名单验证:
            • 检查代码中的所有导入语句
            • 允许: torch, transformers, numpy, pandas, matplotlib等
            • 阻止: 不在白名单中的未授权系统模块、网络库
        
        Args:
            code: 要执行的Python代码
            filename: 目标文件名（必需，如果存在则覆盖）
            
        Returns:
            str: 执行输出，包含导入验证结果和任何错误信息
        """

        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        
        original_cwd = os.getcwd()
        os.chdir(self.workspace_dir)
        
        try:
            # 如果不是不安全模式，则验证导入
            validation_result = ""
            if not self.unsafe_mode:
                is_valid, allowed_imports, forbidden_imports = validate_imports(code, self.import_whitelist)
                
                if not is_valid:
                    error_msg = f"❌ 导入验证失败\n"
                    error_msg += f"禁止的导入: {', '.join(forbidden_imports)}\n"
                    error_msg += f"白名单中允许的导入:\n"
                    for item in sorted(self.import_whitelist):
                        error_msg += f"  • {item}\n"
                    error_msg += f"\n💡 请联系管理员将其他包添加到白名单。"
                    return error_msg
                
                if allowed_imports:
                    validation_result = f"✅ 导入已验证: {', '.join(sorted(allowed_imports))}\n"
                    validation_result += f"🔒 白名单包含: {len(self.import_whitelist)} 个已批准模块\n"
                    validation_result += "=" * 50 + "\n"
            
            # 将代码写入文件（如果存在则覆盖）
            code_file = Path(self.workspace_dir) / filename
            file_existed = code_file.exists()
            code_file.write_text(code, encoding="utf-8")
            logger.info(f"代码写入: {filename} ({'已覆盖' if file_existed else '已创建'})")
            
            # 执行代码
            execution_result = self.interpreter.run(code, code_type="python")
            
            # 合并验证和执行结果
            full_result = validation_result + execution_result
            return full_result
            
        finally:
            os.chdir(original_cwd)

    def execute_terminal_command(self, command: str) -> str:
        """
        在工作区中执行终端命令。
        
        Args:
            command: 要执行的Shell命令
            
        Returns:
            str: 命令执行结果
        """
        original_cwd = os.getcwd()
        os.chdir(self.workspace_dir)
        
        try:
            result = self.interpreter.run(command, code_type="shell")
            return result
        finally:
            os.chdir(original_cwd)


def get_or_create_sandbox(
    workspace_dir: str,
    sandbox: str,
    verbose: bool,
    unsafe_mode: bool,
    import_whitelist: Optional[List[str]] = None
) -> UnifiedWorkspaceSandbox:
    """
    获取工作区的现有沙箱或创建新沙箱。

    此函数使用全局字典基于工作区目录缓存沙箱实例。
    这可确保同一任务中的所有操作使用相同的沙箱，保持状态。

    Args:
        workspace_dir: 工作区目录的绝对路径。
        sandbox: 要创建的沙箱类型。
        verbose: 是否启用详细日志记录。
        unsafe_mode: 是否禁用安全检查（例如导入验证）。
        import_whitelist: 允许的Python模块列表。
        
    Returns:
        UnifiedWorkspaceSandbox的实例。
    """
    global _task_sandboxes
    if workspace_dir not in _task_sandboxes:
        if verbose:
            print(f"为工作区创建新沙箱: {workspace_dir}")
        _task_sandboxes[workspace_dir] = UnifiedWorkspaceSandbox(
            workspace_dir=workspace_dir,
            sandbox=sandbox,
            verbose=verbose,
            unsafe_mode=unsafe_mode,
            import_whitelist=import_whitelist,
        )
    return _task_sandboxes[workspace_dir]
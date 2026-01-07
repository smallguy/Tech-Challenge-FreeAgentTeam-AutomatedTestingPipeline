"""通用工具函数"""
import os
from pathlib import Path
from typing import Optional

#from .constants import CODE_EXTENSIONS


def get_workspace_dir(task_cache_dir: Optional[str] = None) -> str:
    """
    获取或创建任务的统一工作区目录。
    
    📁 目录结构:
        task_cache_dir/workspace/  (扁平结构 - 所有文件都在这里)
    
    Args:
        task_cache_dir: 任务特定的缓存目录路径。这是必需的。
        
    Returns:
        str: 工作区目录的绝对路径
        
    Raises:
        ValueError: 如果未提供task_cache_dir。
    """
    if not task_cache_dir:
        raise ValueError("必须提供task_cache_dir来定位工作区。")
    
    ospath = os.getenv("OSPATH")
    if ospath:
        workspace_dir = Path(ospath) / task_cache_dir / "workspace"
    else:
        workspace_dir = Path(task_cache_dir) / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return str(workspace_dir)
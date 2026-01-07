import datetime
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Demo", log_level="ERROR")

from pathlib import Path
from rich.tree import Tree
from rich.console import Console
from io import StringIO
import os
from typing import Optional, Dict, List, Any, Tuple
import sys
import json
import logging
from sandbox import _task_sandboxes  # 从sd_filemessage复用沙箱检查逻辑
from logger import get_logger

# # 日志配置
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

def normalize_file_path(path: str) -> str:
    """标准化文件路径（兼容Windows大小写不敏感特性）
    
    统一路径格式：转换为POSIX格式并转为小写，解决不同系统路径格式差异问题
    
    Args:
        path: 原始文件路径
    
    Returns:
        标准化后的路径字符串
    """
    if not path:
        return ""
    return Path(path).as_posix().lower()


def recursively_find_file_in_json_tree(tree_data: dict, target_path: str) -> dict | None:
    """递归遍历JSON树状结构，查找指定路径的文件信息
    
    遍历目录结构的JSON数据，匹配目标文件的完整路径（忽略大小写和路径分隔符差异）
    
    Args:
        tree_data: 解析后的树状结构JSON字典
        target_path: 要查找的文件完整路径
    
    Returns:
        匹配的文件节点字典（若找到且为文件）；None（未找到或目标为目录）
    """
    target_path_norm = normalize_file_path(target_path)
    current_path_norm = normalize_file_path(tree_data.get("full_path", ""))

    # 检查当前节点是否为目标文件
    if tree_data.get("type") == "file" and current_path_norm == target_path_norm:
        return tree_data
    
    # 若为目录，递归遍历子节点
    if tree_data.get("type") == "directory" and tree_data.get("children"):
        for child in tree_data["children"]:
            found_node = recursively_find_file_in_json_tree(child, target_path)
            if found_node is not None:
                return found_node
    
    return None


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{int(size) if i == 0 else size:.1f} {size_names[i]}"

def _get_file_type_description(extension: str) -> str:
    """根据扩展名返回文件类型描述"""
    type_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
        '.html': 'HTML', '.css': 'CSS', '.json': 'JSON', '.xml': 'XML',
        '.yaml': 'YAML', '.yml': 'YAML', '.toml': 'TOML', '.ini': 'Config',
        '.conf': 'Config', '.cfg': 'Config', '.txt': 'Text', '.md': 'Markdown',
        '.rst': 'reStruct', '.csv': 'CSV Data', '.tsv': 'TSV Data',
        '.xlsx': 'Excel', '.xls': 'Excel', '.pdf': 'PDF', '.png': 'PNG Image',
        '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image', '.gif': 'GIF Image',
        '.svg': 'SVG Image', '.bmp': 'BMP Image', '.webp': 'WebP Image',
        '.mp4': 'Video', '.avi': 'Video', '.mov': 'Video', '.mp3': 'Audio',
        '.wav': 'Audio', '.zip': 'Archive', '.tar': 'Archive', '.gz': 'Archive',
        '.rar': 'Archive', '.sql': 'SQL', '.db': 'Database', '.sqlite': 'SQLite',
        '.log': 'Log', '.sh': 'Shell', '.bat': 'Batch', '.ps1': 'PowerShell',
        '.r': 'R Script', '.ipynb': 'Jupyter NB'
    }
    return type_map.get(extension, 'Unknown')

def get_workspace_dir(task_cache_dir: Optional[str] = None) -> str:
    """获取/创建工作区目录（复用原有逻辑）"""
    if not task_cache_dir:
        raise ValueError("必须提供task_cache_dir来定位工作区。")
    
    ospath = os.getenv("OSPATH")
    workspace_dir = Path(ospath) / task_cache_dir if ospath else Path(task_cache_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return str(workspace_dir)

def _build_tree_and_stats_recursive(path: Path) -> Tuple[Dict[str, Any], int, int, Dict[str, Dict[str, int]]]:
    """
    单次递归完成：构建树状结构 + 统计文件信息（核心优化函数）
    返回值：
        node: 树节点字典
        total_files: 当前路径下的总文件数
        total_size: 当前路径下的总大小（字节）
        file_types: 当前路径下的文件类型分布 {后缀: {count: 数量, size: 大小}}
    """

    node = {
        "name": path.name,
        "full_path": str(path),
        "type": "directory" if path.is_dir() else "file",
        "children": [] if path.is_dir() else None,
        "error": None
    }

    total_files = 0
    total_size = 0
    file_types = {}

    try:
        if path.is_file():
            # 处理文件：填充文件详情 + 初始化统计
            stat = path.stat()
            suffix = path.suffix.lower() or "no_extension"
            file_size = stat.st_size
            
            # 填充文件节点详情
            node.update({
                "size_bytes": file_size,
                "size_human": _format_file_size(file_size),
                "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "extension": suffix,
                "file_type": _get_file_type_description(suffix)
            })
            
            # 统计当前文件
            total_files = 1
            total_size = file_size
            file_types[suffix] = {"count": 1, "size": file_size}

        else:
            # 处理目录：递归遍历子项 + 汇总统计
            for child in sorted(path.iterdir()):
                child_node, child_files, child_size, child_types = _build_tree_and_stats_recursive(child)
                node["children"].append(child_node)
                
                # 汇总子节点统计信息
                total_files += child_files
                total_size += child_size
                
                # 合并文件类型分布
                for ext, info in child_types.items():
                    if ext not in file_types:
                        file_types[ext] = {"count": 0, "size": 0}
                    file_types[ext]["count"] += info["count"]
                    file_types[ext]["size"] += info["size"]

    except PermissionError:
        node["error"] = "Permission denied (权限不足)"
    except OSError as e:
        node["error"] = f"OS error: {str(e)}"
    except Exception as e:
        node["error"] = f"Unexpected error: {str(e)}"
    
    return node, total_files, total_size, file_types

@mcp.tool()
def get_workspace_structure(task_cache_dir: str ) -> str:
    """
    获取带详细信息的工作区树状结构 + 全量文件统计信息
    
    Args:
        task_cache_dir: 工作区根目录路径
    
    Returns:
        对应格式的工作区结构(保存在file_struct.json)+统计信息字符串(保存在total_mes.txt)
    """
    workspace_dir = get_workspace_dir(task_cache_dir)
    workspace_path = Path(workspace_dir)
    
    if not workspace_path.exists():
        error_result = {
            "error": "Workspace directory does not exist",
            "path": workspace_dir
        }
        return json.dumps(error_result, ensure_ascii=False, indent=2) if return_format == "json" else f"📂 工作区目录不存在: {workspace_dir}"
    
    tree_json, total_files, total_size, file_types = _build_tree_and_stats_recursive(workspace_path)
    
    # 整合sd_filemessage的全量统计信息（含沙箱状态）
    sandbox_active = workspace_dir in _task_sandboxes
    full_stats = {
        "workspace_path": workspace_dir,
        "total_files": total_files,
        "total_size_bytes": total_size,
        "total_size_human": _format_file_size(total_size),
        "sandbox_active": sandbox_active,
        "environment_persistent": sandbox_active,
        "file_type_distribution": file_types
    }
    tree_json["full_statistics"] = full_stats
       
    # 带详细信息的工作区树状结构 + 全量统计信息
    stats_text = "\n\n" + "="*60 + "\n📊 工作区全量统计信息（含子文件夹）\n" + "="*60
    stats_text += f"\n📁 工作区根目录: {workspace_dir}"
    stats_text += f"\n📄 总文件数: {total_files}"
    stats_text += f"\n💾 总大小: {_format_file_size(total_size)} ({total_size:,} 字节)"
    stats_text += f"\n🔧 沙箱激活状态: {'是' if sandbox_active else '否'}"
    stats_text += f"\n🔒 环境持久化: {'是' if sandbox_active else '否'}"
    
    if file_types:
        stats_text += "\n\n📈 文件类型分布:\n" + "-"*40
        for ext, info in sorted(file_types.items()):
            stats_text += f"\n  {ext:<15} {info['count']:>3} 个文件  {_format_file_size(info['size']):>10} ({info['size']:,} 字节)"
    
    tree_json = json.dumps(tree_json, ensure_ascii=False, indent=2)
    with open('file_struct.json', 'w', encoding='utf-8') as f:
                f.write(tree_json)
    with open('total_mes.txt', 'w', encoding='utf-8') as f:
        f.write(stats_text)

    return str(json.dumps(tree_json, ensure_ascii=False, indent=2))


@mcp.tool()
def load_json_and_find_file(target_path: str) -> None:
    """加载由get_workspace_structure函数生成的file_struct.json文件，并从中查找指定路径的在task_cache_dir项目中的文件信息
    注意，此工具只能查找task_cache_dir项目中的文件信息。

    读取文件结构JSON文件，解析为字典后调用递归查找函数，
    并打印查找结果（找到的文件信息或未找到提示）
    
    Args:
        target_path: 要查找的文件完整路径
    Return:
        查询到目标文件的信息
    """
    json_file_path = "file_struct.json"  

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            json_content = f.read()
    except FileNotFoundError:
        print(f"❌ 错误：未找到JSON文件 '{json_file_path}'，请检查文件路径")
        return
    except PermissionError:
        print(f"❌ 错误：没有权限读取文件 '{json_file_path}'")
        return
    except Exception as e:
        print(f"❌ 读取文件失败：{str(e)}")
        return

    try:
        tree_data = json.loads(json_content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败：{str(e)}")
        return

    # 执行查找并处理结果
    file_info = recursively_find_file_in_json_tree(tree_data, target_path)
    if file_info:
        print("✅ 找到文件信息：")
        return str(json.dumps(file_info, ensure_ascii=False, indent=2))
    else:
        print("❌ 未找到该文件（或目标路径是目录）")

if __name__ == "__main__":
    mcp.run(transport="stdio")
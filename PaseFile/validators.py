"""导入验证模块"""
import ast
import re
from typing import List, Set, Tuple, Optional
from pathlib import Path

from constants import DEFAULT_IMPORT_WHITELIST


def extract_imports_from_code(code: str) -> Set[str]:
    """
    从Python代码中提取所有导入的模块名。
    
    Args:
        code: Python源代码
        
    Returns:
        导入的模块名集合
    """
    imports = set()
    
    try:
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    module_name = name.name.split('.')[0]
                    imports.add(module_name)
                    
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    imports.add(module_name)
                    
    except SyntaxError:
        pass
    
    # AST解析失败时的正则回退
    import_patterns = [
        r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
    ]
    
    for pattern in import_patterns:
        matches = re.findall(pattern, code, re.MULTILINE)
        for match in matches:
            imports.add(match.split('.')[0])
    
    return imports


def validate_imports(
    code: str, 
    whitelist: Optional[List[str]] = None
) -> Tuple[bool, List[str], List[str]]:
    """
    验证代码中的所有导入是否在白名单中。
    
    Args:
        code: 要验证的Python源代码
        whitelist: 允许的模块名列表（默认使用DEFAULT_IMPORT_WHITELIST）
        
    Returns:
        (是否有效, 允许的导入列表, 禁止的导入列表) 的元组
    """
    if whitelist is None:
        whitelist = DEFAULT_IMPORT_WHITELIST
    
    whitelist_set = set(whitelist)
    imports = extract_imports_from_code(code)
    
    allowed_imports = []
    forbidden_imports = []
    
    for imp in imports:
        if imp in whitelist_set:
            allowed_imports.append(imp)
        else:
            forbidden_imports.append(imp)
    
    is_valid = len(forbidden_imports) == 0
    return is_valid, allowed_imports, forbidden_imports
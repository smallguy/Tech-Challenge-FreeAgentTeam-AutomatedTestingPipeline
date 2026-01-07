# PaseFile - MCP文件分析工具

## 项目概述

PaseFile是一个基于MCP（Model Context Protocol）的文件分析工具，专为自动化测试工作流设计。该工具提供了强大的文件结构分析、统计信息生成和安全的代码执行环境。

## 核心功能

### 🔍 文件结构分析
- **工作区树状结构生成**：递归扫描目录，生成详细的文件结构JSON
- **全量统计信息**：提供文件数量、大小、类型分布等完整统计
- **智能文件识别**：自动识别文件类型（Python、JavaScript、图片等）
- **路径标准化**：兼容Windows大小写不敏感特性，统一路径格式

### 🛡️ 安全沙箱系统
- **导入白名单验证**：基于预定义白名单验证Python代码导入
- **多解释器支持**：支持内部Python、Jupyter、Docker、子进程、E2B等多种执行环境
- **持久化环境**：跨执行保持环境状态，支持文件覆盖
- **权限控制**：限制对系统资源的访问，确保代码执行安全

### 📊 统计与分析
- **实时文件监控**：跟踪文件修改时间和大小变化
- **类型分布分析**：按文件扩展名分类统计
- **沙箱状态检测**：监控沙箱激活状态和环境持久化
- **人类可读格式**：自动格式化文件大小为易读形式

## 技术架构

### 主要组件

#### 1. 核心引擎 ([`pase_file_tools_main.py`](pase_file_tools_main.py))
- MCP服务器主入口，提供两个核心工具：
  - `get_workspace_structure()`：获取工作区结构和统计信息
  - `load_json_and_find_file()`：在JSON结构中查找文件
- 路径标准化和递归文件查找算法
- 文件类型识别和大小格式化功能

#### 2. 安全验证 ([`validators.py`](validators.py))
- **AST解析**：使用Python AST模块提取导入语句
- **正则回退**：AST失败时的正则表达式备选方案
- **白名单验证**：对比导入模块与预定义白名单
- **安全报告**：生成详细的验证结果和错误信息

#### 3. 沙箱管理 ([`sandbox.py`](sandbox.py))
- **统一沙箱接口**：`UnifiedWorkspaceSandbox`类封装不同执行环境
- **全局缓存**：`_task_sandboxes`字典确保同一工作区复用沙箱
- **导入验证集成**：代码执行前的安全检查
- **多环境支持**：内部Python、Docker、E2B等解释器

#### 4. 解释器层 ([`interpreters/`](interpreters/))
- **基础抽象**：`base.py`定义解释器接口
- **具体实现**：
  - `internal_python_interpreter.py`：内部Python执行
  - `docker_interpreter.py`：Docker容器执行
  - `e2b_interpreter.py`：E2B云端执行
  - `subprocess_interpreter.py`：本地子进程执行
  - `ipython_interpreter.py`：IPython内核执行

#### 5. 配置与工具
- **常量定义** ([`constants.py`](constants.py))：导入白名单、文件扩展名、沙箱类型
- **工具函数** ([`utils.py`](utils.py))：工作区目录管理、路径处理
- **日志系统** ([`logger.py`](logger.py))：统一日志记录和错误处理

## 安全特性

### 🔒 导入白名单系统
包含32个标准库模块和主流数据科学、机器学习库：
- **标准库**：`os`, `sys`, `json`, `datetime`, `pathlib`等
- **数据科学**：`numpy`, `pandas`, `matplotlib`, `scipy`, `sklearn`
- **机器学习**：`torch`, `tensorflow`, `transformers`, `keras`
- **图像处理**：`PIL`, `cv2`, `skimage`
- **网络请求**：`requests`, `urllib3`, `beautifulsoup4`

### 🛡️ 执行环境隔离
- **沙箱化执行**：代码在隔离环境中运行，限制系统访问
- **权限验证**：执行前验证所有导入语句
- **错误处理**：完善的异常捕获和错误报告机制
- **环境持久化**：支持跨执行的状态保持

## 使用示例

### 基本文件分析
```python
# 获取工作区结构
structure = get_workspace_structure("my_project")
# 返回包含文件树和统计信息的JSON字符串
```

### 安全代码执行
```python
# 创建沙箱
sandbox = get_or_create_sandbox(
    workspace_dir="/path/to/workspace",
    sandbox="subprocess",
    verbose=True,
    unsafe_mode=False
)

# 执行带验证的代码
result = sandbox.execute_code(
    code="import numpy as np\nprint(np.array([1,2,3]))",
    filename="test.py"
)
```

## 文件统计信息

- **总文件数**：36个
- **总大小**：728.2 KB
- **Python文件**：17个（83.8 KB）
- **编译文件**：17个（88.0 KB）
- **JSON数据**：1个（571.8 KB）
- **文本文件**：1个（2.0 KB）

## 安装与运行

### 依赖要求
- Python 3.8+
- MCP服务器环境
- 相关解释器依赖（Docker、E2B等，可选）

### ⚠️ 重要配置提醒
**模型上下文窗口设置**：由于PaseFile会生成大容量的JSON结构数据（可能超过500KB），使用costrict时请将上下文窗口设置为**1000000 tokens**或更高，以确保能完整处理大型文件结构。

### 快速启动
```bash
# 安装依赖
pip install mcp fastmcp rich

# 运行MCP服务器
python pase_file_tools_main.py
```

### 模型配置要求
- **上下文窗口**：≥ 1,000,000 tokens
- **最大响应长度**：允许处理大型JSON响应
- **内存配置**：确保有足够内存处理大型文件结构

## 项目特点

1. **安全性优先**：多层验证机制确保代码执行安全
2. **扩展性强**：模块化设计支持新解释器类型
3. **性能优化**：递归算法和缓存机制提升效率
4. **跨平台**：兼容Windows、Linux、macOS系统
5. **标准化输出**：统一的JSON格式便于集成
6. **自动化集成**：支持校园赛SWE-Bench闭环工作流

## 自动化测试集成

### 🎯 校园赛SWE-Bench工作流支持
PaseFile作为自动化测试工作流的核心组件，提供：

- **精准项目分析**：自动识别技术栈和核心模块路径
- **测试资源生成**：为前后端生成≥10个合规测试用例
- **代码行号定位**：支持问题精准定位到具体文件和行号
- **结构化输出**：生成符合自动化测试工程师技能要求的报告

### 🔧 一键测试执行
配合自动化测试提示词，实现：
- **15分钟时限控制**：确保测试在规定时间内完成
- **70%核心用例优先**：优先执行高优先级测试用例
- **安全风险标注**：自动识别和标注安全漏洞
- **失败用例重试**：支持仅执行失败用例的修复验证

### 📊 测试报告生成
- **≤500字结构化报告**：符合校园赛要求的简洁报告格式
- **通过率统计**：自动计算测试覆盖率和通过率
- **修复建议**：基于黄金补丁库提供具体修复方案
- **代码行号引用**：精确定位问题代码位置

## 许可证

MIT License - 详见项目根目录LICENSE文件
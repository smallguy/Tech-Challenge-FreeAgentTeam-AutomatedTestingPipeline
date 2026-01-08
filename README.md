# 自动化测试工作流系统

## 项目目标

本项目面向"设计自动化测试工作流"赛道，提供一套可复用的端到端流程，用于对全新的代码仓库自动完成：仓库结构分析、测试生成、测试执行、基于失败的自动修复、复测与报告输出。流程支持在修复阶段参考 SWE-bench 风格的黄金补丁库，以提升修复的可解释性与成功率。

## 系统架构

整个系统由两个核心组件构成：

### 🔍 PaseFile 文件分析工具
- **形式**：MCP Server（stdio）
- **入口**：`PaseFile/pase_file_tools_main.py`
- **作用**：对目标仓库进行结构化扫描，输出可供后续测试生成与缺陷定位使用的"文件地图"
- **工具接口**：
  - `get_workspace_structure(task_cache_dir: str)` - 获取工作区结构和统计信息
  - `load_json_and_find_file(target_path: str)` - 在JSON结构中查找文件

### 🏆 GoldPatch 黄金补丁库
- **索引文件**：`GoldPatch/gold_patch_directory.json`（约2293条补丁索引记录）
- **补丁详情**：`GoldPatch/gold_patch_txt/`（约2200+个补丁详情文本）
- **作用**：包含多维标签信息与source_file字段，用于定位补丁详情文件

## 完整工作流

### 1️⃣ 仓库结构分析
1. 启动 PaseFile MCP Server
2. 调用 `get_workspace_structure(task_cache_dir)` 扫描目标仓库目录
3. 生成并保存结构化结果：
   - `file_struct.json`：文件树与统计信息
   - `total_mes.txt`：人类可读摘要

### 2️⃣ 测试生成
基于仓库结构分析结果，由LLM生成并落地：
- **后端测试用例**：覆盖不少于10个接口，包含正常与异常路径，包含鉴权验证
- **前端测试用例**：覆盖不少于10个功能或组件，包含正常与边界场景
- **一键执行脚本**：负责依赖准备、服务启动、测试执行与结果汇总

### 3️⃣ 测试执行与失败收敛
运行一键脚本后，工作流收集并结构化解析测试失败信息：
- 失败用例名称与数量
- 错误摘要与关键堆栈
- 可能的故障文件与代码位置
- 环境与依赖信息

### 4️⃣ 黄金补丁检索
当测试失败时，LLM依据失败信息在`gold_patch_directory.json`中进行多维标签匹配：
- **问题精准识别维度**：`error_type`、`error_traceback_key`
- **代码关联维度**：`api_impacted`、`modified_files`、`code_location`
- **环境约束维度**：`python_version_range`、`dependency_versions`、`os_compatibility`

### 5️⃣ 参考补丁修复
根据补丁diff与当前仓库上下文完成修复落地：
- 优先最小化改动范围，避免不必要重构
- 对路径差异、版本差异进行适配
- 对补丁中新增测试优先迁移测试意图

### 6️⃣ 复测与回退策略
修复后再次执行一键脚本：
- **全部通过**：生成最终详细测试报告
- **仍存在失败**：放弃黄金补丁路径，改用LLM基于当前仓库上下文直接修复

## 项目结构

```text
AutomatedTestWorkflow/
├── PaseFile/                    # 文件分析工具
│   ├── pase_file_tools_main.py  # MCP服务器主入口
│   ├── constants.py             # 常量和配置
│   ├── validators.py            # 导入验证模块
│   ├── sandbox.py               # 沙箱管理
│   ├── utils.py                 # 工具函数
│   ├── logger.py                # 日志系统
│   └── interpreters/            # 多种解释器实现
│       ├── base.py              # 基础抽象
│       ├── docker_interpreter.py
│       ├── e2b_interpreter.py
│       ├── internal_python_interpreter.py
│       ├── ipython_interpreter.py
│       └── subprocess_interpreter.py
├── GoldPatch/                   # 黄金补丁库
│   ├── gold_patch_directory.json    # 补丁索引（2293条记录）
│   ├── gold_patch_tag_extractor.py  # 标签提取工具
│   └── gold_patch_txt/              # 补丁详情（2200+文件）
└── README.md                    # 项目总览
```

## 核心特性

### 🛡️ 安全机制
- **导入白名单**：32个标准库模块和主流数据科学库
- **沙箱化执行**：多环境隔离（Docker、E2B、子进程等）
- **权限控制**：限制系统资源访问

### 📊 智能分析
- **文件类型识别**：自动识别100+种文件类型
- **统计信息**：实时文件监控和类型分布分析
- **路径标准化**：兼容Windows大小写不敏感特性

### 🔧 可扩展性
- **模块化设计**：支持新解释器类型扩展
- **MCP协议**：标准化工具接口
- **多语言支持**：Python、JavaScript、Java等

## 快速开始

### 演示视频
为了更直观地展示系统运行流程，我们录制了完整的演示视频：

**视频链接**：[点击查看演示视频](https://pan.baidu.com/s/1WOHm4jWsqgX5FnX6Bdt6yg)
**提取码**：2601
**时长**：3分45秒

视频展示了从原始代码仓库开始，触发自动化测试生成，并完整执行测试内容、输出测试报告的全过程。
### llm生成的测试用例、脚本以及测试报告
**存放地址**：存放在ruoyi_vue_auto_test_resources文件夹中。

### 1. 环境配置
⚠️ **重要配置**：模型测试需要在costrict里面设置上下文窗口为1000000，因为PaseFile生成的JSON内容很多。

```bash
# 安装依赖
pip install mcp fastmcp rich

# 启动PaseFile MCP服务器
python PaseFile/pase_file_tools_main.py
```

### 2. 模型上下文配置
由于PaseFile会生成大容量的JSON结构数据（可能超过500KB），请确保：
- **上下文窗口**：设置为1000000 tokens或更高
- **最大响应长度**：允许处理大型JSON响应
- **内存限制**：确保有足够的内存处理大型文件结构

### 2. 工作流执行
```python
# 1. 分析仓库结构
structure = get_workspace_structure("target_repo")

# 2. 生成测试用例（由LLM完成）
# 3. 执行测试并收集失败信息
# 4. 检索黄金补丁
# 5. 应用修复并复测
```

## 评测对齐

本工作流围绕赛道目标设计，重点覆盖：
- ✅ **自动化程度**：端到端自动完成，支持一键触发
- ✅ **测试覆盖**：前后端各≥10个用例（RuoYi-Vue示例：30个用例，100%覆盖率）
- ✅ **可复现性**：完整日志和结构化输出，含代码行号定位
- ✅ **可靠性**：黄金补丁+回退机制，15分钟时限控制
- ✅ **报告质量**：详细可追溯的测试报告，≤500字结构化输出
- ✅ **安全测试**：SQL注入、XSS攻击、权限验证等安全场景覆盖
- ✅ **性能测试**：接口响应时间、并发压力测试

## 许可证

MIT License - 详见LICENSE文件

---
**注**：黄金补丁来源于特定仓库与版本，落地时可能存在路径与版本差异，工作流通过复测与回退机制控制风险。

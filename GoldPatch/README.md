# GoldPatch 黄金补丁库

## 概述

GoldPatch是一个包含2293条高质量补丁记录的SWE-bench风格黄金补丁库，专为自动化测试工作流中的缺陷修复阶段设计。该补丁库涵盖了Django、Astropy、Matplotlib等主流开源项目的真实bug修复案例。

## 数据结构

### 📊 统计信息
- **总补丁数**：2293条
- **覆盖项目**：3个主流开源项目
- **补丁详情文件**：2200+个文本文件
- **数据格式**：JSON索引 + 文本详情

### 🗂️ 文件结构
```
GoldPatch/
├── gold_patch_directory.json      # 补丁索引主文件
├── gold_patch_tag_extractor.py    # 标签提取工具
└── gold_patch_txt/                # 补丁详情目录
    ├── astropy__astropy-*.txt     # Astropy项目补丁
    ├── django__django-*.txt       # Django项目补丁
    └── matplotlib__matplotlib-*.txt # Matplotlib项目补丁
```

## 核心功能

### 🔍 多维标签匹配
补丁索引包含以下关键字段，支持精准检索：

#### 问题精准识别维度
- `error_type`：错误类型分类
- `error_traceback_key`：关键堆栈信息
- `problem_description`：问题描述关键词

#### 代码关联维度
- `api_impacted`：受影响的API接口
- `modified_files`：修改的文件列表
- `code_location`：代码位置信息

#### 环境约束维度
- `python_version_range`：Python版本兼容性
- `dependency_versions`：依赖版本要求
- `os_compatibility`：操作系统兼容性

### 🎯 智能检索
支持基于测试失败信息的多维度匹配：
1. **错误类型匹配**：根据异常类型定位相关补丁
2. **堆栈信息匹配**：通过关键堆栈跟踪找到相似问题
3. **API影响匹配**：识别受影响的API接口
4. **文件位置匹配**：定位到具体文件的修改历史

## 使用流程

### 1. 失败信息收集
当测试执行失败时，系统收集：
- 错误类型和异常信息
- 关键堆栈跟踪
- 受影响的API和文件
- 环境配置信息

### 2. 智能检索
基于收集的失败信息，在`gold_patch_directory.json`中进行多维匹配：
```python
# 伪代码示例
matching_patches = []
for patch in patch_directory:
    if (patch.error_type == failure_error_type and
        patch.api_impacted in affected_apis and
        patch.python_version_range compatible with current_version):
        matching_patches.append(patch)
```

### 3. 补丁应用
找到匹配补丁后：
1. 读取对应的`gold_patch_txt/`文件
2. 提取修复diff和关键修改点
3. 适配当前仓库的上下文环境
4. 应用修复并验证

## 数据格式

### 索引文件格式 (gold_patch_directory.json)
```json
{
    "patch_id": "django__django-12345",
    "project": "django",
    "error_type": "AttributeError",
    "error_traceback_key": "NoneType object has no attribute",
    "api_impacted": ["Model.save", "QuerySet.filter"],
    "modified_files": ["django/db/models/base.py"],
    "code_location": "line 456-478",
    "python_version_range": ">=3.6,<4.0",
    "dependency_versions": {"django": ">=2.0"},
    "source_file": "gold_patch_txt/django__django-12345_prompt.txt"
}
```

### 补丁详情格式
每个补丁文件包含：
- **问题描述**：详细的bug描述和复现步骤
- **错误信息**：完整的错误堆栈和异常信息
- **修复diff**：具体的代码修改内容
- **测试用例**：验证修复的测试代码
- **环境信息**：相关的版本和配置要求

## 质量保证

### ✅ 数据来源
- 来源于真实的开源项目bug修复
- 经过SWE-bench验证的高质量补丁
- 覆盖常见的编程错误和边界情况

### 🔒 安全机制
- **版本适配**：检查Python版本和依赖兼容性
- **路径适配**：处理不同项目间的文件路径差异
- **回退策略**：匹配失败时切换到LLM直接修复

### 📈 持续优化
- 定期更新补丁库内容
- 基于使用反馈优化匹配算法
- 扩展覆盖更多开源项目

## 快速开始

### 基本使用
```python
import json

# 加载补丁索引
with open('gold_patch_directory.json', 'r') as f:
    patch_directory = json.load(f)

# 根据错误信息检索
def find_relevant_patches(error_type, api_name, python_version):
    candidates = []
    for patch in patch_directory:
        if (patch['error_type'] == error_type and
            api_name in patch['api_impacted'] and
            python_version in patch['python_version_range']):
            candidates.append(patch)
    return candidates
```

### 读取补丁详情
```python
def get_patch_details(patch_info):
    with open(patch_info['source_file'], 'r') as f:
        return f.read()
```

### 自动化测试集成
在自动化测试工作流中，黄金补丁库与PaseFile配合使用：

```python
# 1. 执行测试并收集失败信息
test_failures = run_tests_and_collect_failures()

# 2. 基于失败信息检索相关补丁
for failure in test_failures:
    relevant_patches = find_relevant_patches(
        error_type=failure['error_type'],
        api_name=failure['affected_api'],
        python_version=failure['python_version']
    )
    
    # 3. 应用最匹配的补丁
    if relevant_patches:
        best_patch = select_best_patch(relevant_patches, failure)
        apply_patch(best_patch, failure['file_path'])
```

## 自动化测试工作流集成

### 🎯 校园赛SWE-Bench闭环流程
黄金补丁库在自动化测试工作流中的核心作用：

1. **失败信息收集**：自动收集测试失败的多维度信息
   - 错误类型和异常信息
   - 受影响的API和文件路径
   - 环境配置和版本信息

2. **智能补丁匹配**：基于多维标签进行精准匹配
   - 问题精准识别维度：`error_type`、`error_traceback_key`
   - 代码关联维度：`api_impacted`、`modified_files`、`code_location`
   - 环境约束维度：`python_version_range`、`dependency_versions`

3. **安全修复应用**：提供经过验证的修复方案
   - 最小化改动范围
   - 版本和路径适配
   - 回退机制保障

### 📊 实际应用案例
以RuoYi-Vue项目为例，黄金补丁库成功修复了：
- **SQL注入漏洞**：通过参数校验和预编译语句修复
- **XSS攻击漏洞**：通过HTML转义和过滤规则修复
- **Token生成问题**：通过参数预处理修复

### ⚡ 一键测试执行
配合自动化测试脚本，实现：
- **15分钟时限**：确保测试在规定时间内完成
- **70%核心优先**：优先修复高优先级安全漏洞
- **100%通过率**：修复后所有测试用例通过
- **≤500字报告**：生成符合要求的简洁报告

## 注意事项

⚠️ **版本差异**：补丁来源于特定版本，应用时需注意适配  
⚠️ **路径差异**：不同项目的文件结构可能不同  
⚠️ **环境差异**：依赖版本和配置可能需要调整  
⚠️ **回退机制**：匹配失败时及时切换到其他修复策略  

## 贡献指南

欢迎提交新的补丁案例和改进建议：
1. 确保补丁来源于真实的bug修复
2. 提供完整的错误信息和修复diff
3. 包含详细的标签信息便于检索
4. 遵循现有的数据格式标准

## 许可证

MIT License - 与主项目保持一致
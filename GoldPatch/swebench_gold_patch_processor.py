"""
SWE-bench黄金补丁数据处理工具
==============================
核心功能：
1. 加载本地Parquet格式的SWE-bench数据集
2. 校验黄金补丁的业务有效性（格式、完整性、可解析性）
3. 生成LLM代码修复任务的提示词文件
4. 执行测试脚本并返回执行结果

使用依赖：
- datasets>=2.0.0
- pandas>=1.5.0
- pyarrow>=10.0.0（Parquet文件解析）
"""

import argparse
import subprocess
import traceback
import json
import os
from typing import List, Dict, Any, Optional
import re

try:
    from datasets import load_dataset
except ImportError:
    raise ImportError("请先安装datasets库：pip install datasets")

def is_valid_gold_patch(datum: Dict[str, Any]) -> bool:
    """
    黄金补丁业务有效性校验（整合全量校验规则）

    校验维度：
    1. 核心ID：instance_id非空且格式合法（包含__分隔符）
    2. 补丁内容：存在有效补丁（优先test_patch，次之patch），且为合法diff格式
    3. 业务上下文：关联代码库(repo)和问题描述(problem_statement)非空
    4. 可解析性：补丁能被结构化解析

    Args:
        datum: 单条数据集记录，包含instance_id/patch/repo等字段

    Returns:
        校验通过返回True，否则返回False
    """
    # 规则1：校验instance_id有效性
    instance_id = datum.get("instance_id", "")
    if not instance_id:
        print(f"❌ 无效补丁：instance_id为空 - {instance_id}")
        return False
    if "__" not in instance_id:
        print(f"❌ 无效补丁：instance_id格式非法（无__分隔符） - {instance_id}")
        return False

    # 规则2：校验补丁内容有效性
    golden_patch = datum.get("test_patch", datum.get("patch", ""))
    if not golden_patch or golden_patch.strip() == "":
        print(f"❌ 无效补丁：{instance_id} 补丁字段为空（test_patch/patch）")
        return False
    if not golden_patch.strip().startswith("diff"):
        print(f"❌ 无效补丁：{instance_id} 补丁非合法diff格式（不以diff开头）")
        return False
    # 回写标准化补丁字段，避免后续重复提取
    datum["golden_test_patch"] = golden_patch

    # 规则3：校验业务上下文完整性
    repo = datum.get("repo", "")
    if not repo:
        print(f"❌ 无效补丁：{instance_id} 未关联代码库")
        return False
    problem_statement = datum.get("problem_statement", "")
    if not problem_statement:
        print(f"❌ 无效补丁：{instance_id} 无问题描述")
        return False

    # 规则4：校验补丁可解析性
    try:
        extract_custom_patches(golden_patch)
    except Exception:
        print(f"❌ 无效补丁：{instance_id} 补丁格式无法解析")
        return False

    return True


def filter_valid_gold_patches(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    批量筛选业务有效的黄金补丁

    Args:
        dataset: 原始数据集列表

    Returns:
        过滤后的有效数据集列表
    """
    valid_dataset = [datum for datum in dataset if is_valid_gold_patch(datum)]
    invalid_count = len(dataset) - len(valid_dataset)
    print(f"✅ 黄金补丁筛选完成：有效{len(valid_dataset)}个 / 无效{invalid_count}个")
    return valid_dataset

# ---------------------- 数据集加载逻辑 ----------------------
def load_swebench_dataset(
    dataset_name: str, 
    split: str, 
    is_swt: bool = False, 
    filter_swt: bool = False 
) -> List[Dict[str, Any]]:
    """
    加载本地Parquet格式的SWE-bench数据集并适配字段格式

    说明：
    - 兼容原有接口参数，但实际加载本地固定路径的test集文件
    - 仅做数据加载和字段映射，不做任何筛选/校验逻辑

    Args:
        dataset_name: 兼容历史参数，无实际业务作用
        split: 兼容历史参数，无实际业务作用
        is_swt: 兼容历史参数，无实际过滤逻辑
        filter_swt: 兼容历史参数，无实际过滤逻辑

    Returns:
        格式化后的数据集列表，包含instance_id/test_patch/repo等核心字段

    Raises:
        ValueError: 文件未找到或加载失败时抛出异常
    """
    local_parquet_path = "./swebench_full_local/test-swe-bench.parquet"
    
    try:
        swebench = load_dataset(
            "parquet", 
            data_files={"test": local_parquet_path},  
            split=split  
        )
    except FileNotFoundError:
        raise ValueError(f"本地数据集文件未找到：{local_parquet_path}，请检查文件路径是否正确")
    except Exception as e:
        raise ValueError(f"加载本地数据集失败：{e}，请确认文件格式为Parquet且路径正确")
    
    # 字段映射：标准化输出格式
    dataset = []
    for item in swebench:
        dataset.append({
            "instance_id": item.get("instance_id"),
            "test_patch": item.get("test_patch"),
            "patch": item.get("patch"),
            "repo": item.get("repo"),
            "problem_statement": item.get("problem_statement"),
            "raw_gold_patch": item.get("patch"),  # 备用字段，保留兼容性
        })
    
    print(f"✅ 本地数据集加载完成：共获取 {len(dataset)} 条原始数据（未做校验）")
    return dataset


def get_gold_predictions(dataset_name: str, split: str, is_swt: bool, filter_swt: bool):
    """
    获取经过有效性筛选的黄金补丁数据集

    流程：
    1. 加载原始数据集
    2. 执行业务有效性筛选
    3. 格式化输出字段

    Args:
        dataset_name: 数据集名称（兼容历史参数）
        split: 数据集拆分类型（兼容历史参数）
        is_swt: SWT数据集标识（兼容历史参数）
        filter_swt: SWT过滤开关（兼容历史参数）

    Returns:
        格式化后的有效黄金补丁列表
    """
    raw_dataset = load_swebench_dataset(dataset_name, split, is_swt, filter_swt)
    valid_dataset = filter_valid_gold_patches(raw_dataset)
    return [
        {
            "instance_id": datum["instance_id"],
            "model_patch": datum["golden_test_patch"],  
            "model_name_or_path": "gold",
            "repo": datum["repo"],
            "problem_statement": datum["problem_statement"],
            "raw_gold_patch": datum["raw_gold_patch"],
        } for datum in valid_dataset
    ]

# ---------------------- 补丁解析工具类 ----------------------
class CustomPatch:
    """
    补丁信息结构化封装类

    用于解析diff格式补丁后，存储文件名称、补丁类型、行号范围、变更内容等信息
    """
    def __init__(self, file_name: str, patch_type: str, rough_line_number: str, changed_lines: List[str]):
        self.file_name = file_name          # 补丁关联文件名称
        self.patch_type = patch_type        # 补丁类型（如add/delete/modify）
        self.rough_line_number = rough_line_number  # 补丁涉及的行号范围
        self.changed_lines = changed_lines  # 具体变更代码行

    def __repr__(self) -> str:
        """自定义字符串表示，便于调试"""
        return f"CustomPatch(file={self.file_name}, type={self.patch_type}, lines={self.rough_line_number})"


def extract_custom_patches(model_patch: str) -> List[CustomPatch]:
    """
    解析diff格式补丁，转换为结构化CustomPatch列表

    Args:
        model_patch: 原始diff格式补丁字符串

    Returns:
        结构化的CustomPatch对象列表
    """
    model_patch = model_patch.lstrip("\n").splitlines()
    patches = []
    for i, line in enumerate(model_patch):
        if line.startswith("diff"):
            try:
                file_name = model_patch[i+1]
                patch_type = model_patch[i+2]
                rough_line_number = model_patch[i+3]
                j = i + 4
                # 查找补丁结束标记
                for j in range(i+4, len(model_patch)):
                    if model_patch[j].startswith("end diff"):
                        break
                changed_lines = model_patch[i + 4:j]
            except Exception:
                print(f"该补丁提取失败！\n{model_patch}\n")
                continue
            patches.append(CustomPatch(file_name, patch_type, rough_line_number, changed_lines))
    return patches

# ---------------------- 测试脚本执行工具 ----------------------
def execute_test_script(script_path: str) -> Dict[str, Any]:
    """
    执行测试脚本并返回结构化执行结果

    Args:
        script_path: 测试脚本文件路径

    Returns:
        执行结果字典，包含：
        - status: 执行状态（success/failed/error）
        - stdout: 标准输出内容
        - stderr: 标准错误内容
        - error_trace: 异常堆栈信息（如有）
    """
    try:
        result = subprocess.run(
            [script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            timeout=30
        )
        if result.returncode == 0:
            return {
                "status": "success",
                "stdout": result.stdout,
                "stderr": "",
                "error_trace": ""
            }
        else:
            return {
                "status": "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error_trace": traceback.format_exc()
            }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "error_trace": traceback.format_exc()
        }

# ---------------------- 提示词文件生成逻辑 ----------------------
def generate_prompt_file(
    repair_reports: List[Dict[str, Any]],
    prompt_output_dir: str = "./gold_patch_txt/",
    prompt_format: str = "txt"
) -> str:
    """
    生成LLM代码修复任务的提示词文件（支持TXT/JSON格式）

    Args:
        repair_reports: 修复报告列表，包含补丁信息和执行结果
        prompt_output_dir: 提示词文件输出目录
        prompt_format: 文件格式（txt/json）

    Returns:
        生成的提示词文件路径
    """
    os.makedirs(prompt_output_dir, exist_ok=True)
    
    # 提示词模板（标准化自然语言指令）
    prompt_template = """
### SWE-Bench 代码修复任务提示词
#### 任务背景
基于SWE-Bench真实代码缺陷数据集，完成代码补丁修复任务，确保修复后的测试脚本可正常执行。

#### 有效补丁列表（共{total_valid}个）
{patch_details}

#### 修复要求
1. 基于每个补丁的黄金参考（correct_code_lines），修复测试代码执行错误；
2. 确保修复后的代码符合原代码库的语法规范；
3. 保留原有业务逻辑，仅修复执行错误；
4. 输出格式：按instance_id逐个返回修复后的完整测试脚本。

#### 执行失败参考（如有）
{failed_exec_info}
"""

    # 构建补丁详情和失败信息
    patch_details = []
    failed_exec_info = []
    for idx, report in enumerate(repair_reports, 1):
        instance_id = report["instance_id"]
        golden_ref = report["golden_reference"]
        exec_status = report["execution_status"]
        
        patch_detail = f"""
{idx}. 实例ID：{instance_id}
   - 关联文件：{golden_ref['file_name']}
   - 行号范围：{golden_ref['line_range']}
   - 问题描述：{golden_ref.get('problem_statement', '无')}
   - 黄金补丁参考：{chr(10).join(golden_ref['correct_code_lines'][:3])}...（完整见raw_gold_patch）
   - 执行状态：{exec_status}
"""
        patch_details.append(patch_detail)
        
        if exec_status != "success":
            failed_info = f"""
- 实例ID：{instance_id}
  错误信息：{report['execution_error']['stderr'][:200]}...
  堆栈跟踪：{report['execution_error']['traceback'][:300]}...
"""
            failed_exec_info.append(failed_info)

    # 填充模板内容
    prompt_content = prompt_template.format(
        total_valid=len(repair_reports),
        patch_details="".join(patch_details),
        failed_exec_info="".join(failed_exec_info) if failed_exec_info else "无执行失败案例，所有测试脚本执行成功"
    ).strip()

    # 生成输出文件
    prompt_file_path = os.path.join(prompt_output_dir, f"swe_bench_prompt.{prompt_format}")
    if prompt_format == "txt":
        with open(prompt_file_path, "w", encoding="utf-8") as f:
            f.write(prompt_content)
    elif prompt_format == "json":
        prompt_json = {
            "task_type": "SWE-Bench代码修复",
            "total_valid_patches": len(repair_reports),
            "patch_details": repair_reports,
            "repair_requirement": "基于黄金补丁修复测试脚本执行错误，确保脚本可正常运行",
            "prompt_natural_language": prompt_content
        }
        with open(prompt_file_path, "w", encoding="utf-8") as f:
            json.dump(prompt_json, f, ensure_ascii=False, indent=2)

    print(f"✅ 提示词文件已生成：{prompt_file_path}")
    return prompt_file_path


def generate_prompt_files(
    dataset_name: str,
    split: str,
    prompt_output_dir: str = "./gold_patch_txt/"
) -> List[str]:
    """
    批量生成黄金补丁的提示词文件

    Args:
        dataset_name: 数据集名称（兼容历史参数）
        split: 数据集拆分类型（兼容历史参数）
        prompt_output_dir: 提示词文件输出目录

    Returns:
        生成的文件路径列表
    """
    os.makedirs(prompt_output_dir, exist_ok=True)
    
    # 加载并筛选有效黄金补丁
    gold_predictions = get_gold_predictions(dataset_name, split, is_swt=True, filter_swt=False)
    print(f"✅ 加载 {len(gold_predictions)} 个有效黄金补丁")
    
    generated_files = []
    # 为每个有效补丁生成独立的提示词文件
    for gold_pred in gold_predictions:
        instance_id = gold_pred["instance_id"]
        gold_patch = gold_pred["model_patch"]
        repo = gold_pred.get("repo", "unknown")
        problem_statement = gold_pred.get("problem_statement", "无问题描述")
        
        # 构建提示词内容
        prompt_content = f"""# 修复代码生成提示词（实例ID：{instance_id}）
        ## 代码仓库
        {repo}

        ## 原始问题描述
        {problem_statement}

        ## 参考黄金补丁（正确的修复方案）
        {gold_patch}
        """.strip()
        
        # 保存提示词文件
        prompt_file_path = f"{prompt_output_dir}/{instance_id}_prompt.txt"
        with open(prompt_file_path, "w", encoding="utf-8") as f:
            f.write(prompt_content)
        generated_files.append(prompt_file_path)
    
    print(f"✅ 完成 {len(generated_files)} 个提示词文件生成，输出路径：{prompt_output_dir}")
    return generated_files

# ---------------------- 主程序入口 ----------------------
if __name__ == "__main__":
    """
    程序执行入口：生成SWE-bench黄金补丁提示词文件
    执行流程：
    1. 加载本地Parquet数据集
    2. 筛选有效黄金补丁
    3. 为每个有效补丁生成提示词文件
    """
    # 生成提示词文件（默认输出到./gold_patch_txt/目录）
    prompt_files = generate_prompt_files(
        dataset_name="SWE-bench",
        split="test",
        prompt_output_dir="./gold_patch_txt/"
    )
"""
黄金补丁标签自动提取工具
功能：批量读取包含黄金补丁的TXT文件，调用DeepSeek API提取标准化标签，输出JSON汇总文件
"""
import os
import re
import json
import time
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# ===================== 配置项 =====================
# 环境配置
LOAD_DOTENV: bool = True  # 是否从.env文件读取API Key
TXT_INPUT_DIR: str = "./gold_path_txt"  # 存放TXT文件的目录
JSON_OUTPUT_FILE: str = "./gold_patch_directory.json"  # 汇总输出文件路径
FAIL_FILES_JSON: str = "./fail_files.json"  # 失败文件记录路径
LOG_FILE: str = "./batch_process.log"  # 日志文件路径

# API配置
DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
MODEL_NAME: str = "deepseek-chat"  # 使用的模型名称
API_TIMEOUT: int = 60  # 单个API请求超时时间（秒）
REQUEST_INTERVAL: int = 1  # API调用间隔（避免QPS超限，单位：秒）
RETRY_ATTEMPTS: int = 3  # 失败重试次数

# 正则表达式常量
DIFF_FILE_PATTERN: re.Pattern = re.compile(r"diff --git a/([^\s]+) b/[^\s]+")
JSON_PATTERN: re.Pattern = re.compile(r"\{.*\}", re.DOTALL)

# ===================== 日志配置 =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger: logging.Logger = logging.getLogger(__name__)

# ===================== 初始化 =====================
if LOAD_DOTENV:
    load_dotenv()

DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请在.env文件中配置DEEPSEEK_API_KEY，或直接赋值给DEEPSEEK_API_KEY变量")

# ===================== 核心函数 =====================
def read_txt_file(file_path: str) -> Optional[Dict[str, str]]:
    """
    读取单个TXT文件，提取核心信息
    
    输入文件格式：
    # 修复代码生成提示词（实例ID：xxx）
    ## 代码仓库
    astropy/astropy
    ## 原始问题描述
    （问题详情）
    ## 参考黄金补丁（正确的修复方案）
    （diff代码）
    
    Args:
        file_path: TXT文件路径
    
    Returns:
        包含核心信息的字典，解析失败返回None
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        # 拆分核心区块
        repo_part = content.split("## 代码仓库", 1)
        if len(repo_part) < 2:
            logger.warning(f"文件 {file_path} 缺少「代码仓库」区块")
            return None

        problem_patch_part = repo_part[1].split("## 原始问题描述", 1)
        if len(problem_patch_part) < 2:
            logger.warning(f"文件 {file_path} 缺少「原始问题描述」区块")
            return None

        # 提取仓库名称
        repo_info: str = problem_patch_part[0].strip()
        repo_name: str = _extract_repo_name(repo_info)

        # 提取问题描述和黄金补丁
        patch_split = problem_patch_part[1].split("## 参考黄金补丁（正确的修复方案）", 1)
        problem_statement: str = patch_split[0].strip() if patch_split else "无"
        gold_patch: str = patch_split[1].strip() if len(patch_split) >= 2 else "无"

        # 验证核心信息完整性
        if not problem_statement or not gold_patch:
            logger.warning(f"文件 {file_path} 缺少问题描述或黄金补丁")
            return None

        # 从diff中提取模块路径
        module_path: str = _extract_module_path(gold_patch)

        return {
            "repo_name": repo_name,
            "module_path": module_path,
            "problem_statement": problem_statement,
            "gold_patch": gold_patch,
            "file_name": os.path.basename(file_path)
        }

    except Exception as e:
        logger.error(f"读取文件 {file_path} 失败: {str(e)}", exc_info=True)
        return None


def _extract_repo_name(repo_info: str) -> str:
    """提取仓库名称（从astropy/astropy格式中提取后半部分）"""
    if not repo_info:
        return "未知"
    return repo_info.split("/")[-1].strip() if "/" in repo_info else repo_info.strip()


def _extract_module_path(gold_patch: str) -> str:
    """从黄金补丁的diff中提取模块路径"""
    if not gold_patch:
        return "无"
    
    file_matches = DIFF_FILE_PATTERN.findall(gold_patch)
    if not file_matches:
        return "无"
    
    unique_files = list(set(file_matches))
    # 限制长度避免字段过长
    return ", ".join(unique_files)[:100]


def _build_extract_prompt(info: Dict[str, str]) -> str:
    """构建标签提取的Prompt"""
    prompt_template = """
# 黄金补丁标签自动提取助手
## 输入内容
### 1. 仓库基础信息
repo_name: {repo_name}
module_path: {module_path}
### 2. 问题描述
{problem_statement}
### 3. 黄金补丁
{gold_patch}
## 输出要求
严格按照以下规则生成JSON标签（6大核心维度），所有字段必须存在，无信息按要求填“无”“未知”或空数组：
### 标签提取规则
#### 1. 问题精准识别维度（从问题描述提取）
- **`error_type`**：提取核心错误类型（如`{{TypeError}}`、`{{AttributeError}}`）。若未明确错误且属于功能调整，填“功能优化/需求新增”；
- **`error_traceback_key`**：提取异常堆栈关键信息（含文件名、行号、报错核心内容）。无则填“无”；
- **`problem_trigger`**：明确触发问题的操作（如“调用某函数+传入某类型参数”）；
- **`expected_behavior`**：用户预期的正确行为（如“支持非线畸变WCS坐标转换并收敛”）；
- **`actual_behavior`**：实际错误结果（含错误提示、返回异常）；
- **`bug_severity`**：影响程度分类：`Critical`（阻断功能）、`Medium`（部分场景）、`Low`（轻微异常）。
#### 2. 代码关联维度（从黄金补丁提取）
- **`api_impacted`**：受影响的核心API（函数、类，含完整路径，如`{{astropy.wcs.WCS.all_world2pix}}`）；
- **`code_modify_type`**：修改类型（多选：添加异常处理、调整参数、替换逻辑等，格式为数组）；
- **`code_location`**：修改位置描述（如“WCS类all_world2pix方法的收敛判断分支”）；
- **`key_variables`**：补丁涉及的关键变量/参数（如“scale参数”“CONVERGENCE_THRESHOLD常量”）；
- **`modified_files`**：被修改的文件路径（去重，格式为数组，可空）。
#### 3. 资源关联维度（从问题描述/仓库信息提取）
- **`related_issue_ids`**：问题描述中提到的GitHub Issue号（如`["#11693"]`，可空）；
- **`related_pr_ids`**：问题描述中提到的GitHub PR号（如`["#11700"]`，可空）；
- **`author`**：补丁作者（无则填“未知”）；
- **`reference_links`**：相关文档/教程链接（无则填“无”）。
#### 4. 环境约束维度（从问题描述/仓库配置提取）
- **`python_version_range`**：支持的Python版本范围（如`">=3.7"`，无则填“未知”）；
- **`os_compatibility`**：适配的操作系统（如`["Linux", "macOS"]`，无则填“跨平台”）；
- **`dependency_versions`**：依赖库版本要求（如`{{"numpy": ">=1.18"}}`，无则填“无特殊要求”）；
- **`hardware_constraint`**：硬件约束（如`["64-bit"]`，无则填“无”）。
#### 5. 补丁属性维度（从黄金补丁提取）
- **`patch_type`**：补丁类型（可选：bug修复、功能新增、性能优化、兼容性调整、文档更新）；
- **`patch_size`**：修改代码行数分类（`small`/`medium`/`large`）；
- **`breaking_change`**：是否破坏性修改（`true`/`false`）；
- **`migration_needed`**：是否需迁移（`true`/`false`，无则填`false`）；
- **`test_coverage`**：是否包含测试用例（`true`/`false`）。
#### 6. 效果验证维度（从问题描述/补丁提取）
- **`validation_steps`**：验证步骤（如`["运行测试用例并验证收敛"]`，无则填“运行对应测试用例”）；
- **`performance_impact`**：性能影响（无影响/提升/损耗/未知）。
### 输出格式要求
生成标准JSON，包含所有上述字段，顺序与维度一致。无信息的字段按要求填写（如`无`、`未知`、空数组），字符串字段避免冗余，严格基于输入内容提取。
# 注意
1. 禁止编造信息，所有标签必须来自上述输入内容；
2. 输出仅保留标准JSON，不要添加任何额外文字、注释；
3. 数组字段允许空数组，字符串字段避免冗余。
"""
    return prompt_template.format(
        repo_name=info["repo_name"],
        module_path=info["module_path"],
        problem_statement=info["problem_statement"],
        gold_patch=info["gold_patch"]
    ).strip()


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, json.JSONDecodeError)),
    reraise=True
)
def call_deepseek_api(info: Dict[str, str]) -> Dict[str, Any]:
    """
    调用DeepSeek API提取标签
    
    Args:
        info: 包含仓库、问题、补丁的字典
    
    Returns:
        提取的标签JSON字典
    
    Raises:
        requests.exceptions.RequestException: API请求失败
        json.JSONDecodeError: JSON解析失败
        ValueError: 响应中无有效JSON
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": _build_extract_prompt(info)}],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": False,
        "stop": None
    }

    response = requests.post(
        url=DEEPSEEK_API_URL,
        headers=headers,
        json=payload,
        timeout=API_TIMEOUT
    )
    response.raise_for_status()

    result = response.json()
    ai_reply = result["choices"][0]["message"]["content"].strip()

    # 解析JSON响应
    if ai_reply.startswith("{") and ai_reply.endswith("}"):
        extracted_json = json.loads(ai_reply)
    else:
        json_match = JSON_PATTERN.search(ai_reply)
        if not json_match:
            raise ValueError(f"响应中未找到有效JSON: {ai_reply[:200]}...")
        extracted_json = json.loads(json_match.group())

    # 添加源文件信息
    extracted_json["source_file"] = info["file_name"]
    return extracted_json


def get_txt_files() -> List[str]:
    """获取指定目录下的所有TXT文件"""
    if not os.path.exists(TXT_INPUT_DIR):
        logger.error(f"输入目录不存在: {TXT_INPUT_DIR}")
        return []
    
    return [
        f for f in os.listdir(TXT_INPUT_DIR)
        if f.endswith(".txt") and os.path.isfile(os.path.join(TXT_INPUT_DIR, f))
    ]


def save_results(all_results: List[Dict[str, Any]]) -> None:
    """保存成功结果到JSON文件"""
    try:
        with open(JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        logger.info(f"成功结果已写入: {JSON_OUTPUT_FILE}")
    except Exception as e:
        logger.error(f"写入结果文件失败: {str(e)}", exc_info=True)


def save_fail_files(fail_files: List[tuple]) -> None:
    """保存失败文件列表到JSON文件"""
    try:
        with open(FAIL_FILES_JSON, "w", encoding="utf-8") as f:
            json.dump(fail_files, f, ensure_ascii=False, indent=2)
        logger.info(f"失败文件列表已写入: {FAIL_FILES_JSON}")
    except Exception as e:
        logger.error(f"写入失败文件列表失败: {str(e)}", exc_info=True)


def batch_process() -> None:
    """批量处理TXT文件主函数"""
    all_results: List[Dict[str, Any]] = []
    success_count: int = 0
    fail_files: List[tuple] = []

    txt_files = get_txt_files()
    total_files = len(txt_files)
    
    logger.info(f"开始批量处理: 共发现 {total_files} 个TXT文件")
    if total_files == 0:
        logger.warning("未找到任何TXT文件，请检查输入目录配置")
        return

    # 遍历处理每个文件
    for idx, file_name in enumerate(txt_files, 1):
        file_path = os.path.join(TXT_INPUT_DIR, file_name)
        logger.info(f"处理进度: {idx}/{total_files} - 文件: {file_name}")

        # 读取并解析TXT文件
        file_info = read_txt_file(file_path)
        if not file_info:
            fail_files.append((file_name, "文件格式错误或缺少核心信息"))
            continue

        # 调用API提取标签
        try:
            extracted_tags = call_deepseek_api(file_info)
            all_results.append(extracted_tags)
            success_count += 1
            logger.info(f"文件 {file_name} 处理成功")

            # 控制API调用频率
            time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            error_msg = str(e)[:100]
            logger.error(f"文件 {file_name} 处理失败: {error_msg}", exc_info=True)
            fail_files.append((file_name, error_msg))
            continue

    # 保存处理结果
    if all_results:
        save_results(all_results)
    
    # 输出统计信息
    logger.info("=" * 50)
    logger.info("批量处理完成！")
    logger.info(f"总文件数: {total_files}")
    logger.info(f"成功数: {success_count}")
    logger.info(f"失败数: {len(fail_files)}")

    # 记录失败文件
    if fail_files:
        logger.info("失败文件列表（前10个）:")
        for file_name, error in fail_files[:10]:
            logger.info(f"  - {file_name}: {error}")
        
        if len(fail_files) > 10:
            logger.info(f"  ... 还有 {len(fail_files)-10} 个失败文件，详见日志")
        
        save_fail_files(fail_files)


if __name__ == "__main__":
    batch_process()
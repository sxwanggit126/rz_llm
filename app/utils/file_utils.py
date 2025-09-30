"""
文件处理工具模块
仅支持S3存储
"""
import os
import json
import uuid
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

import pymupdf
from json_repair import repair_json
from json_repair import repair_json
from loguru import logger
from app.tools.data_source.storage_manager import storage_service as default_storage

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB
ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md", ".docx"]


async def extract_file_text_from_s3(
    user_id: str,
    s3_key: str,
    storage_service=None
) -> Optional[str]:
    """
    从S3读取文件内容

    Args:
        user_id: 用户ID
        s3_key: S3对象键
        storage_service: 存储服务实例

    Returns:
        文件内容，失败返回None
    """
    try:
        if storage_service is None:
            storage_service = default_storage

        # 从S3获取文件内容
        file_content = await storage_service.get_user_file(
            user_id=user_id,
            s3_key=s3_key
        )

        if not file_content:
            logger.error(f"无法从S3获取文件: {s3_key}")
            return None

        # 判断文件类型
        file_ext = s3_key.split('.')[-1].lower() if '.' in s3_key else ''
        file_ext = f".{file_ext}" if file_ext and not file_ext.startswith('.') else file_ext

        if file_ext == ".pdf":
            # 处理PDF文件
            import io
            doc = pymupdf.open(stream=file_content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n\n"
            doc.close()
        else:
            # 处理文本文件
            text = file_content.decode('utf-8')

        logger.info(f"S3文件读取成功: {s3_key}, 长度: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"提取S3文件内容失败: {e}, S3键: {s3_key}")
        return None


async def extract_save_json_to_s3(
    content: str,
    user_id: str,
    filename: str,
    sub_dir: str = "processed",
    storage_service=None
) -> Optional[Dict[Any, Any]]:
    """
    从内容中提取JSON并保存到S3

    Args:
        content: 包含JSON的文本内容
        user_id: 用户ID
        filename: 文件名
        sub_dir: 子目录
        storage_service: 存储服务实例

    Returns:
        解析后的JSON对象，失败返回None
    """
    try:
        if storage_service is None:
            storage_service = default_storage

        # 提取JSON内容
        if '```json' in content:
            json_content = content.split('```json')[1].split('```')[0]
        else:
            json_content = content

        # 解析JSON
        json_data = json.loads(json_content)

        # 保存到S3
        s3_key = await storage_service.save_json_data(
            user_id=user_id,
            data=json_data,
            filename=filename,
            sub_dir=sub_dir
        )

        logger.info(f"JSON文件已保存到S3: {s3_key}")
        return json_data

    except Exception as e:
        logger.error(f"提取JSON失败: {e}, 内容: {content[:200]}...")
        return None


def extract_json_from_content(content: str) -> Optional[Dict[Any, Any]]:
    """
    从内容中提取JSON（不保存）

    Args:
        content: 包含JSON的文本内容

    Returns:
        解析后的JSON对象，失败返回None
    """
    try:
        # 提取JSON内容
        if '```json' in content:
            json_content = content.split('```json')[1].split('```')[0]
        else:
            json_content = content

        # 清理和修复JSON
        json_content = json_content.strip()

        # 使用 json_repair 修复损坏的JSON
        try:
            repaired_json = repair_json(json_content)
            json_data = json.loads(repaired_json)
            return json_data
        except Exception as repair_error:
            logger.warning(f"JSON修复失败，尝试直接解析: {repair_error}")
            # 如果修复失败，尝试直接解析原始内容
            json_data = json.loads(json_content)
            return json_data

    except Exception as e:
        logger.error(f"提取JSON失败: {e}")
        logger.error(f"问题内容: {content[:500]}...")
        return None


def get_file_name(s3_key: str) -> str:
    """
    获取文件名（不包含扩展名）

    Args:
        s3_key: S3对象键

    Returns:
        文件名
    """
    # 从S3键中提取文件名
    filename = s3_key.split('/')[-1] if '/' in s3_key else s3_key
    # 去掉扩展名
    if '.' in filename:
        return '.'.join(filename.split('.')[:-1])
    return filename


def get_file_extension(s3_key: str) -> str:
    """
    获取文件扩展名

    Args:
        s3_key: S3对象键

    Returns:
        文件扩展名（包含点号）
    """
    filename = s3_key.split('/')[-1] if '/' in s3_key else s3_key
    if '.' in filename:
        ext = filename.split('.')[-1]
        return f".{ext}" if not ext.startswith('.') else ext
    return ""


async def validate_file_from_s3(
    user_id: str,
    s3_key: str,
    storage_service=None
) -> Dict[str, Any]:
    """
    验证S3中的文件是否有效

    Args:
        user_id: 用户ID
        s3_key: S3对象键
        storage_service: 存储服务实例

    Returns:
        验证结果
    """
    if storage_service is None:
        storage_service = default_storage

    result = {
        "valid": False,
        "s3_key": s3_key,
        "exists": False,
        "size": 0,
        "extension": "",
        "errors": []
    }

    try:
        # 检查文件是否存在
        exists = await storage_service.file_exists(
            user_id=user_id,
            s3_key=s3_key
        )

        if not exists:
            result["errors"].append("文件不存在")
            return result

        result["exists"] = True

        # 获取文件内容以检查大小
        file_content = await storage_service.get_user_file(
            user_id=user_id,
            s3_key=s3_key
        )

        if file_content:
            result["size"] = len(file_content)
            result["extension"] = get_file_extension(s3_key)

            # 检查文件大小
            if result["size"] > MAX_FILE_SIZE:
                result["errors"].append(f"文件过大，最大允许 {MAX_FILE_SIZE / 1024 / 1024:.1f}MB")

            # 检查文件扩展名
            if result["extension"] not in ALLOWED_EXTENSIONS:
                result["errors"].append(f"不支持的文件类型，支持的类型: {', '.join(ALLOWED_EXTENSIONS)}")

            # 检查文件是否为空
            if result["size"] == 0:
                result["errors"].append("文件为空")
        else:
            result["errors"].append("无法读取文件内容")

        result["valid"] = len(result["errors"]) == 0

    except Exception as e:
        logger.error(f"验证S3文件失败: {s3_key}, 错误: {e}")
        result["errors"].append(f"验证失败: {str(e)}")

    return result


async def save_upload_file_to_s3(
    file_content: bytes,
    filename: str,
    user_id: str,
    sub_dir: str = "uploads",
    storage_service=None
) -> str:
    """
    保存上传的文件到S3

    Args:
        file_content: 文件内容
        filename: 文件名
        user_id: 用户ID
        sub_dir: 子目录
        storage_service: 存储服务实例

    Returns:
        S3对象键
    """
    if storage_service is None:
        storage_service = default_storage

    # 保存到S3
    s3_key = await storage_service.save_user_file(
        user_id=user_id,
        file_content=file_content,
        original_filename=filename,
        sub_dir=sub_dir
    )

    logger.info(f"文件已保存到S3: {s3_key}")
    return s3_key


def get_user_s3_prefix(user_id: str, sub_dir: str = "") -> str:
    """
    获取用户在S3中的存储前缀

    Args:
        user_id: 用户ID
        sub_dir: 子目录

    Returns:
        S3前缀路径
    """
    prefix = f"users/{user_id}"
    if sub_dir:
        prefix = f"{prefix}/{sub_dir}"
    return prefix


def get_processed_file_s3_key(
    user_id: str,
    original_filename: str,
    process_type: str
) -> str:
    """
    获取处理后文件的S3键

    Args:
        user_id: 用户ID
        original_filename: 原始文件名
        process_type: 处理类型

    Returns:
        S3对象键
    """
    file_name = get_file_name(original_filename)

    type_mapping = {
        "chunks": ("processed/chunks", f"{file_name}_chunks.txt"),
        "schemas": ("processed/schemas", f"{file_name}_schema.json"),
        "triplets": ("processed/triplets", f"{file_name}_triplets.json"),
        "terms": ("processed/terms", f"{file_name}_terms.json")
    }

    if process_type not in type_mapping:
        raise ValueError(f"不支持的处理类型: {process_type}")

    sub_dir, filename = type_mapping[process_type]
    return f"{get_user_s3_prefix(user_id, sub_dir)}/{filename}"


# 辅助函数：生成唯一文件名
def generate_unique_filename(original_filename: str) -> str:
    """
    生成唯一文件名

    Args:
        original_filename: 原始文件名

    Returns:
        唯一文件名
    """
    file_ext = get_file_extension(original_filename)
    unique_id = uuid.uuid4().hex[:8]
    base_name = get_file_name(original_filename)
    return f"{base_name}_{unique_id}{file_ext}"


# 导出兼容性函数（这些函数会被逐步废弃）
extract_save_json = extract_json_from_content  # 兼容旧代码
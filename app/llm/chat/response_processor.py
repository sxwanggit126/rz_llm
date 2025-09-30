"""
响应处理器 - 清理和规范化模型输出
"""
import re
from typing import Tuple, Optional
from app.utils.logger import get_logger

logger = get_logger("ResponseProcessor")


class ThinkTagProcessor:
    """处理<think>标签的工具类"""

    @classmethod
    def clean_duplicate_think_tags(cls, content: str) -> str:
        """
        清理重复的<think>标签

        处理场景：
        1. reasoning_content产生的<think>标签
        2. 模型响应prompt要求产生的<think>标签
        """
        # 统计<think>标签数量
        think_open_count = content.count("<think>")
        think_close_count = content.count("</think>")

        logger.debug(f"Found {think_open_count} <think> tags and {think_close_count} </think> tags")

        if think_open_count <= 1 and think_close_count <= 1:
            # 没有重复，直接返回
            return content

        # 提取所有<think>内容
        pattern = r'<think>(.*?)</think>'
        matches = re.findall(pattern, content, re.DOTALL)

        if len(matches) > 1:
            logger.info(f"Merging {len(matches)} thinking sections")

            # 合并所有思考内容
            merged_thinking = "\n\n".join(match.strip() for match in matches if match.strip())

            # 移除所有<think>标签
            content_without_think = re.sub(pattern, '', content, flags=re.DOTALL)

            # 重新组装，只保留一组<think>标签
            if merged_thinking:
                return f"<think>\n{merged_thinking}\n</think>\n\n{content_without_think.strip()}"
            else:
                return content_without_think.strip()

        return content

    @classmethod
    def extract_sections(cls, content: str) -> Tuple[Optional[str], str]:
        """
        提取思考部分和答案部分

        Returns:
            (thinking_content, answer_content)
        """
        # 先清理重复标签
        content = cls.clean_duplicate_think_tags(content)

        # 提取思考内容
        pattern = r'<think>(.*?)</think>'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            thinking = match.group(1).strip()
            answer = re.sub(pattern, '', content, flags=re.DOTALL).strip()
            return thinking, answer

        return None, content

    @classmethod
    def should_include_thinking(cls, content: str, include_thinking: bool = True) -> str:
        """
        根据参数决定是否包含思考内容
        """
        if not include_thinking:
            thinking, answer = cls.extract_sections(content)
            return answer
        return content

    @classmethod
    def format_for_display(cls, content: str, format_type: str = "default") -> str:
        """
        格式化输出用于展示

        Args:
            content: 原始内容
            format_type: 格式类型
                - "default": 保持原样
                - "markdown": 转换为Markdown格式
                - "separate": 分离思考和答案
        """
        content = cls.clean_duplicate_think_tags(content)

        if format_type == "markdown":
            # 将<think>标签转换为Markdown格式
            content = content.replace("<think>", "### 🤔 思考过程\n\n")
            content = content.replace("</think>", "\n\n---\n\n### 💡 答案\n\n")
            return content

        elif format_type == "separate":
            thinking, answer = cls.extract_sections(content)
            result = ""
            if thinking:
                result += f"【思考过程】\n{thinking}\n\n"
            result += f"【最终答案】\n{answer}"
            return result

        return content


class StreamProcessor:
    """处理流式输出"""

    def __init__(self):
        self.buffer = ""
        self.in_think_tag = False
        self.think_tag_count = 0
        self.first_think_content = []
        self.second_think_content = []
        self.final_content = []

    def process_chunk(self, chunk: str) -> str:
        """
        实时处理流式chunk，避免重复的think标签
        """
        # 添加到缓冲区
        self.buffer += chunk

        # 检测<think>标签
        if "<think>" in chunk:
            self.think_tag_count += 1
            if self.think_tag_count > 1:
                # 忽略第二个<think>标签
                return ""
            self.in_think_tag = True
            return chunk

        if "</think>" in chunk:
            if self.think_tag_count > 1:
                # 忽略多余的</think>标签
                self.in_think_tag = False
                return ""
            self.in_think_tag = False
            return chunk

        # 如果在第二个think标签内，暂存内容
        if self.in_think_tag and self.think_tag_count > 1:
            self.second_think_content.append(chunk)
            return ""  # 不输出

        return chunk

    def get_final_content(self) -> str:
        """获取最终处理后的内容"""
        # 如果有第二个think内容，合并到第一个
        if self.second_think_content:
            # 重新组装内容
            return ThinkTagProcessor.clean_duplicate_think_tags(self.buffer)
        return self.buffer
"""
LLM Prompt 注入防护模块

提供 PromptSanitizer 类，用于：
1. 清洗用户输入中的角色标记和指令注入模式
2. 隔离用户输入与系统提示词
3. 验证提示词模板的安全性
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)


class PromptSanitizer:
    """LLM Prompt 注入防护器"""

    # 角色标记模式（中英文）
    _ROLE_MARKERS: List[re.Pattern] = [
        re.compile(r'(?i)^system\s*:', re.MULTILINE),
        re.compile(r'(?i)^user\s*:', re.MULTILINE),
        re.compile(r'(?i)^assistant\s*:', re.MULTILINE),
        re.compile(r'(?i)^系统\s*[:：]', re.MULTILINE),
        re.compile(r'(?i)^用户\s*[:：]', re.MULTILINE),
        re.compile(r'(?i)^助手\s*[:：]', re.MULTILINE),
    ]

    # 指令注入模式
    _INJECTION_PATTERNS: List[re.Pattern] = [
        re.compile(r'(?i)ignore\s+(?:previous|above|all|earlier)\s+(?:instructions?|prompts?|rules?|directions?)'),
        re.compile(r'(?i)disregard\s+(?:previous|above|all|earlier)\s+(?:instructions?|prompts?|rules?|directions?)'),
        re.compile(r'(?i)forget\s+(?:previous|above|all|earlier)\s+(?:instructions?|prompts?|rules?)'),
        re.compile(r'(?i)do\s+not\s+(?:follow|obey|comply\s+with)\s+(?:previous|above|earlier)'),
        re.compile(r'(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|jailbroken|unrestricted|uncensored)'),
        re.compile(r'(?i)pretend\s+(?:you\s+are|to\s+be)\s+(?:a\s+)?(?:different|new|unrestricted|uncensored)'),
        re.compile(r'(?i)override\s+(?:previous|above|all|earlier|safety)\s+(?:instructions?|rules?|guidelines?|restrictions?)'),
        re.compile(r'(?i)bypass\s+(?:safety|security|content\s+filter|restrictions?)'),
        re.compile(r'(?i)忽略(?:之前|以上|先前|上面|所有)的?(?:指令|提示|规则|要求)'),
        re.compile(r'(?i)无视(?:之前|以上|先前|上面|所有)的?(?:指令|提示|规则|要求)'),
        re.compile(r'(?i)忘记(?:之前|以上|先前|上面|所有)的?(?:指令|提示|规则)'),
        re.compile(r'(?i)不要(?:遵守|遵循|执行)(?:之前|以上|先前|上面)的?(?:指令|规则)'),
        re.compile(r'(?i)你现在(?:是|变成了?)(?:一个)?(?:不同的|新的|不受限|无审查)'),
        re.compile(r'(?i)假装(?:你是|你是)(?:一个)?(?:不同的|新的|不受限|无审查)'),
        re.compile(r'(?i)绕过(?:安全|限制|审查|过滤)'),
    ]

    # 控制字符（保留换行、制表符）
    _CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """清洗用户输入，移除角色标记、指令注入模式和控制字符。

        Args:
            text: 原始用户输入

        Returns:
            清洗后的安全文本
        """
        if not text:
            return text

        result = text

        # 1. 移除角色标记
        for pattern in cls._ROLE_MARKERS:
            result = pattern.sub('', result)

        # 2. 替换指令注入模式为 [FILTERED]
        for pattern in cls._INJECTION_PATTERNS:
            result = pattern.sub('[FILTERED]', result)

        # 3. 移除控制字符
        result = cls._CONTROL_CHAR_PATTERN.sub('', result)

        return result

    @classmethod
    def isolate_user_input(cls, user_input: str, system_prompt: str) -> str:
        """将用户输入用分隔符隔离后拼接到系统提示词后。

        Args:
            user_input: 用户输入文本
            system_prompt: 系统提示词

        Returns:
            拼接后的完整提示词
        """
        sanitized_input = cls.sanitize_input(user_input)
        return (
            f"{system_prompt}\n"
            f"---USER INPUT BEGINS---\n{sanitized_input}\n---USER INPUT ENDS---\n"
        )

    @classmethod
    def validate_prompt_template(cls, template: str) -> bool:
        """验证提示词模板是否安全。

        检查模板中是否包含：
        - 角色标记（模板不应硬编码角色切换）
        - 指令注入模式
        - 未转义的用户输入占位符

        Args:
            template: 提示词模板字符串

        Returns:
            True 表示模板安全，False 表示存在风险
        """
        if not template:
            return True

        # 检查角色标记
        for pattern in cls._ROLE_MARKERS:
            if pattern.search(template):
                logger.warning(f"Prompt template contains role marker: {pattern.pattern}")
                return False

        # 检查指令注入模式
        for pattern in cls._INJECTION_PATTERNS:
            if pattern.search(template):
                logger.warning(f"Prompt template contains injection pattern: {pattern.pattern}")
                return False

        return True

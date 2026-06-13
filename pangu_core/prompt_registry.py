"""
盘古AI · Prompt注入器注册表

将 1495 行的 prompt_builder.py 拆分为注册式架构:
  - 每个注入器是独立的 @injector 装饰函数
  - 按 stage_id 自动选择激活的注入器
  - 新增注入器只需加一个函数 + 装饰器，不动主逻辑

用法:
    registry = PromptRegistry()
    system_msg = registry.build_system(context, stage="W2")
    user_msg = registry.build_user(context, stage="W2")
"""

from __future__ import annotations

from typing import Dict, List, Callable, Any, Tuple


class PromptRegistry:
    """
    Prompt注入器注册表。

    注入器签名: (context: Any) -> str | ""
    返回空字符串表示该注入器在此stage不激活。
    """

    def __init__(self):
        self._system_injectors: Dict[str, List[Callable]] = {}
        self._user_injectors: Dict[str, List[Callable]] = {}
        self._all_injectors: Dict[str, Callable] = {}  # layer_id → func

    def register_system(self, name: str, func: Callable, stage: str = "*"):
        """注册一个system消息注入器。stage="*"表示所有stage激活。"""
        key = stage
        if key not in self._system_injectors:
            self._system_injectors[key] = []
        self._system_injectors[key].append(func)
        self._all_injectors[name] = func

    def register_user(self, name: str, func: Callable, stage: str = "*"):
        """注册一个user消息注入器。"""
        key = stage
        if key not in self._user_injectors:
            self._user_injectors[key] = []
        self._user_injectors[key].append(func)
        self._all_injectors[name] = func

    def register_layer(self, name: str, func: Callable,
                        target: str = "system", stage: str = "*"):
        """注册一个通用层注入器。"""
        if target == "user":
            self.register_user(name, func, stage)
        else:
            self.register_system(name, func, stage)

    def build_system(self, context: Any, stage: str = "W2") -> str:
        """构建system消息"""
        parts = []
        for s in ["*", stage]:
            for injector in self._system_injectors.get(s, []):
                try:
                    result = injector(context)
                    if result:
                        parts.append(result)
                except Exception:
                    pass  # 单个注入器失败不影响整体
        return "\n\n".join(parts)

    def build_user(self, context: Any, stage: str = "W2") -> str:
        """构建user消息"""
        parts = []
        for s in ["*", stage]:
            for injector in self._user_injectors.get(s, []):
                try:
                    result = injector(context)
                    if result:
                        parts.append(result)
                except Exception:
                    pass
        return "\n\n".join(parts)

    def build_full(self, context: Any, stage: str = "W2") -> Tuple[str, str]:
        """返回 (system_msg, user_msg)"""
        return self.build_system(context, stage), self.build_user(context, stage)


# ================================================================
# 全局单例 (兼容旧 PromptBuilder)
# ================================================================

_default_registry: PromptRegistry = None


def get_registry() -> PromptRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry


def _build_default_registry() -> PromptRegistry:
    """构建默认注册表，注册来自 prompt_builder 的 17 层"""
    reg = PromptRegistry()

    # 延迟导入避免循环依赖
    from .prompt_builder import PromptBuilder
    builder = PromptBuilder()

    # 注册 17 层
    layers = [
        ("L01_system_role",     builder._L01_system_role,     "system"),
        ("L02_mode_rules",      builder._L02_mode_rules,      "system"),
        ("L03_platform_rules",  builder._L03_platform_rules,  "system"),
        ("L04_style_guidance",  builder._L04_style_guidance,  "system"),
        ("L05_sentence_params", builder._L05_sentence_params, "system"),
        ("L06_reference",       builder._L06_reference_material, "system"),
        ("L07_previous",        builder._L07_previous_summary, "system"),
        ("L08_characters",      builder._L08_character_states, "system"),
        ("L09_foreshadowing",   builder._L09_foreshadowing,    "system"),
        ("L10_contracts",       builder._L10_story_contracts,  "system"),
        ("L11_memory",          builder._L11_memory_layers,    "system"),
        ("L12_rag",             builder._L12_rag_retrieval,    "system"),
        ("L13_beat_sheet",      builder._L13_beat_sheet,       "system"),
        ("L15_db_context",      builder._L15_db_context,       "system"),
        ("L16_format_rules",    builder._L16_format_rules,     "system"),
        ("L14_chapter_task",    builder._L14_chapter_task,     "user"),
        ("L17_final_wrap",      builder._L17_final_wrap,       "user"),
    ]

    for name, func, target in layers:
        reg.register_layer(name, func, target=target, stage="*")

    return reg

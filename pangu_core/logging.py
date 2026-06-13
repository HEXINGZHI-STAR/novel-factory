"""
盘古AI · 结构化日志系统

替换 print() 为 structlog, 支持:
  - JSON格式输出 (生产) / 彩色控制台 (开发)
  - 自动绑定上下文 (stage_id, chapter_num, project)
  - 级别过滤 (DEBUG/INFO/WARNING/ERROR)
  - 性能: 惰性求值, 避免不必要的字符串格式化

用法:
    from pangu_core.logging import get_logger
    log = get_logger(__name__)

    log.info("stage_started", stage="W2", chapter=5)
    log.error("ai_call_failed", provider="deepseek", status=429)
"""

from __future__ import annotations

import os
import sys
import logging
from typing import Optional, Dict, Any

# === 尝试加载 structlog ===
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


# === 配置 ===
LOG_LEVEL = os.getenv("PANGU_LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("PANGU_LOG_FORMAT", "console")  # console / json


def setup_logging(level: str = None, fmt: str = None):
    """
    初始化全局日志配置。在应用启动时调用一次。

    Args:
        level: DEBUG/INFO/WARNING/ERROR
        fmt: console (彩色) / json (结构化)
    """
    level = level or LOG_LEVEL
    fmt = fmt or LOG_FORMAT

    if HAS_STRUCTLOG:
        _setup_structlog(level, fmt)
    else:
        _setup_stdlib(level)


def _setup_structlog(level: str, fmt: str):
    """配置 structlog"""
    import structlog

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.set_exc_info,
    ]

    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 设置根日志级别
    logging.getLogger().setLevel(getattr(logging, level.upper()))


def _setup_stdlib(level: str):
    """stdlib logging fallback"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def get_logger(name: str = None, **context) -> Any:
    """
    获取日志器。自动绑定上下文。

    Args:
        name: 模块名 (__name__)
        **context: 绑定的上下文键值对 (如 stage="W2")

    Returns:
        日志器实例 (structlog.BoundLogger 或 stdlib Logger)
    """
    if HAS_STRUCTLOG:
        import structlog
        logger = structlog.get_logger(name or __name__)
        if context:
            logger = logger.bind(**context)
        return logger
    else:
        logger = logging.getLogger(name or __name__)
        return _StdLibAdapter(logger, context)


class _StdLibAdapter:
    """stdlib logger 的结构化适配器"""

    def __init__(self, logger: logging.Logger, context: dict):
        self._logger = logger
        self._context = context

    def bind(self, **ctx):
        new_ctx = {**self._context, **ctx}
        return _StdLibAdapter(self._logger, new_ctx)

    def debug(self, event: str = "", **kwargs):
        self._logger.debug(self._format(event, **kwargs))

    def info(self, event: str = "", **kwargs):
        self._logger.info(self._format(event, **kwargs))

    def warning(self, event: str = "", **kwargs):
        self._logger.warning(self._format(event, **kwargs))

    def error(self, event: str = "", **kwargs):
        self._logger.error(self._format(event, **kwargs))

    def _format(self, event: str, **kwargs) -> str:
        ctx = {**self._context, **kwargs}
        if event:
            ctx["event"] = event
        return " ".join(f"{k}={v}" for k, v in ctx.items())


# === 初始化 ===
setup_logging()

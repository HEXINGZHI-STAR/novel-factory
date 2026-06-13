"""
盘古AI · 统一错误类型

借鉴 Rust 的 Result<T, E> 思想: 每个操作要么成功，要么返回明确的错误类型。
所有自定义错误继承自 PanguError，支持:
  - 错误码 (便于API返回)
  - 错误上下文 (便于调试)
  - 可恢复/不可恢复标记
  - 降级建议

用法:
    raise ConfigError("DEEPSEEK_API_KEY not set", code="CFG001")
    raise PipelineError("W2 draft generation failed", stage="W2", recoverable=True)
"""

from __future__ import annotations

from typing import Optional, Dict, Any


class PanguError(Exception):
    """盘古基础错误。所有自定义异常的基类。"""
    code: str = "PANGU000"
    recoverable: bool = False
    context: Dict[str, Any] = {}

    def __init__(self, message: str, *, code: str = None,
                  recoverable: bool = None, **context):
        super().__init__(message)
        if code:
            self.code = code
        if recoverable is not None:
            self.recoverable = recoverable
        self.context = context
        self.message = message

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "context": self.context,
        }


# ================================================================
# 配置错误 (不可恢复)
# ================================================================

class ConfigError(PanguError):
    """配置错误: 缺少必要配置、格式错误等"""
    code = "CFG001"
    recoverable = False


class APIKeyError(ConfigError):
    """API Key 缺失或无效"""
    code = "CFG002"


# ================================================================
# Pipeline 错误 (部分可恢复)
# ================================================================

class PipelineError(PanguError):
    """Pipeline 执行错误"""
    code = "PIPE001"
    recoverable = True

    def __init__(self, message: str, *, stage: str = "", **ctx):
        super().__init__(message, stage=stage, **ctx)


class StageError(PipelineError):
    """单个 Stage 执行失败"""
    code = "PIPE002"


class AICallError(PipelineError):
    """AI 调用失败 (可恢复——可重试或降级)"""
    code = "PIPE003"
    recoverable = True


class GateBlockError(PipelineError):
    """Write Gate 阻断"""
    code = "PIPE004"
    recoverable = False


# ================================================================
# 数据错误
# ================================================================

class DataError(PanguError):
    """数据访问错误"""
    code = "DATA001"
    recoverable = True


class StateCorruptError(DataError):
    """state.json 损坏"""
    code = "DATA002"
    recoverable = False


class DatabaseError(DataError):
    """数据库操作失败"""
    code = "DATA003"
    recoverable = True


# ================================================================
# Provider 错误
# ================================================================

class ProviderError(PanguError):
    """AI Provider 调用失败"""
    code = "PROV001"
    recoverable = True


class RateLimitError(ProviderError):
    """速率限制"""
    code = "PROV002"
    recoverable = True


class AuthenticationError(ProviderError):
    """认证失败 (API Key 无效)"""
    code = "PROV003"
    recoverable = False


# ================================================================
# 数学/分析错误
# ================================================================

class MathError(PanguError):
    """数学引擎计算失败"""
    code = "MATH001"
    recoverable = True


class InsufficientDataError(MathError):
    """数据不足 (如句子太少无法分析)"""
    code = "MATH002"
    recoverable = True

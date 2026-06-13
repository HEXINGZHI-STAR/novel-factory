"""测试 errors.py — 统一错误类型"""
import pytest
from pangu_core.errors import (
    PanguError, ConfigError, APIKeyError,
    PipelineError, StageError, AICallError, GateBlockError,
    DataError, StateCorruptError, DatabaseError,
    ProviderError, RateLimitError, AuthenticationError,
    MathError, InsufficientDataError,
)


class TestErrors:
    def test_base_error(self):
        e = PanguError("test")
        assert e.message == "test"
        assert e.code == "PANGU000"
        assert e.recoverable is False

    def test_config_error(self):
        e = ConfigError("missing key", code="CFG001")
        assert e.code == "CFG001"
        assert e.recoverable is False

    def test_api_key_error(self):
        e = APIKeyError("key invalid")
        assert isinstance(e, ConfigError)
        assert e.code == "CFG002"

    def test_pipeline_error_recoverable(self):
        e = AICallError("timeout", stage="W2")
        assert e.recoverable is True
        assert e.context["stage"] == "W2"

    def test_gate_block_not_recoverable(self):
        e = GateBlockError("prewrite failed")
        assert e.recoverable is False

    def test_error_to_dict(self):
        e = PipelineError("test", stage="W4", chapter=5)
        d = e.to_dict()
        assert d["error"] == "PIPE001"
        assert d["recoverable"] is True
        assert d["context"]["stage"] == "W4"
        assert d["context"]["chapter"] == 5

    def test_inheritance_chain(self):
        assert issubclass(APIKeyError, ConfigError)
        assert issubclass(ConfigError, PanguError)
        assert issubclass(StateCorruptError, DataError)
        assert issubclass(RateLimitError, ProviderError)
        assert issubclass(InsufficientDataError, MathError)

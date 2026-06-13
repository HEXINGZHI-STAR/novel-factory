"""测试 rag_engine.py — RAG后端检测 + 索引/检索"""
import pytest
from pangu_core.rag_engine import RAGEngine, SearchResult, HAS_FAISS, HAS_NUMPY


class TestRAGEngine:
    def test_backend_detection(self):
        engine = RAGEngine()
        assert engine.backend in ("faiss", "numpy", "none")
        if not HAS_FAISS and not HAS_NUMPY:
            assert engine.backend == "none"
            assert engine.is_available is False

    def test_empty_index(self):
        engine = RAGEngine()
        results = engine.search("测试查询")
        assert results == []

    def test_index_and_search_numpy(self):
        engine = RAGEngine(use_faiss=False)
        docs = ["文档一内容", "文档二内容", "文档三关于AI"]
        # 使用简单的手工embedding (2维)
        embeddings = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        engine.index(docs, embeddings)

        if engine.is_available:
            results = engine.search("文档一", embedding=[1.0, 0.1])
            assert len(results) >= 1

    def test_status(self):
        engine = RAGEngine()
        status = engine.status()
        assert "backend" in status
        assert "available" in status
        assert "documents" in status
        assert "faiss_installed" in status

    def test_degradation_graceful(self):
        """无后端时不应崩溃"""
        engine = RAGEngine(use_faiss=False)
        results = engine.search("查询")
        assert isinstance(results, list)

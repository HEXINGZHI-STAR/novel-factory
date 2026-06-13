"""
RAG知识检索引擎 - STUB (已废弃)

⚠ DEPRECATED: 此为盘古V7.5 Flask后端的stub实现，返回硬编码假数据。
  正式实现: pangu_core/rag_engine.py
  后端: FAISS→NumPy→None 三级自动降级
  用途: Pipeline L12层 + PromptBuilder检索

此文件仅保留以兼容 backend/app_v7.py 的旧导入路径。
新代码请直接使用: from pangu_core.rag_engine import RAGEngine
"""

from pathlib import Path

# 重导出正式实现
try:
    from pangu_core.rag_engine import (
        RAGEngine, SearchResult,
        get_rag_engine, search_for_chapter,
        HAS_FAISS, HAS_NUMPY,
    )
    _USING_REAL = True
except ImportError:
    _USING_REAL = False


# === 旧版兼容类 (backend/app_v7.py 仍在使用 PanguRAG 类名) ===

class PanguRAG:
    """旧版RAG接口 — 内部委托给 pangu_core.rag_engine.RAGEngine"""

    def __init__(self, project_name: str = None):
        self.project_name = project_name
        if _USING_REAL:
            from pangu_core.rag_engine import RAGEngine
            self._engine = RAGEngine()
        else:
            self._engine = None

    def search(self, query: str, top_k: int = 5, mode: str = None,
               platform: str = None, category: str = None) -> list:
        if self._engine and self._engine.is_available:
            results = self._engine.search(query, k=top_k)
            return [{"title": r.source, "category": category or "rag",
                     "source": "知识库", "score": r.score, "text": r.content[:200]}
                    for r in results]
        return []

    def load_index(self): pass
    def get_stats(self) -> dict:
        return {"total_documents": 0, "backend": "stub→pangu_core"}


def get_rag(project_name: str = None) -> PanguRAG:
    return PanguRAG(project_name)

def build_graph_from_project(project_name: str) -> dict:
    return {"nodes": [], "edges": []}

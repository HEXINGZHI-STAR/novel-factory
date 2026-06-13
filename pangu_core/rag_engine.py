"""
盘古AI · 轻量RAG检索引擎

向量检索后端 (自动选择):
  - FAISS (推荐): pip install faiss-cpu
  - NumPy (fallback): 纯Python余弦相似度
  - None (降级): 返回空，不影响核心流程

用法:
    engine = RAGEngine(knowledge_dir)
    engine.index(documents)              # 构建索引
    results = engine.search(query, k=5)  # 检索top-k
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# === 后端检测 ===
HAS_FAISS = False
HAS_NUMPY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    pass

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    pass


@dataclass
class SearchResult:
    """检索结果"""
    content: str
    score: float       # 相似度分数 (0-1)
    source: str = ""    # 来源标识
    metadata: dict = field(default_factory=dict)


class RAGEngine:
    """
    轻量RAG检索引擎。

    后端优先级: FAISS > NumPy > None
    每种后端失败时自动降级，不影响核心流程。
    """

    def __init__(self, knowledge_dir: Path = None, use_faiss: bool = True):
        self.knowledge_dir = knowledge_dir or Path(".")
        self.documents: List[SearchResult] = []
        self._index = None           # FAISS index
        self._embeddings = None      # NumPy embeddings matrix
        self._embedding_dim: int = 768
        self._backend = self._detect_backend(use_faiss)

    def _detect_backend(self, prefer_faiss: bool) -> str:
        if prefer_faiss and HAS_FAISS:
            return "faiss"
        elif HAS_NUMPY:
            return "numpy"
        else:
            return "none"

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def is_available(self) -> bool:
        return self._backend != "none"

    def index(self, documents: List[str], embeddings: List[List[float]] = None):
        """
        构建索引。

        Args:
            documents: 文本列表
            embeddings: 对应的向量嵌入 (None则用零向量占位)
        """
        self.documents = [
            SearchResult(content=doc, score=0.0, source=f"doc_{i}")
            for i, doc in enumerate(documents)
        ]

        if not documents:
            return

        if embeddings is None:
            # 无嵌入 → 降级到零向量
            embeddings = [[0.0] * 128 for _ in documents]
        self._embedding_dim = len(embeddings[0]) if embeddings else 128

        if self._backend == "faiss" and embeddings:
            self._build_faiss_index(embeddings)
        elif self._backend == "numpy" and embeddings:
            self._build_numpy_index(embeddings)

    def _build_faiss_index(self, embeddings: List[List[float]]):
        """构建FAISS索引"""
        try:
            dim = len(embeddings[0])
            self._index = faiss.IndexFlatIP(dim)  # 内积 = 余弦 (归一化后)
            vecs = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(vecs)  # 归一化 → 内积=余弦
            self._index.add(vecs)
        except Exception as e:
            print(f"[RAG] FAISS索引构建失败, 降级到numpy: {e}")
            self._backend = "numpy"
            self._build_numpy_index(embeddings)

    def _build_numpy_index(self, embeddings: List[List[float]]):
        """构建NumPy索引"""
        if not HAS_NUMPY:
            self._backend = "none"
            return
        self._embeddings = np.array(embeddings, dtype=np.float32)
        # 归一化
        norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._embeddings = self._embeddings / norms

    def search(self, query: str, embedding: List[float] = None,
                k: int = 5) -> List[SearchResult]:
        """
        检索与query最相关的k个文档。

        Args:
            query: 查询文本
            embedding: 查询的向量嵌入 (None则用零向量)
            k: 返回结果数

        Returns:
            搜索结果列表，按相似度降序
        """
        if not self.documents:
            return []

        if embedding is None:
            embedding = [0.0] * self._embedding_dim

        if self._backend == "faiss" and self._index is not None:
            scores, indices = self._search_faiss(embedding, k)
        elif self._backend == "numpy" and self._embeddings is not None:
            scores, indices = self._search_numpy(embedding, k)
        else:
            return []  # 降级: 无后端 → 返回空

        results = []
        for score, idx in zip(scores, indices):
            if 0 <= idx < len(self.documents):
                doc = self.documents[idx]
                doc.score = float(score)
                results.append(doc)

        return results

    def _search_faiss(self, embedding: List[float], k: int):
        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)
        scores, indices = self._index.search(vec, min(k, len(self.documents)))
        return scores[0], indices[0]

    def _search_numpy(self, embedding: List[float], k: int):
        vec = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        scores = np.dot(self._embeddings, vec)
        top_k = min(k, len(scores))
        indices = np.argsort(scores)[-top_k:][::-1]
        return scores[indices], indices

    def status(self) -> dict:
        """返回引擎状态"""
        return {
            "backend": self._backend,
            "available": self.is_available,
            "documents": len(self.documents),
            "dimension": self._embedding_dim,
            "faiss_installed": HAS_FAISS,
            "numpy_installed": HAS_NUMPY,
        }


# ================================================================
# 便捷函数: 用于 prompt_builder L12 层的兼容适配
# ================================================================

_global_engine: Optional[RAGEngine] = None


def get_rag_engine(knowledge_dir: Path = None) -> RAGEngine:
    """获取全局RAG引擎单例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = RAGEngine(knowledge_dir)
    return _global_engine


def search_for_chapter(chapter_task: str, project_dir: str = "",
                        k: int = 5) -> List[SearchResult]:
    """
    Prompt builder L12 兼容接口。

    对章节任务进行语义检索，返回相关参考材料。
    未索引或无后端时返回空列表，不阻塞Pipeline。
    """
    engine = get_rag_engine()
    if not engine.is_available or not engine.documents:
        return []
    return engine.search(chapter_task, k=k)

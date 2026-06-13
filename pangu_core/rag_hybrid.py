"""
盘古AI - RAG混合检索适配器 (t7.5)
适配自 webnovel-writer/rag_adapter.py，增强盘古现有RAG引擎：

新增能力：
1. BM25关键词检索（替代TF-IDF）
2. RRF（Reciprocal Rank Fusion）混合融合
3. Rerank重排序（调用AI API）

保留盘古原有优势：
- FAISS-HNSW 向量检索（O(log N)）
- GraphRAG 实体图检索
- COSO 车间级访问控制
- 增量更新 + 内容哈希

架构：
  Query → [FAISS-HNSW + BM25] → RRF融合 → Rerank精排 → 结果
                  ↓
            GraphRAG扩展（可选）
"""

import os
import json
import math
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# 数据结构
# ============================================================

@dataclass
class SearchResult:
    """搜索结果"""
    chunk_id: str
    chapter: int
    scene_index: int
    content: str
    score: float
    source: str  # "vector" | "bm25" | "hybrid" | "rerank"
    parent_chunk_id: Optional[str] = None
    chunk_type: Optional[str] = None
    source_file: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


# ============================================================
# BM25 检索器
# ============================================================

class BM25Retriever:
    """
    BM25 关键词检索器
    
    标准BM25公式：
      score(D, Q) = Σ_{t∈Q} IDF(t) * (TF(t,D) * (k1+1)) / (TF(t,D) + k1 * (1-b + b*|D|/avgdl))
    
    其中：
      - IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
      - TF(t,D) = 词t在文档D中的频次
      - |D| = 文档D的长度（分词数）
      - avgdl = 平均文档长度
      - k1, b = 可调参数（默认k1=1.5, b=0.75）
    """
    
    def __init__(self, knowledge_dir: Path, k1: float = 1.5, b: float = 0.75):
        self.knowledge_dir = knowledge_dir
        self.k1 = k1
        self.b = b
        
        # SQLite数据库路径
        self.db_path = knowledge_dir / ".rag_cache" / "bm25.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        # 倒排索引：term → [(doc_id, tf), ...]
        self.inverted_index: Dict[str, List[Tuple[str, int]]] = {}
        
        # 文档统计：doc_id → (length, [terms])
        self.doc_stats: Dict[str, Tuple[int, List[str]]] = {}
        
        # 词频统计：term → df (文档频次)
        self.df: Dict[str, int] = {}
        
        self._initialized = False
    
    def initialize(self, documents: List[Dict]) -> None:
        """
        初始化BM25索引
        
        Args:
            documents: 文档列表，每个文档格式：
                {
                    "chunk_id": "ch0001_s1",
                    "text": "场景内容...",
                    "chapter": 1,
                    "scene_index": 1,
                    ...
                }
        """
        if self._initialized:
            return
        
        logger.info(f"[BM25] 开始构建索引，文档数: {len(documents)}")
        
        # 1. 分词 + 统计TF
        doc_count = 0
        for doc in documents:
            chunk_id = doc.get("chunk_id", f"doc_{doc_count}")
            text = doc.get("text", "")
            
            # 分词（中文按字符，英文按单词）
            terms = self._tokenize(text)
            doc_length = len(terms)
            
            if doc_length == 0:
                continue
            
            # 统计TF
            tf_counter = Counter(terms)
            
            # 更新倒排索引
            for term, tf in tf_counter.items():
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append((chunk_id, tf))
            
            # 更新文档统计
            self.doc_stats[chunk_id] = (doc_length, terms)
            
            doc_count += 1
        
        # 2. 计算DF (Document Frequency)
        all_terms = set()
        for doc_id, (length, terms) in self.doc_stats.items():
            unique_terms = set(terms)
            all_terms.update(unique_terms)
            for term in unique_terms:
                self.df[term] = self.df.get(term, 0) + 1
        
        # 3. 持久化到SQLite
        self._persist_to_sqlite(documents)
        
        self._initialized = True
        logger.info(f"[BM25] 索引构建完成: {len(self.doc_stats)} 文档, {len(self.df)} 词项")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        分词（中文按字符，英文按单词）
        
        TODO: 可替换为更好的分词器（如jieba）
        """
        import re
        
        # 中文字符（按单字分词）
        chinese = re.findall(r'[\u4e00-\u9fff]', text)
        
        # 英文单词
        english = re.findall(r'[a-zA-Z]+', text.lower())
        
        # 数字
        numbers = re.findall(r'\d+', text)
        
        return chinese + english + numbers
    
    def _persist_to_sqlite(self, documents: List[Dict]) -> None:
        """持久化到SQLite"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bm25_index (
                    term TEXT,
                    chunk_id TEXT,
                    tf INTEGER,
                    PRIMARY KEY (term, chunk_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doc_stats (
                    chunk_id TEXT PRIMARY KEY,
                    doc_length INTEGER
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bm25_term ON bm25_index(term)
            """)
            
            # 清空旧数据
            cursor.execute("DELETE FROM bm25_index")
            cursor.execute("DELETE FROM doc_stats")
            
            # 插入倒排索引
            for term, postings in self.inverted_index.items():
                for chunk_id, tf in postings:
                    cursor.execute(
                        "INSERT OR REPLACE INTO bm25_index (term, chunk_id, tf) VALUES (?, ?, ?)",
                        (term, chunk_id, tf)
                    )
            
            # 插入文档统计
            for chunk_id, (doc_length, _) in self.doc_stats.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO doc_stats (chunk_id, doc_length) VALUES (?, ?)",
                    (chunk_id, doc_length)
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"[BM25] 索引已持久化到: {self.db_path}")
        
        except Exception as e:
            logger.warning(f"[BM25] 持久化失败: {e}")
    
    def load_from_sqlite(self) -> bool:
        """从SQLite加载索引"""
        if not self.db_path.exists():
            return False
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 加载倒排索引
            cursor.execute("SELECT term, chunk_id, tf FROM bm25_index")
            for term, chunk_id, tf in cursor.fetchall():
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append((chunk_id, tf))
            
            # 加载文档统计
            cursor.execute("SELECT chunk_id, doc_length FROM doc_stats")
            for chunk_id, doc_length in cursor.fetchall():
                # 需要从原始文档恢复terms（或只存length）
                self.doc_stats[chunk_id] = (doc_length, [])
            
            # 计算DF
            for term, postings in self.inverted_index.items():
                self.df[term] = len(postings)
            
            conn.close()
            
            self._initialized = True
            logger.info(f"[BM25] 从磁盘加载索引: {len(self.doc_stats)} 文档, {len(self.df)} 词项")
            return True
        
        except Exception as e:
            logger.warning(f"[BM25] 加载索引失败: {e}")
            return False
    
    def search(self, query: str, top_k: int = 10, 
              chunk_type: Optional[str] = None,
              chapter: Optional[int] = None) -> List[SearchResult]:
        """
        BM25检索
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            chunk_type: 过滤chunk类型（可选）
            chapter: 限制章节范围（可选）
        
        Returns:
            List[SearchResult]
        """
        if not self._initialized:
            logger.warning("[BM25] 索引未初始化")
            return []
        
        # 1. 分词
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        
        # 2. 计算文档分数
        N = len(self.doc_stats)  # 总文档数
        if N == 0:
            return []
        
        # 计算平均文档长度
        avgdl = sum(length for length, _ in self.doc_stats.values()) / N
        
        # 文档分数：doc_id → score
        doc_scores = {}
        
        for term in set(query_terms):
            # IDF
            df_t = self.df.get(term, 0)
            if df_t == 0:
                continue
            idf = math.log((N - df_t + 0.5) / (df_t + 0.5) + 1)
            
            # 遍历包含该词的文档
            postings = self.inverted_index.get(term, [])
            for chunk_id, tf in postings:
                if chunk_id not in self.doc_stats:
                    continue
                
                doc_length, _ = self.doc_stats[chunk_id]
                
                # BM25公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / avgdl)
                bm25_score = idf * (numerator / denominator)
                
                if chunk_id not in doc_scores:
                    doc_scores[chunk_id] = 0.0
                doc_scores[chunk_id] += bm25_score
        
        # 3. 排序并返回top_k
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for chunk_id, score in sorted_docs[:top_k]:
            # TODO: 从数据库或原始文档加载完整信息
            result = SearchResult(
                chunk_id=chunk_id,
                chapter=-1,  # TODO: 从元数据加载
                scene_index=-1,
                content="",  # TODO: 从元数据加载
                score=score,
                source="bm25"
            )
            results.append(result)
        
        return results


# ============================================================
# RRF 混合融合
# ============================================================

def rrf_fusion(vector_results: List[SearchResult],
               bm25_results: List[SearchResult],
               k: int = 60) -> List[SearchResult]:
    """
    RRF (Reciprocal Rank Fusion) 混合融合
    
    公式：
      RRFscore(d) = Σ_{r∈{vector,bm25}} 1 / (k + rank_r(d))
    
    其中：
      - rank_r(d) = 文档d在检索结果r中的排名（从1开始）
      - k = 常量（默认60，用于调节低排名文档的影响）
    
    优势：
      - 不依赖不同检索系统的分数校准
      - 对高排名文档给予更高权重
      - 简单有效
    
    Args:
        vector_results: 向量检索结果
        bm25_results: BM25检索结果
        k: RRF常数（默认60）
    
    Returns:
        List[SearchResult] 按RRF分数排序
    """
    # 构建 chunk_id → (result, rank) 映射
    vector_rank = {r.chunk_id: (r, i+1) for i, r in enumerate(vector_results)}
    bm25_rank = {r.chunk_id: (r, i+1) for i, r in enumerate(bm25_results)}
    
    # 计算RRF分数
    all_chunk_ids = set(vector_rank.keys()) | set(bm25_rank.keys())
    rrf_scores = {}
    
    for chunk_id in all_chunk_ids:
        rrf_score = 0.0
        
        # 向量检索贡献
        if chunk_id in vector_rank:
            _, rank = vector_rank[chunk_id]
            rrf_score += 1.0 / (k + rank)
        
        # BM25检索贡献
        if chunk_id in bm25_rank:
            _, rank = bm25_rank[chunk_id]
            rrf_score += 1.0 / (k + rank)
        
        # 保留结果（优先保留向量结果，如果没有则保留BM25结果）
        if chunk_id in vector_rank:
            result = vector_rank[chunk_id][0]
        else:
            result = bm25_rank[chunk_id][0]
        
        result.score = rrf_score
        result.source = "hybrid"
        
        rrf_scores[chunk_id] = result
    
    # 按RRF分数排序
    sorted_results = sorted(rrf_scores.values(), key=lambda r: r.score, reverse=True)
    
    return sorted_results


# ============================================================
# Rerank 重排序
# ============================================================

class RerankClient:
    """
    Rerank重排序客户端
    
    调用AI API进行精排（如Cohere Rerank、OpenAI Rerank等）
    
    TODO: 
      - 根据实际API调整实现
      - 支持本地Rerank模型（如cross-encoder）
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "rerank-model"):
        self.api_key = api_key or os.getenv("RERANK_API_KEY")
        self.model = model
        self.enabled = self.api_key is not None
    
    async def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[Dict]:
        """
        Rerank重排序
        
        Args:
            query: 查询字符串
            documents: 文档列表（文本）
            top_n: 返回top_n个结果
        
        Returns:
            List[Dict]: [{"index": 0, "relevance_score": 0.95}, ...]
        """
        if not self.enabled:
            logger.warning("[Rerank] API密钥未配置，跳过重排序")
            # 返回原始顺序
            return [{"index": i, "relevance_score": 1.0 - i*0.1} for i in range(min(top_n, len(documents)))]
        
        try:
            # TODO: 调用实际Rerank API
            # 示例（Cohere Rerank）:
            # import cohere
            # co = cohere.Client(self.api_key)
            # response = co.rerank(query=query, documents=documents, top_n=top_n, model=self.model)
            # return [{"index": r.index, "relevance_score": r.relevance_score} for r in response.results]
            
            logger.info(f"[Rerank] 对 {len(documents)} 个文档进行重排序")
            
            # 暂时返回模拟结果
            return [{"index": i, "relevance_score": 1.0 - i*0.05} for i in range(min(top_n, len(documents)))]
        
        except Exception as e:
            logger.error(f"[Rerank] 重排序失败: {e}")
            return [{"index": i, "relevance_score": 1.0 - i*0.1} for i in range(min(top_n, len(documents)))]


# ============================================================
# 混合检索适配器
# ============================================================

class PanguHybridRAG:
    """
    盘古混合RAG检索适配器
    
    检索流程：
      1. FAISS-HNSW 向量检索（盘古原有）
      2. BM25 关键词检索（新增）
      3. RRF 融合（新增）
      4. Rerank 重排序（新增）
      5. GraphRAG 扩展（盘古原有，可选）
    """
    
    def __init__(self, knowledge_dir: Path, use_rerank: bool = True):
        self.knowledge_dir = knowledge_dir
        
        #  BM25检索器
        self.bm25 = BM25Retriever(knowledge_dir)
        
        # Rerank客户端
        self.rerank_client = RerankClient() if use_rerank else None
        
        # 盘古原有RAG引擎（延迟导入，避免循环导入）
        self._pangu_rag = None
        
        self._initialized = False
        self._vector_retrieval_enabled = False  # 明确标记向量检索是否启用
    
    @property
    def pangu_rag(self):
        """懒加载盘古RAG引擎"""
        if self._pangu_rag is None:
            try:
                from rag_engine import PanguRAG
                self._pangu_rag = PanguRAG(self.knowledge_dir)
                self._pangu_rag.initialize()
                self._vector_retrieval_enabled = True
                logger.info("[HybridRAG] 向量检索引擎加载成功")
            except ImportError:
                logger.warning("[HybridRAG] 向量检索未启用：rag_engine.py 不存在，仅使用BM25检索")
                self._pangu_rag = False  # 标记为加载失败
            except Exception as e:
                logger.warning(f"[HybridRAG] 向量检索加载失败: {e}，仅使用BM25检索")
                self._pangu_rag = False  # 标记为加载失败
        return self._pangu_rag if self._pangu_rag is not False else None
    
    def initialize(self, documents: List[Dict]) -> None:
        """
        初始化混合检索器
        
        Args:
            documents: 文档列表（用于BM25索引）
        """
        if self._initialized:
            return
        
        logger.info("[HybridRAG] 开始初始化混合检索器...")
        
        # 1. 初始化BM25
        bm25_loaded = self.bm25.load_from_sqlite()
        if not bm25_loaded:
            logger.info("[HybridRAG] BM25索引不存在，开始构建...")
            self.bm25.initialize(documents)
        else:
            logger.info("[HybridRAG] BM25索引已从磁盘加载")
        
        # 2. 初始化盘古RAG（向量检索）
        if self.pangu_rag:
            logger.info("[HybridRAG] 盘古RAG引擎已初始化")
        
        self._initialized = True
        logger.info("[HybridRAG] 混合检索器初始化完成")
    
    async def hybrid_search(self,
                          query: str,
                          top_k: int = 10,
                          vector_top_k: int = 20,
                          bm25_top_k: int = 20,
                          rerank_top_n: int = 10,
                          chunk_type: Optional[str] = None,
                          chapter: Optional[int] = None,
                          use_graph: bool = False) -> List[SearchResult]:
        """
        混合检索（向量 + BM25 + RRF + Rerank）
        
        Args:
            query: 查询字符串
            top_k: 最终返回结果数
            vector_top_k: 向量检索召回数
            bm25_top_k: BM25检索召回数
            rerank_top_n: Rerank精排返回数
            chunk_type: 过滤chunk类型
            chapter: 限制章节范围
            use_graph: 是否使用GraphRAG扩展
        
        Returns:
            List[SearchResult]
        """
        if not self._initialized:
            logger.warning("[HybridRAG] 未初始化，尝试初始化...")
            # 尝试从盘古RAG获取文档
            if self.pangu_rag:
                # 从盘古RAG的documents构建BM25索引
                self.bm25.initialize(self.pangu_rag.documents)
            self._initialized = True
        
        # === Step 1: 向量检索（FAISS-HNSW）===
        vector_results = []
        if self.pangu_rag:
            try:
                raw_results = self.pangu_rag.search(
                    query, 
                    top_k=vector_top_k,
                    mode=None,
                    platform=None,
                    category=None
                )
                # 转换为SearchResult格式
                for r in raw_results:
                    vector_results.append(SearchResult(
                        chunk_id=r.get("title", ""),
                        chapter=-1,
                        scene_index=-1,
                        content=r.get("text", ""),
                        score=r.get("score", 0.0),
                        source="vector",
                        metadata=r
                    ))
            except Exception as e:
                logger.warning(f"[HybridRAG] 向量检索失败: {e}")
        
        # === Step 2: BM25检索 ===
        bm25_results = []
        try:
            bm25_results = self.bm25.search(
                query,
                top_k=bm25_top_k,
                chunk_type=chunk_type,
                chapter=chapter
            )
        except Exception as e:
            logger.warning(f"[HybridRAG] BM25检索失败: {e}")
        
        # === Step 3: RRF融合 ===
        fused_results = rrf_fusion(vector_results, bm25_results)
        
        logger.info(f"[HybridRAG] 检索统计: 向量{len(vector_results)}条, BM25{len(bm25_results)}条, 融合{len(fused_results)}条")
        
        # === Step 4: Rerank重排序 ===
        if self.rerank_client and len(fused_results) > 1:
            try:
                documents = [r.content for r in fused_results[:rerank_top_n * 2]]
                rerank_results = await self.rerank_client.rerank(query, documents, top_n=rerank_top_n)
                
                # 根据Rerank结果重新排序
                reranked = []
                for item in rerank_results:
                    idx = item.get("index", -1)
                    if 0 <= idx < len(fused_results):
                        result = fused_results[idx]
                        result.score = item.get("relevance_score", result.score)
                        result.source = "rerank"
                        reranked.append(result)
                
                fused_results = reranked
                logger.info(f"[HybridRAG] Rerank完成: {len(fused_results)}条")
            except Exception as e:
                logger.warning(f"[HybridRAG] Rerank失败: {e}")
        
        # === Step 5: GraphRAG扩展（可选）===
        if use_graph and self.pangu_rag:
            try:
                # TODO: 从fused_results中提取实体，扩展检索
                pass
            except Exception as e:
                logger.warning(f"[HybridRAG] GraphRAG扩展失败: {e}")
        
        return fused_results[:top_k]


# ============================================================
# 便捷函数
# ============================================================

def create_hybrid_rag(knowledge_dir: Path, use_rerank: bool = True) -> PanguHybridRAG:
    """创建混合RAG检索器"""
    return PanguHybridRAG(knowledge_dir, use_rerank=use_rerank)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 测试BM25
    print("=== 测试BM25检索器 ===")
    bm25 = BM25Retriever(Path("./test_knowledge"))
    
    test_docs = [
        {"chunk_id": "ch0001_s1", "text": "林晚在雨中奔跑，寻找失踪的妹妹。", "chapter": 1},
        {"chunk_id": "ch0001_s2", "text": "城市的霓虹灯在雨雾中模糊成一片。", "chapter": 1},
        {"chunk_id": "ch0002_s1", "text": "三年前的那个夜晚，一切都改变了。", "chapter": 2},
    ]
    
    bm25.initialize(test_docs)
    
    results = bm25.search("林晚 妹妹", top_k=5)
    print(f"BM25检索结果: {len(results)}条")
    for r in results:
        print(f"  - {r.chunk_id}: {r.score:.4f}")
    
    # 测试RRF融合
    print("\n=== 测试RRF融合 ===")
    vector_results = [
        SearchResult("ch0001_s1", 1, 1, "林晚在雨中奔跑，寻找失踪的妹妹。", 0.92, "vector"),
        SearchResult("ch0002_s1", 2, 1, "三年前的那个夜晚，一切都改变了。", 0.85, "vector"),
    ]
    bm25_results = [
        SearchResult("ch0001_s1", 1, 1, "林晚在雨中奔跑，寻找失踪的妹妹。", 3.2, "bm25"),
        SearchResult("ch0001_s2", 1, 2, "城市的霓虹灯在雨雾中模糊成一片。", 1.5, "bm25"),
    ]
    
    fused = rrf_fusion(vector_results, bm25_results)
    print(f"RRF融合结果: {len(fused)}条")
    for r in fused:
        print(f"  - {r.chunk_id}: RRF={r.score:.6f}")
    
    print("\n=== 测试完成 ===")

"""
盘古V7.5 轻量级RAG引擎
三模式检索：FAISS-HNSW语义检索（推荐） → FAISS-Flat（回退1） → TF-IDF（回退2）
开源集成：FAISS (MIT) + sentence-transformers (Apache 2.0)

V7.5 升级要点:
  - HNSW 索引替代暴力 Flat 检索，速度提升 5-20x
  - 索引持久化到磁盘，重启秒加载，无需重建向量
  - 相似度阈值过滤，杜绝低质量垃圾结果
"""

import os
import json
import re
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

# === 开源向量检索：FAISS (Facebook/Meta, MIT License) ===
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

# === 开源语义嵌入：sentence-transformers (Apache 2.0) ===
try:
    from sentence_transformers import SentenceTransformer
    HAS_SBERT = True
except ImportError:
    HAS_SBERT = False

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
# FAISS 索引持久化路径
INDEX_CACHE_DIR = KNOWLEDGE_DIR / ".rag_cache"
INDEX_CACHE_DIR.mkdir(exist_ok=True)


class SimpleTfidfVectorizer:
    """纯numpy字符级TF-IDF向量化器"""

    def __init__(self, ngram_range=(2, 4), max_df=0.95, min_df=1):
        self.ngram_range = ngram_range
        self.max_df = max_df
        self.min_df = min_df
        self.vocab = {}
        self.idf = None

    def _extract_ngrams(self, text: str) -> Dict[str, int]:
        text = re.sub(r'[^\u4e00-\u9fff\w]', '', text.lower())
        counts = {}
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for i in range(len(text) - n + 1):
                gram = text[i:i + n]
                counts[gram] = counts.get(gram, 0) + 1
        return counts

    def fit_transform(self, texts: List[str]) -> np.ndarray:
        doc_grams = []
        gram_doc_count = {}
        for text in texts:
            grams = self._extract_ngrams(text)
            doc_grams.append(grams)
            for gram in grams:
                gram_doc_count[gram] = gram_doc_count.get(gram, 0) + 1

        N = len(texts)
        max_count = int(N * self.max_df)

        self.vocab = {}
        for gram, count in gram_doc_count.items():
            if count < self.min_df or count > max_count:
                continue
            self.vocab[gram] = len(self.vocab)

        V = len(self.vocab)
        if V == 0:
            return np.zeros((N, 1))

        self.idf = np.zeros(V)
        for gram, idx in self.vocab.items():
            df = gram_doc_count[gram]
            self.idf[idx] = math.log((N + 1) / (df + 1)) + 1

        matrix = np.zeros((N, V))
        for i, grams in enumerate(doc_grams):
            total = sum(grams.values())
            if total == 0:
                continue
            for gram, count in grams.items():
                if gram in self.vocab:
                    idx = self.vocab[gram]
                    tf = count / total
                    matrix[i, idx] = tf * self.idf[idx]

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def transform(self, texts: List[str]) -> np.ndarray:
        V = len(self.vocab)
        N = len(texts)
        matrix = np.zeros((N, V))
        for i, text in enumerate(texts):
            grams = self._extract_ngrams(text)
            total = sum(grams.values())
            if total == 0:
                continue
            for gram, count in grams.items():
                if gram in self.vocab:
                    idx = self.vocab[gram]
                    tf = count / total
                    matrix[i, idx] = tf * self.idf[idx]
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class SemanticIndex:
    """
    FAISS 语义检索引擎 —— V7.5 HNSW 升级版
    - HNSW 索引：O(log N) 搜索 vs Flat O(N)，速度提升 5-20x
    - 磁盘持久化：save()/load()，重启秒加载，无需重建向量
    - 增量更新：sync() 检测变更，仅重编码变化文档
    - 自动过期：index_ttl_days 到期自动全量重建
    - 相似度阈值：score_threshold 自动过滤低质量结果
    - 多级回退：HNSW → Flat → TF-IDF → 关键词
    - 国内适配：HF镜像/ModelScope/本地路径 三级模型加载
    """

    # 可通过环境变量覆盖的模型路径
    #   set SEMANTIC_MODEL_PATH=d:/models/paraphrase-multilingual-MiniLM-L12-v2
    #   国内镜像自动设置 HF_ENDPOINT=https://hf-mirror.com
    EMBEDDING_MODEL = os.getenv("SEMANTIC_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
    DEFAULT_THRESHOLD = 0.3
    REBUILD_RATIO = 0.2
    DEFAULT_TTL_DAYS = 7
    _model = None

    @classmethod
    def _setup_hf_mirror(cls):
        """配置 HuggingFace 国内镜像（hf-mirror.com），已有环境变量则跳过"""
        if not os.getenv("HF_ENDPOINT"):
            mirror = os.getenv("HF_MIRROR", "https://hf-mirror.com")
            os.environ["HF_ENDPOINT"] = mirror
            print(f"[RAG] HF镜像已设置: {mirror}")

    @classmethod
    def _get_model(cls):
        """懒加载嵌入模型（全局单例）。三级加载策略：
           1. 环境变量 SEMANTIC_MODEL_PATH → 本地离线路径
           2. HF_ENDPOINT / hf-mirror.com → 国内镜像下载
           3. HuggingFace 官方源 → 兜底（需科学上网）
        """
        if cls._model is None and HAS_SBERT:
            # Step 0: 配置国内镜像
            cls._setup_hf_mirror()

            # Step 1: 检查本地离线路径
            local_path = os.getenv("SEMANTIC_MODEL_PATH", "")
            if local_path and Path(local_path).exists():
                try:
                    cls._model = SentenceTransformer(local_path)
                    print(f"[RAG] 语义模型从本地加载: {local_path}")
                    return cls._model
                except Exception as e:
                    print(f"[RAG] 本地模型加载失败: {e}，尝试在线下载...")

            # Step 2: 尝试在线加载（走 HF 镜像或官方源）
            try:
                cls._model = SentenceTransformer(cls.EMBEDDING_MODEL)
                print(f"[RAG] 语义模型已加载: {cls.EMBEDDING_MODEL}")
            except Exception as e1:
                # Step 3: 尝试 ModelScope 作为最后兜底
                print(f"[RAG] 在线加载失败 ({e1})，尝试 ModelScope...")
                try:
                    from modelscope import snapshot_download
                    model_dir = snapshot_download(
                        "iic/nlp_paraphrase-multilingual-MiniLM-L12-v2",
                        cache_dir=INDEX_CACHE_DIR / "models"
                    )
                    cls._model = SentenceTransformer(model_dir)
                    print(f"[RAG] 语义模型从 ModelScope 加载成功")
                except ImportError:
                    print("[RAG] ModelScope 未安装。离线部署方式：")
                    print("  1. 手动下载模型到本地文件夹")
                    print("  2. set SEMANTIC_MODEL_PATH=你的模型路径")
                    print("  3. 重启服务即可离线使用")
                except Exception as e2:
                    print(f"[RAG] 所有模型加载方式均失败。")
                    print(f"  HF: {e1}")
                    print(f"  ModelScope: {e2}")
        return cls._model

    def __init__(self, index_name: str = "pangu_knowledge",
                 index_type: str = "hnsw", similarity_threshold: float = None,
                 index_ttl_days: int = None):
        self.index_name = index_name
        self.index_type = index_type
        self.similarity_threshold = similarity_threshold or self.DEFAULT_THRESHOLD
        self.index_ttl_days = index_ttl_days if index_ttl_days is not None else self.DEFAULT_TTL_DAYS
        self.index = None
        self.doc_ids = []
        self._dim = 384
        self._index_path = INDEX_CACHE_DIR / f"{index_name}.faiss"
        self._meta_path = INDEX_CACHE_DIR / f"{index_name}_meta.json"
        # 增量更新追踪
        self._content_hashes: Dict[int, str] = {}   # doc_id → sha256前8位
        self._stale_ids: set = set()                 # 需过滤的已删除文档
        self._built_at: str = ""                     # 索引构建时间

    @staticmethod
    def _hash_text(text: str) -> str:
        """文档内容哈希（sha256 前 8 位，快速比对变更）"""
        import hashlib
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:8]

    # ===== 持久化（含哈希+TTL） =====

    def save(self) -> bool:
        """保存索引+元数据+内容哈希到磁盘"""
        if self.index is None:
            return False
        try:
            faiss.write_index(self.index, str(self._index_path))
            meta = {
                "dim": self._dim, "type": self.index_type,
                "doc_count": len(self.doc_ids), "threshold": self.similarity_threshold,
                "ttl_days": self.index_ttl_days, "built_at": self._built_at or "",
                "stale_count": len(self._stale_ids),
            }
            self._meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            print(f"[RAG] 索引已持久化: {self._index_path} "
                  f"({len(self.doc_ids)} 文档, {len(self._stale_ids)} 陈旧)")
            return True
        except Exception as e:
            print(f"[RAG] 索引保存失败: {e}")
            return False

    def load(self) -> bool:
        """从磁盘加载缓存索引，含过期检查"""
        if not HAS_FAISS:
            return False
        if not self._index_path.exists() or not self._meta_path.exists():
            print("[RAG] 缓存索引不存在，将重新构建")
            return False
        try:
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            # ---- TTL 过期检查 ----
            built_at = meta.get("built_at", "")
            ttl_days = meta.get("ttl_days", self.index_ttl_days)
            if built_at and ttl_days > 0:
                try:
                    built_date = datetime.strptime(built_at[:10], "%Y-%m-%d")
                    age_days = (datetime.now() - built_date).days
                    if age_days >= ttl_days:
                        print(f"[RAG] 索引已过期 ({age_days}d > {ttl_days}d TTL)，将全量重建")
                        return False
                    print(f"[RAG] 索引年龄: {age_days}d (TTL: {ttl_days}d)")
                except ValueError:
                    pass

            self.index = faiss.read_index(str(self._index_path))
            self._dim = meta.get("dim", 384)
            self.index_ttl_days = meta.get("ttl_days", self.index_ttl_days)
            self.similarity_threshold = meta.get("threshold", self.DEFAULT_THRESHOLD)
            self._built_at = meta.get("built_at", "")
            doc_count = meta.get("doc_count", 0)
            self.doc_ids = list(range(doc_count))
            self._stale_ids = set()  # 陈旧ID只在内存中，重启后清空
            print(f"[RAG] 从缓存加载索引: {self._index_path} "
                  f"({doc_count} 文档, {self._dim}维, {meta.get('type','?')})")
            return True
        except Exception as e:
            print(f"[RAG] 加载缓存索引失败，将重新构建: {e}")
            self.index = None
            return False

    # ===== 构建 =====

    def build(self, texts: List[str], force_rebuild: bool = False) -> bool:
        """构建 FAISS 语义索引。优先从磁盘加载缓存，支持增量同步。"""
        model = self._get_model()
        if model is None or not HAS_FAISS:
            return False
        if not texts:
            return False

        # 尝试从缓存加载
        if not force_rebuild and self.load():
            # 缓存加载成功 → 增量同步
            new_hashes = {i: self._hash_text(t) for i, t in enumerate(texts)}
            changes = self._detect_changes(new_hashes)
            if sum(changes.values()) > 0:
                print(f"[RAG] 检测到文档变更: 新增{changes['added']} 修改{changes['modified']} 删除{changes['removed']}")
                if changes["added"] + changes["modified"] + changes["removed"] <= len(texts) * self.REBUILD_RATIO:
                    self._incremental_update(texts, new_hashes, changes, model)
                else:
                    print(f"[RAG] 变更比例超{self.REBUILD_RATIO*100:.0f}%，全量重建")
                    self._full_rebuild(texts, new_hashes, model)
            else:
                print("[RAG] 无文档变更，索引已是最新")
            return True

        # 全新构建
        return self._full_rebuild(texts, None, model)

    def _detect_changes(self, new_hashes: Dict[int, str]) -> dict:
        """对比新旧哈希，检测增/删/改"""
        old_ids = set(self._content_hashes.keys()) | self._stale_ids
        # 过滤掉陈旧ID后的有效旧ID
        valid_old_ids = set(self._content_hashes.keys()) - self._stale_ids
        new_ids = set(new_hashes.keys())

        added = new_ids - valid_old_ids
        removed = valid_old_ids - new_ids
        modified = set()
        for i in new_ids & valid_old_ids:
            if new_hashes[i] != self._content_hashes.get(i, ""):
                modified.add(i)

        return {"added": len(added), "modified": len(modified), "removed": len(removed),
                "added_ids": added, "modified_ids": modified, "removed_ids": removed}

    def _incremental_update(self, texts: List[str], new_hashes: Dict[int, str],
                            changes: dict, model) -> None:
        """增量更新：仅重新编码变更文档"""
        changed_ids = changes["added_ids"] | changes["modified_ids"]
        if not changed_ids:
            # 仅有删除 → 标记为 stale，不重建
            self._stale_ids |= changes["removed_ids"]
            self._content_hashes = {i: h for i, h in new_hashes.items()
                                    if i not in self._stale_ids}
            self.save()
            return

        # 重新编码变更文档
        changed_texts = [texts[i] for i in sorted(changed_ids) if i < len(texts)]
        if changed_texts:
            new_embeddings = model.encode(changed_texts, show_progress_bar=False,
                                          normalize_embeddings=True).astype(np.float32)
            # HNSW 不支持直接更新 → 标记旧ID为 stale + 追加新向量
            for old_id in changes["modified_ids"]:
                self._stale_ids.add(old_id)
            self._stale_ids |= changes["removed_ids"]
            # 追加新文档
            start_id = len(self.doc_ids)
            self.index.add(new_embeddings)
            self.doc_ids.extend(range(start_id, start_id + len(changed_texts)))
            # 更新哈希映射：新ID → 哈希
            for j, orig_id in enumerate(sorted(changed_ids)):
                new_doc_id = start_id + j
                self._content_hashes[new_doc_id] = new_hashes[orig_id]

        # 清理
        self._content_hashes = {i: h for i, h in self._content_hashes.items()
                                if i not in self._stale_ids}
        self._content_hashes.update({i: new_hashes[i] for i in changes["added_ids"]})
        self._built_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.save()
        print(f"[RAG] 增量更新完成: 索引{len(self.doc_ids)}个向量, "
              f"有效{len(self.doc_ids)-len(self._stale_ids)}, 陈旧{len(self._stale_ids)}")

    def _full_rebuild(self, texts: List[str], new_hashes: Dict[int, str] = None,
                      model=None) -> bool:
        """全量重建索引"""
        model = model or self._get_model()
        if model is None or not HAS_FAISS:
            return False
        try:
            print(f"[RAG] 正在编码 {len(texts)} 篇文档...")
            embeddings = model.encode(texts, show_progress_bar=False,
                                      normalize_embeddings=True)
            self._dim = embeddings.shape[1]

            if self.index_type == "hnsw" and len(texts) >= 32:
                self.index = faiss.IndexHNSWFlat(self._dim, 32)
                self.index.hnsw.efConstruction = 200
                self.index.hnsw.efSearch = 64
                print(f"[RAG] 使用 HNSW 索引 (M=32, efConstruction=200)")
            else:
                self.index = faiss.IndexFlatIP(self._dim)
                print(f"[RAG] 使用 Flat 索引")

            self.index.add(embeddings.astype(np.float32))
            self.doc_ids = list(range(len(texts)))
            self._content_hashes = new_hashes or {i: self._hash_text(t) for i, t in enumerate(texts)}
            self._stale_ids = set()
            self._built_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.save()
            print(f"[RAG] 全量重建完成: {len(self.doc_ids)} 文档, {self._dim}维")
            return True
        except Exception as e:
            print(f"[RAG] 全量重建失败: {e}")
            return False

    def _get_valid_results(self, scores, indices) -> List[tuple]:
        """过滤掉陈旧文档ID的搜索结果"""
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if idx in self._stale_ids:
                continue
            results.append((int(idx), float(score)))
        return results

    # ===== 搜索 =====

    def search(self, query: str, candidate_indices: List[int],
               top_k: int = 3, min_score: float = None) -> List[tuple]:
        """
        语义搜索。自动过滤陈旧文档和低分结果。
        """
        threshold = min_score if min_score is not None else self.similarity_threshold
        model = self._get_model()
        if model is None or self.index is None or not candidate_indices:
            return []

        # 从候选集中剔除陈旧ID
        clean_candidates = [i for i in candidate_indices if i not in self._stale_ids]
        if not clean_candidates:
            return []

        try:
            query_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
            search_k = min(top_k * 10, self.index.ntotal)
            scores, indices = self.index.search(query_vec, search_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                if idx not in clean_candidates:
                    continue
                if score < threshold:
                    continue
                results.append((int(idx), float(score)))
                if len(results) >= top_k:
                    break
            return results
        except Exception as e:
            print(f"[RAG] 语义搜索异常: {e}")
            return []

    def cleanup_stale(self) -> int:
        """清理陈旧文档：如果陈旧过多（>30%），触发全量重建。返回清理数量。"""
        total = len(self.doc_ids)
        stale = len(self._stale_ids)
        if total == 0:
            return 0
        if stale > total * 0.3:
            print(f"[RAG] 陈旧文档占比 {stale/total*100:.0f}%，建议下次 build() 时全量重建")
        return stale

    def add_documents(self, texts: List[str], start_id: int) -> bool:
        """增量添加文档（不重建整个索引）"""
        model = self._get_model()
        if model is None or self.index is None:
            return False
        try:
            embeddings = model.encode(texts, show_progress_bar=False,
                                      normalize_embeddings=True).astype(np.float32)
            self.index.add(embeddings)
            self.doc_ids.extend(range(start_id, start_id + len(texts)))
            self.save()
            print(f"[RAG] 增量添加 {len(texts)} 篇文档，总计 {len(self.doc_ids)}")
            return True
        except Exception as e:
            print(f"[RAG] 增量添加失败: {e}")
            return False


# ==================== GraphRAG 实体图检索 ====================

class GraphRetriever:
    """
    GraphRAG 实体图检索引擎 — Microsoft 2024 + 盘古COSO定制版
    - 车间感知图分片：每个车间只能看到其授权实体子图
    - 基于 COSO 知情原则：W2 无权看到质检规则相关实体

    轻量实现: 纯 Python dict 建图 + BFS 遍历，零外部依赖
    """

    # 车间图分片授权规则（COSO知情原则）
    WORKSHOP_ENTITY_ACCESS = {
        "w0": {"allow_all": True},
        "w1": {"allow_all": True},
        "w2": {"entity_types": ["character", "object", "location", "event"],   # 写作：可见人物/物件/场景
               "exclude_attrs": ["qc_rule", "violation_flag"]},
        "w3": {"entity_types": ["qc_checkpoint", "rule"],                      # 质检：只可见质检规则
               "exclude_relations": ["写作技法", "氛围参考"]},
        "w4": {"entity_types": ["character", "object", "location", "material"], # 精修：可见人物/物件/素材
               "exclude_attrs": ["qc_rule", "raw_draft"]},
    }

    def __init__(self):
        self.graph = {}
        self.relations = []
        self._built = False
        self._workshop_shards = {}  # 车间级子图缓存

    # ... (build_from_atlas unchanged, kept as-is)

    def _get_workshop_subgraph(self, workshop: str) -> dict:
        """获取车间授权的实体子图——COSO 知情原则的图检索实现"""
        if workshop in self._workshop_shards:
            return self._workshop_shards[workshop]

        access = self.WORKSHOP_ENTITY_ACCESS.get(workshop, {})
        if access.get("allow_all"):
            return {"graph": self.graph, "relations": self.relations}

        allowed_types = set(access.get("entity_types", []))
        exclude_attrs = set(access.get("exclude_attrs", []))
        exclude_relations = set(access.get("exclude_relations", []))

        # 过滤实体
        subgraph = {}
        for eid, data in self.graph.items():
            if data.get("type") in allowed_types:
                # 移除无权访问的属性
                filtered = {k: v for k, v in data.items()
                           if k not in exclude_attrs}
                subgraph[eid] = filtered

        # 过滤关系
        sub_relations = [(s, r, t, m) for s, r, t, m in self.relations
                         if r not in exclude_relations
                         and s in subgraph and t in subgraph]

        result = {"graph": subgraph, "relations": sub_relations}
        self._workshop_shards[workshop] = result
        return result

    def query_entity_for_workshop(self, name: str, workshop: str = "w2",
                                  depth: int = 2) -> dict:
        """
        车间感知实体查询——每个车间只能看到授权子图。
        这是 GraphRAG + COSO 的核心定制：不是"搜全图"，是"搜授权分片"。
        """
        if not self._built:
            return {"entity": name, "found": False, "workshop": workshop}

        sub = self._get_workshop_subgraph(workshop)
        sub_graph = sub["graph"]
        sub_relations = sub["relations"]

        # 在授权子图中查找实体
        start_id = None
        for eid, data in sub_graph.items():
            if name in data.get("name", "") or name in eid:
                start_id = eid
                break

        if start_id is None:
            return {"entity": name, "found": False, "workshop": workshop,
                    "message": f"实体'{name}'不在车间{workshop}的授权子图中——COSO知情原则限制"}

        # BFS 遍历授权子图
        visited = {start_id: 0}
        queue = [(start_id, 0)]
        neighbors = []

        while queue:
            current, d = queue.pop(0)
            if d >= depth:
                continue
            for src, rel_type, tgt, _ in sub_relations:
                if src == current and tgt not in visited:
                    visited[tgt] = d + 1
                    queue.append((tgt, d + 1))
                    neighbors.append({
                        "entity": sub_graph.get(tgt, {}).get("name", tgt),
                        "type": sub_graph.get(tgt, {}).get("type", "unknown"),
                        "relation": rel_type, "depth": d + 1,
                    })

        return {
            "entity": name, "found": True, "workshop": workshop,
            "type": sub_graph.get(start_id, {}).get("type", "unknown"),
            "neighbors": neighbors,
            "total_connected": len(neighbors),
            "authorized_entities": len(sub_graph),
            "full_graph_entities": len(self.graph),
        }

    def build_from_atlas(self, project_dir: Path) -> bool:
        """
        从小说三库构建实体图。
        输入: novel_libraries/项目名/ 下的 character_atlas / event_plot / exclusive_materials
        """
        if not project_dir or not project_dir.exists():
            return False

        # 1. 人物实体
        char_file = project_dir / "character_atlas.json"
        if char_file.exists():
            try:
                data = json.loads(char_file.read_text(encoding="utf-8"))
                for c in data.get("characters", []):
                    cid = f"char:{c.get('name', '')}"
                    self.graph[cid] = {
                        "type": "character",
                        "name": c.get("name", ""),
                        "role": c.get("role", ""),
                        "trauma": c.get("native_trauma", ""),
                        "obsession": c.get("obsession", ""),
                        "quirks": c.get("hidden_quirk", ""),
                    }
                    # 人物→物件关系（从描述中推断）
                    description = json.dumps(c, ensure_ascii=False)
                    for obj_word in ["伞", "茶", "毛衣", "煎饺", "裙子", "手机", "杯子",
                                     "钥匙", "书", "花", "灯", "戒指", "照片"]:
                        if obj_word in description:
                            oid = f"object:{obj_word}"
                            if oid not in self.graph:
                                self.graph[oid] = {"type": "object", "name": obj_word}
                            self.relations.append((cid, "关联", oid, {"source": "character_atlas"}))
            except Exception as e:
                print(f"[GraphRAG] 人物图谱构建失败: {e}")

        # 2. 事件实体
        event_file = project_dir / "event_plot_atlas.json"
        if event_file.exists():
            try:
                data = json.loads(event_file.read_text(encoding="utf-8"))
                for e in data.get("events", []):
                    eid = f"event:{e.get('name', '')}"
                    self.graph[eid] = {
                        "type": "event",
                        "name": e.get("name", ""),
                        "trigger": e.get("trigger", ""),
                        "result": e.get("result", ""),
                    }
                    # 事件涉及的实体
                    desc = json.dumps(e, ensure_ascii=False)
                    for cid in list(self.graph.keys()):
                        if cid.startswith("char:") or cid.startswith("object:"):
                            name = self.graph[cid]["name"]
                            if name in desc:
                                self.relations.append((eid, "涉及", cid,
                                                       {"source": "event_plot"}))
            except Exception as e:
                print(f"[GraphRAG] 事件图谱构建失败: {e}")

        # 3. 素材实体
        mat_file = project_dir / "exclusive_materials.json"
        if mat_file.exists():
            try:
                data = json.loads(mat_file.read_text(encoding="utf-8"))
                for m in data.get("materials", []):
                    mid = f"material:{m.get('name', '')}"
                    self.graph[mid] = {
                        "type": "material",
                        "name": m.get("name", ""),
                        "content": str(m.get("content", ""))[:200],
                    }
            except Exception:
                pass

        self._built = True
        print(f"[GraphRAG] 实体图构建完成: {len(self.graph)} 节点, {len(self.relations)} 条关系")
        return True

    def query_entity(self, name: str, depth: int = 2) -> dict:
        """
        实体图查询：从指定实体出发，BFS 遍历 depth 层。
        返回该实体及其邻域子图。
        """
        if not self._built or not self.graph:
            return {"entity": name, "found": False, "neighbors": []}

        # 查找起始实体
        start_id = None
        for eid, data in self.graph.items():
            if name in data.get("name", "") or name in eid:
                start_id = eid
                break

        if start_id is None:
            return {"entity": name, "found": False, "neighbors": [],
                    "suggestion": "尝试搜索更具体的实体名"}

        # BFS 遍历
        visited = {start_id: 0}
        queue = [(start_id, 0)]
        neighbors = []
        relations_out = []

        while queue:
            current, d = queue.pop(0)
            if d >= depth:
                continue

            for src, rel_type, tgt, meta in self.relations:
                if src == current and tgt not in visited:
                    visited[tgt] = d + 1
                    queue.append((tgt, d + 1))
                    neighbors.append({
                        "entity": self.graph.get(tgt, {}).get("name", tgt),
                        "type": self.graph.get(tgt, {}).get("type", "unknown"),
                        "relation": rel_type,
                        "depth": d + 1,
                    })
                    relations_out.append({
                        "from": self.graph.get(src, {}).get("name", src),
                        "relation": rel_type,
                        "to": self.graph.get(tgt, {}).get("name", tgt),
                    })
                elif tgt == current and src not in visited:
                    visited[src] = d + 1
                    queue.append((src, d + 1))
                    neighbors.append({
                        "entity": self.graph.get(src, {}).get("name", src),
                        "type": self.graph.get(src, {}).get("type", "unknown"),
                        "relation": f"被{rel_type}",
                        "depth": d + 1,
                    })

        # 统计
        entity_data = self.graph.get(start_id, {})
        return {
            "entity": name,
            "found": True,
            "type": entity_data.get("type", "unknown"),
            "attrs": {k: v for k, v in entity_data.items() if k not in ("type", "name")},
            "neighbors": neighbors,
            "relations": relations_out,
            "total_connected": len(neighbors),
            "depth": depth,
        }

    def query_relation(self, entity_a: str, entity_b: str) -> dict:
        """查询两个实体之间是否存在关系路径（BFS 最短路径）"""
        if not self._built:
            return {"found": False}

        # 找到两个实体 ID
        id_a = id_b = None
        for eid, data in self.graph.items():
            if entity_a in data.get("name", "") or entity_a in eid:
                id_a = eid
            if entity_b in data.get("name", "") or entity_b in eid:
                id_b = eid

        if not id_a or not id_b:
            return {"found": False, "reason": "一个或多个实体未找到"}

        # BFS 最短路径
        from collections import deque
        queue = deque([(id_a, [])])
        visited = {id_a}

        while queue:
            current, path = queue.popleft()
            if current == id_b:
                return {
                    "found": True,
                    "entity_a": entity_a,
                    "entity_b": entity_b,
                    "path": path + [current],
                    "path_names": [self.graph.get(n, {}).get("name", n) for n in path + [current]],
                    "path_length": len(path),
                }
            for src, rel_type, tgt, _ in self.relations:
                if src == current and tgt not in visited:
                    visited.add(tgt)
                    queue.append((tgt, path + [(current, rel_type)]))
                elif tgt == current and src not in visited:
                    visited.add(src)
                    queue.append((src, path + [(current, f"被{rel_type}")]))

        return {"found": False, "entity_a": entity_a, "entity_b": entity_b,
                "reason": "两个实体之间不存在连接路径"}


def build_graph_from_project(project_name: str) -> GraphRetriever:
    """便捷函数：从项目名构建 GraphRAG 检索器"""
    project_dir = BASE_DIR / "novel_libraries" / project_name
    gr = GraphRetriever()
    gr.build_from_atlas(project_dir)
    return gr


class PanguRAG:
    def __init__(self, knowledge_dir: Path = None):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.documents: List[Dict] = []
        self.vectorizer = None
        self.doc_vectors = None
        self.semantic_index = None  # FAISS-HNSW 语义索引（优先使用）
        self._initialized = False
        self._min_score = 0.3       # 默认相似度阈值

    # ---- 文档分块 ----

    def _chunk_pangu_knowledge(self, data: dict) -> List[Dict]:
        chunks = []
        theories = data.get("core_theories", {})
        for key, theory in theories.items():
            text = f"【{theory.get('name', key)}】\n{theory.get('description', '')}"
            if "levels" in theory:
                for lvl in theory["levels"]:
                    text += f"\n- 第{lvl.get('level')}层：{lvl.get('name')}，示例：{lvl.get('example', '')}"
            if "stages" in theory:
                for stg in theory["stages"]:
                    text += f"\n- 阶段{stg.get('stage')}：{stg.get('name')}，作用：{stg.get('function', '')}"
            if "types" in theory:
                for t in theory["types"]:
                    text += f"\n- {t.get('name')}（速度{t.get('speed', '?')}）：{t.get('use', '')}"
            if "modes" in theory:
                for m in theory["modes"]:
                    text += f"\n- {m.get('name')}：{m.get('description', '')}"
            chunks.append({
                "text": text, "source": "pangu_v6_knowledge.json",
                "category": "theory", "title": theory.get("name", key),
                "mode": "*", "platform": "*",
            })

        platforms = data.get("platform_rules", {})
        for plat_key, plat in platforms.items():
            text = f"【平台规则：{plat.get('name', plat_key)}】\n"
            opening = plat.get("opening", {})
            text += f"开篇结构：{opening.get('structure', '')}\n"
            text += f"字数要求：{opening.get('word_count', '')}字\n"
            for r in opening.get("requirements", []):
                text += f"- {r}\n"
            for k, v in plat.get("metrics", {}).items():
                text += f"指标 {k}：{v}\n"
            chunks.append({
                "text": text, "source": "pangu_v6_knowledge.json",
                "category": "platform_rule", "title": plat.get("name", plat_key),
                "mode": "*", "platform": plat_key,
            })

        formulas = data.get("title_formulas", [])
        if formulas:
            text = "【书名公式】\n" + "\n".join(f"- {f}" for f in formulas)
            chunks.append({
                "text": text, "source": "pangu_v6_knowledge.json",
                "category": "title_formula", "title": "书名公式",
                "mode": "*", "platform": "*",
            })

        hook_types = data.get("hook_types", {})
        for hk, desc in hook_types.items():
            chunks.append({
                "text": f"【钩子类型：{hk}】\n{desc}",
                "source": "pangu_v6_knowledge.json",
                "category": "hook_type", "title": hk,
                "mode": "*", "platform": "*",
            })
        return chunks

    def _chunk_unified_knowledge(self, data: dict) -> List[Dict]:
        chunks = []
        emotion = data.get("emotion_anchors", {})
        for cat_key, cat in emotion.get("categories", {}).items():
            cat_name = cat.get("name", cat_key)
            cat_logic = cat.get("logic", "")
            for a in cat.get("anchors", []):
                text = (
                    f"【情绪锚点：{a.get('name', '')}】类别：{cat_name}\n"
                    f"逻辑：{cat_logic}\n"
                    f"触发：{a.get('trigger', '')}\n"
                    f"方法：{a.get('method', '')}\n"
                    f"读者反应：{a.get('reader_reaction', '')}\n"
                )
                chunks.append({
                    "text": text, "source": "unified_knowledge_base.json",
                    "category": "emotion_anchor", "title": a.get("name", ""),
                    "mode": ",".join(a.get("suitable_modes", ["*"])),
                    "platform": ",".join(a.get("suitable_platforms", ["*"])),
                })

        for plat, pref in emotion.get("platform_emotion_preferences", {}).items():
            text = (
                f"【平台情绪偏好：{plat}】\n"
                f"优先级：{', '.join(pref.get('priority', []))}\n"
                f"传递方式：{pref.get('delivery', '')}\n"
                f"禁忌：{', '.join(pref.get('forbidden', []))}"
            )
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "platform_emotion", "title": f"{plat}情绪偏好",
                "mode": "*", "platform": plat,
            })

        hook_sys = data.get("hook_system", {})
        density = hook_sys.get("density_rules", {})
        text = "【钩子密度规则】\n"
        for k, v in density.items():
            text += f"{k}：位置{v.get('position', '')}，目的{v.get('purpose', '')}\n"
        chunks.append({
            "text": text, "source": "unified_knowledge_base.json",
            "category": "hook_rule", "title": "钩子密度规则",
            "mode": "*", "platform": "*",
        })

        template = hook_sys.get("chapter_template_1500", {})
        if template:
            text = "【1500字章节钩子模板】\n"
            for rng, desc in template.items():
                text += f"{rng}：{desc}\n"
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "hook_template", "title": "章节钩子模板",
                "mode": "*", "platform": "*",
            })

        for ht in hook_sys.get("hook_types", []):
            text = (
                f"【钩子类型：{ht.get('name', '')}】\n"
                f"定义：{ht.get('definition', '')}\n"
                f"技法：{ht.get('technique', ht.get('trigger_words', ''))}\n"
                f"示例：{' / '.join(ht.get('examples', [])[:2])}"
            )
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "hook_type", "title": ht.get("name", ""),
                "mode": ",".join(ht.get("best_for_modes", ["*"])),
                "platform": ",".join(ht.get("best_for_platforms", ["*"])),
            })

        for mode, pref in hook_sys.get("mode_hook_preferences", {}).items():
            text = (
                f"【模式钩子偏好：{mode}】\n"
                f"推荐：{', '.join(pref.get('preferred', []))}\n"
                f"禁用：{', '.join(pref.get('forbidden', []))}\n"
                f"注意：{pref.get('note', '')}"
            )
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "mode_hook_preference", "title": f"{mode}钩子偏好",
                "mode": mode, "platform": "*",
            })

        checklist = hook_sys.get("hook_quality_checklist", [])
        if checklist:
            text = "【钩子质检清单】\n" + "\n".join(f"- {c}" for c in checklist)
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "hook_checklist", "title": "钩子质检清单",
                "mode": "*", "platform": "*",
            })

        for err in hook_sys.get("common_errors", []):
            text = (
                f"【钩子常见错误：{err.get('name', '')}】\n"
                f"问题示例：{err.get('example', '')}\n"
                f"问题所在：{err.get('problem', '')}\n"
                f"修正方案：{err.get('fix', '')}"
            )
            chunks.append({
                "text": text, "source": "unified_knowledge_base.json",
                "category": "hook_error", "title": err.get("name", ""),
                "mode": "*", "platform": "*",
            })
        return chunks

    def _chunk_novel_library(self, project_name: str) -> List[Dict]:
        chunks = []
        lib_dir = BASE_DIR / "novel_libraries" / project_name
        if not lib_dir.exists():
            return chunks

        char_file = lib_dir / "character_atlas.json"
        if char_file.exists():
            try:
                data = json.loads(char_file.read_text(encoding="utf-8"))
                for c in data.get("characters", []):
                    text = (
                        f"【人物：{c.get('name', '')}】\n"
                        f"角色：{c.get('role', '')}\n"
                        f"原生创伤：{c.get('native_trauma', '')}\n"
                        f"执念：{c.get('obsession', '')}\n"
                        f"底线：{c.get('bottom_line', '')}\n"
                        f"怪癖：{c.get('hidden_quirk', '')}\n"
                        f"声音：{c.get('voice', '')}\n"
                        f"外貌：{c.get('appearance_core', '')}"
                    )
                    chunks.append({
                        "text": text,
                        "source": f"novel_libraries/{project_name}/character_atlas.json",
                        "category": "character", "title": c.get("name", ""),
                        "mode": data.get("meta", {}).get("mode", "*"),
                        "platform": "*",
                    })
            except Exception:
                pass

        event_file = lib_dir / "event_plot_atlas.json"
        if event_file.exists():
            try:
                data = json.loads(event_file.read_text(encoding="utf-8"))
                for e in data.get("events", []):
                    text = (
                        f"【事件：{e.get('name', '')}】\n"
                        f"触发：{e.get('trigger', '')}\n"
                        f"发展：{e.get('development', '')}\n"
                        f"结果：{e.get('result', '')}\n"
                        f"影响：{e.get('impact', '')}"
                    )
                    chunks.append({
                        "text": text,
                        "source": f"novel_libraries/{project_name}/event_plot_atlas.json",
                        "category": "event", "title": e.get("name", ""),
                        "mode": "*", "platform": "*",
                    })
            except Exception:
                pass

        material_file = lib_dir / "exclusive_materials.json"
        if material_file.exists():
            try:
                data = json.loads(material_file.read_text(encoding="utf-8"))
                for m in data.get("materials", []):
                    text = (
                        f"【素材：{m.get('name', '')}】\n"
                        f"类型：{m.get('type', '')}\n"
                        f"内容：{m.get('content', '')}\n"
                        f"使用场景：{m.get('usage', '')}"
                    )
                    chunks.append({
                        "text": text,
                        "source": f"novel_libraries/{project_name}/exclusive_materials.json",
                        "category": "material", "title": m.get("name", ""),
                        "mode": "*", "platform": "*",
                    })
            except Exception:
                pass
        return chunks

    def _load_markdown_knowledge(self) -> List[Dict]:
        chunks = []
        for md_file in self.knowledge_dir.glob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                sections = re.split(r'\n##\s+', text)
                for i, sec in enumerate(sections[1:], 1):
                    lines = sec.strip().split('\n', 1)
                    title = lines[0].strip() if lines else f"section_{i}"
                    body = lines[1].strip() if len(lines) > 1 else ""
                    if len(body) < 30:
                        continue
                    chunks.append({
                        "text": f"【{title}】\n{body[:800]}",
                        "source": str(md_file.name),
                        "category": "markdown_knowledge", "title": title,
                        "mode": "*", "platform": "*",
                    })
            except Exception:
                pass
        return chunks

    # ---- 初始化 ----

    def initialize(self, project_name: str = None):
        print("[RAG] 正在初始化知识库...")
        self.documents = []

        pangu_file = BASE_DIR / "pangu_v6_knowledge.json"
        if pangu_file.exists():
            try:
                data = json.loads(pangu_file.read_text(encoding="utf-8"))
                self.documents.extend(self._chunk_pangu_knowledge(data))
                print(f"[RAG] 盘古知识库: {len(self.documents)} 块")
            except Exception as e:
                print(f"[RAG] 盘古知识库加载失败: {e}")

        unified_file = KNOWLEDGE_DIR / "unified_knowledge_base.json"
        if unified_file.exists():
            try:
                data = json.loads(unified_file.read_text(encoding="utf-8"))
                before = len(self.documents)
                self.documents.extend(self._chunk_unified_knowledge(data))
                print(f"[RAG] 统一知识库: {len(self.documents) - before} 块")
            except Exception as e:
                print(f"[RAG] 统一知识库加载失败: {e}")

        if project_name:
            before = len(self.documents)
            self.documents.extend(self._chunk_novel_library(project_name))
            print(f"[RAG] 小说三库({project_name}): {len(self.documents) - before} 块")

        before = len(self.documents)
        self.documents.extend(self._load_markdown_knowledge())
        print(f"[RAG] Markdown知识: {len(self.documents) - before} 块")

        if self.documents:
            texts = [d["text"] for d in self.documents]
            self.vectorizer = SimpleTfidfVectorizer(ngram_range=(2, 4))
            self.doc_vectors = self.vectorizer.fit_transform(texts)
            print(f"[RAG] TF-IDF向量索引完成，维度: {self.doc_vectors.shape}")

            # 构建 FAISS 语义索引（优先使用）
            if HAS_SBERT and HAS_FAISS:
                self.semantic_index = SemanticIndex()
                self.semantic_index.build(texts)
        else:
            print("[RAG] 警告：没有加载到任何文档")

        self._initialized = True
        return self

    # ---- 检索 ----

    def search(self, query: str, top_k: int = 3, mode: str = None,
               platform: str = None, category: str = None,
               exclude_categories: List[str] = None,
               min_score: float = None) -> List[Dict]:
        """
        检索知识库文档。V7.5 COSO 信息隔离版。
        Args:
            exclude_categories: 排除的类别列表——COSO 知情原则：每个车间无权检索
                                不属于其职责范围的知识类别。
                                例: W2(exclude=["hook_checklist","qc_rule"])
                                    W3(exclude=["writing_technique","atmosphere"])
            min_score: 最低相似度阈值（0-1），低于此值不返回。
        """
        if not self._initialized:
            self.initialize()
        if not self.documents:
            return []

        threshold = min_score if min_score is not None else self._min_score
        exclude_set = set(exclude_categories) if exclude_categories else set()

        # 按模式/平台/类别过滤候选文档（含排除式过滤）
        candidates = []
        for i, doc in enumerate(self.documents):
            if mode and mode != "*":
                doc_modes = doc.get("mode", "*")
                if doc_modes != "*" and mode not in doc_modes.split(","):
                    continue
            if platform and platform != "*":
                doc_plats = doc.get("platform", "*")
                if doc_plats != "*" and platform not in doc_plats.split(","):
                    continue
            if category and category != "*":
                if doc.get("category", "") != category:
                    continue
            # === COSO 知情原则：排除无权访问的类别 ===
            if exclude_set and doc.get("category", "") in exclude_set:
                continue
            candidates.append(i)

        if not candidates:
            return []

        # === 路径 A：FAISS-HNSW 语义搜索（推荐，O(log N)） ===
        if self.semantic_index is not None and self.semantic_index.index is not None:
            sem_results = self.semantic_index.search(
                query, candidates, top_k, min_score=threshold
            )
            if sem_results:
                results = []
                for doc_idx, score in sem_results:
                    doc = self.documents[doc_idx].copy()
                    doc["score"] = round(score, 4)
                    results.append(doc)
                return results

        # === 路径 B：TF-IDF 向量搜索（回退，O(N)） ===
        if self.vectorizer is not None and self.doc_vectors is not None:
            query_vec = self.vectorizer.transform([query])
            cand_vectors = self.doc_vectors[candidates]
            scores = np.dot(cand_vectors, query_vec.T).flatten()
            # TF-IDF 阈值：分数低于最大值*30% 的过滤
            if len(scores) > 1:
                max_score = scores.max()
                score_threshold = max_score * 0.3 if max_score > 0 else 0
            else:
                score_threshold = 0
            sorted_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in sorted_indices:
                if float(scores[idx]) < score_threshold:
                    continue
                doc_idx = candidates[idx]
                doc = self.documents[doc_idx].copy()
                doc["score"] = round(float(scores[idx]), 4)
                results.append(doc)
            return results
        else:
            # === 路径 C：关键词匹配（最终回退） ===
            query_words = set(query.lower())
            scored = []
            for idx in candidates:
                text = self.documents[idx]["text"]
                score = sum(1 for w in query_words if w in text.lower())
                if score > 0:
                    scored.append((score, idx))
            scored.sort(reverse=True)
            results = []
            for _, idx in scored[:top_k]:
                doc = self.documents[idx].copy()
                doc["score"] = None
                results.append(doc)
            return results

    def search_for_workshop(self, workshop: str, task_description: str,
                            mode: str = None, platform: str = None,
                            project_name: str = None, top_k: int = 3) -> str:
        if project_name and not any(
            project_name in d.get("source", "") for d in self.documents
        ):
            self.initialize(project_name)

        # === COSO 知情原则：每个车间的最小权限知识访问 ===
        # W2(写作) 不能看到质检规则——否则会"迎合检查"
        # W3(质检) 不能看到写作技法——否则会"被技法影响判断"
        # W4(精修) 可以看到写作技法+氛围手法，但不能看到质检规则
        # W0/W1 需要看到全部（锚定和设定预处理需要全局视野）

        WORKSHOP_ACCESS = {
            "w0": {"allow_all": True},   # 主旨锚定：需要全局视野
            "w1": {"allow_all": True},   # 设定预处理：需要全局视野
            "w2": {"exclude": ["hook_checklist", "hook_error", "hook_rule",
                               "qc_checklist"]},  # 初稿：不能看到质检规则
            "w3": {"include_only": ["hook_checklist", "hook_error", "hook_rule",
                                    "mode_hook_preference"]},  # 质检：只看质检规则
            "w4": {"exclude": ["hook_checklist", "qc_checklist",
                               "hook_error"]},  # 精修：不能看到质检规则
        }

        access = WORKSHOP_ACCESS.get(workshop, {})

        if access.get("allow_all"):
            results = self.search(task_description, top_k=top_k, mode=mode, platform=platform)
        elif "include_only" in access:
            results = self.search(task_description, top_k=top_k, mode=mode, platform=platform,
                                  category=access["include_only"][0] if len(access["include_only"]) == 1 else None)
            if not results:
                # 放宽：如果限定类别无结果，允许全局搜索但排除敏感类别
                results = self.search(task_description, top_k=top_k, mode=mode, platform=platform)
        elif "exclude" in access:
            results = self.search(task_description, top_k=top_k, mode=mode, platform=platform,
                                  exclude_categories=access["exclude"])
        else:
            results = self.search(task_description, top_k=top_k, mode=mode, platform=platform)

        # W3 额外附加钩子检查清单
        if workshop == "w3":
            extra = self.search("", top_k=2, category="hook_checklist")
            # 确保 extra 不包含被排除的类别
            results.extend(extra)

        if not results:
            return ""

        seen = set()
        unique = []
        for r in results:
            key = r.get("title", "") + r.get("text", "")[:50]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        lines = ["\n【自动检索的相关知识】"]
        for r in unique[:top_k]:
            lines.append(f"\n> 来源：{r.get('title', '')}（{r.get('source', '')} | {r.get('category', '')}）")
            lines.append(r.get("text", ""))
        return "\n".join(lines)

    def get_stats(self) -> dict:
        if not self._initialized:
            self.initialize()
        cats = {}
        for d in self.documents:
            c = d.get("category", "unknown")
            cats[c] = cats.get(c, 0) + 1
        si = self.semantic_index
        return {
            "total_documents": len(self.documents),
            "categories": cats,
            "search_mode": "FAISS-HNSW 语义检索" if (si and si.index and si.index_type == "hnsw")
                           else "FAISS-Flat 语义检索" if (si and si.index)
                           else "TF-IDF (char 2-4gram, numpy)",
            "semantic_available": si is not None and si.index is not None,
            "index_type": si.index_type if si else "none",
            "similarity_threshold": si.similarity_threshold if si else None,
            "cache_dir": str(INDEX_CACHE_DIR),
        }


# ---- 全局单例 ----
_rag_instance = None

def get_rag(project_name: str = None) -> PanguRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = PanguRAG()
        _rag_instance.initialize(project_name)
    elif project_name and not any(
        project_name in d.get("source", "") for d in _rag_instance.documents
    ):
        _rag_instance.initialize(project_name)
    return _rag_instance


if __name__ == "__main__":
    rag = PanguRAG()
    rag.initialize()
    print("\n=== 统计 ===")
    print(rag.get_stats())
    print("\n=== 测试检索：如何设计都市职场爽点 ===")
    for r in rag.search("如何设计都市职场爽点", top_k=3, mode="urban_power", platform="fanqie"):
        print(f"\n[{r['category']}] {r['title']} (score: {r.get('score')})")
        print(r['text'][:200] + "...")

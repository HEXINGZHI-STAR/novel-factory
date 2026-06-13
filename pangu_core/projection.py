#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI 五路投影模块 (Pangu Projection)

受 webnovel-writer 的 vector_projection_writer + event_projection_router 启发，
在章节写作完成后，自动将内容投影到5个知识维度：

1. STATE  → state.json（角色状态/伏笔/设定更新）
2. VECTOR → FAISS向量索引（语义检索用）
3. MEMORY → memory_bank.json（长期记忆存储）
4. INDEX  → 关键词索引（BM25/TF-IDF检索用）
5. EVENT  → 事件日志（结构化事件链，供后续查询）

核心设计：
  - 写作后自动触发（WorkflowEngine.run()末尾调用）
  - 每个投影路独立降级（某路失败不影响其他）
  - 投影结果持久化到 .projections/ 目录

使用方式：
  from pangu_core.projection import run_projections

  result = run_projections(
      project_dir="projects/深渊猎人",
      chapter_num=5,
      chapter_content="...",
      chapter_task="...",
  )
"""

import json
import re
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# 事件路由表（从webnovel移植+扩展）
# ============================================================

EVENT_ROUTE_TABLE = {
    "character_state_changed": ["state", "memory", "vector"],
    "power_breakthrough": ["state", "memory", "vector"],
    "relationship_changed": ["index", "vector"],
    "world_rule_revealed": ["memory", "vector"],
    "world_rule_broken": ["memory", "vector"],
    "open_loop_created": ["memory"],
    "open_loop_closed": ["memory"],
    "promise_created": ["memory"],
    "promise_paid_off": ["memory"],
    "artifact_obtained": ["index", "vector"],
    "location_changed": ["state", "index"],
    "knowledge_revealed": ["memory", "vector"],
    "combat_occurred": ["vector"],
    "emotional_peak": ["memory", "vector"],
}

# 事件提取关键词映射
EVENT_KEYWORDS = {
    "character_state_changed": ["受伤", "昏迷", "觉醒", "升级", "突破", "变化", "状态", "蜕变", "变异", "恢复"],
    "power_breakthrough": ["突破", "升级", "觉醒", "领悟", "修炼成功", "进化", "提升", "变异"],
    "relationship_changed": ["背叛", "联盟", "结盟", "对立", "合作", "和解", "分手", "告白", "结拜"],
    "world_rule_revealed": ["规则", "法则", "定律", "禁忌", "秘密", "真相", "规律", "机制"],
    "world_rule_broken": ["违反", "打破", "违背", "突破极限", "超越"],
    "artifact_obtained": ["获得", "得到", "捡到", "夺取", "继承", "赠予"],
    "location_changed": ["前往", "到达", "离开", "传送", "进入", "逃出"],
    "combat_occurred": ["战斗", "对决", "交锋", "厮杀", "交手", "攻击", "防御"],
    "emotional_peak": ["愤怒", "绝望", "狂喜", "悲痛", "震惊", "恐惧", "决心"],
}


# ============================================================
# 核心投影函数
# ============================================================

def run_projections(
    project_dir: str,
    chapter_num: int,
    chapter_content: str,
    chapter_task: str = "",
    mode: str = "general",
) -> Dict[str, Any]:
    """
    运行五路投影：章节写作完成后，将内容投影到5个知识维度。

    Args:
        project_dir: 项目目录
        chapter_num: 章节号
        chapter_content: 章节内容
        chapter_task: 章节任务
        mode: 写作模式

    Returns:
        Dict: 各路投影的结果摘要
    """
    proj_dir = Path(project_dir) / ".projections"
    proj_dir.mkdir(exist_ok=True)

    results = {}

    # 1. STATE投影：提取角色状态变更，更新state.json
    results["state"] = _project_state(project_dir, chapter_num, chapter_content, mode)

    # 2. VECTOR投影：将章节分块存入向量索引
    results["vector"] = _project_vector(project_dir, chapter_num, chapter_content)

    # 3. MEMORY投影：提取关键信息到记忆银行
    results["memory"] = _project_memory(project_dir, chapter_num, chapter_content, chapter_task)

    # 4. INDEX投影：构建关键词索引
    results["index"] = _project_index(proj_dir, chapter_num, chapter_content, chapter_task)

    # 5. EVENT投影：提取结构化事件
    results["event"] = _project_event(proj_dir, chapter_num, chapter_content, mode)

    # 持久化投影结果摘要
    summary_path = proj_dir / f"ch{chapter_num:04d}_projection.json"
    try:
        summary = {
            "chapter": chapter_num,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(chapter_content),
            "results": {k: {"applied": v.get("applied", False), "detail": str(v.get("detail", ""))[:100]}
                        for k, v in results.items()},
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"投影摘要持久化失败: {e}")

    applied_count = sum(1 for v in results.values() if v.get("applied"))
    logger.info(f"五路投影完成: {applied_count}/5路成功 (第{chapter_num}章)")

    return results


# ============================================================
# 各路投影实现
# ============================================================

def _project_state(project_dir: str, chapter_num: int, content: str, mode: str) -> Dict:
    """STATE投影：从章节内容提取角色状态变更，更新state.json"""
    try:
        state_path = Path(project_dir) / "state.json"
        if not state_path.exists():
            return {"applied": False, "detail": "state.json不存在"}

        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        # 提取角色状态变更（简单关键词匹配）
        characters = state.get("characters", {})
        updated_chars = []

        for char_name, char_data in characters.items():
            if not isinstance(char_data, dict):
                continue
            # 检查角色名是否出现在章节中
            if char_name in content:
                # 更新"最后出现章节"
                char_data["last_chapter"] = chapter_num
                updated_chars.append(char_name)

        # 更新chapter_meta
        chapter_meta = state.get("chapter_meta", {})
        chapter_meta[str(chapter_num)] = {
            "word_count": len(content),
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
        }
        state["chapter_meta"] = chapter_meta

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        return {"applied": True, "detail": f"更新了{len(updated_chars)}个角色状态"}

    except Exception as e:
        logger.warning(f"STATE投影失败: {e}")
        return {"applied": False, "detail": str(e)[:100]}


def _project_vector(project_dir: str, chapter_num: int, content: str) -> Dict:
    """VECTOR投影：将章节分块，尝试添加到RAG向量索引"""
    try:
        # 尝试使用盘古RAG引擎
        import sys
        backend_dir = str(Path(project_dir).parent.parent / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from rag_engine import PanguRAG
        rag = PanguRAG(Path(project_dir))
        chunks = _split_into_chunks(content, chapter_num)
        added = 0
        for chunk in chunks:
            rag.add_chunk(
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                metadata={"chapter": chapter_num, "type": chunk["chunk_type"]},
            )
            added += 1

        return {"applied": True, "detail": f"添加{added}个向量块"}

    except ImportError:
        # RAG引擎不可用（rag_engine.py 不存在），降级到文件存储
        logger.warning("[Projection] VECTOR投影降级：rag_engine.py 不存在，使用JSON文件存储")
        return _project_vector_fallback(project_dir, chapter_num, content)
    except Exception as e:
        logger.warning(f"VECTOR投影失败: {e}")
        return {"applied": False, "detail": str(e)[:100]}


def _project_vector_fallback(project_dir: str, chapter_num: int, content: str) -> Dict:
    """VECTOR投影降级：分块存到JSON文件"""
    try:
        proj_dir = Path(project_dir) / ".projections"
        proj_dir.mkdir(exist_ok=True)

        chunks = _split_into_chunks(content, chapter_num)
        chunks_path = proj_dir / f"ch{chapter_num:04d}_chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        return {"applied": True, "detail": f"降级存储{len(chunks)}个块到文件"}
    except Exception as e:
        return {"applied": False, "detail": str(e)[:100]}


def _project_memory(project_dir: str, chapter_num: int, content: str, chapter_task: str) -> Dict:
    """MEMORY投影：提取关键信息到记忆银行"""
    try:
        # 使用盘古的memory_bank
        memory_path = Path(project_dir) / "memory_bank.json"
        if not memory_path.exists():
            return {"applied": False, "detail": "memory_bank.json不存在"}

        with open(memory_path, "r", encoding="utf-8") as f:
            memory = json.load(f)

        # 提取摘要（取首段和末段）
        paragraphs = [p.strip() for p in content.split("\n") if p.strip() and len(p.strip()) > 20]
        summary_parts = []
        if paragraphs:
            summary_parts.append(paragraphs[0][:200])
            if len(paragraphs) > 1:
                summary_parts.append(paragraphs[-1][:200])

        chapter_summaries = memory.get("chapter_summaries", {})
        chapter_summaries[str(chapter_num)] = {
            "task": chapter_task[:100],
            "summary": " ... ".join(summary_parts)[:500],
            "word_count": len(content),
            "timestamp": datetime.now().isoformat(),
        }
        memory["chapter_summaries"] = chapter_summaries

        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

        return {"applied": True, "detail": f"更新第{chapter_num}章摘要"}

    except Exception as e:
        logger.warning(f"MEMORY投影失败: {e}")
        return {"applied": False, "detail": str(e)[:100]}


def _project_index(proj_dir: Path, chapter_num: int, content: str, chapter_task: str) -> Dict:
    """INDEX投影：构建关键词索引（供BM25/TF-IDF检索用）"""
    try:
        # 提取关键词（简单分词）
        keywords = _extract_keywords(content)

        # 保存索引
        index_path = proj_dir / f"ch{chapter_num:04d}_index.json"
        index_data = {
            "chapter": chapter_num,
            "keywords": keywords[:50],
            "task_keywords": _extract_keywords(chapter_task)[:10],
            "content_hash": hashlib.md5(content.encode("utf-8")).hexdigest()[:12],
            "length": len(content),
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        return {"applied": True, "detail": f"索引{len(keywords[:50])}个关键词"}

    except Exception as e:
        logger.warning(f"INDEX投影失败: {e}")
        return {"applied": False, "detail": str(e)[:100]}


def _project_event(proj_dir: Path, chapter_num: int, content: str, mode: str) -> Dict:
    """EVENT投影：从章节内容提取结构化事件"""
    try:
        events = []

        # 遍历事件类型，检查关键词匹配
        for event_type, keywords in EVENT_KEYWORDS.items():
            for kw in keywords:
                if kw in content:
                    # 找到关键词位置，提取上下文
                    idx = content.index(kw)
                    context_start = max(0, idx - 30)
                    context_end = min(len(content), idx + len(kw) + 50)
                    context = content[context_start:context_end]

                    events.append({
                        "event_type": event_type,
                        "trigger": kw,
                        "chapter": chapter_num,
                        "context": context,
                        "routes": EVENT_ROUTE_TABLE.get(event_type, []),
                    })
                    break  # 每种事件类型最多取一次

        # 持久化事件
        event_path = proj_dir / f"ch{chapter_num:04d}_events.json"
        with open(event_path, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        return {"applied": True, "detail": f"提取{len(events)}个事件"}

    except Exception as e:
        logger.warning(f"EVENT投影失败: {e}")
        return {"applied": False, "detail": str(e)[:100]}


# ============================================================
# 辅助函数
# ============================================================

def _split_into_chunks(content: str, chapter_num: int, chunk_size: int = 500) -> List[Dict]:
    """将章节内容分块"""
    chunks = []
    # 按段落分块
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

    current_chunk = ""
    chunk_idx = 0

    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunk_id = f"ch{chapter_num:04d}_p{chunk_idx:03d}"
            chunks.append({
                "chunk_id": chunk_id,
                "chapter": chapter_num,
                "text": current_chunk.strip(),
                "chunk_type": "paragraph",
            })
            current_chunk = para
            chunk_idx += 1
        else:
            current_chunk += "\n" + para if current_chunk else para

    # 最后一块
    if current_chunk.strip():
        chunk_id = f"ch{chapter_num:04d}_p{chunk_idx:03d}"
        chunks.append({
            "chunk_id": chunk_id,
            "chapter": chapter_num,
            "text": current_chunk.strip(),
            "chunk_type": "paragraph",
        })

    return chunks


def _extract_keywords(text: str) -> List[str]:
    """简单关键词提取（基于频率和长度）"""
    if not text:
        return []

    # 去除标点
    cleaned = re.sub(r'[^\u4e00-\u9fff]', '', text)

    # 提取2-4字词
    stop_chars = set("的了在是我有和就不人都一上也很到说要去你会着没看好自己这那他她它们个")
    words = []

    # 2字词
    for i in range(len(cleaned) - 1):
        word = cleaned[i:i+2]
        if not any(c in stop_chars for c in word):
            words.append(word)

    # 3字词
    for i in range(len(cleaned) - 2):
        word = cleaned[i:i+3]
        if not any(c in stop_chars for c in word):
            words.append(word)

    # 按频率排序
    from collections import Counter
    counter = Counter(words)
    return [w for w, _ in counter.most_common(50)]

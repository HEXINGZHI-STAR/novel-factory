#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - RAG注入器
从参考素材库中检索与当前章节相关的写作技法、桥段套路、场景写法，
注入到写作流程中作为"风格锚点"。

优先级：向量RAG检索 > 关键词匹配
"""

import re
from pathlib import Path
from typing import Optional

# 优先尝试导入后端RAG引擎（FAISS-HNSW + GraphRAG + COSO）
try:
    import sys
    _backend_dir = str(Path(__file__).parent.parent / "backend")
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
    from rag_engine import PanguRAG
    _rag_engine = PanguRAG(str(Path(__file__).parent))
    HAS_BACKEND_RAG = True
except Exception:
    HAS_BACKEND_RAG = False
    _rag_engine = None

# 尝试导入reference_engine
try:
    from reference_engine import WritingTechniqueLibrary, WritingReference
    HAS_REF_ENGINE = True
except ImportError:
    HAS_REF_ENGINE = False


def get_writing_hints(
    mode: str,
    chapter_task: str,
    platform: str = "qimao",
    chapter_num: int = 1,
    max_chars: int = 200,
) -> str:
    """
    从素材库检索与当前章节相关的写作提示。
    返回可直接注入user message的文本，长度控制在max_chars以内。

    优先级：后端RAG(FAISS-HNSW) > 关键词匹配
    """
    # 优先使用后端RAG引擎（FAISS-HNSW + GraphRAG + COSO）
    if HAS_BACKEND_RAG and _rag_engine:
        try:
            query = f"{mode} {chapter_task} {platform}"
            results = _rag_engine.search(query, top_k=3)
            if results:
                hints = ["【RAG写作参考】"]
                for i, r in enumerate(results[:3], 1):
                    text = r.get("text", r.get("content", str(r)))[:150]
                    score = r.get("score", 0)
                    hints.append(f"{i}. (相似度:{score:.2f}) {text}")
                return "\n".join(hints)[:max_chars]
        except Exception:
            pass  # 降级到关键词匹配

    if not HAS_REF_ENGINE:
        return ""

    hints = []

    # 1. 检索写作技法
    try:
        lib = WritingTechniqueLibrary
        techniques = lib.techniques()
        if techniques:
            # 按关键词匹配
            keywords = _extract_keywords(chapter_task)
            matched = _search_entries(techniques, keywords, max_results=1)
            if matched:
                for m in matched:
                    name = m.get('技法名称', m.get('名称', ''))
                    desc = m.get('要点', m.get('描述', m.get('说明', '')))
                    if name and desc:
                        hints.append(f"技法参考【{name}】: {desc[:60]}")
    except Exception:
        pass

    # 2. 检索桥段套路
    try:
        beats = WritingTechniqueLibrary.plot_beats()
        if beats:
            keywords = _extract_keywords(chapter_task)
            matched = _search_entries(beats, keywords, max_results=1)
            if matched:
                for m in matched:
                    name = m.get('桥段名称', m.get('名称', ''))
                    desc = m.get('核心', m.get('要点', m.get('描述', '')))
                    if name and desc:
                        hints.append(f"桥段参考【{name}】: {desc[:60]}")
    except Exception:
        pass

    # 3. 检索爽点节奏
    try:
        payoffs = WritingTechniqueLibrary.payoffs()
        if payoffs:
            # 根据章节位置选择爽点类型
            position = _chapter_position(chapter_num)
            keywords = _extract_keywords(chapter_task) + [position]
            matched = _search_entries(payoffs, keywords, max_results=1)
            if matched:
                for m in matched:
                    name = m.get('爽点类型', m.get('名称', ''))
                    desc = m.get('写法', m.get('要点', m.get('描述', '')))
                    if name and desc:
                        hints.append(f"爽点参考【{name}】: {desc[:60]}")
    except Exception:
        pass

    if not hints:
        return ""

    result = "【素材库参考】\n" + "\n".join(hints[:2])  # 最多2条

    # 截断到max_chars
    if len(result) > max_chars:
        result = result[:max_chars-3] + "..."

    return result


def get_style_anchor(mode: str, platform: str = "qimao") -> str:
    """
    获取同题材的风格锚点（few-shot示例片段）。
    从参考库中提取1个优秀片段作为风格参考。
    返回可直接注入system message的文本。

    优先级：后端RAG(FAISS-HNSW) > 关键词匹配
    """
    # 优先使用后端RAG引擎
    if HAS_BACKEND_RAG and _rag_engine:
        try:
            query = f"{mode} 风格锚点 {platform}"
            results = _rag_engine.search(query, top_k=2)
            if results:
                anchors = ["【风格锚点】"]
                for r in results[:2]:
                    text = r.get("text", r.get("content", str(r)))[:150]
                    anchors.append(text)
                return "\n".join(anchors)
        except Exception:
            pass

    if not HAS_REF_ENGINE:
        return ""

    try:
        ref = WritingReference()
        # 尝试获取参考片段
        # 这里用简化版：从style-adapter.md读取对应题材的风格参数
        style_file = Path(__file__).parent / "references" / "writing" / "style-adapter.md"
        if style_file.exists():
            content = style_file.read_text(encoding='utf-8')
            # 提取与mode相关的段落
            genre_map = {
                "urban_power": "都市", "general": "通用", "xianxia": "仙侠",
                "xuanhuan": "玄幻", "rule_mystery": "悬疑", "romance": "言情",
            }
            genre = genre_map.get(mode, "通用")
            section = _extract_section(content, genre)
            if section:
                return f"【风格锚点·{genre}】{section[:150]}"
    except Exception:
        pass

    return ""


# ============ 辅助函数 ============

def _extract_keywords(text: str) -> list:
    """从文本中提取关键词"""
    # 去除停用词，提取2-4字的关键词
    stopwords = {'的', '了', '在', '是', '我', '他', '她', '这', '那', '和', '与', '但', '而', '要', '会', '能', '到', '把', '被', '让', '给', '对', '又', '也', '都', '就', '才', '还', '又', '很', '非常', '已经', '之后', '然后', '接着', '于是'}
    # 简单分词：按标点和空格分割
    words = re.split(r'[，。！？、；：\s\n]', text)
    keywords = [w for w in words if 2 <= len(w) <= 6 and w not in stopwords]
    return keywords[:5]  # 最多5个关键词


def _search_entries(entries: list, keywords: list, max_results: int = 1) -> list:
    """在条目列表中搜索匹配项"""
    if not entries or not keywords:
        return []

    scored = []
    for entry in entries:
        text = ' '.join(str(v) for v in entry.values() if v)
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:max_results]]


def _chapter_position(chapter_num: int) -> str:
    """根据章节号判断位置"""
    if chapter_num <= 3:
        return "开篇"
    elif chapter_num <= 10:
        return "前期"
    elif chapter_num <= 30:
        return "中期"
    else:
        return "后期"


def _extract_section(content: str, genre: str) -> str:
    """从markdown中提取指定题材的段落"""
    # 查找 ## 题材名 或 ### 题材名
    pattern = rf'#+\s*{re.escape(genre)}.*?\n(.*?)(?=\n#|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()[:200]
    return ""

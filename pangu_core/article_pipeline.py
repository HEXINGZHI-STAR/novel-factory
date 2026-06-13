"""
盘古 · 文章模式 Pipeline

公众号情感文/观点文/热点文 写作流水线。
W0: 选题策划 → W1: 素材检索 → W2: AI初稿 → W3: 质量检查 → W4: 精修成文
"""

from __future__ import annotations

import sys, json, time, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))


@dataclass
class ArticleConfig:
    """文章写作配置"""
    topic: str           # 选题
    angle: str           # 角度
    article_type: str = "情感文"  # 情感文/观点文/热点文
    target_words: int = 1500
    materials: List[str] = field(default_factory=list)  # 素材列表


@dataclass
class ArticleResult:
    """文章写作结果"""
    success: bool
    content: str = ""
    words: int = 0
    golden_sentences: int = 0
    material_usage: int = 0
    persuasion_score: float = 0.0
    errors: List[str] = field(default_factory=list)


class ArticlePipeline:
    """文章写作管线"""

    def __init__(self, config: ArticleConfig):
        self.config = config

    def run(self) -> ArticleResult:
        """执行文章Pipeline"""
        errors = []

        # W0: 选题策划
        plan = self._w0_plan()

        # W1: 素材检索
        materials = self._w1_materials()

        # W2: AI初稿
        draft = self._w2_draft(plan, materials)
        if not draft:
            return ArticleResult(success=False, errors=["W2 初稿生成失败"])

        # W3: 质量检查
        qc = self._w3_qc(draft)

        # W4: 精修
        final = self._w4_polish(draft, qc)
        if not final:
            final = draft  # 精修失败用初稿

        words = len(final.replace('\n', '').replace(' ', ''))
        golden = self._count_golden(final)
        mat_use = self._count_material_usage(final, materials)

        return ArticleResult(
            success=True, content=final, words=words,
            golden_sentences=golden, material_usage=mat_use,
            persuasion_score=qc.get("persuasion", 0.5),
            errors=errors,
        )

    def _w0_plan(self) -> str:
        """W0: 构建写作计划"""
        return (
            f"选题: {self.config.topic}\n"
            f"角度: {self.config.angle}\n"
            f"文体: {self.config.article_type}\n"
            f"目标字数: {self.config.target_words}字\n"
            f"结构: 场景开头→素材论证→个人经历/观察→情绪高潮→金句收尾"
        )

    def _w1_materials(self) -> List[str]:
        """W1: 加载素材"""
        materials = list(self.config.materials)
        # 从素材库补充
        try:
            data = json.loads((BASE / 'knowledge' / 'article_materials.json')
                              .read_text(encoding='utf-8'))
            # 匹配相关素材
            for category in ['情感类', '观点类', '热点类']:
                for sub, items in data.get(category, {}).items():
                    if isinstance(items, list):
                        for item in items:
                            if any(kw in item for kw in self.config.topic[:3]):
                                materials.append(item)
        except Exception:
            pass
        return materials[:5]

    def _w2_draft(self, plan: str, materials: List[str]) -> str:
        """W2: AI生成初稿"""
        from dotenv import load_dotenv; load_dotenv(override=True)
        from pangu_core.config import reset_config; reset_config()
        from .ai_client import call_ai

        system = (BASE / 'system_prompts' / 'article_writer.txt').read_text(encoding='utf-8')
        mat_text = '\n'.join(f'- {m[:200]}' for m in materials)
        user = f"{plan}\n\n可用素材:\n{mat_text}\n\n直接输出文章正文，不要标题。"
        return call_ai(user, system_msg=system)

    def _w3_qc(self, draft: str) -> dict:
        """W3: 文章质量检查"""
        issues = []
        score = 0.7

        # 1. 金句检测
        golden = self._count_golden(draft)
        if golden < 1:
            issues.append("缺金句——至少1句可截图传播的话")
            score -= 0.2

        # 2. 开头Hook检测
        first_200 = draft[:200]
        if not any(kw in first_200 for kw in ['那天', '有一次', '我认识', '最怕', '突然']):
            issues.append("开头Hook偏弱——用具体场景而非道理开头")
            score -= 0.1

        # 3. 结构检查
        if '所以' in draft[-50:] or '因此' in draft[-50:]:
            issues.append("结尾标语化——不用'所以/因此'收尾")
            score -= 0.1

        # 4. 素材使用
        mat_count = sum(1 for kw in ['说过','写过','讲过','提到','有一个','问到','回答'] if kw in draft)
        if mat_count < 2:
            issues.append("素材不足——每300字至少1个具体素材")
            score -= 0.15

        # 5. 说服力
        from pangu_analytics.persuasion_engine import PersuasionAnalyzer
        try:
            pers = PersuasionAnalyzer().full_report(draft)
            score = pers.get('persuasion_index', score)
        except Exception:
            pass

        return {"score": max(0.1, score), "issues": issues, "golden": golden}

    def _w4_polish(self, draft: str, qc: dict) -> str:
        """W4: AI精修"""
        from dotenv import load_dotenv; load_dotenv(override=True)
        from pangu_core.config import reset_config; reset_config()
        from .ai_client import call_ai

        issues_text = '\n'.join(f'- {i}' for i in qc.get('issues', []))
        prompt = (
            f"以下是文章初稿，质检发现以下问题:\n{issues_text}\n\n"
            f"请精修这篇文章，保持原结构，修正上述问题。直接输出精修后的全文:\n\n{draft}"
        )
        result = call_ai(prompt)
        return result if result else draft

    def _count_golden(self, text: str) -> int:
        """检测金句数量"""
        golden_patterns = [
            r'不是因为.{3,15}而是因为.{3,20}',  # 转折句式
            r'所以.{3,15}不是.{3,15}是.{3,20}',  # 递进句式
            r'后来.{2,5}才明白.{3,20}',          # 时间体悟
            r'最怕.{3,15}因为.{3,20}',           # 恐惧句式
        ]
        count = 0
        for pat in golden_patterns:
            count += len(re.findall(pat, text))
        return min(count, 5)

    def _count_material_usage(self, text: str, materials: List[str]) -> int:
        """统计素材使用数量"""
        used = 0
        for mat in materials:
            if mat[:15] in text:
                used += 1
        return used

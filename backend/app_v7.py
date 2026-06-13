# -*- coding: utf-8 -*-
"""
盘古V7.5 小说工厂后端API
四车间流水线调度系统 + LiteLLM多模型路由 + RAG知识检索
专注: 治愈系·情绪释放·电影质感

开源集成:
  - LiteLLM (MIT) — 统一100+模型供应商接口，替代手动多模型路由
  - FAISS (MIT)  — Facebook向量检索，替代纯numpy TF-IDF
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# LiteLLM — 开源多模型统一接口 (MIT License)
# 支持 OpenAI / DeepSeek / Anthropic / Ollama / 通义千问 等100+供应商
# 通过模型名前缀自动路由：openai/gpt-4o, deepseek/deepseek-chat, etc.
try:
    import litellm
    litellm.suppress_debug_info = True
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    print("[WARN] litellm 未安装，回退到手动HTTP调用。安装: pip install litellm")

# RAG知识检索引擎
try:
    from rag_engine import get_rag, PanguRAG
    from rag_engine import build_graph_from_project
except ImportError:
    # 处理导入失败的情况
    get_rag = None
    PanguRAG = None
    build_graph_from_project = None

# 可观测性模块——轻量 LLM 追踪 + 治愈系自动评分
try:
    from observability import (trace_llm, score_text, score_metrics,
                               get_tracer, load_custom_weights, save_custom_weights,
                               detect_emotional_curve, detect_emotional_curve_quick,
                               extract_style_fingerprint, check_style_consistency,
                               StyleFingerprint, HeroArcDetector, ShonenStyleDetector,
                               TensionCurveGenerator, HeatmapGenerator, GiskardAuditor,
                               InkOS, PacingChecker, AutoRewriteEngine, WorkflowRunner,
                               LLMAdapter, HAS_LLM_ADAPTER, load_snapshot,
                               MemoryChecker, SemanticDiffChecker)
except ImportError:
    # 定义安全的回退函数
    def trace_llm(*args, **kwargs): pass
    def score_text(*args, **kwargs): return {"score": 0}
    def score_metrics(*args, **kwargs): return {}
    def get_tracer(*args, **kwargs): return None
    def load_custom_weights(*args, **kwargs): return {}
    def save_custom_weights(*args, **kwargs): pass
    def detect_emotional_curve(*args, **kwargs): return {"curve_valid": False}
    def detect_emotional_curve_quick(*args, **kwargs): return {"curve_valid": False}
    def extract_style_fingerprint(*args, **kwargs): return {}
    def check_style_consistency(*args, **kwargs): return True
    HAS_LLM_ADAPTER = False

# TextGrad优化模块
try:
    from textgrad_opt import textgrad_refine
except ImportError:
    def textgrad_refine(text, *args, **kwargs): return {"refined_text": text}

# 风格库模块
try:
    from style_library import StyleProfileManager
except ImportError:
    class StyleProfileManager:
        @staticmethod
        def list_profiles(): return []

# 状态追踪系统
try:
    from state_tracker import StateTracker
except ImportError:
    # 回退实现
    class StateTracker:
        def __init__(self): pass
        def initialize_from_project(self, data): pass
        def update_after_chapter(self, *args): pass
        def get_full_context(self): return ""
        def to_dict(self): return {}

# 任务队列系统
try:
    from task_queue import (
        task_queue, task_monitor, init_task_queue,
        submit_task, get_task_status, get_all_tasks, get_task_stats, shutdown_task_queue
    )
except ImportError:
    # 回退实现
    submit_task = lambda data, priority=1: "mock-task-id"
    get_task_status = lambda task_id: None
    get_all_tasks = lambda: []
    get_task_stats = lambda: {}
    shutdown_task_queue = lambda: None

# 监控系统
try:
    from monitoring import (
        record_llm_call, record_request, record_pipeline_run,
        record_error, update_memory_stats, get_llm_stats,
        get_performance_metrics, get_health_status
    )
except ImportError:
    # 回退实现
    record_llm_call = lambda *args, **kwargs: None
    record_request = lambda *args, **kwargs: None
    record_pipeline_run = lambda *args, **kwargs: None
    record_error = lambda *args, **kwargs: None
    update_memory_stats = lambda *args, **kwargs: None
    get_llm_stats = lambda: {}
    get_performance_metrics = lambda: {}
    get_health_status = lambda: {"status": "healthy"}

app = Flask(__name__)
CORS(app)

# ============ 路径配置 ============
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSHOP_DIR = BASE_DIR / "workshops"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
MODES_DIR = BASE_DIR / "modes"
LIBRARIES_DIR = BASE_DIR / "novel_libraries"

# ============ 模型路由（LiteLLM优先，环境变量兜底）============
# 设置方式：
#   set LLM_MODEL=deepseek/deepseek-chat          （所有车间共用）
#   set WORKSHOP_W2_MODEL=anthropic/claude-sonnet  （W2单独配置）
#   set WORKSHOP_W4_MODEL=openai/gpt-4o            （W4单独配置）
#
# LiteLLM 模型格式：provider/model_name
#   例: openai/gpt-4o, deepseek/deepseek-chat, anthropic/claude-sonnet-4-6
#       ollama/qwen2.5:14b, dashscope/qwen-turbo, zhipuai/glm-4

DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

# 各车间模型（环境变量覆盖，否则用默认）
WORKSHOP_MODELS = {
    "w0": os.getenv("WORKSHOP_W0_MODEL", DEFAULT_MODEL),
    "w1": os.getenv("WORKSHOP_W1_MODEL", DEFAULT_MODEL),
    "w2": os.getenv("WORKSHOP_W2_MODEL", DEFAULT_MODEL),
    "w3": os.getenv("WORKSHOP_W3_MODEL", DEFAULT_MODEL),
    "w4": os.getenv("WORKSHOP_W4_MODEL", DEFAULT_MODEL),
    "fusion": os.getenv("WORKSHOP_FUSION_MODEL", DEFAULT_MODEL),
    "default": DEFAULT_MODEL,
}

# API Key（LiteLLM 自动从环境变量读取，这里保留手动兼容）
# LiteLLM 标准环境变量：OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, etc.
LLM_API_KEY = os.getenv("LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")

# ============ LiteLLM 高可用配置（纯配置，零代码改动） ============
# 熔断/重试/fallback/超时 —— 全部由 LiteLLM 原生支持

if HAS_LITELLM:
    # 全局超时（秒）
    litellm.request_timeout = int(os.getenv("LLM_TIMEOUT", "180"))

    # 自动重试：次数 + 指数退避
    litellm.num_retries = int(os.getenv("LLM_RETRIES", "3"))
    # 指数退避策略：等待 2^attempt 秒后重试
    litellm.retry_after = 2

    # 熔断：连续失败 N 次后冷却该模型（秒）
    litellm.allowed_fails = int(os.getenv("LLM_ALLOWED_FAILS", "5"))
    litellm.cooldown_time = float(os.getenv("LLM_COOLDOWN_SEC", "30"))

    # 速率限制（每分钟最大请求数，0=不限制）
    litellm.rpm = int(os.getenv("LLM_RPM", "0"))
    litellm.tpm = int(os.getenv("LLM_TPM", "0"))  # tokens per minute

    # 失败回调（记录到日志）
    def _on_failure(kwargs, completion, start_time, end_time):
        """LiteLLM 失败钩子——记录但不阻断"""
        exc = kwargs.get("exception")
        model = kwargs.get("model", "unknown")
        print(f"[LLM_FAIL] 模型={model} 耗时={end_time-start_time:.1f}s 错误={exc}")

    litellm.failure_callback = [_on_failure]

    print(f"[LiteLLM] 高可用已配置: 超时={litellm.request_timeout}s "
          f"重试={litellm.num_retries}次 熔断={litellm.allowed_fails}次/{litellm.cooldown_time}s")

# 模型 fallback 链（环境变量逗号分隔）
# 例: set WORKSHOP_W2_FALLBACK=deepseek/deepseek-chat,openai/gpt-4o-mini
def _get_fallback_models(workshop: str) -> list:
    """获取指定车间的 fallback 模型链"""
    fallback_str = os.getenv(f"WORKSHOP_{workshop.upper()}_FALLBACK", "")
    if fallback_str:
        return [m.strip() for m in fallback_str.split(",") if m.strip()]
    global_fallback = os.getenv("LLM_FALLBACK", "")
    if global_fallback:
        return [m.strip() for m in global_fallback.split(",") if m.strip()]
    return []


# ============ 工具函数 ============

def load_file(path: Path) -> str:
    """安全加载文件，不存在时返回空字符串"""
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_json(path: Path) -> dict:
    """安全加载JSON，不存在时返回空字典"""
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return {}
    return {}


# ============ 加载 System Prompt ============

def load_workshop_prompt(workshop_id: int) -> str:
    """加载指定车间的 system prompt"""
    workshop_map = {
        0: WORKSHOP_DIR / "workshop_0_anchor" / "system_prompt.txt",
        1: WORKSHOP_DIR / "workshop_1_setup" / "system_prompt.txt",
        2: WORKSHOP_DIR / "workshop_2_draft" / "system_prompt.txt",
        3: WORKSHOP_DIR / "workshop_3_qc" / "system_prompt.txt",
        4: WORKSHOP_DIR / "workshop_4_polish" / "system_prompt.txt",
    }
    return load_file(workshop_map.get(workshop_id))


def load_mode_config(mode: str) -> dict:
    """加载指定模式的配置文件"""
    path = MODES_DIR / f"{mode}.json"
    return load_json(path)


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
    workshop: str = "default",
) -> dict:
    """
    JSON 模式 LLM 调用。
    优先用 response_format 约束模型输出 JSON；模型不支持时回退到文本解析。
    返回: (parsed_dict, raw_text)  — parsed_dict 解析失败时为 {}
    """
    model = WORKSHOP_MODELS.get(workshop, DEFAULT_MODEL)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt + "\n\n请只返回有效的 JSON 对象，不要包含 markdown 代码块或任何其他文本。"},
    ]

    if not LLM_API_KEY:
        # 模拟模式：返回有效的模拟数据以测试流水线
        import random
        mock_data = {
            "w0": {
                "thesis": "都市青年回归山村行医",
                "anchor": user_prompt[:50] + "...",
                "keywords": ["乡村", "医生", "神秘", "治愈"],
                "emotion_tone": "温暖",
                "story_direction": "正向治愈",
                "core_conflict": "现代医学与传统智慧的碰撞",
                "character_growth": "从迷茫到坚定",
                "is_generic": False,
                "irreplaceability_score": 7,
                "anchor_scene": "村口老银杏树下，白发老人静静等待",
                "counterintuitive_point": "年轻医生从城市来到山村，却发现老中医掌握着失传医术"
            },
            "w1": {
                "setting_enhanced": "云雾山村，海拔八百米，常年云雾缭绕，村口有一棵千年银杏树",
                "characters": ["林晓（26岁，医科大学毕业生）", "陈老爷子（78岁，神秘老中医）"],
                "scene_atmosphere": "宁静祥和，略带神秘气息",
                "time_period": "现代",
                "location_details": "村口老银杏树下"
            },
            "w2": {
                "content": f"第{random.randint(1, 100)}章 初入山村\n\n林晓背着简单的行囊，踏上了云雾山村的土地。山风带着草木的清香，远处传来几声鸟鸣。\n\n他抬头望去，只见村口一棵巨大的银杏树，枝繁叶茂，树下坐着一位白发苍苍的老人。\n\n\"小伙子，你就是新来的医生吧？\"老人缓缓开口，声音带着岁月的沧桑。\n\n林晓连忙点头：\"您好，我是林晓，来这里支援乡村医疗。\"\n\n老人微微一笑：\"我等你很久了...\"\n\n阳光透过树叶的缝隙洒落，在老人身上镀上一层金色的光晕。\n\n林晓注意到老人的手指修长，指甲修剪得整整齐齐，不像是常年劳作的农人。\n\n\"村里的人都叫我陈老爷子，\"老人站起身，\"跟我来吧，我带你去看看村里的卫生室。\"",
                "word_count": 800,
                "chapters_outline": ["初遇", "进村", "了解情况"]
            },
            "w3": {
                "consistency_score": 92,
                "logic_issues": [],
                "emotion_consistency": 95,
                "character_consistency": 98,
                "suggestions": ["建议增加一些环境描写来增强氛围"]
            },
            "w4": {
                "polished_content": f"第{random.randint(1, 100)}章 云雾深处\n\n晨雾尚未散尽，林晓的皮鞋碾过青石板路上的露珠，发出细微的声响。\n\n云雾山村，这个在地图上几乎找不到的地方，此刻就安静地躺在群山的怀抱里。\n\n村口那棵千年银杏树依旧枝繁叶茂，仿佛一位沉默的守护者，见证着岁月的流转。\n\n树下，一位身着青色布衣的老者正闭目养神，晨光穿透薄雾，为他银白的发丝染上金边。\n\n\"年轻人，你来了。\"老者睁开眼睛，目光深邃如古井。\n\n林晓心头微震，这老人似乎早已料到他的到来。\n\n\"晚辈林晓，受县里派遣，前来支援乡村医疗。\"他恭敬地鞠了一躬。\n\n老者缓缓起身，步履稳健得不像年近八旬：\"我是陈默，村里的赤脚医生。跟我来，卫生室就在前面。\"\n\n两人并肩走在蜿蜒的石板路上，两旁是错落有致的土坯房，袅袅炊烟从屋顶升起，与山间云雾融为一体。",
                "style_score": 94,
                "readability_score": 96,
                "polish_level": "精修完成"
            }
        }
        workshop_key = workshop.lower()
        if workshop_key in mock_data:
            return mock_data[workshop_key], str(mock_data[workshop_key])
        return {"content": "[模拟模式] 测试内容生成成功"}, "[模拟模式] 已生成模拟数据"

    raw = ""
    if HAS_LITELLM:
        try:
            kwargs = dict(model=model, messages=messages,
                          temperature=temperature, max_tokens=max_tokens)
            # 尝试 JSON mode（OpenAI/DeepSeek 兼容）
            try:
                kwargs["response_format"] = {"type": "json_object"}
            except Exception:
                pass
            response = litellm.completion(**kwargs)
            raw = response.choices[0].message.content or ""
        except Exception:
            # 回退到普通调用
            raw = call_llm(system_prompt, user_prompt, temperature, max_tokens, workshop)
    else:
        raw = call_llm(system_prompt, user_prompt, temperature, max_tokens, workshop)

    # 解析 JSON
    if raw and not raw.startswith("[ERROR]") and not raw.startswith("[模拟"):
        # 去掉可能的 markdown 代码块包裹
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:]) if len(lines) > 1 else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        try:
            return json.loads(cleaned.strip()), raw
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 片段
            import re as _re
            match = _re.search(r'\{[^{}]*\}', cleaned, _re.DOTALL)
            if match:
                try:
                    return json.loads(match.group()), raw
                except json.JSONDecodeError:
                    pass
    return {}, raw


# ============ 多模型 LLM 调用 ============

def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    max_tokens: int = 4000,
    workshop: str = "default",
) -> str:
    """
    调用大模型生成内容。V7.5 高可用版：
    - 自动重试（指数退避，litellm.num_retries）
    - 模型级熔断（连续失败冷却，litellm.allowed_fails + cooldown_time）
    - Fallback 链（主模型挂了自动切备用）
    - 超时拦截 + 错误分类（区分可重试/不可重试）
    """
    model = WORKSHOP_MODELS.get(workshop, DEFAULT_MODEL)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if not LLM_API_KEY:
        import random
        mock_outputs = {
            "w0": """{
    "thesis": "都市青年回归山村行医",
    "is_generic": false,
    "generic_reason": "",
    "irreplaceability_score": 7,
    "anchor_scene": "村口老银杏树下，白发老人静静等待",
    "counterintuitive_point": "年轻医生从城市来到山村，却发现老中医掌握着失传医术",
    "keywords": ["乡村", "医生", "神秘", "治愈"],
    "emotion_tone": "温暖",
    "story_direction": "正向治愈",
    "core_conflict": "现代医学与传统智慧的碰撞",
    "character_growth": "从迷茫到坚定"
}""",
            "w1": """云雾山村坐落于海拔八百米的群山之间，常年被缭绕的云雾笼罩，宛如世外桃源。村里只有二十几户人家，大多是留守的老人和孩子。村口那棵千年银杏树是村子的标志，据说已经有八百多年的历史。

【主要人物】
- 林晓：26岁，医科大学毕业生，怀揣理想来到山村支援医疗
- 陈默：78岁，村里的赤脚医生，性格神秘，似乎隐藏着不为人知的过去

【世界规则】
1. 山村与世隔绝，信息传播缓慢
2. 村民们相信传统医术，对现代医学持怀疑态度
3. 每年秋天会举办传统的草药节

【潜在冲突】
- 现代医学与传统医术的碰撞
- 城市价值观与乡村生活方式的冲突
- 陈默老人的神秘过往""",
            "w2": """林晓背着简单的行囊踏上了云雾山村的土地。山风带着草木的清香，远处传来几声清脆的鸟鸣。

村口那棵巨大的银杏树映入眼帘，枝繁叶茂，树下坐着一位白发苍苍的老人。

"小伙子，你就是新来的医生吧？"老人缓缓开口，声音带着岁月的沧桑。

林晓连忙点头："您好，我是林晓，来这里支援乡村医疗。"

老人微微一笑，眼角的皱纹如同水波般漾开："我等你很久了..."

阳光透过树叶的缝隙洒落，在老人身上镀上一层金色的光晕。林晓注意到老人的手指修长，指甲修剪得整整齐齐，不像是常年劳作的农人。

"村里的人都叫我陈老爷子，"老人站起身，拍了拍身上的尘土，"跟我来吧，我带你去看看村里的卫生室。"

两人并肩走在蜿蜒的石板路上，两旁是错落有致的土坯房，袅袅炊烟从屋顶升起，与山间云雾融为一体。""",
            "w3": """{
    "consistency_score": 92,
    "logic_issues": [],
    "emotion_consistency": 95,
    "character_consistency": 98,
    "pacing_score": 88,
    "suggestions": ["建议增加一些环境描写来增强氛围", "可以适当增加村民的反应", "考虑加入一个小冲突来推动情节"],
    "rewrite_needed": false,
    "rewrite_sections": []
}""",
            "w4": """晨雾尚未散尽，林晓的皮鞋碾过青石板路上的露珠，发出细微的声响。

云雾山村，这个在地图上几乎找不到的地方，此刻就安静地躺在群山的怀抱里。村口那棵千年银杏树依旧枝繁叶茂，仿佛一位沉默的守护者，见证着岁月的流转。

树下，一位身着青色布衣的老者正闭目养神，晨光穿透薄雾，为他银白的发丝染上金边。

"年轻人，你来了。"老者睁开眼睛，目光深邃如古井。

林晓心头微震，这老人似乎早已料到他的到来。

"晚辈林晓，受县里派遣，前来支援乡村医疗。"他恭敬地鞠了一躬。

老者缓缓起身，步履稳健得不像年近八旬："我是陈默，村里的赤脚医生。跟我来，卫生室就在前面。"

两人并肩走在蜿蜒的石板路上，两旁是错落有致的土坯房，袅袅炊烟从屋顶升起，与山间云雾融为一体。空气中弥漫着柴草燃烧的气息，夹杂着淡淡的草药香。

"村里已经很久没有来过年轻医生了，"陈默忽然开口，"上一个来的，还是十年前。"

林晓好奇地问："后来呢？"

陈默的脚步顿了顿，目光望向远方："他来了，又走了。"

话语中带着一丝说不清道不明的意味。"""
        }
        return mock_outputs.get(workshop.lower(), f"【模拟内容】第{random.randint(1, 100)}章\n\n这是{workshop}车间生成的模拟内容。\n\n测试段落...")

    # fallback 链
    fallback_models = _get_fallback_models(workshop)

    # === 路径 A：LiteLLM（推荐，含高可用特性） ===
    if HAS_LITELLM:
        last_error = ""
        models_to_try = [model] + fallback_models
        for attempt_model in models_to_try:
            t0 = time.time()
            try:
                kwargs = dict(
                    model=attempt_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response = litellm.completion(**kwargs)
                latency = (time.time() - t0) * 1000
                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if hasattr(response, 'usage') and response.usage else 0
                trace_llm(workshop, attempt_model, True, latency, tokens=tokens_used)
                if attempt_model != model:
                    print(f"[LLM] Fallback: {model} → {attempt_model} (成功, {latency:.0f}ms)")
                return content
            except litellm.exceptions.Timeout:
                latency = (time.time() - t0) * 1000
                last_error = f"超时({attempt_model})"
                trace_llm(workshop, attempt_model, False, latency, error=last_error)
                print(f"[LLM] 超时: {attempt_model}，尝试下一个...")
                continue
            except litellm.exceptions.RateLimitError:
                latency = (time.time() - t0) * 1000
                last_error = f"限流({attempt_model})"
                trace_llm(workshop, attempt_model, False, latency, error=last_error)
                print(f"[LLM] 限流: {attempt_model}，等待5s后尝试下一个...")
                time.sleep(5)
                continue
            except litellm.exceptions.APIConnectionError:
                latency = (time.time() - t0) * 1000
                last_error = f"连接失败({attempt_model})"
                trace_llm(workshop, attempt_model, False, latency, error=last_error)
                print(f"[LLM] 连接失败: {attempt_model}，尝试下一个...")
                continue
            except litellm.exceptions.ServiceUnavailableError:
                latency = (time.time() - t0) * 1000
                last_error = f"服务不可用({attempt_model})"
                trace_llm(workshop, attempt_model, False, latency, error=last_error)
                print(f"[LLM] 服务不可用: {attempt_model}，尝试fallback...")
                continue
            except Exception as e:
                latency = (time.time() - t0) * 1000
                last_error = f"{attempt_model}: {str(e)[:120]}"
                trace_llm(workshop, attempt_model, False, latency, error=last_error)
                print(f"[LLM] 未分类错误: {last_error}")
                continue
        return f"[ERROR] 所有模型尝试失败 ({len(models_to_try)}个): {last_error}"

    # === 路径 B：手动HTTP回退 ===
    t0 = time.time()
    try:
        import requests as req
        
        # 根据模型选择正确的API地址
        if "deepseek" in model.lower():
            api_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        elif "openai" in model.lower():
            api_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        else:
            api_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        payload = {
            "model": model.split("/")[-1],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = req.post(
            f"{api_base}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        latency = (time.time() - t0) * 1000
        trace_llm(workshop, model, True, latency)
        return resp.json()["choices"][0]["message"]["content"]
    except ImportError:
        trace_llm(workshop, model, False, (time.time()-t0)*1000, error="缺少依赖")
        return "[ERROR] 缺少依赖。安装: pip install litellm requests"
    except Exception as e:
        trace_llm(workshop, model, False, (time.time()-t0)*1000, error=str(e)[:200])
        return f"[ERROR] API调用失败 ({workshop}): {str(e)}"


# ============ Fusion Engine 混搭引擎核心 ============

class FusionEngine:
    """
    题材混搭引擎
    功能：将1-3个模式融合为统一的创作协议
    原则：保留各模式爽点，消灭冲突，生成新的核心矛盾
    """

    # 统一模式矩阵（所有归档模式的技法已吸收到核心模型中）
    COMPATIBILITY_MATRIX = {
        ("healing_life", "general"): 3,
        ("healing_life_v2", "general"): 3,
        ("general", "*"): 2,
        ("*", "general"): 2,
    }

    def __init__(self, primary: str, secondary: str = None, tertiary: str = None):
        self.primary = primary
        self.secondary = secondary
        self.tertiary = tertiary
        self.weights = {"primary": 0.6, "secondary": 0.3, "tertiary": 0.1}

    def check_compatibility(self) -> dict:
        """检查模式混搭的兼容性"""
        result = {
            "valid": True,
            "score": 3,
            "warnings": [],
            "taboos": [],
            "adjustments": {},
        }

        pairs = []
        if self.secondary:
            pairs.append((self.primary, self.secondary))
        if self.tertiary and self.secondary:
            pairs.append((self.secondary, self.tertiary))

        for p, s in pairs:
            key = (p, s)
            reverse_key = (s, p)
            score = self.COMPATIBILITY_MATRIX.get(
                key, self.COMPATIBILITY_MATRIX.get(
                    reverse_key,
                    self.COMPATIBILITY_MATRIX.get((p, "*"), 2)
                )
            )

            if score == 0:
                result["valid"] = False
                result["taboos"].append(f"【绝对禁忌】{p} + {s} = 不可混搭")
            elif score == 1:
                result["warnings"].append(f"【警告】{p} + {s} = 高风险混搭，需要特殊处理")
            elif score >= 3:
                result["warnings"].append(f"【推荐】{p} + {s} = 黄金混搭")

            result["score"] = min(result["score"], score)

        # 根据兼容性输出调整建议
        if self.secondary:
            result["adjustments"] = self._generate_adjustments()

        return result

    def _generate_adjustments(self) -> dict:
        """生成混搭调整建议"""
        adjustments = {
            "core_conflict": self._resolve_core_conflict(),
            "rhythm": self._adjust_rhythm(),
            "taboo_list": self._get_taboos(),
        }
        return adjustments

    def _resolve_core_conflict(self) -> str:
        """统一核心冲突：回答"谁说了算"""
        # 规则：以主模式的世界观为底，副模式做"变异"
        mode_names = {
            "urban_power": "都市职业异能",
            "history_scholar": "历史考据流",
            "female_solo": "无CP大女主",
            "rule_mystery": "规则怪谈",
            "romance": "言情",
            "folk_horror": "中式民俗悬疑",
            "healing_life": "治愈生活流",
            "general": "通用网文",
        }

        primary_name = mode_names.get(self.primary, self.primary)
        if self.secondary:
            secondary_name = mode_names.get(self.secondary, self.secondary)
            return f"以「{primary_name}」的世界观为底色，融入「{secondary_name}」的叙事质感和情绪基调。主模式的规则优先，副模式作为'变异因子'影响具体场景的氛围和选择。"
        return f"纯「{primary_name}」模式，无混搭。"

    def _adjust_rhythm(self) -> dict:
        """调整节奏权重"""
        # 各模式的节奏参数
        rhythm_params = {
            "urban_power": {"pace": "fast", "hook_position": "前300字", "scene_count": 4},
            "history_scholar": {"pace": "medium", "hook_position": "前500字", "scene_count": 3},
            "female_solo": {"pace": "medium", "hook_position": "前300字", "scene_count": 3},
            "rule_mystery": {"pace": "medium", "hook_position": "前300字", "scene_count": 3},
            "romance": {"pace": "slow", "hook_position": "前800字", "scene_count": 2},
            "folk_horror": {"pace": "slow", "hook_position": "前500字", "scene_count": 3},
            "healing_life": {"pace": "slow", "hook_position": "前800字", "scene_count": 2},
            "general": {"pace": "medium", "hook_position": "前500字", "scene_count": 3},
        }

        primary_r = rhythm_params.get(self.primary, rhythm_params["general"])
        base = primary_r.copy()

        if self.secondary:
            secondary_r = rhythm_params.get(self.secondary, rhythm_params["general"])

            # 根据权重调整
            if secondary_r["pace"] == "fast" and base["pace"] == "slow":
                base["hook_position"] = "前300字"
                base["scene_count"] = min(base["scene_count"] + 1, 5)
            elif secondary_r["pace"] == "slow" and base["pace"] == "fast":
                base["scene_count"] = max(base["scene_count"] - 1, 2)

            # 副模式的钩子位置做加权平均（取较早的）
            if secondary_r["hook_position"] < base["hook_position"]:
                base["hook_position"] = secondary_r["hook_position"]

        return base

    def _get_taboos(self) -> list:
        """获取混搭禁忌清单"""
        taboos = []

        # 通用禁忌
        if self.primary == "female_solo" and self.secondary == "romance":
            taboos.append("无CP大女主 + 言情 = 绝对冲突：女主的核心驱动会从'事业'变为'关系'")
        if self.primary == "romance" and self.secondary == "female_solo":
            taboos.append("言情 + 无CP大女主 = 逻辑矛盾：无法同时追求爱情和完全没有爱情")

        # 从模式配置中加载各模式的禁忌
        primary_config = load_mode_config(self.primary)
        if primary_config and "fusion_compatibility" in primary_config:
            primary_taboos = primary_config["fusion_compatibility"].get("禁忌混搭", [])
            taboos.extend(primary_taboos)

        return taboos

    def generate_protocol(self) -> dict:
        """
        生成完整的混搭协议
        """
        compatibility = self.check_compatibility()

        if not compatibility["valid"]:
            return {
                "success": False,
                "error": "混搭方案存在绝对禁忌，无法生成协议",
                "taboos": compatibility["taboos"],
                "suggestion": "请更换主模式或副模式",
            }

        protocol = {
            "success": True,
            "fusion_weights": self.weights,
            "compatibility": compatibility,
            "core_conflict": compatibility["adjustments"].get("core_conflict", ""),
            "rhythm_adjustment": compatibility["adjustments"].get("rhythm", {}),
            "taboo_list": compatibility["adjustments"].get("taboo_list", []),
            "mode_configs": {
                "primary": load_mode_config(self.primary),
                "secondary": load_mode_config(self.secondary) if self.secondary else None,
                "tertiary": load_mode_config(self.tertiary) if self.tertiary else None,
            },
        }
        return protocol


# ============ 三库验证器 ============

class NovelLibraryValidator:
    """小说专属三库完整性验证器"""

    REQUIRED_LIBS = {
        "character_atlas.json": ["必需：人物图谱库"],
        "event_plot_atlas.json": ["必需：事件剧情图谱库"],
        "exclusive_materials.json": ["必需：专属素材库"],
    }

    @staticmethod
    def validate(project_name: str) -> dict:
        """验证指定项目的三库完整性"""
        project_dir = LIBRARIES_DIR / project_name
        result = {
            "project": project_name,
            "exists": project_dir.exists(),
            "libraries": {},
            "all_present": False,
            "missing": [],
        }

        if not project_dir.exists():
            result["missing"] = list(NovelLibraryValidator.REQUIRED_LIBS.keys())
            return result

        for lib_name in NovelLibraryValidator.REQUIRED_LIBS:
            lib_path = project_dir / lib_name
            if lib_path.exists():
                try:
                    data = json.loads(lib_path.read_text(encoding="utf-8"))
                    result["libraries"][lib_name] = {
                        "present": True,
                        "size": len(str(data)),
                        "has_content": bool(data),
                    }
                except (json.JSONDecodeError, Exception):
                    result["libraries"][lib_name] = {
                        "present": True,
                        "size": 0,
                        "has_content": False,
                        "error": "JSON格式错误",
                    }
            else:
                result["libraries"][lib_name] = {"present": False}
                result["missing"].append(lib_name)

        result["all_present"] = len(result["missing"]) == 0
        return result


# ============ V7 调度器 ============

class SchedulerV7:
    """盘古V7.0 四车间调度器"""

    def __init__(self, user_input: dict):
        self.mode = user_input.get("mode", "general")
        self.chapter_num = user_input.get("chapter_num", 1)
        self.chapter_task = user_input.get("chapter_task", "")
        self.word_count = user_input.get("word_count", 3000)
        self.cold_storage = user_input.get("cold_storage", "")
        self.genre = user_input.get("genre", "都市")
        self.title = user_input.get("title", "未命名作品")
        self.project_name = user_input.get("project_name", "")
        self.platform = user_input.get("platform", "fanqie")
        self.enable_fusion = user_input.get("enable_fusion", False)
        self.fusion_modes = user_input.get("fusion_modes", {})

        # 加载架构和模式
        self.mode_config = load_mode_config(self.mode)

        # 加载车间prompt
        self.w0_prompt = load_workshop_prompt(0)
        self.w1_prompt = load_workshop_prompt(1)
        self.w2_prompt = load_workshop_prompt(2)
        self.w3_prompt = load_workshop_prompt(3)
        self.w4_prompt = load_workshop_prompt(4)

        # 执行日志
        self.logs = []

        # 初始化状态追踪系统
        self.state_tracker = StateTracker()
        self.state_tracker.initialize_from_project(user_input)

        # 初始化RAG引擎（懒加载）
        self._rag = None

    def _get_rag(self) -> PanguRAG:
        """获取RAG引擎实例"""
        if self._rag is None:
            self._rag = get_rag(self.project_name)
        return self._rag

    def _rag_context(self, workshop: str, task_desc: str = "", top_k: int = 3) -> str:
        """为指定车间检索RAG知识"""
        rag = self._get_rag()
        desc = task_desc or self.chapter_task or f"第{self.chapter_num}章 {self.genre}"
        return rag.search_for_workshop(
            workshop=workshop,
            task_description=desc,
            mode=self.mode,
            platform=self.platform,
            project_name=self.project_name,
            top_k=top_k,
        )

    def log(self, stage: str, message: str):
        entry = {"time": time.strftime("%H:%M:%S"), "stage": stage, "message": message}
        self.logs.append(entry)
        print(f"[{entry['time']}] {stage}: {message}")

    def _build_fusion_context(self) -> str:
        """构建Fusion Engine上下文（如果启用了混搭）"""
        if not self.enable_fusion:
            return ""

        primary = self.fusion_modes.get("primary", self.mode)
        secondary = self.fusion_modes.get("secondary", "")
        tertiary = self.fusion_modes.get("tertiary", "")

        engine = FusionEngine(primary, secondary, tertiary)
        protocol = engine.generate_protocol()

        if not protocol.get("success", False):
            self.log("FUSION", f"混搭验证失败: {protocol.get('error', '')}")
            return f"\n【混搭协议警告】{protocol.get('error', '')}\n建议修改混搭方案。"

        self.log("FUSION", f"混搭协议生成成功: {primary} + {secondary}")

        context = f"""
【Fusion Engine 混搭协议】
主模式（60%）：{primary}
副模式（30%）：{secondary}
调味模式（10%）：{tertiary if tertiary else '无'}

核心冲突统一：{protocol.get('core_conflict', '')}

节奏调整：
- 钩子位置：{protocol.get('rhythm_adjustment', {}).get('hook_position', '前500字')}
- 场景数/章：{protocol.get('rhythm_adjustment', {}).get('scene_count', 3)}

禁忌清单：
{chr(10).join('- ' + t for t in protocol.get('taboo_list', []))}
"""
        return context

    def _build_w0_input(self) -> str:
        """构建W0输入：一句话故事 + 用户想写的感觉 + 目标平台"""
        return f"""【用户的一句话故事/核心概念】
{self.chapter_task[:500] if self.chapter_task else '（用户未提供）'}

【用户想写的感觉/情绪基调】
题材：{self.genre}
模式：{self.mode}
作品暂定名：{self.title}

【用户的目标平台】
{self.platform}

【用户已有设定/人物】
{self.cold_storage[:800] if self.cold_storage else '（用户未提供详细设定）'}

请锁定这篇小说的核心主旨。不要写大纲、不要设计情节——只锚定"这篇小说到底要说什么"。
"""

    def _validate_w0_pass(self, w0_output: str, w0_json: dict = None) -> tuple:
        """
        W0 阻断型闸门 V2——结构化 JSON 校验优先，文本关键词回退。
        返回: (is_blocked: bool, reason: str)
        """
        # === 路径 A：结构化 JSON 校验（高准确率） ===
        if w0_json and isinstance(w0_json, dict) and "thesis" in w0_json:
            errors = []

            thesis = w0_json.get("thesis", "")
            if not thesis or len(thesis) < 5 or len(thesis) > 30:
                errors.append(f"一句话主旨长度异常（{len(thesis)}字），需5-25字")

            is_generic = w0_json.get("is_generic", False)
            if is_generic is True:
                generic_reason = w0_json.get("generic_reason", "")
                if not generic_reason or generic_reason in ("通过", "pass", ""):
                    errors.append("判定为万能主旨但未给出原因")
                else:
                    errors.append(f"主旨被判定为万能主旨: {generic_reason[:80]}")

            irreplaceability = w0_json.get("irreplaceability_score", 5)
            if isinstance(irreplaceability, (int, float)) and irreplaceability < 5:
                errors.append(f"不可替换性评分过低 ({irreplaceability}/10)——主旨太模糊，换掉主角名后依然成立")

            anchor = w0_json.get("anchor_scene", "")
            if not anchor or len(anchor) < 10:
                errors.append("情绪锚点画面为空或过短——需具体场景/动作/画面")
            elif any(kw in anchor for kw in ["最终", "终于", "慢慢", "逐渐", "开始"]):
                errors.append("情绪锚点画面过于抽象——应包含具体物品/动作/天气，而非情绪描述")

            counterintuitive = w0_json.get("counterintuitive_point", "")
            if not counterintuitive:
                errors.append("缺少反直觉成分——好的主旨需要'表面X实际Y'的转折")

            if errors:
                return True, " | ".join(errors)
            return False, ""

        # === 路径 B：文本关键词回退（低准确率，兜底） ===
        if not w0_output or len(w0_output) < 50:
            return True, "W0 输出为空或过短"

        output_lower = w0_output.lower()
        for marker in ["万能主旨", "主旨太模糊", "无法锚定", "无情绪锚点"]:
            if marker in w0_output:
                return True, f"W0 输出含否定标记: {marker}"

        return False, ""

    def _build_w1_input(self) -> str:
        """构建W1输入：从冷库提取 + 用户任务 + 可选的混搭协议 + RAG知识"""
        fusion_ctx = self._build_fusion_context()
        platform_profile = self._get_platform_profile()
        rag_ctx = self._rag_context("w1", f"设定预处理 {self.genre} {self.mode}")

        return f"""【全书冷库摘要】（由调度中枢筛选）
{self.cold_storage[:2000]}

【用户本章任务】
作品名：{self.title}
第{self.chapter_num}章任务：{self.chapter_task}
字数要求：{self.word_count}字
题材：{self.genre}
模式：{self.mode}
平台：{self.platform}
{fusion_ctx}
{platform_profile}
{rag_ctx}

【近3章已发生剧情】
（请用户补充，或调度中枢自动提取）
"""

    def _build_w2_input(self, hot_storage: str) -> str:
        """构建W2输入：热库 + 用户要求 + RAG知识"""
        rag_ctx = self._rag_context("w2", f"正文写作 {self.genre} 钩子设计")
        return f"""【本章热库】
{hot_storage}

【用户补充要求】
- 本章字数：{self.word_count}字
- 题材：{self.genre}
- 模式：{self.mode}
- 平台：{self.platform}
- 章末必须有强钩子
- 严格遵循热库约束，不能调用冷库设定
{rag_ctx}
"""

    def _build_w3_input(self, hot_storage: str, draft: str) -> str:
        """构建W3输入：热库 + 初稿 + RAG质检知识"""
        mode_note = ""
        mode_config = self.mode_config

        if mode_config:
            w3 = mode_config.get("w3_special", {})
            relax = w3.get("relax_checks", [])
            strict = w3.get("strict_checks", [])
            if relax:
                mode_note += f"\n【本模式放松检查项】\n{chr(10).join('- ' + r for r in relax)}\n"
            if strict:
                mode_note += f"\n【本模式严格检查项】\n{chr(10).join('- ' + s for s in strict)}\n"

        rag_ctx = self._rag_context("w3", f"逻辑质检 钩子检查 {self.mode}")

        return f"""【本章热库】
{hot_storage}

【正文初稿】
{draft}

【模式质检说明】
当前模式：{self.mode}
{mode_note}
{rag_ctx}
"""

    def _build_w4_input(self, skeleton: str) -> str:
        """构建W4输入：修正骨架 + 模式 + 字数 + RAG精修知识"""
        mode_config = self.mode_config
        w4_special = ""
        platform_param = ""

        if mode_config and "w4_special" in mode_config:
            w4 = mode_config["w4_special"]
            atmosphere = w4.get("atmosphere_techniques", [])
            if atmosphere:
                w4_special = "\n".join(f"- {a}" for a in atmosphere)
            shot_types = w4.get("shot_types", [])
            if shot_types:
                w4_special += "\n\n镜头语言优先级：\n" + "\n".join(f"- {s}" for s in shot_types)

        # 平台参数
        platform_profiles = load_json(KNOWLEDGE_DIR / "platform_writing_profiles.json")
        if platform_profiles:
            profile = platform_profiles.get("profiles", {}).get(self.platform, {})
            if profile:
                emotion = profile.get("emotion_delivery", {})
                platform_param = f"""
【平台精修参数】
平台：{profile.get('name', self.platform)}
情绪 delivery：{emotion.get('style', '标准型')}
段落限制：每段不超过{profile.get('paragraph_rules', {}).get('max_lines_per_para', 5)}行
对话占比：不低于{profile.get('dialogue_rules', {}).get('min_ratio', 0.3)*100}%
"""

        rag_ctx = self._rag_context("w4", f"文笔精修 氛围手法 {self.mode}")

        return f"""【修正后的骨架】
{skeleton}

【精修参数】
模式：{self.mode}
字数要求：{self.word_count}字
平台：{self.platform}
{platform_param}
【模式氛围手法参考】
{w4_special}
{rag_ctx}
"""

    def _run_conflict_check(self, results: dict) -> dict:
        """
        跨车间冲突校验——检测性控制的核心。
        在 W3 质检后运行，检查 W2(写作) 与 W4(精修) 的模块兼容性。
        基于 COSO 不相容岗位分离原则：W2 的技法选择必须与 W4 的技法选择兼容。
        """
        conflicts = []
        warnings_list = []

        # 加载冲突规则
        rules_file = MODES_DIR / "modules" / "conflict_rules.json"
        rules_data = {}
        if rules_file.exists():
            try:
                rules_data = json.loads(rules_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 检查跨车间约束
        w2_hooks = self.mode_config.get("w2_special", {}).get("forbidden_hooks", [])
        w4_techs = self.mode_config.get("w4_special", {}).get("atmosphere_techniques", [])
        w4_sensory = self.mode_config.get("w4_special", {}).get("sensory_priority", [])

        # 约束1: 治愈系 W2 禁用悬念钩子 → W4 不能用悬念式收尾
        if any("悬念" in h for h in w2_hooks):
            for tech in w4_techs:
                if any(kw in tech for kw in ["悬念", "冲突", "爆炸"]):
                    conflicts.append({
                        "rule": "cross_001",
                        "severity": "error",
                        "message": f"W2 禁用悬念钩子，但 W4 包含冲突性技法'{tech}'——钩子和收尾风格不可调和",
                        "resolution": "将 W4 切换为治愈系模块（healing_w4_polish）"
                    })

        # 约束2: 治愈系 W4 触觉优先 → W2 的动作描写必须支持触觉主导
        if w4_sensory and "触觉" in w4_sensory[0]:
            w2_style = self.mode_config.get("w2_special", {}).get("action_style", "")
            if "强节奏" in w2_style or "快速" in w2_style:
                warnings_list.append({
                    "rule": "sensory_priority_003",
                    "severity": "warning",
                    "message": "W4 触觉优先(慢镜头) vs W2 强节奏动作(快剪辑)——感官通道和叙事节奏存在张力",
                    "resolution": "W4 可在触觉描写中适当加快镜头切换频率"
                })

        # 约束3: 车间模式一致性检查
        w2_source = self.mode_config.get("w2_special", {}).get("source_mode",
                   self.mode_config.get("core", ""))
        w4_source = self.mode_config.get("w4_special", {}).get("source_mode", w2_source)
        # 从 mode_config 推断
        mode_core = self.mode_config.get("core", "")
        if "healing" in mode_core:
            # 治愈系强制约束
            w4_taboo = self.mode_config.get("w4_special", {}).get("taboo", [])
            has_ending_rule = any("悬念" in t for t in w4_taboo)
            if not has_ending_rule:
                warnings_list.append({
                    "rule": "ending_style_005",
                    "severity": "warning",
                    "message": "治愈系模式下 W4 应明确禁止悬念收尾——当前配置未检测到此约束",
                    "resolution": "确保 W4 的 taboo 列表包含'禁用以悬念收尾'"
                })

        # 汇总判定
        error_count = len(conflicts)
        blocked = error_count > 0

        return {
            "blocked": blocked,
            "reason": conflicts[0]["message"] if conflicts else "",
            "details": conflicts,
            "warnings": warnings_list,
            "errors": error_count,
        }

    def _get_platform_profile(self) -> str:
        """获取平台配置概要"""
        profiles = load_json(KNOWLEDGE_DIR / "platform_writing_profiles.json")
        profile = profiles.get("profiles", {}).get(self.platform, {})
        if not profile:
            return ""

        emotion = profile.get("emotion_delivery", {})
        return f"""
【平台配置：{profile.get('name', self.platform)}】
核心逻辑：{profile.get('core_logic', '')}
钩子位置：{profile.get('opening', {}).get('hook_position', '')}
情绪风格：{emotion.get('style', '')}
禁忌：{', '.join(profile.get('taboo', []))}
"""

    def run(self) -> dict:
        """执行五车间流水线 W0 -> W1 -> W2 -> W3 -> W4"""
        results = {}

        # ========== Step 0: 三库验证（如果有项目名） ==========
        if self.project_name:
            lib_validation = NovelLibraryValidator.validate(self.project_name)
            results["library_validation"] = lib_validation
            if not lib_validation["all_present"]:
                self.log("VALIDATION", f"三库不完整，缺少: {lib_validation['missing']}")
                # 不阻断，但记录警告
            else:
                self.log("VALIDATION", "三库验证通过")

        # ========== Step 0.5: W0 主旨锚定（阻断型闸门 V2——JSON结构化） ==========
        if self.w0_prompt:
            self.log("W0", "开始主旨锚定（JSON模式）...")
            w0_input = self._build_w0_input()
            w0_json, w0_raw = call_llm_json(
                system_prompt=self.w0_prompt,
                user_prompt=w0_input,
                temperature=0.3,
                max_tokens=800,
                workshop="w0",
            )
            results["w0_anchor"] = w0_raw
            results["w0_structured"] = w0_json if w0_json else None

            # === W0 结构化阻断校验 ===
            w0_blocked, w0_block_reason = self._validate_w0_pass(w0_raw, w0_json)
            if w0_blocked:
                self.log("W0", f"主旨锚定未通过——阻断后续车间: {w0_block_reason}")
                return {
                    "success": False,
                    "blocked_by": "W0",
                    "title": self.title,
                    "reason": w0_block_reason,
                    "w0_anchor": w0_raw,
                    "w0_structured": w0_json if w0_json else {},
                    "message": "主旨锚定校验未通过。请在 chapter_task 中修正你的故事概念后重试。",
                    "logs": self.logs,
                }

            w0_score = w0_json.get("irreplaceability_score", "?") if w0_json else "?"
            self.log("W0", f"主旨锚定校验通过 (不可替换性: {w0_score}/10)")
            # W0 通过 → 注入冷库
            if not self.cold_storage:
                self.cold_storage = ""
            self.cold_storage = f"【W0主旨锚定结果】\n{w0_raw}\n\n---\n{self.cold_storage}"
        else:
            self.log("W0", "W0 prompt 未加载，跳过主旨锚定")

        # ========== Step 1: W1 设定预处理 ==========
        self.log("W1", "开始设定预处理...")
        w1_input = self._build_w1_input()
        w1_result = call_llm(
            system_prompt=self.w1_prompt,
            user_prompt=w1_input,
            temperature=0.3,
            max_tokens=1500,
            workshop="w1",
        )
        results["w1_hot_storage"] = w1_result
        self.log("W1", "热库生成完成")

        # 提取热库内容（严格限流500字）
        hot_storage = w1_result[:500]

        # ========== Step 2: W2 正文初稿 ==========
        self.log("W2", "开始正文初稿...")
        w2_input = self._build_w2_input(hot_storage)
        w2_result = call_llm(
            system_prompt=self.w2_prompt,
            user_prompt=w2_input,
            temperature=0.4,
            max_tokens=4000,
            workshop="w2",
        )
        results["w2_draft"] = w2_result
        self.log("W2", "正文初稿完成")

        # === W2.5: 情绪曲线独立检测（LLM无关的第三方检测器） ===
        curve_result = detect_emotional_curve_quick(w2_result, target="healing" if "healing" in self.mode else "general")
        results["w2_curve_check"] = curve_result
        if curve_result["curve_valid"]:
            self.log("CURVE", f"情绪曲线通过: {curve_result['curve_type']} ({curve_result['score']}分)")
        else:
            self.log("CURVE", f"情绪曲线警告: {curve_result['curve_type']} ({curve_result['score']}分) — {curve_result['recommendation'][:60]}")

        # ========== Step 3: W3 逻辑质检 ==========
        self.log("W3", "开始逻辑质检...")
        w3_input = self._build_w3_input(hot_storage, w2_result)
        w3_result = call_llm(
            system_prompt=self.w3_prompt,
            user_prompt=w3_input,
            temperature=0.2,
            max_tokens=3000,
            workshop="w3",
        )
        results["w3_qc_report"] = w3_result
        self.log("W3", "质检完成")

        # 提取修正后的骨架
        if "无需修正" in w3_result:
            corrected_skeleton = w2_result
            self.log("W3", "质检通过，无需修正")
        else:
            corrected_skeleton = w3_result
            self.log("W3", "质检发现问题，已生成修正方案")

        # === W3.5: 跨车间冲突校验（检测性控制） ===
        conflict_result = self._run_conflict_check(results)
        if conflict_result["blocked"]:
            self.log("CONFLICT", f"跨车间冲突阻断W4: {conflict_result['reason']}")
            results["w3_conflict_check"] = conflict_result
            return {
                "success": False,
                "blocked_by": "CROSS_WORKSHOP_CONFLICT",
                "title": self.title,
                "chapter": self.chapter_num,
                "reason": conflict_result["reason"],
                "conflict_details": conflict_result["details"],
                "results": results,
                "logs": self.logs,
            }
        elif conflict_result["warnings"]:
            self.log("CONFLICT", f"跨车间冲突告警(不阻断): {len(conflict_result['warnings'])}项")
            results["w3_conflict_warnings"] = conflict_result["warnings"]
        else:
            self.log("CONFLICT", "跨车间冲突校验通过")

        # ========== Step 4: W4 文笔氛围精修 ==========
        self.log("W4", "开始文笔氛围精修...")
        w4_input = self._build_w4_input(corrected_skeleton)
        w4_result = call_llm(
            system_prompt=self.w4_prompt,
            user_prompt=w4_input,
            temperature=0.8,
            max_tokens=5000,
            workshop="w4",
        )
        results["w4_final_chapter"] = w4_result
        self.log("W4", "成品章节输出完成")

        return {
            "success": True,
            "title": self.title,
            "chapter": self.chapter_num,
            "mode": self.mode,
            "platform": self.platform,
            "results": results,
            "logs": self.logs,
        }


# ============ API路由 ============

@app.route("/api/v7/health", methods=["GET"])
def health():
    """健康检查 + 系统状态"""
    modes_files = list(MODES_DIR.glob("*.json"))
    return jsonify({
        "status": "ok",
        "version": "7.5",
        "litellm": HAS_LITELLM,
        "models": {k: WORKSHOP_MODELS.get(k, DEFAULT_MODEL) for k in ["w0","w1","w2","w3","w4"]},
        "workshops_loaded": [
            bool(load_workshop_prompt(i)) for i in range(0, 5)
        ],
        "modes_available": [
            p.stem for p in modes_files
        ],
    })


@app.route("/api/v7/rag/search", methods=["POST"])
def rag_search():
    """RAG知识检索接口"""
    data = request.get_json() or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"success": False, "error": "缺少query参数"}), 400

    top_k = data.get("top_k", 3)
    mode = data.get("mode")
    platform = data.get("platform")
    category = data.get("category")
    project_name = data.get("project_name")

    try:
        rag = get_rag(project_name)
        results = rag.search(
            query=query,
            top_k=top_k,
            mode=mode,
            platform=platform,
            category=category,
        )
        return jsonify({
            "success": True,
            "query": query,
            "count": len(results),
            "results": [
                {
                    "title": r.get("title"),
                    "category": r.get("category"),
                    "source": r.get("source"),
                    "score": r.get("score"),
                    "text": r.get("text"),
                }
                for r in results
            ],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v7/rag/stats", methods=["GET"])
def rag_stats():
    """RAG知识库统计"""
    try:
        rag = get_rag()
        return jsonify({
            "success": True,
            "stats": rag.get_stats(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v7/modes", methods=["GET"])
def get_modes():
    """获取所有模式配置"""
    modes = {}
    for mode_file in sorted(MODES_DIR.glob("*.json")):
        try:
            data = json.loads(mode_file.read_text(encoding="utf-8"))
            # 只返回元信息，不返回完整配置（体积太大）
            modes[mode_file.stem] = {
                "name": data.get("name", mode_file.stem),
                "description": data.get("description", "")[:100],
                "target_platforms": data.get("target_platforms", []),
                "fusion_compatibility": data.get("fusion_compatibility", {}),
            }
        except Exception:
            pass
    return jsonify(modes)


@app.route("/api/v7/mode/<mode_id>", methods=["GET"])
def get_mode_detail(mode_id):
    """获取单个模式的完整配置"""
    config = load_mode_config(mode_id)
    if not config:
        return jsonify({"success": False, "error": f"模式 '{mode_id}' 不存在"}), 404
    return jsonify(config)


@app.route("/api/v7/generate", methods=["POST"])
def generate_chapter():
    """主调度入口：执行完整四车间流水线"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    required = ["title", "chapter_num", "chapter_task"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"success": False, "error": f"缺少必填字段: {missing}"}), 400

    # 验证模式是否存在
    mode = data.get("mode", "general")
    if not load_mode_config(mode):
        return jsonify({
            "success": False,
            "error": f"模式 '{mode}' 不存在。可用模式: {[p.stem for p in MODES_DIR.glob('*.json')]}"
        }), 400

    scheduler = SchedulerV7(data)
    result = scheduler.run()
    return jsonify(result)


@app.route("/api/v7/fusion/check", methods=["POST"])
def fusion_check():
    """检查混搭兼容性"""
    data = request.get_json()
    primary = data.get("primary", "")
    secondary = data.get("secondary", "")
    tertiary = data.get("tertiary", "")

    if not primary:
        return jsonify({"success": False, "error": "请至少指定主模式"}), 400

    engine = FusionEngine(primary, secondary, tertiary)
    protocol = engine.generate_protocol()
    return jsonify(protocol)


@app.route("/api/v7/fusion/protocol", methods=["POST"])
def fusion_protocol():
    """生成完整混搭协议（调用LLM优化描述）"""
    data = request.get_json()
    primary = data.get("primary", "")
    secondary = data.get("secondary", "")
    tertiary = data.get("tertiary", "")

    if not primary:
        return jsonify({"success": False, "error": "请至少指定主模式"}), 400

    # 先用规则引擎生成协议骨架
    engine = FusionEngine(primary, secondary, tertiary)
    protocol = engine.generate_protocol()

    # 再用LLM优化自然语言描述
    if protocol.get("success", False):
        system_p = "你是盘古Fusion Engine的叙事顾问，精通题材混搭。"
        user_p = f"""请为一个混搭方案撰写创作指南：

主模式（60%）：{primary}
副模式（30%）：{secondary}
调味模式（10%）：{tertiary if tertiary else '无'}

核心冲突：{protocol.get('core_conflict', '')}
节奏参数：{json.dumps(protocol.get('rhythm_adjustment', {}), ensure_ascii=False)}

请输出：
1. 一段200字以内的"一句话卖点"（用于向读者推荐）
2. 3个核心创作原则
3. 1个可立即执行的章节结构示例
"""

        llm_guide = call_llm(
            system_prompt=system_p,
            user_prompt=user_p,
            temperature=0.7,
            max_tokens=2000,
            workshop="fusion",
        )
        protocol["llm_guide"] = llm_guide

    return jsonify(protocol)


@app.route("/api/v7/workshop/<int:workshop_id>", methods=["POST"])
def run_single_workshop(workshop_id):
    """单独调用某个车间（0-4），用于调试或分步执行"""
    if workshop_id not in [0, 1, 2, 3, 4]:
        return jsonify({"success": False, "error": "车间ID必须是0-4"}), 400

    workshop_map = {0: "w0", 1: "w1", 2: "w2", 3: "w3", 4: "w4"}
    data = request.get_json() or {}
    system_prompt = load_workshop_prompt(workshop_id)
    user_prompt = data.get("input", "")
    temperature = data.get("temperature", 0.5)
    max_tokens = data.get("max_tokens", 4000)

    if not system_prompt:
        return jsonify({"success": False, "error": f"车间{workshop_id}的system prompt未找到"}), 500

    result = call_llm(
        system_prompt, user_prompt,
        temperature=temperature, max_tokens=max_tokens,
        workshop=workshop_map[workshop_id],
    )
    return jsonify({"success": True, "workshop_id": workshop_id, "output": result})


@app.route("/api/v7/library/validate/<project_name>", methods=["GET"])
def validate_library(project_name):
    """验证指定项目的小说三库完整性"""
    import traceback
    try:
        result = NovelLibraryValidator.validate(project_name)
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] validate_library: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v7/library/list", methods=["GET"])
def list_libraries():
    """列出所有已有三库的项目"""
    import traceback
    try:
        if not LIBRARIES_DIR.exists():
            return jsonify({"projects": []})
        projects = []
        for d in LIBRARIES_DIR.iterdir():
            if d.is_dir():
                validation = NovelLibraryValidator.validate(d.name)
                projects.append({
                    "name": d.name,
                    "libraries_present": validation["all_present"],
                    "library_count": sum(
                        1 for v in validation["libraries"].values() if v.get("present")
                    ),
                })
        return jsonify({"projects": projects})
    except Exception as e:
        print(f"[ERROR] list_libraries: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v7/platforms", methods=["GET"])
def get_platforms():
    """获取平台配置信息"""
    profiles = load_json(KNOWLEDGE_DIR / "platform_writing_profiles.json")
    platforms = profiles.get("profiles", {})
    result = {}
    for key, profile in platforms.items():
        result[key] = {
            "name": profile.get("name", key),
            "core_logic": profile.get("core_logic", ""),
            "key_metric": profile.get("key_metric", ""),
            "chapter_length": profile.get("chapter_length", ""),
            "hook_position": profile.get("opening", {}).get("hook_position", ""),
        }
    return jsonify(result)


# ============ V7.5 可观测性 API ============

@app.route("/api/v7/observability/stats", methods=["GET"])
def observability_stats():
    """LLM 调用统计（成功率/P50/P95延迟/按模型分布）"""
    return jsonify({
        "success": True,
        **get_llm_stats(),
    })


@app.route("/api/v7/observability/performance", methods=["GET"])
def observability_performance():
    """性能监控指标"""
    return jsonify({
        "success": True,
        **get_performance_metrics(),
    })


@app.route("/api/v7/observability/health", methods=["GET"])
def observability_health():
    """系统健康状态"""
    return jsonify({
        "success": True,
        **get_health_status(),
    })


@app.route("/api/v7/tasks", methods=["GET"])
def tasks_list():
    """获取任务列表"""
    return jsonify({
        "success": True,
        "tasks": get_all_tasks(),
        "stats": get_task_stats(),
    })


@app.route("/api/v7/tasks/<task_id>", methods=["GET"])
def task_status(task_id):
    """获取任务状态"""
    status = get_task_status(task_id)
    if status:
        return jsonify({"success": True, "task": status})
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route("/api/v7/dashboard", methods=["GET"])
def dashboard():
    """综合仪表盘 - 所有监控数据"""
    return jsonify({
        "success": True,
        "llm_stats": get_llm_stats(),
        "performance": get_performance_metrics(),
        "health": get_health_status(),
        "tasks": {
            "list": get_all_tasks()[:5],
            "stats": get_task_stats(),
        },
    })


@app.route("/api/v7/observability/score", methods=["POST"])
def observability_score():
    """治愈系 8 项指标自动评分（支持自定义权重）"""
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短（<200字）"}), 400
    custom_weights = data.get("weights", None)
    result = score_text(text, custom_weights)
    return jsonify({"success": True, **result})


@app.route("/api/v7/observability/curve", methods=["POST"])
def observability_curve():
    """
    情绪曲线确定性检测——独立于 LLM 的第三方检测器。
    Body: {"text": "...", "target": "healing"}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    target = data.get("target", "healing")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短（<200字）"}), 400
    quick = data.get("quick", False)
    if quick:
        result = detect_emotional_curve_quick(text, target)
    else:
        result = detect_emotional_curve(text, target)
    return jsonify({"success": True, **result})


@app.route("/api/v7/observability/style", methods=["POST"])
def observability_style():
    """风格指纹检测——12维风格向量"""
    data = request.get_json() or {}
    text = data.get("text", "")
    target = data.get("target", "healing")
    mode = data.get("mode", "full")
    if not text or len(text) < 100:
        return jsonify({"success": False, "error": "文本太短"}), 400
    if mode == "quick":
        result = check_style_consistency(text, target)
    else:
        fp = extract_style_fingerprint(text)
        result = StyleFingerprint.compare(fp, target) if "error" not in fp else fp
    return jsonify({"success": True, "algorithm": "Stylometry (2024)", **result})


@app.route("/api/v7/observability/arc", methods=["POST"])
def observability_arc():
    """
    人物弧光检测——英雄旅程8阶段状态机。
    Body: {"text": "...", "chapter_num": 5, "total_chapters": 20}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    chapter = data.get("chapter_num", 5)
    total = data.get("total_chapters", 20)
    if not text or len(text) < 100:
        return jsonify({"success": False, "error": "文本太短"}), 400
    result = HeroArcDetector.analyze(text, chapter, total)
    return jsonify({"success": True, "algorithm": "HeroArc State Machine", **result})


@app.route("/api/v7/observability/shonen", methods=["POST"])
def observability_shonen():
    """
    热血格斗浓度检测——JUMP五段结构+热血台词+战斗短句。
    Body: {"text": "..."}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 100:
        return jsonify({"success": False, "error": "文本太短"}), 400
    result = ShonenStyleDetector.analyze(text)
    return jsonify({"success": True, "algorithm": "Shonen Style Detector", **result})


@app.route("/api/v7/observability/tension", methods=["POST"])
def observability_tension():
    """叙事张力曲线"""
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短"}), 400
    result = TensionCurveGenerator.generate(text)
    return jsonify({"success": True, "algorithm": "pyliwc Tension Curve", **result})


@app.route("/api/v7/observability/audit", methods=["POST"])
def observability_audit():
    """Giskard跨模块一致性审计"""
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短"}), 400
    arc = HeroArcDetector.analyze(text, data.get("chapter_num", 5), data.get("total_chapters", 20))
    shonen = ShonenStyleDetector.analyze(text)
    tension = TensionCurveGenerator.generate(text)
    audit = GiskardAuditor.audit(arc, shonen, tension)
    return jsonify({"success": True, "algorithm": "Giskard Audit", **audit})


@app.route("/api/v7/inkos/truth", methods=["GET", "POST"])
def inkos_truth():
    """InkOS全局真相文件系统"""
    if request.method == "GET":
        project = request.args.get("project", ".")
        result = InkOS.load_truth(project if project != "." else None)
        return jsonify({"success": True, **result})
    else:
        data = request.get_json() or {}
        text = data.get("text", "")
        project = data.get("project", ".")
        chapter = data.get("chapter_num", 1)
        truth = InkOS.load_truth(project if project != "." else None)
        check = InkOS.check_consistency(text, truth, chapter)
        return jsonify({"success": True, **check})


@app.route("/api/v7/observability/pacing", methods=["POST"])
def observability_pacing():
    """PacingChecker跨章节奏均衡"""
    data = request.get_json() or {}
    chapters = data.get("chapters", {})
    if not chapters or len(chapters) < 2:
        return jsonify({"success": False, "error": "需要至少2章文本"}), 400
    result = PacingChecker.analyze_chapter_set(chapters)
    return jsonify({"success": True, "algorithm": "PacingChecker", **result})


# ============ V7.5 AutoRewrite 闭环流水线 API ============

@app.route("/api/v7/inspect", methods=["POST"])
def inspect_chapter():
    """
    全量质检——37项检测器批量运行，输出结构化缺陷JSON。
    Body: {"text": "...", "chapter_num": 1, "total_chapters": 50}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短"}), 400
    result = AutoRewriteEngine.full_inspection(
        text, data.get("chapter_num", 1), data.get("total_chapters", 50))
    return jsonify({"success": True, **result})


@app.route("/api/v7/rewrite/prompt", methods=["POST"])
def rewrite_constrained_prompt():
    """
    生成带评分约束的系统提示词——生成前调用，注入评分规则到prompt。
    Body: {"base_prompt": "...", "mode": "chinese_shonen", "chapter_num": 1,
           "total_chapters": 50, "project": "桃木刀"}
    """
    data = request.get_json() or {}
    base = data.get("base_prompt", "你是一个小说写作助手。")
    mode = data.get("mode", "chinese_shonen")
    project = data.get("project", "")
    # 加载 InkOS 真相文档
    truth = {}
    if project:
        inkos = InkOS.load_truth(BASE_DIR / "novel_libraries" / project)
        truth = inkos.get("docs", {})
    constrained = AutoRewriteEngine.generate_constrained_prompt(
        base, mode, data.get("chapter_num", 1),
        data.get("total_chapters", 50), truth)
    return jsonify({"success": True, "constrained_prompt": constrained})


@app.route("/api/v7/rewrite/build_fix", methods=["POST"])
def rewrite_build_fix():
    """
    根据缺陷清单生成精准返修指令。
    Body: {"text": "...", "inspection": {...}}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    inspection = data.get("inspection", {})
    if not text or not inspection:
        return jsonify({"success": False, "error": "需要 text 和 inspection"}), 400
    rewrite_prompt = AutoRewriteEngine.build_rewrite_prompt(text, inspection)
    return jsonify({"success": True, "rewrite_prompt": rewrite_prompt})


@app.route("/api/v7/workflow/full", methods=["POST"])
def workflow_full():
    """
    完整工作流总控——固化标准流程。
    Body: {"concept":"...", "draft_text":"...", "chapter_num":1, "total_chapters":50,
           "mode":"chinese_shonen", "project":"桃木刀", "llm_configured":false,
           "base_prompt":"...", "max_auto_round":3, "final_check_round":3}
    """
    data = request.get_json() or {}
    draft_text = data.get("draft_text", "")
    concept = data.get("concept", "")
    llm_configured = data.get("llm_configured", False)

    # LLM配置
    if llm_configured:
        LLMAdapter.configure(
            model=data.get("model", "deepseek/deepseek-chat"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
        )

    result = WorkflowRunner.run_full_pipeline(
        concept=concept, draft_text=draft_text,
        chapter_num=data.get("chapter_num", 1),
        total_chapters=data.get("total_chapters", 50),
        mode=data.get("mode", "chinese_shonen"),
        project=data.get("project", ""),
        base_prompt=data.get("base_prompt", ""),
        max_auto_round=data.get("max_auto_round", 3),
        final_check_round=data.get("final_check_round", 3),
        llm_configured=llm_configured and HAS_LLM_ADAPTER,
    )
    result["has_llm_adapter"] = HAS_LLM_ADAPTER
    result["llm_configured"] = llm_configured
    return jsonify({"success": True, **result})


@app.route("/api/v7/workflow/record/<record_id>", methods=["GET"])
def workflow_record(record_id):
    """查询工作流历史版本快照"""
    snap = load_snapshot(record_id)
    if "error" in snap:
        return jsonify({"success": False, "error": snap["error"]}), 404
    return jsonify({"success": True, "snapshot": snap})


# ============ V7.5 MemoryChecker 记忆管控 API ============

@app.route("/api/v7/memory/ingest", methods=["POST"])
def memory_ingest():
    """
    抽取项目全书设定到记忆库。
    Body: {"project": "桃木刀"}
    """
    data = request.get_json() or {}
    project = data.get("project", "")
    if not project:
        return jsonify({"success": False, "error": "需要 project"}), 400
    proj_dir = BASE_DIR / "novel_libraries" / project
    result = MemoryChecker.ingest_project(str(proj_dir))
    return jsonify({"success": True, **result})


@app.route("/api/v7/memory/constraints", methods=["GET"])
def memory_constraints():
    """
    获取设定约束块——注入到系统提示词中。
    ?project=桃木刀
    """
    project = request.args.get("project", "")
    if not project:
        return jsonify({"success": False, "error": "需要 project 参数"}), 400
    proj_dir = BASE_DIR / "novel_libraries" / project
    constraints = MemoryChecker.build_constraint_block(str(proj_dir))
    return jsonify({"success": True, "constraints": constraints,
                    "length": len(constraints)})


@app.route("/api/v7/memory/precheck", methods=["POST"])
def memory_precheck():
    """
    生成前预检——前置拦截设定冲突。
    Body: {"text": "...", "project": "桃木刀", "mode": "inkos"}
    mode=inkos: 运行全部42条InkOS规则
    mode=basic: 仅运行基础预检
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    project = data.get("project", "")
    mode = data.get("mode", "inkos")
    if not text or not project:
        return jsonify({"success": False, "error": "需要 text 和 project"}), 400
    proj_dir = str(BASE_DIR / "novel_libraries" / project)
    if mode == "inkos":
        result = MemoryChecker.run_inkos_checks(text, proj_dir)
    else:
        result = MemoryChecker.precheck(text, proj_dir)
    return jsonify({"success": True, "mode": mode, **result})


@app.route("/api/v7/memory/trace", methods=["GET"])
def memory_trace():
    """
    伏笔溯源——追踪关键词在全书的来源和演变。
    ?project=桃木刀&keyword=秀
    """
    project = request.args.get("project", "")
    keyword = request.args.get("keyword", "")
    if not project or not keyword:
        return jsonify({"success": False, "error": "需要 project 和 keyword"}), 400
    proj_dir = str(BASE_DIR / "novel_libraries" / project)
    result = MemoryChecker.trace_foreshadowing(keyword, proj_dir)
    return jsonify({"success": True, **result})


@app.route("/api/v7/diff/check", methods=["POST"])
def diff_check():
    """
    语义差异校验——检测LLM是否敷衍改写。
    Body: {"before":"...", "after":"...", "target_section":"..."}
    """
    data = request.get_json() or {}
    before = data.get("before", "")
    after = data.get("after", "")
    target = data.get("target_section", "")
    if not before or not after:
        return jsonify({"success": False, "error": "需要 before 和 after"}), 400
    result = SemanticDiffChecker.compare(before, after, target)
    return jsonify({"success": True, **result})


@app.route("/api/v7/observability/heatmap", methods=["POST"])
def observability_heatmap():
    """
    四线热力图数据——弧光/热血/张力/战斗密度+伏笔标记。
    Body: {"chapters": {"1": "第一章文本", "2": "第二章文本", ...}}
    返回 ECharts 可直接渲染的多系列数据。
    """
    data = request.get_json() or {}
    chapters = data.get("chapters", {})
    if not chapters:
        return jsonify({"success": False, "error": "需要 chapters 字段"}), 400
    result = HeatmapGenerator.generate(chapters)
    return jsonify({"success": True, **result})


@app.route("/api/v7/observability/weights", methods=["GET", "POST"])
def observability_weights():
    """GET: 获取当前评分权重  POST: 保存自定义权重"""
    if request.method == "GET":
        saved = load_custom_weights()
        defaults = {k: v["weight"] for k, v in score_metrics().items()}
        return jsonify({"success": True, "weights": saved or defaults, "is_custom": bool(saved)})
    else:
        data = request.get_json() or {}
        weights = data.get("weights", {})
        if not weights:
            return jsonify({"success": False, "error": "缺少 weights 字段"}), 400
        ok = save_custom_weights(weights)
        return jsonify({"success": ok, "weights": weights})


@app.route("/api/v7/observability/metrics", methods=["GET"])
def observability_metrics():
    """返回 8 项评分指标说明"""
    return jsonify({"success": True, "metrics": score_metrics()})


@app.route("/api/v7/report", methods=["GET"])
def export_iteration_report():
    """
    一键导出迭代报告——汇总 LLM 调用、RAG 状态、评分数据。
    记录版本能力提升曲线。
    """
    try:
        tracer = get_tracer()
        rag = get_rag()

        # LLM 统计
        llm_stats = tracer.get_stats(window_minutes=10080)  # 7天

        # RAG 统计
        rag_stats = rag.get_stats()

        # 加载模块信息
        modules_dir = MODES_DIR / "modules"
        index_data = {}
        if (modules_dir / "index.json").exists():
            index_data = json.loads((modules_dir / "index.json").read_text(encoding="utf-8"))

        # 权重
        weights = load_custom_weights()
        defaults = {k: v["weight"] for k, v in score_metrics().items()}

        # 评分统计（从日志目录读取评分记录）
        score_logs = []
        score_dir = BASE_DIR / "logs"
        for log_file in sorted(score_dir.glob("llm_calls_*.jsonl")):
            try:
                lines = log_file.read_text(encoding="utf-8").strip().split("\n")
                score_logs.append({"date": log_file.stem.replace("llm_calls_", ""),
                                   "calls": len(lines)})
            except Exception:
                pass

        report = {
            "report_title": "盘古V7.5 迭代报告",
            "generated_at": datetime.now().isoformat(),
            "version": "7.5",
            "sections": {
                "llm_routing": {
                    "title": "LLM 路由高可用",
                    "stats": llm_stats,
                    "models_active": list(llm_stats.get("by_model", {}).keys()),
                },
                "rag_search": {
                    "title": "RAG 向量检索",
                    "stats": rag_stats,
                },
                "scoring_system": {
                    "title": "治愈系自动评分",
                    "weights": weights or defaults,
                    "is_custom": bool(weights),
                    "metrics_defined": len(defaults),
                },
                "modules": {
                    "title": "可插拔模块库",
                    "available_modules": {
                        ws: [m["id"] for m in mods]
                        for ws, mods in index_data.get("modules", {}).items()
                    },
                    "assembly_examples": len(index_data.get("assembly_examples", [])),
                },
                "deployment": {
                    "title": "部署状态",
                    "has_litellm": HAS_LITELLM,
                    "port": 5001,
                },
            },
            "call_history": score_logs,
        }

        return jsonify({"success": True, "report": report})
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e),
                        "detail": traceback.format_exc()}), 500


# ============ V7.5 模块化管理 API ============

@app.route("/api/v7/modules", methods=["GET"])
def list_modules():
    """列出所有可插拔车间模块"""
    modules_dir = MODES_DIR / "modules"
    index_file = modules_dir / "index.json"
    if index_file.exists():
        return jsonify(json.loads(index_file.read_text(encoding="utf-8")))
    return jsonify({"modules": {}, "message": "模块目录不存在"})


@app.route("/api/v7/modules/<workshop>", methods=["GET"])
def get_module(workshop):
    """获取指定车间的可用模块列表"""
    modules_dir = MODES_DIR / "modules"
    files = list(modules_dir.glob(f"{workshop}_*.json"))
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({"id": data.get("module_id"), "name": data.get("name"),
                            "description": data.get("description"),
                            "compatible_styles": data.get("compatible_styles", [])})
        except Exception:
            pass
    return jsonify({"workshop": workshop, "modules": results})


@app.route("/api/v7/modules/validate", methods=["POST"])
def validate_module_assembly():
    """
    校验模块混搭方案的冲突。
    Body: {
      "assembly": {
        "w1": "healing_w1_setup",
        "w2": "healing_w2_draft",
        "w3": "healing_w3_qc",
        "w4": "healing_w4_polish"
      }
    }
    """
    data = request.get_json() or {}
    assembly = data.get("assembly", {})

    if not assembly:
        return jsonify({"success": False, "error": "缺少 assembly 字段"}), 400

    # 加载模块
    modules_dir = MODES_DIR / "modules"
    loaded = {}
    for ws, module_id in assembly.items():
        # 尝试找到对应的模块文件
        candidates = list(modules_dir.glob(f"{ws}_*.json"))
        found = None
        for c in candidates:
            try:
                d = json.loads(c.read_text(encoding="utf-8"))
                if d.get("module_id") == module_id:
                    found = d
                    break
            except Exception:
                pass
        if found:
            loaded[ws] = found
        else:
            return jsonify({"success": False,
                            "error": f"模块 '{module_id}' (车间{ws}) 不存在"}), 404

    # 加载冲突规则
    rules_file = modules_dir / "conflict_rules.json"
    rules_data = {}
    if rules_file.exists():
        rules_data = json.loads(rules_file.read_text(encoding="utf-8"))

    # 执行校验
    issues = []
    matrix = rules_data.get("compatibility_matrix", {})

    # 1. 跨车间约束检查
    for constraint in rules_data.get("cross_workshop_constraints", []):
        if "healing" in constraint.get("rule", "") and "w2" in constraint.get("rule", ""):
            w2_mode = loaded.get("w2", {}).get("source_mode", "")
            w4_mode = loaded.get("w4", {}).get("source_mode", "")
            if w2_mode == "healing_life_v2" and "healing" not in w4_mode:
                issues.append({
                    "severity": "error",
                    "rule": constraint["id"],
                    "message": constraint["description"],
                    "resolution": "将W4切换为治愈系模块"
                })

    # 2. 风格兼容性矩阵检查
    styles_used = set()
    for ws, mod in loaded.items():
        src = mod.get("source_mode", "")
        if src:
            styles_used.add(src)

    if len(styles_used) > 1:
        style_scores = {}
        for s1 in styles_used:
            compat = matrix.get(s1, {})
            for s2 in styles_used:
                if s1 < s2:
                    score = compat.get(s2, 2)
                    style_scores[f"{s1}+{s2}"] = score
                    if score <= 1:
                        issues.append({
                            "severity": "warning" if score == 1 else "error",
                            "rule": "compatibility_matrix",
                            "message": f"风格 '{s1}' 和 '{s2}' 的兼容性评分为 {score}/3",
                            "resolution": "建议使用同一风格的所有车间，或选择更高兼容性的配对"
                        })

    # 3. 钩子类型冲突检查 (rule: hook_incompat_001)
    w2_forbidden = loaded.get("w2", {}).get("forbidden_hooks", [])
    if w2_forbidden:
        for ws, mod in loaded.items():
            if ws == "w2":
                continue
            mod_hooks = mod.get("hook_types", [])
            forbidden_set = set(h.lower() for h in w2_forbidden)
            for h in mod_hooks:
                for keyword in ["悬念", "危机", "信息缺口"]:
                    if keyword in h and any(keyword in f for f in forbidden_set):
                        issues.append({
                            "severity": "error",
                            "rule": "hook_incompat_001",
                            "message": f"W2禁用钩子类型含'{keyword}'，与{ws.upper()}模块的钩子类型'{h}'冲突",
                            "resolution": "以W2的forbidden_hooks为准，禁用冲突类型"
                        })

    # 4. 结尾风格冲突 (rule: ending_style_005)
    w4_techs = loaded.get("w4", {}).get("atmosphere_techniques", [])
    w2_fh = [h.lower() for h in w2_forbidden]
    has_healing_ending = any("余韵" in t or "画面" in t or "物件" in t for t in w4_techs)
    has_suspense_forbidden = any("悬念" in f for f in w2_fh)
    if has_healing_ending and not has_suspense_forbidden:
        issues.append({
            "severity": "info",
            "rule": "ending_style_005",
            "message": "W4使用治愈系余韵收尾，但W2未明确禁用悬念钩子——确认风格一致性",
            "resolution": "如主模式为治愈系，建议W2明确禁用悬念钩子"
        })

    # 汇总
    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")
    info_count = sum(1 for i in issues if i["severity"] == "info")

    return jsonify({
        "success": True,
        "assembly": assembly,
        "styles_detected": list(styles_used),
        "valid": error_count == 0,
        "issues": {
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
            "total": len(issues),
        },
        "details": issues,
    })


@app.route("/api/v7/anchor", methods=["POST"])
def anchor_theme():
    """
    W0·主旨锚定（独立入口——推荐在写第一章之前调用）
    Body: {"idea": "一句话概念", "feeling": "想写的感觉",
           "platform": "douban", "mode": "healing_life_v2"}
    """
    data = request.get_json() or {}
    idea = data.get("idea", "")
    feeling = data.get("feeling", "")
    platform = data.get("platform", "douban")
    mode = data.get("mode", "healing_life_v2")

    if not idea:
        return jsonify({"success": False, "error": "至少需要 idea 字段——一句话描述你想写什么"}), 400

    w0_prompt = load_workshop_prompt(0)
    if not w0_prompt:
        return jsonify({"success": False, "error": "W0 system prompt 未找到"}), 500

    user_prompt = f"""【用户的一句话故事/核心概念】
{idea}

【用户想写的感觉/情绪基调】
{feeling if feeling else '（用户未指定）'}

【用户的目标平台】
{platform}

【模式】
{mode}

请锁定这篇小说的核心主旨。"""

    result = call_llm(system_prompt=w0_prompt, user_prompt=user_prompt,
                      temperature=0.3, max_tokens=800, workshop="w0")
    return jsonify({"success": True, "w0_anchor": result})


# ============ V7.5 超参自动调优 API ============

@app.route("/api/v7/optimize", methods=["POST"])
def optimize_workshop():
    """
    Optuna 贝叶斯超参优化。
    Body: {"workshop": "w2", "trials": 20, "text": "..."}
    返回最优 temperature/max_tokens 组合。
    """
    try:
        from hyperopt import WorkshopHyperOptimizer
    except ImportError:
        return jsonify({"success": False,
                        "error": "hyperopt 模块未找到"}), 500

    data = request.get_json() or {}
    workshop = data.get("workshop", "all")
    trials = min(data.get("trials", 20), 100)
    text = data.get("text", "")

    texts = [text] if text and len(text) >= 200 else []
    optimizer = WorkshopHyperOptimizer(sample_texts=texts)

    if workshop == "all":
        result = optimizer.optimize_multi_workshop(n_trials_per=trials)
    else:
        result = optimizer.optimize_temperature(workshop=workshop, n_trials=trials)

    return jsonify({"success": True, **result})


# ============ V7.5 风格样本库 API ============

@app.route("/api/v7/style/profiles", methods=["GET"])
def style_list_profiles():
    """列出所有已保存的风格配置"""
    return jsonify({"success": True, "profiles": StyleProfileManager.list_profiles()})


@app.route("/api/v7/style/create", methods=["POST"])
def style_create_profile():
    """
    从样本文本创建风格配置。
    Body: {"name": "my_style", "text": "...", "description": "...", "author": "..."}
    """
    data = request.get_json() or {}
    name = data.get("name", "")
    text = data.get("text", "")
    if not name or not text:
        return jsonify({"success": False, "error": "需要 name 和 text"}), 400
    result = StyleProfileManager.create_profile(
        name=name, sample_text=text,
        description=data.get("description", ""),
        author=data.get("author", "unknown"),
    )
    return jsonify(result)


@app.route("/api/v7/style/compare", methods=["POST"])
def style_compare_profile():
    """
    将文本与已保存风格比对。
    Body: {"text": "...", "profile": "healing_life"}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    profile = data.get("profile", "")
    if not text or not profile:
        return jsonify({"success": False, "error": "需要 text 和 profile"}), 400
    result = StyleProfileManager.compare_to_profile(text, profile)
    return jsonify(result)


@app.route("/api/v7/style/<name>", methods=["GET", "DELETE"])
def style_profile_detail(name):
    """GET: 加载风格配置  DELETE: 删除"""
    if request.method == "DELETE":
        return jsonify(StyleProfileManager.delete_profile(name))
    return jsonify(StyleProfileManager.load_profile(name))


# ============ V7.5 全球前沿算法 API ============

@app.route("/api/v7/textgrad/refine", methods=["POST"])
def textgrad_refine_api():
    """
    TextGrad (Stanford 2024): 用评分反馈反向传播优化文本。
    Body: {"text": "...", "target": "healing", "target_score": 80, "max_iter": 5}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text or len(text) < 200:
        return jsonify({"success": False, "error": "文本太短"}), 400

    target_mode = data.get("target", "healing")
    target_score = data.get("target_score", 80)
    max_iter = min(data.get("max_iter", 5), 10)

    # 用盘古自己的 call_llm 作为修正器
    def llm_caller(**kwargs):
        return call_llm(**kwargs)

    result = textgrad_refine(
        text=text, llm_caller=llm_caller,
        target_mode=target_mode, target_score=target_score,
        max_iter=max_iter
    )
    return jsonify({"success": True, "algorithm": "TextGrad (Stanford 2024)", **result})


@app.route("/api/v7/dspy/compile", methods=["POST"])
def dspy_compile_api():
    """
    DSPy (Stanford ICLR 2024): MIPRO自动优化车间prompt。
    Body: {"mode": "healing", "trials": 30}
    """
    try:
        from dspy_compile import PanguDSPyCompiler
    except ImportError:
        return jsonify({"success": False,
                        "error": "dspy_compile 模块未找到或 dspy 未安装"}), 500

    data = request.get_json() or {}
    mode = data.get("mode", "healing")
    trials = min(data.get("trials", 30), 100)

    compiler = PanguDSPyCompiler(mode=mode)
    result = compiler.compile(trials=trials)

    if data.get("export", False):
        export_result = compiler.export_prompts()
        result["export"] = export_result

    return jsonify({"success": True, "algorithm": "DSPy MIPRO (Stanford ICLR 2024)", **result})


@app.route("/api/v7/graphrag/query", methods=["POST"])
def graphrag_query_api():
    """
    GraphRAG (Microsoft 2024): 实体图检索——跨章节人物/物件/事件查询。
    Body: {"project": "下北泽的雨天", "entity": "林柚", "depth": 2}
    或:   {"project": "下北泽的雨天", "entity_a": "林柚", "entity_b": "透明伞"}
    """
    data = request.get_json() or {}
    project = data.get("project", "")

    if not project:
        return jsonify({"success": False, "error": "需要 project 字段"}), 400

    try:
        gr = build_graph_from_project(project)
    except Exception as e:
        return jsonify({"success": False, "error": f"图构建失败: {e}"}), 500

    # 实体查询
    if "entity" in data:
        entity = data["entity"]
        depth = data.get("depth", 2)
        result = gr.query_entity(entity, depth=depth)
        return jsonify({"success": True,
                        "algorithm": "GraphRAG (Microsoft 2024)",
                        "query_type": "entity", **result})

    # 关系查询
    if "entity_a" in data and "entity_b" in data:
        result = gr.query_relation(data["entity_a"], data["entity_b"])
        return jsonify({"success": True,
                        "algorithm": "GraphRAG (Microsoft 2024)",
                        "query_type": "relation", **result})

    return jsonify({"success": False,
                    "error": "需要 entity（实体查询）或 entity_a+entity_b（关系查询）"}), 400


# ============ 写作状态管理器（嵌入版） ============

class WritingStateManager:
    """章节写作状态追踪器——自动记忆、自动注入、自动更新"""

    PROJECTS_DIR = BASE_DIR / "novel_libraries"

    @staticmethod
    def get_state_path(project_name: str) -> Path:
        return WritingStateManager.PROJECTS_DIR / project_name / "_writing_state.json"

    @staticmethod
    def load_state(project_name: str) -> dict:
        """加载项目写作状态"""
        path = WritingStateManager.get_state_path(project_name)
        if path.exists():
            return load_json(path)
        return {
            "已完成章节": [], "已使用物件": [], "已用释放方式": [],
            "主角状态": "初期", "章节摘要": {},
            "物件追踪": {}, "情绪蓄力值": 0, "本周释放循环位置": 0,
            "已用无用细节": []
        }

    @staticmethod
    def save_state(project_name: str, state: dict):
        """保存写作状态"""
        path = WritingStateManager.get_state_path(project_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    @staticmethod
    def scan_chapter(project_dir: Path, state: dict):
        """扫描已完成的章节，提取状态"""
        chapters = sorted([f for f in os.listdir(project_dir)
                          if f.endswith('.md') and f.startswith('第') and not f.startswith('_')])
        state["已完成章节"] = chapters
        return chapters

    @staticmethod
    def extract_objects(text: str) -> list:
        objs = ['裙子','白衬衫','手机','通讯录','保温杯','护手霜','工牌','婚纱','钥匙',
                '煎饺','热水','床单','画册','咖啡','书签','明信片','花','伞','毛衣','茶']
        return list(set(o for o in objs if o in text))

    @staticmethod
    def extract_release_methods(text: str) -> list:
        methods = []
        if '哭' in text and ('咬' in text or '手背' in text): methods.append("善意崩溃·咬手背")
        if '煎饺' in text and '哭' in text: methods.append("食物触发·煎饺")
        if '暴风雨' in text and ('说' in text or '话' in text): methods.append("诉说型·黑暗")
        if '删除' in text or '号码' in text: methods.append("无声的胜利·删除")
        if '撑懒腰' in text or '伸了' in text: methods.append("无声的胜利·动作")
        return methods

    @staticmethod
    def extract_emotional_state(text: str, chapter_num: int) -> str:
        last_300 = text[-300:]
        if '没有哭' in last_300 or '一滴眼泪也没有' in last_300:
            return "压着,但没有哭出来"
        if '伸了一个懒腰' in last_300 or '撑懒腰' in last_300:
            return "已释放,轻松"
        if '哭' in last_300 or '泪' in last_300:
            return "刚释放过,脆弱"
        if '笑' in last_300:
            return "恢复中,有笑意"
        if '睡' in last_300:
            return "疲惫但暂时安顿"
        if chapter_num <= 5:
            return "绷着"
        return "过渡中"

    @staticmethod
    def extract_useless_details(text: str) -> list:
        """提取'无用但让世界变活'的细节"""
        details = []
        if '鸽子' in text or '翅膀' in text: details.append("鸽子飞过")
        if '电视' in text or '综艺' in text: details.append("隔壁电视声")
        if '百合' in text or '花枯萎' in text: details.append("枯萎的花")
        if '复印' in text or '卡纸' in text: details.append("办公室日常")
        if '自动贩卖机' in text or '便利店灯光' in text: details.append("贩卖机/便利店光")
        if '垃圾车' in text or '回收' in text: details.append("垃圾车声音")
        if '电梯' in text: details.append("电梯")
        if '狗' in text or '遛狗' in text: details.append("狗")
        return details

    @staticmethod
    def get_emotional_stack_level(state: dict) -> int:
        """计算当前情绪蓄力值（半沢式stacking）"""
        releases_used = len(state.get("已用释放方式", []))
        chapters_done = len(state.get("已完成章节", []))
        # 蓄力值 = 已完成章节数 - 已释放次数*2
        # 值越高，越需要释放
        return max(0, chapters_done - releases_used * 2)

    @staticmethod
    def get_release_cycle_position(chapter_num: int) -> str:
        """判断当前在半沢式循环中的位置"""
        cycle_pos = chapter_num % 4
        if cycle_pos == 1: return "压抑期(堆积)"
        elif cycle_pos == 2: return "蓄力期(准备)"
        elif cycle_pos == 3: return "蓄力后期(即将到达顶点)"
        else: return "释放期"  # 4的倍数

    @staticmethod
    def update_state(project_name: str, project_dir: Path, chapter_num: int, chapter_text: str):
        """写完一章后自动更新状态"""
        state = WritingStateManager.load_state(project_name)
        WritingStateManager.scan_chapter(project_dir, state)

        # 提取物件
        objs = WritingStateManager.extract_objects(chapter_text)
        state["已使用物件"] = list(set(state.get("已使用物件", []) + objs))

        # 物件追踪（坂元式——同一个物件出现次数）
        if "物件追踪" not in state:
            state["物件追踪"] = {}
        for o in objs:
            state["物件追踪"][o] = state["物件追踪"].get(o, 0) + 1

        # 提取释放方式
        methods = WritingStateManager.extract_release_methods(chapter_text)
        state["已用释放方式"] = list(set(state.get("已用释放方式", []) + methods))

        # 提取无用细节
        details = WritingStateManager.extract_useless_details(chapter_text)
        state["已用无用细节"] = list(set(state.get("已用无用细节", []) + details))

        # 更新主角状态
        state["主角状态"] = WritingStateManager.extract_emotional_state(chapter_text, chapter_num)

        # 更新情绪蓄力值
        state["情绪蓄力值"] = WritingStateManager.get_emotional_stack_level(state)

        # 更新循环位置
        state["本周释放循环位置"] = chapter_num % 4

        # 保存章节摘要
        summary = chapter_text[:100].replace('\n', ' ').strip()[:80]
        if "章节摘要" not in state:
            state["章节摘要"] = {}
        state["章节摘要"][f"第{chapter_num}章"] = summary

        WritingStateManager.save_state(project_name, state)
        return state


# ============ 写作状态简报生成函数 ============

def generate_writing_brief(project_name: str, chapter_num: int) -> str:
    """生成写作状态简报——写入新章前调用"""
    project_dir = WritingStateManager.PROJECTS_DIR / project_name
    if not project_dir.exists():
        return f"项目 {project_name} 不存在。"

    state = WritingStateManager.load_state(project_name)
    WritingStateManager.scan_chapter(project_dir, state)

    # 加载事件图谱
    atlas = load_json(project_dir / "event_plot_atlas.json")
    release_points = atlas.get("情绪释放点分布", [])
    scenes = atlas.get("关键场景三拍结构", {})

    # 找下一释放点
    next_release = "无"
    for rp in release_points:
        if rp.get("章") == chapter_num:
            next_release = f"第{rp['章']}章·{rp.get('类型','')}·{rp.get('方式','')}"
            break

    # 找三拍结构
    scene_detail = ""
    chapter_key = None
    for key in scenes:
        tag = f"第{chapter_num}章"
        if tag in key:
            chapter_key = key
            break
    if chapter_key:
        s = scenes[chapter_key]
        scene_detail = f"日常: {s.get('日常','')[:50]}\n微澜: {s.get('微澜','')[:50]}\n回归: {s.get('回归','')[:50]}"

    # 释放方式去重检查
    used_methods = state.get("已用释放方式", [])
    used_str = ', '.join(used_methods) if used_methods else "无"

    # 物件列表
    objs = state.get("已使用物件", [])
    objs_str = ', '.join(objs[-8:]) if objs else "尚无"

    # 物件追踪——高频重复物件（坂元式）
    obj_track = state.get("物件追踪", {})
    recurring_objs = [f"{k}×{v}" for k,v in obj_track.items() if v >= 2]
    recurring_str = ', '.join(recurring_objs[-5:]) if recurring_objs else "尚无重复物件"

    # 半沢式蓄力值
    stack = state.get("情绪蓄力值", 0)
    cycle = WritingStateManager.get_release_cycle_position(chapter_num)
    stack_warning = "⚠️ 建议在本章或下章安排释放" if stack >= 3 else "蓄力中，继续堆积"

    # 无用细节
    details = state.get("已用无用细节", [])
    details_str = ', '.join(details[-5:]) if details else "尚无"

    brief = f"""## 当前状态（第{chapter_num}章前）
- 已完成: {len(state.get('已完成章节',[]))}章
- 主角状态: {state.get('主角状态','初期')}
- 已用释放方式: {used_str}
- 已出现物件: {objs_str}
- 本章释放设计: {next_release}
{chr(10)+'## 本章场景设计'+chr(10)+scene_detail if scene_detail else ''}

【半沢式蓄力状态】
- 情绪蓄力值: {stack}/4 ({stack_warning})
- 当前循环位置: {cycle}

【坂元式物件追踪】
- 高频重复物件: {recurring_str}

【日剧式无用细节】
- 已用细节: {details_str}
"""
    return brief.strip()


# ============ 写章节 API ============

@app.route("/api/v7/write", methods=["POST"])
def write_chapter():
    """一体化写章节：加载状态→注入上下文→生成→自动记忆"""
    import traceback as tb
    try:
        data = request.get_json() or {}
        project_name = data.get("project", "")
        chapter_num = data.get("chapter_num", 0)
        mode = data.get("mode", "healing_life_v2")
        temperature = data.get("temperature", 0.6)
        instructions = data.get("instructions", "")

        if not project_name or not chapter_num:
            return jsonify({"success": False, "error": "需要 project 和 chapter_num"}), 400

        project_dir = WritingStateManager.PROJECTS_DIR / project_name
        if not project_dir.exists():
            return jsonify({"success": False, "error": f"项目 {project_name} 不存在"}), 404

        # 1. 加载状态 + 生成状态简报
        ws_state = WritingStateManager.load_state(project_name)
        brief = generate_writing_brief(project_name, chapter_num)

        # 2. 加载模式配置
        mode_config = load_mode_config(mode)
        mode_context = json.dumps(mode_config, ensure_ascii=False)[:500] if mode_config else ""

        # 3. 加载通用写作系统提示词
        sys_prompt = load_file(BASE_DIR / "system_prompts" / "novel_writer.txt") or ""
        if not sys_prompt:
            sys_prompt = "你是盘古V2治愈系写作助手，专注治愈系·情绪释放·电影质感。"

        # 4. 构建写作提示词（含中日国民级技法）
        stack = ws_state.get("情绪蓄力值", 0)
        cycle_warning = ""
        if stack >= 3:
            cycle_warning = "\n⚠️ 蓄力值已达上限——本章必须安排释放节点。"
        elif stack <= 1 and chapter_num % 4 != 0:
            cycle_warning = "\n📌 当前在堆积期——只堆积不释放，为更大释放蓄力。"

        user_prompt = f"""请为【{project_name}】写第{chapter_num}章。

{chr(10).join([f'【写作状态】'])}
{brief}

【用户补充要求】
{instructions if instructions else '无'}

【模式配置参考】
{mode_context[:300]}

【写作要求】
- 每句要有画面感——读者能"看到"而不是"知道"
- 触觉优先——温度/质地/湿度
- 加入1个"无用但让世界变活"的细节（鸽子/电视声/贩卖机的光/落叶——不推进剧情但让世界真实）
- 坂元式物件运用：如果有已出现的物件，让它在不经意间再次出现，状态的变化暗示情绪的变化
- 以画面/天气/物件收尾，不设悬念
- 禁用：内心OS、直白情绪词、"突然""猛然"
- 字数：约2000汉字
{cycle_warning}

请直接输出正文，不要解释，不要前缀。
"""

        # 5. 调用LLM
        result = call_llm(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=4000,
            workshop="w2",
        )

        if result.startswith("[模拟输出"):
            return jsonify({"success": True, "chapter": chapter_num, "content": result, "state_updated": False})

        # 6. 保存文件（去掉模型可能重复生成的标题）
        final_content = result.strip()
        if final_content.startswith(f"# 第{chapter_num}章"):
            final_content = final_content.split('\n', 1)[1] if '\n' in final_content else ""
            final_content = final_content.strip()

        chapter_file = project_dir / f"第{chapter_num:02d}章_{data.get('title','')}.md"
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(f"# 第{chapter_num}章 {data.get('title','')}\n\n")
            f.write(final_content)

        # 7. 自动更新状态
        state = WritingStateManager.update_state(project_name, project_dir, chapter_num, result)

        return jsonify({
            "success": True,
            "chapter": chapter_num,
            "file": str(chapter_file.name),
            "content": result,
            "state": {
                "completed": len(state.get("已完成章节", [])),
                "主角状态": state.get("主角状态", ""),
                "已用物件": state.get("已使用物件", [])[-5:],
                "释放方式": state.get("已用释放方式", []),
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "detail": tb.format_exc()}), 500


# ============ 半人工工作台 API ============

@app.route("/api/v7/workshop/openings", methods=["POST"])
def workshop_openings():
    """生成3个可选开场——人选择，AI不决定"""
    data = request.get_json() or {}
    genre = data.get("genre", "治愈日常")
    scene = data.get("scene", "一个人在海边醒来")
    tone = data.get("tone", "安静克制")

    sys_p = "你是盘古开场设计师。你的任务是给3个完全不同风格的开场选项，不扩展，每个控制80字以内。"
    user_p = f"""为以下场景设计3种不同开场：

场景：{scene}
调性：{tone}
题材：{genre}"""

    result = call_llm(sys_p, user_p, temperature=0.8, max_tokens=600, workshop="w2")
    return jsonify({"success": True, "options": result, "choose_hint": "选一个，用 /workshop/expand 扩展"})


@app.route("/api/v7/workshop/expand", methods=["POST"])
def workshop_expand():
    """扩展选中的场景——人选定方向，AI填充细节"""
    data = request.get_json() or {}
    opening = data.get("opening", "")
    direction = data.get("direction", "")
    word_count = data.get("word_count", 600)

    sys_p = "你是盘古场景填充师。你只扩展不创造，只填充不改变方向。不要加新情节，只加深感官细节和情绪层次。"
    user_p = f"""扩展以下开场到{word_count}字左右：

【开场】
{opening}

【方向】
{direction if direction else '按自然方向推进'}

要求：
- 不添加新事件
- 加深触觉/听觉细节
- 加入1个"无用但让世界变活"的细节
- 在扩展内容的末尾，提供2个不同方向的继续选项（每句20字以内）
"""

    result = call_llm(sys_p, user_p, temperature=0.6, max_tokens=2000, workshop="w2")
    return jsonify({"success": True, "content": result})


@app.route("/api/v7/workshop/ending", methods=["POST"])
def workshop_ending():
    """生成2个收尾方案——人选择收尾风格"""
    data = request.get_json() or {}
    context = data.get("context", "")
    style = data.get("style", "余韵型")

    sys_p = "你是盘古收尾设计师。给出2个不同情绪走向的收尾，每个控制在100字以内。"
    user_p = f"""为以下上下文设计2种收尾：

【上下文】{context[:300]}

【收尾风格】
A. 余韵型（画面/天气收尾，不解答）
B. 释然型（主角有一个极小的动作暗示变化）

要求：
- 不以悬念收尾
- 收尾后读者应该"想在这一刻停留"而不是"想点下一页"
"""

    result = call_llm(sys_p, user_p, temperature=0.7, max_tokens=600, workshop="w2")
    return jsonify({"success": True, "options": result})


@app.route("/api/v7/short", methods=["POST"])
def write_short():
    """一键短篇——直接生成治愈系独立短篇"""
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    temperature = data.get("temperature", 0.6)

    sys_p = load_file(BASE_DIR / "system_prompts" / "short_story_template.txt")
    if not sys_p:
        sys_p = "你是一个治愈系短篇写手。不解释、不写'她想起'、收尾落在画面/天气上。"

    user_p = prompt if prompt else "请写一篇治愈系短篇。一个人在下着小雨的傍晚遇到一件小事。"

    result = call_llm(sys_p, user_p, temperature=temperature, max_tokens=3000, workshop="w2")
    return jsonify({"success": True, "content": result})


# ================================================================
# V2 API: 统一管线 (pangu_core.Pipeline)
# 替代旧版 workshops/*.txt + SchedulerV7 + call_llm 双管线
# ================================================================

# V7 端点废弃警告
@app.before_request
def deprecate_v7():
    """对 /api/v7/* 请求添加废弃警告头"""
    if request.path.startswith("/api/v7/"):
        from flask import g
        g.deprecated = True

@app.after_request
def add_deprecation_header(response):
    if getattr(g, 'deprecated', False):
        response.headers["X-Deprecated-API"] = "V7"
        response.headers["X-Migration-Path"] = "/api/v2/generate"
    return response

@app.route("/api/v2/generate", methods=["POST"])
def generate_v2():
    """
    统一写作接口 — 调用 pangu_core.Pipeline。

    与旧版 /api/v7/generate 的区别:
      - Prompt: PromptBuilder 17层动态构建 (替代 workshops/*.txt)
      - LLM: call_ai() 多Provider路由 (替代 call_llm/litellm)
      - RAG: pangu_core/rag_engine.py FAISS (替代 backend/rag_engine.py stub)
      - 模式: modes/*.json W2/W4差异化规则 (替代硬编码)

    Request: {project, chapter, task?, mode?, platform?, fast?}
    Response: {success, chapter_content, words, warnings, errors, intelligence?}
    """
    import sys
    sys.path.insert(0, str(BASE_DIR))

    data = request.get_json() or {}
    project_name = data.get("project", "")
    chapter_num = data.get("chapter", 1)
    chapter_task = data.get("task", "")
    mode_name = data.get("mode", "general")
    platform_name = data.get("platform", "qimao")
    use_fast = data.get("fast", True)
    with_intelligence = data.get("intelligence", True)

    # 查找项目
    from pangu_workshop import find_project
    proj = find_project(project_name)
    if not proj:
        return jsonify({"success": False, "error": f"项目 '{project_name}' 未找到"}), 404

    # 构建配置
    from pangu_core.pipeline import WritingPipeline, PipelineConfig
    if use_fast:
        config = PipelineConfig.from_quick_mode(
            str(proj), chapter_num,
            chapter_task or f"第{chapter_num}章",
            mode=mode_name, platform=platform_name)
    else:
        config = PipelineConfig.from_workshop_mode(
            str(proj), chapter_num,
            chapter_task or f"第{chapter_num}章",
            mode=mode_name, platform=platform_name)

    # 执行
    t0 = time.time()
    pipeline = WritingPipeline(config)
    result = pipeline.run()
    elapsed = time.time() - t0

    response = {
        "success": result.success,
        "chapter_content": result.chapter_content,
        "words": len(result.chapter_content.replace('\n', '').replace(' ', '')),
        "elapsed": round(elapsed, 1),
        "warnings": result.warnings,
        "errors": result.errors,
    }

    # 情报
    if with_intelligence and result.success:
        try:
            from pangu_intelligence import analyze_chapter
            state = json.loads(
                (proj / ".webnovel" / "state.json").read_text(encoding="utf-8"))
            ci = analyze_chapter(str(proj), chapter_num,
                                  result.chapter_content, state)
            response["intelligence"] = {
                "quality_posterior": ci.quality_posterior,
                "ai_risk": ci.ai_risk_score,
                "audit": ci.audit_opinion,
                "recommendation": ci.recommendation,
            }
        except Exception:
            pass

    return jsonify(response)


@app.route("/api/v2/projects", methods=["GET"])
def projects_v2():
    """项目列表 (走 pangu_workshop)"""
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from pangu_workshop import PROJECT_ROOTS, load_state
    projects = []
    for root in PROJECT_ROOTS:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            state = load_state(child)
            if not state:
                continue
            info = state.get("project_info", {})
            prog = state.get("progress", {})
            projects.append({
                "title": info.get("title", child.name),
                "platform": info.get("platform", "?"),
                "genre": info.get("genre", "?"),
                "progress": f"Ch{prog.get('current_chapter',0)}/{info.get('target_chapters','?')}",
                "words": prog.get("total_words", 0),
            })
    return jsonify({"projects": projects})


@app.route("/api/v2/diagnose", methods=["POST"])
def diagnose_v2():
    """智能诊断 (走 pangu_workshop_smart)"""
    import sys
    sys.path.insert(0, str(BASE_DIR))
    data = request.get_json() or {}
    project_name = data.get("project", "")
    chapter_num = data.get("chapter")

    from pangu_workshop import find_project
    from pangu_workshop_smart import SmartStrategyEngine

    proj = find_project(project_name)
    if not proj:
        return jsonify({"success": False, "error": "项目未找到"}), 404

    engine = SmartStrategyEngine(proj)
    if chapter_num:
        strategy = engine.recommend_strategy(chapter_num)
        task = engine.generate_chapter_task(chapter_num)
        return jsonify({
            "project": project_name,
            "chapter": chapter_num,
            "strategy": {
                "mode": strategy.mode,
                "target_words": strategy.target_words,
                "temperature": strategy.temperature,
                "hook_type": strategy.hook_type,
                "release_type": strategy.release_type,
                "use_claude_w4": strategy.use_claude_w4,
                "priority_dimensions": strategy.priority_dimensions,
            },
            "task": task,
        })

    return jsonify({"success": False, "error": "需要 chapter 参数"})


# ============ 启动 ============
if __name__ == "__main__":
    print("=" * 60)
    print("  盘古V2.0 小说工厂后端服务")
    print("  统一管线: pangu_core.Pipeline + PromptBuilder + ai_client")
    print("=" * 60)
    print("  V2 API (推荐 — 统一管线):")
    print("    POST /api/v2/generate          统一写作 (pangu_core.Pipeline)")
    print("    GET  /api/v2/projects          项目列表")
    print("    POST /api/v2/diagnose          智能诊断")
    print("  V7 API (兼容 — 旧版workshops管线):")
    print("    POST /api/v7/generate          旧版生成 (已废弃)")
    print("    POST /api/v7/write             旧版写章 (已废弃)")
    print("=" * 60)

    app.run(host="127.0.0.1", port=5001, debug=False)

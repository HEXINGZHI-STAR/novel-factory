#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古写作系统 - 优化版
更流畅的运行流程，支持快速模式和模板
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime
from loguru import logger

# 日志配置
logger.add("pangu_optimized_{time}.log", rotation="500 MB")

# 尝试导入requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# 尝试导入dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加knowledge和backend目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))
sys.path.insert(0, str(Path(__file__).parent / 'backend'))
try:
    from db_manager import NovelReferenceDB
    from reference_prompt import ReferencePromptGenerator
    from workshop_db_manager import WorkshopDBManager
    from unified_db_manager import UnifiedDBManager
except ImportError:
    logger.warning("警告：未找到模块，部分功能将不可用")
    NovelReferenceDB = None
    ReferencePromptGenerator = None
    WorkshopDBManager = None
    UnifiedDBManager = None

# 尝试导入五车间流水线
try:
    # 从backend目录导入app_v7中的五车间模块
    from app_v7 import load_workshop_prompt, load_mode_config
    HAS_FIVE_WORKSHOP = True
except Exception as e:
    logger.warning(f"警告：五车间流水线导入失败: {e}")
    HAS_FIVE_WORKSHOP = False

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
CONFIG_FILE = BASE_DIR / ".env"
PROJECTS_DIR.mkdir(exist_ok=True)

# 项目模板
PROJECT_TEMPLATES = {
    "七猫爽文": {
        "mode": "都市_power",
        "platform": "qimao",
        "default_words": 400000,
        "default_chapters": 200,
        "description": "七猫风格爽文，节奏快、爽点密集"
    },
    "二次元": {
        "mode": "female_solo",
        "platform": "qidian",
        "default_words": 300000,
        "default_chapters": 150,
        "description": "轻小说风格二次元作品"
    },
    "玄幻仙侠": {
        "mode": "general",
        "platform": "qidian",
        "default_words": 1000000,
        "default_chapters": 500,
        "description": "经典玄幻仙侠，升级打怪"
    },
    "历史架空": {
        "mode": "general",
        "platform": "zongheng",
        "default_words": 600000,
        "default_chapters": 300,
        "description": "历史穿越、权谋争霸"
    },
    "体育竞技": {
        "mode": "general",
        "platform": "qimao",
        "default_words": 500000,
        "default_chapters": 250,
        "description": "热血竞技，青春成长"
    }
}


def load_config():
    """加载配置"""
    config = {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("AI_MODEL", "deepseek-v4-flash"),
        "temperature": 0.7,
        "max_tokens": 4000,
        "timeout": 120,
        "retry_times": 3,
        "auto_context": True,  # 默认开启上下文保持
        "quick_mode": False,  # 快速模式
    }
    
    if not config["api_key"]:
        logger.warning("未设置API Key，请检查.env文件")
        config["api_key"] = "sk-d0a65c094b53413d8712e93c364ebeea"
    
    return config


CONFIG = load_config()


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     盘古写作系统 - 优化版                      ║
║                流畅体验 · 智能创作 · 高效流程                   ║
╚══════════════════════════════════════════════════════════════╝
    """)


def init_db():
    """初始化数据库连接"""
    if NovelReferenceDB is None:
        return None
    try:
        db = NovelReferenceDB()
        return db
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None


def init_workshop_db():
    """初始化车间数据库连接"""
    if WorkshopDBManager is None:
        return None
    try:
        db = WorkshopDBManager()
        return db
    except Exception as e:
        logger.error(f"车间数据库连接失败: {e}")
        return None


def init_unified_db():
    """初始化统一数据库连接"""
    if UnifiedDBManager is None:
        return None
    try:
        db = UnifiedDBManager()
        return db
    except Exception as e:
        logger.error(f"统一数据库连接失败: {e}")
        return None


def get_projects():
    """获取项目列表（优先从统一数据库，否则从JSON）"""
    # 先尝试从统一数据库读取
    db = init_unified_db()
    if db:
        try:
            projects_data = db.get_all_projects()
            projects = []
            for proj in projects_data:
                pd = Path(proj["project_dir"])
                if pd.exists():
                    projects.append({
                        "dir": pd,
                        "title": proj["title"],
                        "current_ch": proj["current_chapter"],
                        "total_ch": proj["target_chapters"],
                        "mtime": pd.stat().st_mtime,
                        "db_id": proj["id"]
                    })
            if projects:
                projects.sort(key=lambda x: x["mtime"], reverse=True)
                return projects
        except Exception as e:
            logger.warning(f"从数据库读取项目失败，回退到JSON方式: {e}")
    
    # 回退到从JSON读取的方式（保持向后兼容）
    projects = []
    for pd in PROJECTS_DIR.iterdir():
        if pd.is_dir() and (pd / "state.json").exists():
            try:
                state = json.loads((pd / "state.json").read_text(encoding='utf-8'))
                title = state.get("project_info", {}).get("title", pd.name)
                current_ch = state.get("progress", {}).get("current_chapter", 0)
                total_ch = state.get("project_info", {}).get("target_chapters", "?")
                mtime = pd.stat().st_mtime
                projects.append({
                    "dir": pd,
                    "title": title,
                    "current_ch": current_ch,
                    "total_ch": total_ch,
                    "mtime": mtime
                })
            except:
                pass
    
    projects.sort(key=lambda x: x["mtime"], reverse=True)
    return projects


def create_project_quick():
    """快速创建项目 - 三步完成"""
    print("\n" + "="*60)
    print("  快速创建项目")
    print("="*60)
    
    # 1. 选择模板
    print("\n请选择项目模板:")
    for i, (name, info) in enumerate(PROJECT_TEMPLATES.items(), 1):
        print(f"  [{i}] {name} - {info['description']}")
    print("  [0] 自定义")
    
    choice = input("\n选择模板 (1-5, 0自定义): ").strip()
    
    template_name = None
    template = None
    if choice.isdigit() and 1 <= int(choice) <= len(PROJECT_TEMPLATES):
        template_names = list(PROJECT_TEMPLATES.keys())
        template_name = template_names[int(choice)-1]
        template = PROJECT_TEMPLATES[template_name]
        print(f"✓ 已选择模板: {template_name}")
    else:
        print("自定义模式")
        template = None
    
    # 2. 输入基本信息
    title = input("\n书名: ").strip()
    if not title:
        print("书名不能为空！")
        return None
    
    concept = input("一句话核心概念 (可选): ").strip()
    
    # 3. 确认并创建
    if template:
        mode = template["mode"]
        platform = template["platform"]
        words = template["default_words"]
        chapters = template["default_chapters"]
    else:
        mode = "general"
        platform = "qimao"
        words = 400000
        chapters = 200
    
    # 快速确认
    print(f"\n快速确认:")
    print(f"  书名: {title}")
    print(f"  模式: {mode}")
    print(f"  平台: {platform}")
    print(f"  目标: {words}字 / {chapters}章")
    
    confirm = input("\n确认创建？(y/n, 默认y): ").strip().lower()
    if confirm and confirm != "y":
        print("已取消")
        return None
    
    # 创建项目
    project_dir = PROJECTS_DIR / title
    if project_dir.exists():
        print("项目已存在！")
        return project_dir
    
    project_dir.mkdir(exist_ok=True)
    (project_dir / "大纲").mkdir(exist_ok=True)
    (project_dir / "正文").mkdir(exist_ok=True)
    
    # 创建基本大纲
    outline = f"""# {title} 总大纲

## 一句话核心概念
{concept or '[填写一句话概括你的小说]'}

## 核心卖点
1. [卖点1]
2. [卖点2]
3. [卖点3]

## 主要人物
### 主角
- 姓名: [名字]
- 核心创伤/执念: [填写]
- 核心目标: [填写]

### 关键配角
- [角色名]: [简要描述]

## 章节规划（每章约2000字）
"""
    for i in range(1, chapters+1):
        outline += f"{i}. 第{i}章: [本章任务]\n"
    
    with open(project_dir / "大纲" / "总大纲.md", 'w', encoding='utf-8') as f:
        f.write(outline)
    
    # 创建章节规划
    with open(project_dir / "大纲" / "章节规划.md", 'w', encoding='utf-8') as f:
        f.write(f"# {title} 章节规划\n\n")
        for i in range(1, chapters+1):
            f.write(f"## 第{i}章\n- 任务: [填写本章内容]\n- 要点: [填写本章钩子/爽点]\n\n")
    
    # 创建state（增强版——含伏笔追踪+角色状态+设定一致性）
    state = {
        "project_info": {
            "title": title,
            "type": "novel",
            "genre": mode,
            "platform": platform,
            "target_words": words,
            "target_chapters": chapters,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "progress": {"current_chapter": 0, "total_words": 0},
        "chapter_meta": {},
        "template": template_name if template_name else "custom",
        # 新增：长篇一致性追踪
        "foreshadowing": {
            "active_threads": [],  # [{"id":"f01","planted_ch":3,"description":"...","status":"open","resolved_ch":null}]
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "characters": {
            "protagonist": {"name": "", "current_state": "", "location": "", "last_chapter": 0},
            "key_characters": []  # [{"name":"","role":"","current_state":"","last_chapter":0}]
        },
        "setting_log": {
            "locked_rules": [],    # 已确立不可改的设定
            "pending_rules": [],   # 已引入但未确定的设定
            "last_checked_chapter": 0
        },
        "references": []
    }

    with open(project_dir / "state.json", 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # 同时在统一数据库中创建项目记录
    db = init_unified_db()
    if db:
        try:
            db.create_project(
                title=title,
                project_dir=str(project_dir),
                mode_id=mode,
                platform_id=platform,
                target_words=words,
                target_chapters=chapters
            )
        except Exception as e:
            logger.warning(f"保存项目到数据库失败，继续运行: {e}")

    print(f"\n✓ 项目创建成功！")
    print(f"  路径: {project_dir}")
    return project_dir


def get_context_chapters(project_dir, current_chapter, max_chapters=2):
    """获取前序章节作为上下文"""
    content_dir = project_dir / "正文"
    if not content_dir.exists():
        return ""
    
    prev_chapters = []
    for ch_num in range(max(1, current_chapter - max_chapters), current_chapter):
        possible_files = list(content_dir.glob(f"第{ch_num}章*.txt"))
        if possible_files:
            try:
                content = possible_files[0].read_text(encoding='utf-8')
                prev_chapters.append((ch_num, content))
            except Exception:
                pass
    
    if not prev_chapters:
        return ""
    
    result = "## 前面的章节（上下文参考）\n\n"
    for ch_num, content in prev_chapters:
        result += f"### 第{ch_num}章\n\n"
        result += content[:1500]
        if len(content) > 1500:
            result += "\n...（本章内容较长，只显示前1500字）"
        result += "\n\n"
    
    return result


# ============ 盘古知识注入系统 ============

def load_mode_rules(mode_name):
    """从统一数据库加载创作模式的写作规则（优先从DB，否则从JSON）"""
    # 优先从统一数据库读取
    db = init_unified_db()
    if db:
        try:
            mode = db.get_mode(mode_name)
            if mode:
                rules = []
                if mode.get("core_principle"):
                    rules.append(f"核心原则: {mode['core_principle']}")

                # 获取车间配置
                workshop_configs = mode.get("workshop_configs", {})
                w2 = workshop_configs.get("w2_special", {})
                if w2.get("dialogue_priority"):
                    rules.append(f"对话优先级: {w2['dialogue_priority']}")
                if w2.get("action_style"):
                    rules.append(f"动作风格: {w2['action_style']}")
                if w2.get("hook_types"):
                    rules.append(f"可用钩子类型: {', '.join(w2['hook_types'])}")
                if w2.get("forbidden_hook_types"):
                    rules.append(f"禁用钩子类型: {', '.join(w2['forbidden_hook_types'])}")

                w4 = workshop_configs.get("w4_special", {})
                if w4.get("emotion_parameter"):
                    rules.append(f"情绪参数: {w4['emotion_parameter']}")
                if w4.get("sensory_priority"):
                    rules.append(f"五感优先级: {' > '.join(w4['sensory_priority'])}")
                if w4.get("dialogue_style"):
                    rules.append(f"对话风格: {w4['dialogue_style']}")
                if w4.get("taboo"):
                    rules.append(f"禁用: {w4['taboo']}")

                return "\n".join(f"  - {r}" for r in rules) if rules else ""
        except Exception as e:
            logger.warning(f"从数据库读取模式配置失败，回退到JSON: {e}")
    
    # 回退到从JSON读取（保持向后兼容）
    mode_file = BASE_DIR / "modes" / f"{mode_name}.json"
    if not mode_file.exists():
        # 尝试模糊匹配
        for mf in (BASE_DIR / "modes").glob("*.json"):
            try:
                data = json.loads(mf.read_text(encoding='utf-8'))
                if data.get("mode_id") == mode_name or data.get("name", "").startswith(mode_name):
                    mode_file = mf
                    break
            except Exception:
                pass
    if not mode_file.exists():
        logger.warning(f"未找到模式配置: {mode_name}，使用通用模式")
        mode_file = BASE_DIR / "modes" / "general.json"

    try:
        mode = json.loads(mode_file.read_text(encoding='utf-8'))
        rules = []
        if mode.get("core_principle"):
            rules.append(f"核心原则: {mode['core_principle']}")

        w2 = mode.get("w2_special", {})
        if w2.get("dialogue_priority"):
            rules.append(f"对话优先级: {w2['dialogue_priority']}")
        if w2.get("action_style"):
            rules.append(f"动作风格: {w2['action_style']}")
        if w2.get("hook_types"):
            rules.append(f"可用钩子类型: {', '.join(w2['hook_types'])}")
        if w2.get("forbidden_hook_types"):
            rules.append(f"禁用钩子类型: {', '.join(w2['forbidden_hook_types'])}")

        w4 = mode.get("w4_special", {})
        if w4.get("emotion_parameter"):
            rules.append(f"情绪参数: {w4['emotion_parameter']}")
        if w4.get("sensory_priority"):
            rules.append(f"五感优先级: {' > '.join(w4['sensory_priority'])}")
        if w4.get("dialogue_style"):
            rules.append(f"对话风格: {w4['dialogue_style']}")
        if w4.get("taboo"):
            rules.append(f"禁用: {w4['taboo']}")

        return "\n".join(f"  - {r}" for r in rules) if rules else ""
    except Exception as e:
        logger.error(f"加载模式配置失败: {e}")
        return ""


def load_platform_rules(platform_name):
    """从统一数据库加载平台写作规则（优先从DB，否则从JSON）"""
    # 优先从统一数据库读取
    db = init_unified_db()
    if db:
        try:
            platform = db.get_platform(platform_name)
            if platform:
                rules = []
                rules.append(f"平台: {platform.get('name', platform_name)}")
                rules.append(f"核心逻辑: {platform.get('core_logic', '')}")
                rules.append(f"章节字数: {platform.get('chapter_length', '2000')}字")

                opening = platform.get("opening_rules", {})
                if opening.get("golden_rule"):
                    rules.append(f"黄金开篇: {opening['golden_rule']}")

                sent = platform.get("sentence_rules", {})
                if sent.get("max_chars_per_sentence"):
                    rules.append(f"句长上限: {sent['max_chars_per_sentence']}字")
                if sent.get("style"):
                    rules.append(f"句法风格: {sent['style']}")
                if sent.get("forbidden_patterns"):
                    rules.append(f"禁用句式: {', '.join(sent['forbidden_patterns'])}")

                para = platform.get("paragraph_rules", {})
                if para.get("max_lines_per_para"):
                    rules.append(f"段落上限: {para['max_lines_per_para']}行")
                if para.get("forbidden"):
                    rules.append(f"禁用段落: {', '.join(para['forbidden'])}")

                dia = platform.get("dialogue_rules", {})
                if dia.get("min_ratio"):
                    rules.append(f"对话率: ≥{int(dia['min_ratio']*100)}%")
                if dia.get("style"):
                    rules.append(f"对话风格: {dia['style']}")

                emo = platform.get("emotion_delivery", {})
                if emo.get("style"):
                    rules.append(f"情绪交付: {emo['style']}")
                if emo.get("required"):
                    rules.append(f"情绪要求: {emo['required']}")

                char = platform.get("character_rules", {})
                if char.get("protagonist"):
                    rules.append(f"主角要求: {char['protagonist']}")

                taboo = platform.get("taboo", [])
                if taboo:
                    rules.append(f"禁忌: {', '.join(taboo[:5])}")

                ai_risk = platform.get("ai_trace_high_risk", [])
                if ai_risk:
                    rules.append(f"AI痕迹高风险词（禁用）: {', '.join(ai_risk)}")

                return "\n".join(f"  - {r}" for r in rules) if rules else ""
        except Exception as e:
            logger.warning(f"从数据库读取平台配置失败，回退到JSON: {e}")
    
    # 回退到从JSON读取（保持向后兼容）
    config_file = BASE_DIR / "knowledge" / "platform_writing_profiles.json"
    if not config_file.exists():
        return ""

    try:
        configs = json.loads(config_file.read_text(encoding='utf-8'))
        profile = configs.get("profiles", {}).get(platform_name)
        if not profile:
            return ""

        rules = []
        rules.append(f"平台: {profile.get('name', platform_name)}")
        rules.append(f"核心逻辑: {profile.get('core_logic', '')}")
        rules.append(f"章节字数: {profile.get('chapter_length', '2000')}字")

        opening = profile.get("opening", {})
        if opening.get("golden_rule"):
            rules.append(f"黄金开篇: {opening['golden_rule']}")

        sent = profile.get("sentence_rules", {})
        if sent.get("max_chars_per_sentence"):
            rules.append(f"句长上限: {sent['max_chars_per_sentence']}字")
        if sent.get("style"):
            rules.append(f"句法风格: {sent['style']}")
        if sent.get("forbidden_patterns"):
            rules.append(f"禁用句式: {', '.join(sent['forbidden_patterns'])}")

        para = profile.get("paragraph_rules", {})
        if para.get("max_lines_per_para"):
            rules.append(f"段落上限: {para['max_lines_per_para']}行")
        if para.get("forbidden"):
            rules.append(f"禁用段落: {', '.join(para['forbidden'])}")

        dia = profile.get("dialogue_rules", {})
        if dia.get("min_ratio"):
            rules.append(f"对话率: ≥{int(dia['min_ratio']*100)}%")
        if dia.get("style"):
            rules.append(f"对话风格: {dia['style']}")

        emo = profile.get("emotion_delivery", {})
        if emo.get("style"):
            rules.append(f"情绪交付: {emo['style']}")
        if emo.get("required"):
            rules.append(f"情绪要求: {emo['required']}")

        char = profile.get("character_rules", {})
        if char.get("protagonist"):
            rules.append(f"主角要求: {char['protagonist']}")

        taboo = profile.get("taboo", [])
        if taboo:
            rules.append(f"禁忌: {', '.join(taboo[:5])}")

        ai_risk = profile.get("ai_trace_high_risk", [])
        if ai_risk:
            rules.append(f"AI痕迹高风险词（禁用）: {', '.join(ai_risk)}")

        return "\n".join(f"  - {r}" for r in rules) if rules else ""
    except Exception as e:
        logger.error(f"加载平台配置失败: {e}")
        return ""


def build_smart_prompt(state, chapter_task, chapter_num, context_content=""):
    """构建注入盘古知识的智能提示词——规则转风格指引，不设硬约束"""
    info = state.get("project_info", {})
    mode_name = info.get("genre", "general")
    platform_name = info.get("platform", "qimao")
    title = info.get("title", "")

    # 从DB/JSON加载模式元信息，转为自然风格描述
    db = init_unified_db()
    mode_vibe = ""
    platform_vibe = ""
    taboo_words = []

    # 平台 → 一句话风格底色
    platform_tones = {
        "qimao": "七猫风格——节奏快，开篇就抓住读者。短句多对话，情绪浓烈不克制。语言通俗好读。每章结尾让人想翻下一章。",
        "fanqie": "番茄风格——节奏快，大白话。开篇300字出冲突。主角杀伐果断，不圣母不内耗。每章有打脸或逆袭。",
        "qidian": "起点风格——允许中长句，节奏可以稍慢热。世界观有纵深感。人物有成长弧光。钩子多用悬念和信息缺口。",
        "jinjiang": "晋江风格——细腻，五感丰富。对话有潜台词，话不说满。情绪是渗透型的，不直给。主角人设鲜明。",
    }
    platform_vibe = platform_tones.get(platform_name, platform_tones["qimao"])

    # 模式 → 补充风格微调
    if db:
        try:
            mode = db.get_mode(mode_name)
            if mode:
                core = mode.get("core_principle", "")
                if core:
                    mode_vibe = f"内核方向：{core}。"
                w2 = mode.get("workshop_configs", {}).get("w2_special", {})
                if w2.get("dialogue_priority"):
                    mode_vibe += f"对话{'' if '高' in str(w2['dialogue_priority']) else '不'}是主要推进手段。"
                if w2.get("action_style"):
                    mode_vibe += f"动作{str(w2['action_style'])}。"
            # 取AI高风险词仅用于提醒
            plat = db.get_platform(platform_name)
            if plat:
                taboo_words = plat.get("ai_trace_high_risk", [])
        except Exception:
            pass

    if not mode_vibe:
        mode_vibe = "通用网文风格——节奏紧凑，爽点到位。"

    # 构建提示词：风格指引 + 一个提醒 + 上下文 + 输出指令
    taboo_line = ""
    if taboo_words:
        taboo_line = f"PS: 尽量避开这些词: {', '.join(taboo_words[:8])}"

    prompt = f"""你是一位擅长{platform_tones.get(platform_name, '网文')}的作家。

{mode_vibe}

请为小说《{title}》写第{chapter_num}章。

本章任务：{chapter_task}

{taboo_line}

要求：约2000字。直接输出正文，不要前言后记。

{context_content}

第{chapter_num}章正文："""
    return prompt


def clean_ai_output(content):
    """清理AI输出"""
    if not content:
        return content
    
    prefixes_to_remove = [
        r'^好的[，,。！!]?\s*',
        r'^好的，我来',
        r'^好的，以下是',
    ]
    
    for pattern in prefixes_to_remove:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    content = re.sub(r'^#+\s*.+?\s*\n', '', content)
    return content.strip()


def call_ai(prompt, model=None):
    """调用AI生成"""
    if not HAS_REQUESTS:
        logger.warning("未安装requests库，无法调用AI")
        return None
    
    cfg = CONFIG
    model = model or cfg["model"]
    
    if not cfg["api_key"]:
        print("未配置API Key！")
        return None
    
    last_error = None
    for attempt in range(cfg["retry_times"]):
        try:
            if attempt > 0:
                print(f"重试 {attempt}/{cfg['retry_times']}...")
            
            headers = {
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": cfg["temperature"],
                "max_tokens": cfg["max_tokens"]
            }
            
            print(f"正在调用 {model}...")
            response = requests.post(
                f"{cfg['base_url']}/chat/completions", 
                json=data, 
                headers=headers, 
                timeout=cfg["timeout"]
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return clean_ai_output(content)
            else:
                logger.error(f"API返回错误: {response.status_code}")
        
        except Exception as e:
            last_error = e
            logger.error(f"调用失败: {e}")
    
    return None


# ============ 五车间流水线引擎 ============

WORKSHOP_PROMPTS = {
    0: Path(__file__).parent / "workshops/workshop_0_anchor/system_prompt.txt",
    1: Path(__file__).parent / "workshops/workshop_1_setup/system_prompt.txt",
    2: Path(__file__).parent / "workshops/workshop_2_draft/system_prompt.txt",
    3: Path(__file__).parent / "workshops/workshop_3_qc/system_prompt.txt",
    4: Path(__file__).parent / "workshops/workshop_4_polish/system_prompt.txt",
}

def _load_workshop_prompt(workshop_id):
    path = WORKSHOP_PROMPTS.get(workshop_id)
    if path and path.exists():
        return path.read_text(encoding='utf-8')
    return ""


def run_workshop_pipeline(project_dir, chapter_task, use_ai=True):
    """
    完整五车间流水线：W0→W1→W2→W3→W4
    每步调用API，输入输出全部记录到 workshop_steps 表
    支持断点续传
    """
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return None

    state = json.loads(state_file.read_text(encoding='utf-8'))
    info = state.get("project_info", {})
    current_chapter = state["progress"]["current_chapter"] + 1
    mode_name = info.get("genre", "general")
    platform_name = info.get("platform", "qimao")
    title = info.get("title", "")

    wdb = init_workshop_db()
    if not wdb:
        print("车间数据库不可用")
        return None

    # 创建或恢复任务
    task = wdb.get_resumable_task(title, current_chapter)
    if task:
        task_id = task['id']
        progress = wdb.get_task_progress(task_id)
        last_step = progress['last_completed_workshop'] if progress else -1
        print(f"\n恢复任务 #{task_id}，从 W{last_step+1} 继续")
    else:
        task_id = wdb.create_task(
            project_name=title, chapter_num=current_chapter,
            title=f"第{current_chapter}章", mode=mode_name, platform=platform_name
        )
        last_step = -1
        print(f"\n新建车间任务 #{task_id}")

    wdb.update_task_status(task_id, "running")
    context = ""
    if CONFIG["auto_context"] and current_chapter > 1:
        context = get_context_chapters(project_dir, current_chapter)

    w_outputs = {}
    final_content = None

    # W0: 主旨锚定
    if last_step < 0:
        print("[W0] 主旨锚定...")
        w0_sys = _load_workshop_prompt(0)
        w0_input = f"一句话故事：{title}——{chapter_task}\n平台：{platform_name}\n请输出JSON："
        step_id = wdb.create_workshop_step(task_id, 0, w0_input)
        wdb.start_workshop_step(step_id)
        t0 = time.time()
        w0_out = call_ai(f"{w0_sys}\n\n---\n\n{w0_input}") if use_ai else '{}'
        if w0_out:
            wdb.complete_workshop_step(step_id, w0_out, CONFIG["model"], CONFIG["temperature"], len(w0_out), time.time()-t0)
            w_outputs[0] = w0_out
            print("  W0 完成")
        else:
            wdb.fail_workshop_step(step_id, "API失败"); wdb.update_task_status(task_id, "failed", "W0失败"); return None

    # W1: 设定预处理
    if last_step < 1:
        print("[W1] 设定预处理...")
        w1_sys = _load_workshop_prompt(1)
        w1_input = f"全书冷库摘要：{title}，{mode_name}模式\n本章任务：{chapter_task}\n近3章：{context[:500] if context else '（首章）'}\nW0主旨：{w_outputs.get(0,'')[:300]}"
        step_id = wdb.create_workshop_step(task_id, 1, w1_input)
        wdb.start_workshop_step(step_id)
        t0 = time.time()
        w1_out = call_ai(f"{w1_sys}\n\n---\n\n{w1_input}\n\n请输出【本章热库】（500字以内）：") if use_ai else ""
        if w1_out:
            wdb.complete_workshop_step(step_id, w1_out, CONFIG["model"], CONFIG["temperature"], len(w1_out), time.time()-t0)
            w_outputs[1] = w1_out
            print("  W1 完成")
        else:
            wdb.fail_workshop_step(step_id, "API失败"); wdb.update_task_status(task_id, "failed", "W1失败"); return None

    # W2: 正文初稿
    if last_step < 2:
        print("[W2] 正文初稿...")
        w2_sys = _load_workshop_prompt(2)
        w2_input = f"本章热库：{w_outputs.get(1,'')[:500]}\n本章任务：{chapter_task}\n字数：2000字"
        step_id = wdb.create_workshop_step(task_id, 2, w2_input)
        wdb.start_workshop_step(step_id)
        t0 = time.time()
        w2_out = call_ai(f"{w2_sys}\n\n---\n\n{w2_input}\n\n请输出【正文初稿】：") if use_ai else ""
        if w2_out:
            wdb.complete_workshop_step(step_id, w2_out, CONFIG["model"], CONFIG["temperature"], len(w2_out), time.time()-t0)
            w_outputs[2] = w2_out
            print("  W2 完成")
        else:
            wdb.fail_workshop_step(step_id, "API失败"); wdb.update_task_status(task_id, "failed", "W2失败"); return None

    # W3: 逻辑质检
    if last_step < 3:
        print("[W3] 逻辑质检...")
        w3_sys = _load_workshop_prompt(3)
        w3_input = f"本章热库：{w_outputs.get(1,'')[:300]}\n正文初稿：{w_outputs.get(2,'')[:2000]}"
        step_id = wdb.create_workshop_step(task_id, 3, w3_input)
        wdb.start_workshop_step(step_id)
        t0 = time.time()
        w3_out = call_ai(f"{w3_sys}\n\n---\n\n{w3_input}\n\n请输出【质检报告】+【修正后的骨架】：") if use_ai else ""
        if w3_out:
            passed = "无需修正" in w3_out or "全部通过" in w3_out
            wdb.complete_workshop_step(step_id, w3_out, CONFIG["model"], CONFIG["temperature"], len(w3_out), time.time()-t0)
            w_outputs[3] = w3_out
            print(f"  W3 完成{'（通过）' if passed else '（有修正）'}")
        else:
            wdb.fail_workshop_step(step_id, "API失败"); wdb.update_task_status(task_id, "failed", "W3失败"); return None

    # W4: 文笔精修
    if last_step < 4:
        print("[W4] 文笔精修...")
        w4_sys = _load_workshop_prompt(4)
        skeleton = w_outputs.get(3, w_outputs.get(2, ''))
        w4_input = f"修正后的骨架：{skeleton[:2000]}\n模式：{mode_name}\n字数：2000字"
        step_id = wdb.create_workshop_step(task_id, 4, w4_input)
        wdb.start_workshop_step(step_id)
        t0 = time.time()
        final_content = call_ai(f"{w4_sys}\n\n---\n\n{w4_input}\n\n请输出【成品章节】：") if use_ai else skeleton
        if final_content:
            wdb.complete_workshop_step(step_id, final_content, CONFIG["model"], CONFIG["temperature"], len(final_content), time.time()-t0)
            w_outputs[4] = final_content
            print("  W4 完成")
        else:
            wdb.fail_workshop_step(step_id, "API失败"); wdb.update_task_status(task_id, "failed", "W4失败"); return None

    # 保存成品
    if final_content:
        chapter_file = project_dir / "正文" / f"第{current_chapter}章.txt"
        chapter_file.write_text(final_content, encoding='utf-8')
        wc = len(final_content.replace('\n','').replace(' ',''))
        wdb.save_chapter_output(task_id, f"第{current_chapter}章", final_content, is_final=True)
        wdb.update_task_status(task_id, "completed")
        state["progress"]["current_chapter"] = current_chapter
        state["chapter_meta"][f"chapter_{current_chapter}"] = {
            "task": chapter_task, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ai_generated": use_ai, "workshop_task_id": task_id
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n五车间完成！第{current_chapter}章 {wc}字 任务#{task_id} 已保存")

    return final_content


def write_chapter_quick(project_dir, use_workshop=False):
    """快速写章节 - 简化流程"""
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return
    
    state = json.loads(state_file.read_text(encoding='utf-8'))
    current_chapter = state["progress"]["current_chapter"] + 1
    
    print(f"\n" + "="*60)
    print(f"  写第 {current_chapter} 章")
    print("="*60)
    
    # 初始化车间数据库
    workshop_db = None
    task_id = None
    if use_workshop and WorkshopDBManager is not None:
        workshop_db = init_workshop_db()
        if workshop_db:
            print(f"\n✓ 车间数据库已启用，执行过程将被记录")
            # 创建任务
            info = state.get("project_info", {})
            task_id = workshop_db.create_task(
                project_name=info.get("title", project_dir.name),
                chapter_num=current_chapter,
                title=f"第{current_chapter}章",
                mode=info.get("genre", "general"),
                platform=info.get("platform", "qimao")
            )
            workshop_db.update_task_status(task_id, "running")
    
    # 快速模式：只需输入核心任务
    chapter_task = input(f"\n这章要写什么？（一句话描述）: ").strip()
    if not chapter_task:
        print("请输入任务！")
        if task_id:
            workshop_db.update_task_status(task_id, "failed", "未输入章节任务")
        return
    
    # 快速配置
    use_ai = input("用AI生成？(y/n, 默认y): ").strip().lower()
    if not use_ai or use_ai == "y":
        use_ai = True
    else:
        use_ai = False
    
    # 自动上下文
    context_content = ""
    if CONFIG["auto_context"] and current_chapter > 1:
        context_content = get_context_chapters(project_dir, current_chapter)
        if context_content:
            print("✓ 已读取前序章节作为上下文")
    
    # 生成智能提示词（注入模式+平台规则）
    prompt = build_smart_prompt(state, chapter_task, current_chapter, context_content)

    # 显示注入的规则摘要
    mode_name = state['project_info'].get('genre', 'general')
    platform_name = state['project_info'].get('platform', 'qimao')
    print(f"\n✓ 已注入模式规则: {mode_name}")
    print(f"✓ 已注入平台规则: {platform_name}")
    if context_content:
        print(f"✓ 已读取前序章节作为上下文")

    generated_content = None
    step_start_time = None
    if use_ai:
        if task_id:
            # 记录步骤开始
            step_id = workshop_db.create_workshop_step(task_id, 2, prompt)  # W2 草稿车间
            workshop_db.start_workshop_step(step_id)
            step_start_time = time.time()
        
        generated_content = call_ai(prompt)
        
        if task_id and step_start_time:
            # 记录步骤完成
            duration = time.time() - step_start_time
            if generated_content:
                workshop_db.complete_workshop_step(
                    step_id, generated_content, CONFIG["model"], 
                    CONFIG["temperature"], len(generated_content), duration
                )
            else:
                workshop_db.fail_workshop_step(step_id, "AI生成失败")

    if generated_content:
        chapter_file = project_dir / "正文" / f"第{current_chapter}章.txt"
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(generated_content)
        # 统计字数
        word_count = len(generated_content.replace('\n', '').replace(' ', ''))
        print(f"\n✓ 已保存到: {chapter_file}")
        print(f"✓ 字数: {word_count}")
        print(f"\n前100字预览:\n{generated_content[:100]}...")
        
        if task_id:
            # 保存章节输出
            workshop_db.save_chapter_output(
                task_id, f"第{current_chapter}章", generated_content, is_final=True
            )
            workshop_db.update_task_status(task_id, "completed")
    else:
        # 创建草稿
        chapter_file = project_dir / "正文" / f"第{current_chapter}章_草稿.txt"
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(f"# 第{current_chapter}章\n\n任务: {chapter_task}\n\n[在这里写正文]\n")
        print(f"\n已生成草稿: {chapter_file}")
        
        if task_id:
            workshop_db.update_task_status(task_id, "failed", "未生成内容")

    # 更新状态
    state["progress"]["current_chapter"] = current_chapter
    state["chapter_meta"][f"chapter_{current_chapter}"] = {
        "task": chapter_task,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_generated": use_ai,
        "workshop_task_id": task_id
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # 同时在统一数据库中更新项目进度
    db = init_unified_db()
    if db:
        try:
            project = db.get_project_by_dir(str(project_dir))
            if project:
                total_words = sum(
                    len((project_dir / "正文" / f"第{ch}章.txt").read_text(encoding='utf-8')) 
                    for ch in range(1, current_chapter + 1)
                    if (project_dir / "正文" / f"第{ch}章.txt").exists()
                )
                db.update_project_progress(project["id"], current_chapter, total_words)
                
                # 同时创建章节记录
                db.create_chapter(
                    project_id=project["id"],
                    chapter_num=current_chapter,
                    title=f"第{current_chapter}章",
                    task=chapter_task,
                    word_count=word_count,
                    ai_generated=use_ai,
                    workshop_task_id=task_id
                )
        except Exception as e:
            logger.warning(f"同步进度到数据库失败，继续运行: {e}")


def batch_generate(project_dir, count=5, use_workshop=False):
    """批量生成章节（增强版：带上下文传递+智能提示词+断点续传）"""
    print(f"\n准备批量生成 {count} 章...")

    state_file = project_dir / "state.json"
    state = json.loads(state_file.read_text(encoding='utf-8'))
    start_chapter = state["progress"]["current_chapter"] + 1

    success = 0
    failed = 0
    last_content = None  # 用于章间上下文传递
    
    # 初始化车间数据库
    workshop_db = None
    if use_workshop and WorkshopDBManager is not None:
        workshop_db = init_workshop_db()
        if workshop_db:
            print(f"✓ 车间数据库已启用")

    for i in range(count):
        ch_num = start_chapter + i
        task_id = None
        step_id = None
        step_start_time = None
        
        print(f"\n{'='*40}")
        print(f"  生成第 {ch_num} 章 ({i+1}/{count})...")
        print(f"{'='*40}")
        
        # 检查本章是否已存在，避免覆盖
        chapter_file = project_dir / "正文" / f"第{ch_num}章.txt"
        if chapter_file.exists():
            print(f"⚠ 第{ch_num}章已存在，跳过...")
            # 读取已存在的内容作为下一章的上下文
            try:
                last_content = chapter_file.read_text(encoding='utf-8')
            except:
                last_content = None
            # 更新state以反映实际进度
            if state["progress"]["current_chapter"] < ch_num:
                state["progress"]["current_chapter"] = ch_num
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            success += 1
            continue
        
        # 创建车间任务
        if workshop_db:
            info = state.get("project_info", {})
            task_id = workshop_db.create_task(
                project_name=info.get("title", project_dir.name),
                chapter_num=ch_num,
                title=f"第{ch_num}章",
                mode=info.get("genre", "general"),
                platform=info.get("platform", "qimao")
            )
            workshop_db.update_task_status(task_id, "running")

        # 构建上下文：读前序章节 + 上一轮生成的内容
        context_parts = []
        if CONFIG["auto_context"] and ch_num > 1:
            prev_context = get_context_chapters(project_dir, ch_num)
            if prev_context:
                context_parts.append(prev_context)
        if last_content:
            context_parts.append(f"## 上一章（第{ch_num-1}章）结尾（确保衔接）\n\n{last_content[-500:]}\n")

        context_content = "\n".join(context_parts) if context_parts else ""
        if context_content:
            print(f"✓ 已加载上下文（{len(context_content)}字符）")

        # 章节任务：如果能读到章节规划就用规划，否则用默认
        chapter_task = "继续推进剧情，保持爽点和钩子密度"
        plan_file = project_dir / "大纲" / "章节规划.md"
        if plan_file.exists():
            plan_text = plan_file.read_text(encoding='utf-8')
            section_head = f"## 第{ch_num}章"
            if section_head in plan_text:
                try:
                    plan_section = plan_text.split(section_head, 1)[1].split("## ", 1)[0].strip()
                    if "- 任务:" in plan_section:
                        chapter_task = plan_section.split("- 任务:", 1)[1].split("\n", 1)[0].strip()
                        print(f"✓ 从章节规划读取任务: {chapter_task[:50]}...")
                except Exception as e:
                    logger.warning(f"读取章节规划失败: {e}")

        # 使用智能提示词
        prompt = build_smart_prompt(state, chapter_task, ch_num, context_content)
        print(f"✓ 已注入模式+平台规则")
        
        # 记录车间步骤
        content = None
        if task_id:
            step_id = workshop_db.create_workshop_step(task_id, 2, prompt)  # W2 草稿车间
            workshop_db.start_workshop_step(step_id)
            step_start_time = time.time()

        # 重试机制
        max_retries = 2
        for retry in range(max_retries + 1):
            if retry > 0:
                print(f"🔄 重试第{retry}次...")
                time.sleep(1)
            
            content = call_ai(prompt)
            if content:
                break
        
        # 记录车间步骤完成
        if step_id and step_start_time:
            duration = time.time() - step_start_time
            if content:
                workshop_db.complete_workshop_step(
                    step_id, content, CONFIG["model"], 
                    CONFIG["temperature"], len(content), duration
                )
            else:
                workshop_db.fail_workshop_step(step_id, "AI生成失败")

        if content:
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(content)
            # 只在成功时更新进度
            state["progress"]["current_chapter"] = ch_num
            state["chapter_meta"][f"chapter_{ch_num}"] = {
                "task": chapter_task,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_generated": True,
                "workshop_task_id": task_id
            }
            # 立即保存状态，防止中断丢失
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            
            # 保存章节输出到车间数据库
            if task_id:
                workshop_db.save_chapter_output(
                    task_id, f"第{ch_num}章", content, is_final=True
                )
                workshop_db.update_task_status(task_id, "completed")

            word_count = len(content.replace('\n', '').replace(' ', ''))
            print(f"✓ 第{ch_num}章已保存 ({word_count}字)")
            last_content = content  # 传递给下一章
            success += 1
            
            # 同时在统一数据库中更新项目进度和创建章节记录
            db = init_unified_db()
            if db:
                try:
                    project = db.get_project_by_dir(str(project_dir))
                    if project:
                        total_words = sum(
                            len((project_dir / "正文" / f"第{ch}章.txt").read_text(encoding='utf-8')) 
                            for ch in range(1, ch_num + 1)
                            if (project_dir / "正文" / f"第{ch}章.txt").exists()
                        )
                        db.update_project_progress(project["id"], ch_num, total_words)
                        
                        # 同时创建章节记录
                        db.create_chapter(
                            project_id=project["id"],
                            chapter_num=ch_num,
                            title=f"第{ch_num}章",
                            task=chapter_task,
                            word_count=word_count,
                            ai_generated=True,
                            workshop_task_id=task_id
                        )
                except Exception as e:
                    logger.warning(f"同步进度到数据库失败，继续运行: {e}")
        else:
            print(f"✗ 第{ch_num}章生成失败")
            if task_id:
                workshop_db.update_task_status(task_id, "failed", "AI生成失败")
            failed += 1
            # 询问用户是否继续
            if failed < 2:  # 只在连续失败较少时询问
                try:
                    choice = input("\n是否继续生成下一章？(y/n, 默认y): ").strip().lower()
                    if choice and choice != 'y':
                        print("已停止批量生成")
                        break
                except Exception:
                    pass

    print(f"\n批量生成完成！成功 {success}/{count} 章，失败 {failed} 章，进度已保存")


def show_workshop_tasks(project_dir):
    """显示车间任务记录"""
    if WorkshopDBManager is None:
        print("车间数据库模块不可用！")
        return
    
    workshop_db = init_workshop_db()
    if not workshop_db:
        print("车间数据库连接失败！")
        return
    
    state_file = project_dir / "state.json"
    state = json.loads(state_file.read_text(encoding='utf-8'))
    project_name = state.get("project_info", {}).get("title", project_dir.name)
    
    tasks = workshop_db.list_tasks(project_name=project_name)
    
    if not tasks:
        print("\n没有找到该项目的车间任务记录！")
        return
    
    print("\n" + "="*80)
    print(f"  {project_name} - 车间任务记录")
    print("="*80)
    
    for task in tasks:
        print(f"\n[{task['id']}] {task['title']} (第{task['chapter_num']}章)")
        print(f"    状态: {task['status']} | 模式: {task['mode']} | 平台: {task['platform']}")
        print(f"    创建时间: {task['created_at']}")
        
        # 获取任务进度
        progress = workshop_db.get_task_progress(task['id'])
        if progress:
            print(f"    进度: {progress['completed_steps']}/{progress['total_steps']} 车间已完成")
            if progress['last_completed_workshop'] >= 0:
                print(f"    最后完成车间: W{progress['last_completed_workshop']}")
        
        # 获取章节输出
        output = workshop_db.get_final_chapter_output(task['id'])
        if output:
            print(f"    输出字数: {output['word_count']}")
    
    print("\n" + "="*80)
    
    # 显示统计
    stats = workshop_db.get_workshop_stats()
    print(f"\n车间系统统计:")
    print(f"  总任务数: {stats.get('total_tasks', 0)}")
    print(f"  任务状态分布: {stats.get('by_status', {})}")
    
    # 提示用户输入任务ID查看详情
    task_id = input("\n输入任务ID查看详情（0返回）: ").strip()
    if task_id.isdigit() and int(task_id) > 0:
        show_task_detail(workshop_db, int(task_id))


def generate_with_five_workshop(project_dir, chapter_num, chapter_task=None):
    """
    使用五车间流水线生成单章
    简化版：集成W0-W4的核心流程
    """
    if not HAS_FIVE_WORKSHOP:
        print("✗ 五车间流水线不可用，请检查backend目录的模块！")
        return None
    
    print(f"\n{'='*60}")
    print(f"  五车间流水线 - 第{chapter_num}章")
    print(f"{'='*60}")
    
    # 读取项目信息
    state_file = project_dir / "state.json"
    state = json.loads(state_file.read_text(encoding='utf-8'))
    info = state.get("project_info", {})
    
    # 获取前序章节作为上下文
    context_content = ""
    if CONFIG["auto_context"] and chapter_num > 1:
        prev_context = get_context_chapters(project_dir, chapter_num)
        if prev_context:
            context_content = prev_context
            print(f"✓ 已加载前序章节上下文")
    
    # 获取冷库设定
    cold_storage = ""
    lore_file = project_dir / "lore" / "worldview.md"
    if lore_file.exists():
        cold_storage += f"【世界观设定】\n{lore_file.read_text(encoding='utf-8')}\n\n"
    
    char_file = project_dir / "lore" / "characters.md"
    if char_file.exists():
        cold_storage += f"【人物设定】\n{char_file.read_text(encoding='utf-8')}\n\n"
    
    # 如果没有任务，从章节规划读取
    if not chapter_task:
        chapter_task = "继续推进剧情，保持爽点和钩子密度"
        plan_file = project_dir / "大纲" / "章节规划.md"
        if plan_file.exists():
            plan_text = plan_file.read_text(encoding='utf-8')
            section_head = f"## 第{chapter_num}章"
            if section_head in plan_text:
                try:
                    plan_section = plan_text.split(section_head, 1)[1].split("## ", 1)[0].strip()
                    if "- 任务:" in plan_section:
                        chapter_task = plan_section.split("- 任务:", 1)[1].split("\n", 1)[0].strip()
                        print(f"✓ 从章节规划读取任务: {chapter_task[:50]}...")
                except Exception as e:
                    logger.warning(f"读取章节规划失败: {e}")
    
    # ========== 简化版五车间流程 ==========
    results = {}
    
    # 加载车间prompt
    try:
        w1_prompt = load_workshop_prompt(1)
        w2_prompt = load_workshop_prompt(2)
        w3_prompt = load_workshop_prompt(3)
        w4_prompt = load_workshop_prompt(4)
    except Exception as e:
        print(f"✗ 加载车间prompt失败: {e}")
        return None
    
    # W1 - 设定预处理
    print("\n[W1] 开始设定预处理...")
    w1_input = f"""【全书冷库摘要】
{cold_storage[:2000]}

【用户本章任务】
作品名：{info.get('title', '')}
第{chapter_num}章任务：{chapter_task}
字数要求：{CONFIG.get('word_count', 3000)}字
题材：{info.get('genre', '都市')}
模式：{info.get('genre', 'general')}
平台：{info.get('platform', 'fanqie')}

【前序章节上下文】
{context_content}
"""
    w1_result = call_ai(w1_input, system_prompt=w1_prompt, temperature=0.3)
    results["w1_hot_storage"] = w1_result
    print("✓ W1设定预处理完成")
    
    # 提取热库内容（限流500字）
    hot_storage = w1_result[:500]
    
    # W2 - 正文初稿
    print("\n[W2] 开始正文初稿...")
    w2_input = f"""【本章热库】
{hot_storage}

【用户补充要求】
- 本章字数：{CONFIG.get('word_count', 3000)}字
- 题材：{info.get('genre', '都市')}
- 模式：{info.get('genre', 'general')}
- 平台：{info.get('platform', 'fanqie')}
- 章末必须有强钩子
- 严格遵循热库约束，不要调用冷库设定

【前序章节上下文】
{context_content}
"""
    w2_result = call_ai(w2_input, system_prompt=w2_prompt, temperature=0.4)
    results["w2_draft"] = w2_result
    print("✓ W2正文初稿完成")
    
    # W3 - 逻辑质检
    print("\n[W3] 开始逻辑质检...")
    w3_input = f"""【本章热库】
{hot_storage}

【正文初稿】
{w2_result}
"""
    w3_result = call_ai(w3_input, system_prompt=w3_prompt, temperature=0.2)
    results["w3_qc_report"] = w3_result
    
    # 提取修正后的骨架
    if "无需修正" in w3_result or "没有问题" in w3_result:
        corrected_skeleton = w2_result
        print("✓ W3质检通过，无需修正")
    else:
        corrected_skeleton = w3_result
        print("✓ W3质检完成，已生成修正方案")
    
    # W4 - 文笔精修
    print("\n[W4] 开始文笔精修...")
    w4_input = f"""【修正后的骨架】
{corrected_skeleton}

【精修参数】
模式：{info.get('genre', 'general')}
字数要求：{CONFIG.get('word_count', 3000)}字
平台：{info.get('platform', 'fanqie')}
"""
    w4_result = call_ai(w4_input, system_prompt=w4_prompt, temperature=0.7)
    results["w4_final_chapter"] = w4_result
    print("✓ W4精修完成")
    
    print(f"\n{'='*60}")
    print("  五车间流水线完成！")
    print(f"{'='*60}")
    
    return w4_result


def show_task_detail(workshop_db, task_id):
    """显示任务详情"""
    task = workshop_db.get_task(task_id)
    if not task:
        print("任务不存在！")
        return
    
    print("\n" + "="*80)
    print(f"  任务详情: {task['title']}")
    print("="*80)
    
    print(f"\n基本信息:")
    print(f"  项目: {task['project_name']}")
    print(f"  章节: 第{task['chapter_num']}章")
    print(f"  状态: {task['status']}")
    print(f"  模式: {task['mode']}")
    print(f"  平台: {task['platform']}")
    print(f"  创建时间: {task['created_at']}")
    
    # 显示车间步骤
    steps = workshop_db.get_workshop_steps(task_id)
    if steps:
        print(f"\n车间步骤:")
        for step in steps:
            print(f"\n  W{step['workshop_id']} ({step['workshop_name']}): {step['status']}")
            if step['start_time']:
                print(f"    开始: {step['start_time']}")
            if step['end_time']:
                print(f"    结束: {step['end_time']}")
            if step['duration_seconds']:
                print(f"    耗时: {step['duration_seconds']:.2f}秒")
            if step['model_used']:
                print(f"    模型: {step['model_used']}")
            if step['tokens_used']:
                print(f"    Token: {step['tokens_used']}")
            if step['error_message']:
                print(f"    错误: {step['error_message']}")
    
    # 显示RAG检索记录
    rag_records = workshop_db.get_rag_retrievals(task_id)
    if rag_records:
        print(f"\nRAG检索记录:")
        for record in rag_records:
            print(f"  [W{record['workshop_id']}] 检索了 {record['retrieved_count']} 条结果")
    
    # 显示章节输出
    outputs = workshop_db.get_chapter_outputs(task_id)
    if outputs:
        print(f"\n章节输出:")
        for output in outputs:
            print(f"  版本{output['version']} ({'最终版' if output['is_final'] else '草稿'}): {output['word_count']}字")
            if output['content']:
                print(f"  内容预览: {output['content'][:100]}...")
    
    print("\n" + "="*80)


def open_file(file_path):
    """跨平台打开文件"""
    import subprocess
    import platform
    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(file_path)])
    else:
        subprocess.run(["xdg-open", str(file_path)])


def project_menu_optimized(project_dir):
    """优化的项目菜单"""
    state_file = project_dir / "state.json"
    use_workshop_db = False  # 默认不使用车间数据库
    
    while True:
        state = json.loads(state_file.read_text(encoding='utf-8'))
        info = state.get("project_info", {})
        progress = state.get("progress", {})
        
        title = info.get("title", project_dir.name)
        current_ch = progress.get("current_chapter", 0)
        total_ch = info.get("target_chapters", "?")
        
        print("\n" + "="*60)
        print(f"  项目: {title}")
        print(f"  进度: 第{current_ch}章 / {total_ch}章")
        print(f"  车间记录: {'已启用' if use_workshop_db else '未启用'}")
        print("="*60)
        print("  [1] 快速写新章节")
        print("  [2] 五车间模式生成")
        print("  [3] 批量生成章节")
        print("  [4] 查看总大纲")
        print("  [5] 打开最新章节")
        print("  [6] 打开项目文件夹")
        print("  [7] 切换车间记录状态")
        print("  [8] 查看车间任务记录")
        print("  [0] 返回")
        print("="*60)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            write_chapter_quick(project_dir, use_workshop_db)
        elif choice == "2":
            # 五车间模式
            chapter_num = current_ch + 1
            task = input(f"第{chapter_num}章任务描述（可选，回车跳过）: ").strip()
            chapter_task = task if task else None
            
            # 调用五车间生成
            result = generate_with_five_workshop(project_dir, chapter_num, chapter_task)
            
            if result:
                # 保存结果
                chapter_file = project_dir / "正文" / f"第{chapter_num}章.txt"
                with open(chapter_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                
                # 更新状态
                state["progress"]["current_chapter"] = chapter_num
                state["chapter_meta"][f"chapter_{chapter_num}"] = {
                    "task": chapter_task or "使用五车间模式生成",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ai_generated": True,
                    "five_workshop": True
                }
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                
                word_count = len(result.replace('\n', '').replace(' ', ''))
                print(f"\n✓ 第{chapter_num}章已保存！({word_count}字)")
                
                # 询问是否立即打开
                open_now = input("立即打开查看？(y/n, 默认n): ").strip().lower()
                if open_now == "y":
                    open_file(chapter_file)
        elif choice == "3":
            count = input("生成多少章？(默认5): ").strip()
            count = int(count) if count.isdigit() else 5
            batch_generate(project_dir, count, use_workshop_db)
        elif choice == "4":
            outline_file = project_dir / "大纲" / "总大纲.md"
            if outline_file.exists():
                open_file(outline_file)
        elif choice == "5":
            content_dir = project_dir / "正文"
            if content_dir.exists():
                files = list(content_dir.glob("第*.txt"))
                if files:
                    files.sort(key=lambda x: int(re.search(r'第(\d+)章', x.name).group(1)) if re.search(r'第(\d+)章', x.name) else 0)
                    latest = files[-1]
                    open_file(latest)
        elif choice == "6":
            open_file(project_dir)
        elif choice == "7":
            use_workshop_db = not use_workshop_db
            print(f"✓ 车间记录已{'启用' if use_workshop_db else '关闭'}")
        elif choice == "8":
            show_workshop_tasks(project_dir)


def main_menu():
    """优化的主菜单"""
    print_banner()
    
    projects = get_projects()
    
    while True:
        print("\n" + "="*60)
        print("  主菜单")
        print("="*60)
        print(f"  当前模型: {CONFIG['model']}")
        print("="*60)
        print("  [1] 快速创建项目")
        print("  [2] 查看项目列表")
        
        if projects:
            print("  [3] 打开最近项目")
        print("  [0] 退出")
        print("="*60)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            print("再见！")
            break
        
        elif choice == "1":
            project_dir = create_project_quick()
            if project_dir:
                # 问是否直接开始写
                go_on = input("\n现在开始写第一章？(y/n, 默认y): ").strip().lower()
                if not go_on or go_on == "y":
                    project_menu_optimized(project_dir)
        
        elif choice == "2":
            projects = get_projects()
            if not projects:
                print("\n还没有项目！")
                continue
            
            print("\n" + "="*60)
            print("  项目列表")
            print("="*60)
            for i, p in enumerate(projects, 1):
                progress = f" (第{p['current_ch']}章/{p['total_ch']}章)"
                print(f"  [{i}] {p['title']}{progress}")
            print("="*60)
            
            idx_choice = input("\n输入项目编号打开（0返回）: ").strip()
            if idx_choice.isdigit():
                idx = int(idx_choice) - 1
                if 0 <= idx < len(projects):
                    project_menu_optimized(projects[idx]["dir"])
        
        elif choice == "3" and projects:
            project_menu_optimized(projects[0]["dir"])


if __name__ == "__main__":
    main_menu()

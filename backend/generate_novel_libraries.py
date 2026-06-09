#!/usr/bin/env python3
"""
盘古V7.0 小说专属三库生成器
每启动一部新小说，必须独立创建三个库，禁止共用通用素材池。

用法:
  python generate_novel_libraries.py --project=作品名 --mode=female_solo --genre=古代权谋

可用模式:
  general, romance, rule_mystery, urban_power, folk_horror,
  history_scholar, female_solo, healing_life

输出:
  novel_libraries/{project_name}/
  ├── character_atlas.json      人物图谱库
  ├── event_plot_atlas.json     事件剧情图谱库
  ├── exclusive_materials.json  专属素材库
  └── workshop_config.json      车间微调配置（可选）
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import argparse

# ============ 路径 ============
BASE_DIR = Path(__file__).parent.parent
LIBRARIES_DIR = BASE_DIR / "novel_libraries"
MODES_DIR = BASE_DIR / "modes"


def load_mode_config(mode_id: str) -> dict:
    """加载模式配置作为生成模板的参考"""
    path = MODES_DIR / f"{mode_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


# ============ 库1：人物图谱库 ============

def generate_character_atlas(mode_id: str, genre: str) -> dict:
    """生成人物图谱库模板"""
    mode_config = load_mode_config(mode_id)

    templates = {
        "female_solo": {
            "protagonist_note": "无CP大女主：删除所有恋爱线，事业线唯一核心。女性同盟是核心情感纽带。",
            "relationship_types": ["对手", "工具人", "垫脚石", "女性盟友", "师徒", "宿敌"],
        },
        "history_scholar": {
            "protagonist_note": "历史考据流：主角的核心优势是历史知识，知识库有等级限制。",
            "relationship_types": ["历史对手", "政见同盟", "知识传承者", "时代局限者", "制度博弈方"],
        },
        "urban_power": {
            "protagonist_note": "都市职业异能：异能和职业深度绑定，现实压力是成长驱动力。",
            "relationship_types": ["直属领导", "竞争对手", "潜在盟友", "行业前辈", "职场拖累者"],
        },
        "folk_horror": {
            "protagonist_note": "中式民俗悬疑：主角有民俗职业身份，禁忌感和仪式感是核心。",
            "relationship_types": ["师承渊源", "同行竞争", "民俗知情人", "因果关联者", "禁忌触碰者"],
        },
    }

    tpl = templates.get(mode_id, {
        "protagonist_note": "标准网文人设：主角有清晰的成长弧光和记忆点特征。",
        "relationship_types": ["战友", "宿敌", "遗憾故人", "潜在盟友"],
    })

    return {
        "meta": {
            "project": "{{PROJECT_NAME}}",
            "mode": mode_id,
            "genre": genre,
            "version": "1.0",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "note": tpl["protagonist_note"],
        },
        "character_core_library": {
            "description": "底层内核库：每个角色绑定原生创伤、执念、底线、隐性怪癖",
            "template": {
                "name": "角色名",
                "role": "主角/核心反派/重要配角",
                "native_trauma": "原生创伤（童年/过去的关键事件，塑造了角色的核心恐惧或驱动）",
                "obsession": "执念（角色最想要的东西，可能是权力/认可/复仇/真相/保护某人）",
                "bottom_line": "底线（角色绝对不会做的事，或绝对不会跨越的边界）",
                "hidden_quirk": "隐性怪癖（一个让角色鲜活的小习惯/小毛病，不为外人知）",
                "voice": "声音特征（说话方式、常用词、语速、沉默的习惯）",
                "appearance_core": "核心视觉特征（1-2个让人一眼记住的外形特征，如：总是戴着旧手套、左眉有疤）",
            },
            "required_count": "至少创建：主角 + 核心反派 + 2个重要配角",
            "characters": [
                {
                    "name": "（输入角色名）",
                    "role": "主角",
                    "native_trauma": "",
                    "obsession": "",
                    "bottom_line": "",
                    "hidden_quirk": "",
                    "voice": "",
                    "appearance_core": "",
                },
                {
                    "name": "（输入角色名）",
                    "role": "核心反派",
                    "native_trauma": "",
                    "obsession": "",
                    "bottom_line": "",
                    "hidden_quirk": "",
                    "voice": "",
                    "appearance_core": "",
                },
            ],
        },
        "growth_stages": {
            "description": "阶段成长库：初登场→中期蜕变→结局蜕变三段变化",
            "template": {
                "character": "角色名",
                "initial": {
                    "power_level": "初始能力/地位/资源",
                    "mindset": "初始心态（天真/世故/激进/保守）",
                    "key_flaw": "关键缺陷（阻碍成长的核心问题）",
                },
                "mid_stage": {
                    "trigger_event": "触发中期蜕变的关键事件",
                    "change": "中期变化（性格/能力/关系的显著改变）",
                    "new_flaw": "新出现的缺陷或代价",
                },
                "final_stage": {
                    "trigger_event": "触发最终蜕变的关键事件",
                    "transformation": "结局蜕变（最终形态）",
                    "cost": "付出的最终代价",
                },
            },
            "characters": [],
        },
        "relationships": {
            "description": "羁绊关系库：战友/宿敌/遗憾故人/潜在盟友/女性同盟（female_solo模式必填）",
            "template": {
                "character_a": "角色A",
                "character_b": "角色B",
                "relationship_type": "关系类型",
                "history": "关系历史（他们怎么认识的，过去发生了什么）",
                "current_state": "当前关系状态",
                "conflict_seed": "潜在冲突点（什么情况下他们会反目/合作/牺牲）",
                "emotional_weight": "情感权重（1-10，这段关系对读者情绪的影响强度）",
            },
            "relationships": [],
        },
        "character_conflict_generator": {
            "description": "人物随机冲突生成器：两个人物的内核相遇时自动生成独有矛盾",
            "rules": [
                "当A的执念触碰B的底线 → 爆发不可调和的冲突",
                "当A的原生创伤与B的隐性怪癖重合 → 产生微妙的不信任",
                "当A和B有相同执念但不同底线 → 既是战友也是潜在对手",
                "当A的原生创伤需要B所拥有的东西 → A对B有情感依赖，但同时憎恨这种依赖",
            ],
        },
    }


# ============ 库2：事件剧情图谱库 ============

def generate_event_plot_atlas(mode_id: str, genre: str) -> dict:
    """生成事件剧情图谱库模板"""
    return {
        "meta": {
            "project": "{{PROJECT_NAME}}",
            "mode": mode_id,
            "genre": genre,
            "version": "1.0",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        },
        "unit_event_pool": {
            "description": "单元小事件池（最少10个）。每个事件必须同时满足：①表面是类型化冲突 ②深层隐藏更大的问题 ③触发至少两个人物的内核冲突 ④包含一个反常识设定",
            "events": [
                {
                    "id": "EVT-001",
                    "name": "事件名称",
                    "trigger": "触发条件（什么情况下这个事件会发生）",
                    "surface_conflict": "表面冲突（读者第一眼看到的冲突类型）",
                    "deep_conflict": "深层冲突（事件背后真正的矛盾/产业链/制度性问题）",
                    "characters_involved": ["人物A", "人物B"],
                    "inner_conflict_triggered": "触发的人物内核冲突描述",
                    "anti_common_setting": "反常识设定（让这个事件与众不同的关键）",
                    "possible_outcomes": ["可能结果1", "可能结果2"],
                    "branch_hooks": ["分支伏笔1", "分支伏笔2"],
                }
            ],
            "required_count": 10,
        },
        "long_term_foreshadowing_pool": {
            "description": "长线伏笔事件池（最少4条线）。每大事件预埋3-5处跨章节隐性伏笔，零散小事后期串联引爆。",
            "foreshadowing_lines": [
                {
                    "id": "FS-001",
                    "name": "伏笔线名称",
                    "seed_chapters": ["埋设章节编号"],
                    "harvest_chapter": "回收章节编号",
                    "seed_content": "伏笔的具体内容（一个物件/一句话/一个异常细节）",
                    "reveal_content": "回收时揭示的真相",
                    "reader_reaction": "预期读者反应（恍然大悟/细思极恐/泪目）",
                    "status": "待埋设/已埋设/待回收/已回收",
                }
            ],
            "required_count": 4,
        },
        "modular_plot_matrix": {
            "description": "模块化拼接矩阵：事件A+B+C可重组，不再固定开篇遇险→中段升级→结尾决战",
            "arc_structure": {
                "opening_arc": ["推荐的开篇事件组合（2-3个事件ID）"],
                "mid_development": ["推荐的推进事件组合（3-5个事件ID）"],
                "climax_options": ["可选的高潮事件组合（2-3个事件ID）"],
                "ending_options": ["可选的结局走向（基于不同的事件回收情况）"],
            },
        },
    }


# ============ 库3：专属素材库 ============

def generate_exclusive_materials(mode_id: str, genre: str) -> dict:
    """生成专属素材库模板"""
    mode_suggestions = {
        "female_solo": {
            "worldview_note": "建议收录：女性主导的隐秘组织、打破性别壁垒的行业、没有男性干预的社交空间",
            "prop_note": "建议能力设计：能力必须有代价（如：说真话的能力=每月失去一段记忆）",
            "environment_note": "建议场景：女性专属的深夜茶室、只有女性知道的地下通道、女校旧址",
        },
        "history_scholar": {
            "worldview_note": "建议收录：冷门朝代的真实制度细节、失传的古代技艺、被遗忘的历史事件",
            "prop_note": "建议道具：有真实历史考据的器物、古籍、地图、信物",
            "environment_note": "建议场景：古代衙门、书院、军营、市集、驿站、朝堂",
        },
        "urban_power": {
            "worldview_note": "建议收录：各类小众职业的行业黑话和工作流程、都市传说、城市隐秘空间",
            "prop_note": "建议能力：职业工具变成异能媒介、日常物品有隐藏功能",
            "environment_note": "建议场景：深夜便利店、地下车库、天台、老小区、24小时快餐店",
        },
        "folk_horror": {
            "worldview_note": "建议收录：真实存在的民间传说和禁忌（可查证）、地方丧葬习俗、风水口诀",
            "prop_note": "建议道具：有灵性的职业工具（如捞尸绳、纸扎人、罗盘、铜钱剑）",
            "environment_note": "建议场景：黄河渡口、深夜义庄、雨中的纸扎铺、废弃祠堂、封了三十年的老井",
        },
    }

    tips = mode_suggestions.get(mode_id, {
        "worldview_note": "建议收录：独特的世界观法则、势力划分、稀有资源/货币体系",
        "prop_note": "建议道具：拒绝冰火雷三系异能。能力附带副作用。每件道具有过往故事。",
        "environment_note": "建议场景：替换山洞寻宝/深山修炼。每个场景必须有'情绪功能'而非单纯背景。",
    })

    return {
        "meta": {
            "project": "{{PROJECT_NAME}}",
            "mode": mode_id,
            "genre": genre,
            "version": "1.0",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        },
        "worldview_materials": {
            "description": "世界观设定素材库 — " + tips["worldview_note"],
            "items": [
                {
                    "id": "WV-001",
                    "name": "素材名称",
                    "category": "地理/法则/文明/势力/经济体系",
                    "description": "具体描述（让读者能'看见'这个设定）",
                    "emotional_function": "这个设定给读者的情绪体验（新奇/震撼/压抑/温暖）",
                    "usage_constraint": "使用限制（这个设定不能和什么冲突）",
                }
            ],
            "required_count": 5,
        },
        "prop_ability_materials": {
            "description": "道具/能力素材库 — " + tips["prop_note"],
            "items": [
                {
                    "id": "PA-001",
                    "name": "道具/能力名称",
                    "type": "道具/能力",
                    "function": "功能描述",
                    "side_effect": "副作用或代价（必须有）",
                    "backstory": "过往故事（它从哪里来，经历过什么）",
                    "emotional_anchor": "情感锚点（读者为什么会记住它）",
                    "upgrade_path": "升级路线（可选，用于长线剧情）",
                }
            ],
            "required_count": 5,
        },
        "environment_atmosphere_materials": {
            "description": "环境氛围素材库 — " + tips["environment_note"],
            "items": [
                {
                    "id": "EA-001",
                    "name": "场景名称",
                    "location": "具体位置",
                    "time": "最佳出现时间（清晨/深夜/雨夜/黄昏）",
                    "sensory_details": {
                        "视觉": "看到的画面描述",
                        "听觉": "听到的声音描述",
                        "嗅觉": "闻到的气味描述",
                        "触觉": "触感/温度/湿度描述",
                    },
                    "emotional_function": "这个场景给读者的情绪体验",
                    "plot_function": "这个场景适合推动什么类型的剧情",
                }
            ],
            "required_count": 5,
        },
        "anti_routine_twist_materials": {
            "description": "反套路转折素材库 — 眼看胜利突然失去关键能力、反派动机是守护苍生而非称霸世界",
            "items": [
                {
                    "id": "TW-001",
                    "name": "反转类型",
                    "trigger_point": "触发节点（什么剧情阶段使用这个反转）",
                    "expected_reader_reaction": "预期读者反应",
                    "setup_required": "前置铺垫要求（需要提前埋设什么信息）",
                    "example": "具体示例（在什么故事里可以怎么用）",
                }
            ],
            "required_count": 5,
        },
    }


# ============ 库4：车间微调配置（可选） ============

def generate_workshop_config(mode_id: str) -> dict:
    """生成车间微调配置"""
    mode_config = load_mode_config(mode_id)

    return {
        "mode": mode_id,
        "version": "1.0",
        "temperature_overrides": {
            "w1": 0.3,
            "w2": mode_config.get("w4_special", {}).get("temperature", 0.4),
            "w3": 0.2,
            "w4": mode_config.get("w4_special", {}).get("temperature", 0.8),
        },
        "special_instructions": {
            "w1_note": mode_config.get("w1_special", {}).get("focus", ""),
            "w2_note": f"钩子类型: {', '.join(mode_config.get('w2_special', {}).get('hook_types', []))}" if mode_config.get("w2_special") else "",
            "w3_checks": (mode_config.get("w3_special", {}).get("strict_checks", [])),
            "w4_techniques": (mode_config.get("w4_special", {}).get("atmosphere_techniques", [])),
        },
        "fusion_allowed": True,
        "fusion_preferences": mode_config.get("fusion_compatibility", {}),
    }


# ============ 主逻辑 ============

def create_project(
    project_name: str,
    mode_id: str = "general",
    genre: str = "都市",
    force: bool = False,
) -> dict:
    """
    为指定项目创建三库文件。
    如果目录已存在且非force模式，跳过不覆盖。
    """
    project_dir = LIBRARIES_DIR / project_name
    result = {
        "project": project_name,
        "mode": mode_id,
        "genre": genre,
        "created": False,
        "files": [],
        "errors": [],
    }

    # 检查是否已存在
    if project_dir.exists() and not force:
        existing = list(project_dir.glob("*.json"))
        if existing:
            result["errors"].append(f"目录已存在且包含 {len(existing)} 个JSON文件。使用 --force 覆盖。")
            return result

    # 创建目录
    project_dir.mkdir(parents=True, exist_ok=True)

    # 生成各库
    generators = {
        "character_atlas.json": generate_character_atlas(mode_id, genre),
        "event_plot_atlas.json": generate_event_plot_atlas(mode_id, genre),
        "exclusive_materials.json": generate_exclusive_materials(mode_id, genre),
        "workshop_config.json": generate_workshop_config(mode_id),
    }

    for filename, data in generators.items():
        filepath = project_dir / filename
        try:
            # 替换占位符
            data_str = json.dumps(data, ensure_ascii=False, indent=2)
            data_str = data_str.replace("{{PROJECT_NAME}}", project_name)
            data_str = data_str.replace("{{MODE_ID}}", mode_id)
            data_str = data_str.replace("{{GENRE}}", genre)

            filepath.write_text(data_str, encoding="utf-8")
            result["files"].append(str(filepath.relative_to(BASE_DIR)))
        except Exception as e:
            result["errors"].append(f"写入 {filename} 失败: {str(e)}")

    result["created"] = len(result["errors"]) == 0
    return result


def list_available_modes() -> list:
    """列出所有可用的模式"""
    modes = []
    for path in sorted(MODES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            modes.append({
                "id": path.stem,
                "name": data.get("name", path.stem),
                "description": data.get("description", "")[:80],
            })
        except Exception:
            modes.append({"id": path.stem, "name": path.stem, "description": ""})
    return modes


def list_existing_projects() -> list:
    """列出所有已有三库的项目"""
    projects = []
    if not LIBRARIES_DIR.exists():
        return projects
    for d in LIBRARIES_DIR.iterdir():
        if d.is_dir():
            json_files = list(d.glob("*.json"))
            projects.append({
                "name": d.name,
                "files": [f.name for f in json_files],
                "count": len(json_files),
            })
    return projects


# ============ CLI入口 ============

def main():
    # Windows GBK 编码兼容
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(
        description="盘古V7.0 小说专属三库生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建新项目三库
  python generate_novel_libraries.py --project=我的新书 --mode=female_solo --genre=古代权谋

  # 强制覆盖已存在的项目
  python generate_novel_libraries.py --project=分手事务所 --mode=urban_power --genre=都市职场 --force

  # 查看可用模式
  python generate_novel_libraries.py --list-modes

  # 查看已有项目
  python generate_novel_libraries.py --list-projects
        """,
    )

    parser.add_argument("--project", "-p", help="项目名称（英文或中文）")
    parser.add_argument("--mode", "-m", default="general", help="创作模式（默认: general）")
    parser.add_argument("--genre", "-g", default="都市", help="题材分类（默认: 都市）")
    parser.add_argument("--force", "-f", action="store_true", help="强制覆盖已存在的文件")
    parser.add_argument("--list-modes", action="store_true", help="列出所有可用模式")
    parser.add_argument("--list-projects", action="store_true", help="列出所有已有项目")

    args = parser.parse_args()

    if args.list_modes:
        print("\n📋 可用模式:")
        print("=" * 60)
        for mode in list_available_modes():
            print(f"  {mode['id']:20s} {mode['name']}")
            if mode['description']:
                print(f"  {'':20s} {mode['description']}")
            print()
        return

    if args.list_projects:
        projects = list_existing_projects()
        if not projects:
            print("\n📭 还没有创建任何项目三库。")
            print(f"   存储位置: {LIBRARIES_DIR}")
            return
        print("\n📚 已有项目:")
        print("=" * 60)
        for proj in projects:
            status = "✅ 完整" if proj["count"] >= 4 else f"⚠️  部分 ({proj['count']}/4)"
            print(f"  {proj['name']:20s} {status}")
            for f in proj["files"]:
                print(f"    └─ {f}")
            print()
        return

    if not args.project:
        parser.print_help()
        print("\n❌ 请使用 --project 指定项目名称")
        return

    # 验证模式是否存在
    available = [m["id"] for m in list_available_modes()]
    if args.mode not in available:
        print(f"\n❌ 模式 '{args.mode}' 不存在。可用模式: {', '.join(available)}")
        return

    print(f"\n🚀 创建项目三库: {args.project}")
    print(f"   模式: {args.mode}")
    print(f"   题材: {args.genre}")
    print("=" * 50)

    result = create_project(args.project, args.mode, args.genre, args.force)

    if result["errors"]:
        print(f"\n❌ 创建失败:")
        for err in result["errors"]:
            print(f"   {err}")
        return

    print(f"\n✅ 三库创建成功!")
    print(f"   位置: {LIBRARIES_DIR / result['project']}")
    print(f"   文件:")
    for f in result["files"]:
        print(f"     📄 {f}")
    print(f"\n   下一步: 编辑上述JSON文件，填入你的人物设定、事件规划和专属素材。")
    print(f"   然后在生成章节时传入 project_name='{args.project}' 即可自动加载三库。")

    if args.mode in ["female_solo", "history_scholar", "folk_horror"]:
        print(f"\n   💡 提示: '{args.mode}' 模式的特殊要求已预设在模板中，请务必阅读相关字段的说明。")
        print(f"      女性角色/考据细节/民俗元素等核心约束已标注在JSON注释中。")


if __name__ == "__main__":
    main()

"""
五车间流水线桥接模块
让 CLI 能够调用 backend/app_v7.py 的 SchedulerV7 五车间流水线
"""

import sys
import json
from pathlib import Path

# 添加 backend 目录到路径
BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

try:
    from app_v7 import SchedulerV7, load_mode_config
    HAS_SCHEDULER = True
except ImportError as e:
    HAS_SCHEDULER = False
    print(f"[WARN] 无法导入 SchedulerV7: {e}")


def run_workshop_pipeline_api(project_dir, chapter_task, chapter_num=None):
    """
    通过 API 方式调用五车间流水线（使用 SchedulerV7）
    
    参数:
        project_dir: 项目目录路径
        chapter_task: 章节任务描述
        chapter_num: 章节号（可选，自动从 state.json 获取）
    
    返回:
        dict: 包含各车间输出的结果
    """
    if not HAS_SCHEDULER:
        return {"success": False, "error": "SchedulerV7 不可用"}
    
    project_path = Path(project_dir)
    state_file = project_path / "state.json"
    
    if not state_file.exists():
        return {"success": False, "error": "项目状态文件不存在"}
    
    try:
        state = json.loads(state_file.read_text(encoding='utf-8'))
    except Exception as e:
        return {"success": False, "error": f"读取状态文件失败: {e}"}
    
    info = state.get("project_info", {})
    title = info.get("title", project_path.name)
    mode = info.get("genre", "general")
    platform = info.get("platform", "qimao")
    cold_storage = json.dumps(state, ensure_ascii=False)[:2000]  # 作为冷库数据
    
    if chapter_num is None:
        chapter_num = state.get("progress", {}).get("current_chapter", 0) + 1
    
    # 构建 SchedulerV7 输入
    user_input = {
        "title": title,
        "chapter_num": chapter_num,
        "chapter_task": chapter_task,
        "word_count": 2000,
        "cold_storage": cold_storage,
        "genre": mode,
        "mode": mode,
        "platform": platform,
        "project_name": project_path.name,
    }
    
    # 执行五车间流水线
    scheduler = SchedulerV7(user_input)
    result = scheduler.run()
    
    return result


def generate_chapter_with_workshop(project_dir, chapter_task, chapter_num=None):
    """
    使用五车间流水线生成章节，并保存结果
    
    参数:
        project_dir: 项目目录路径
        chapter_task: 章节任务描述
        chapter_num: 章节号（可选）
    
    返回:
        tuple: (success: bool, content: str, logs: list)
    """
    project_path = Path(project_dir)
    result = run_workshop_pipeline_api(project_path, chapter_task, chapter_num)
    
    if not result.get("success", False):
        return False, "", result.get("logs", [])
    
    final_content = result.get("results", {}).get("w4_final_chapter", "")
    if not final_content:
        return False, "", result.get("logs", [])
    
    # 确定章节号
    chapter_num = result.get("chapter", chapter_num)
    if chapter_num is None:
        state_file = project_path / "state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding='utf-8'))
                chapter_num = state.get("progress", {}).get("current_chapter", 0) + 1
            except:
                chapter_num = 1
        else:
            chapter_num = 1
    
    # 保存章节文件
    chapter_file = project_path / "正文" / f"第{chapter_num}章.txt"
    chapter_file.parent.mkdir(exist_ok=True)
    chapter_file.write_text(final_content, encoding='utf-8')
    
    # 更新状态文件
    state_file = project_path / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding='utf-8'))
            state["progress"]["current_chapter"] = chapter_num
            state["chapter_meta"][f"chapter_{chapter_num}"] = {
                "task": chapter_task,
                "created_at": result.get("created_at", ""),
                "ai_generated": True,
                "engine_version": "v7_workshop",
                "workshop_results": result.get("results", {}),
            }
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[WARN] 更新状态文件失败: {e}")
    
    return True, final_content, result.get("logs", [])


def get_workshop_logs(result):
    """从流水线结果中提取日志"""
    logs = result.get("logs", [])
    if not isinstance(logs, list):
        logs = []
    return logs


def print_workshop_summary(result):
    """打印五车间流水线执行摘要"""
    print("\n" + "="*60)
    print("  五车间流水线执行摘要")
    print("="*60)
    
    if result.get("success", False):
        chapter = result.get("chapter", "?")
        mode = result.get("mode", "?")
        platform = result.get("platform", "?")
        
        print(f"\n✓ 执行成功")
        print(f"  章节: 第{chapter}章")
        print(f"  模式: {mode}")
        print(f"  平台: {platform}")
        
        results = result.get("results", {})
        if results:
            print("\n  各车间输出:")
            for key, value in results.items():
                if isinstance(value, str):
                    print(f"    {key}: {len(value)}字")
        
        logs = result.get("logs", [])
        if logs:
            print("\n  执行日志:")
            for log in logs[-5:]:  # 只显示最后5条
                time = log.get("time", "")
                stage = log.get("stage", "")
                message = log.get("message", "")
                print(f"    [{time}] {stage}: {message}")
    else:
        print(f"\n✗ 执行失败")
        reason = result.get("reason", "")
        blocked_by = result.get("blocked_by", "")
        print(f"  原因: {reason}")
        print(f"  阻断环节: {blocked_by}")
    
    print("\n" + "="*60)

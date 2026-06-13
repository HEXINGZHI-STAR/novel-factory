#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深渊猎人 - 第1章流水线测试
测试五车间流水线：W0锚定→W1预处理→W2初稿→W3质检→W4精修
"""

import sys
import json
from pathlib import Path

# 强制刷新输出
import functools
print = functools.partial(print, flush=True)

# 添加路径
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "knowledge"))
sys.path.insert(0, str(BASE_DIR / "backend"))

# 加载.env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

import os

# 设置更短的超时
os.environ["TIMEOUT"] = "60"

# 导入AI调用函数
from pangu_optimized import call_ai, init_workshop_db, CONFIG
CONFIG["timeout"] = 60  # 缩短超时

# 导入工作流引擎
from workflow_engine import run_workflow_pipeline

# 项目配置
PROJECT_DIR = BASE_DIR / "projects" / "深渊猎人"

def main():
    print("=" * 60)
    print("  深渊猎人 - 第1章流水线测试")
    print("  五车间: W0锚定→W1预处理→W2初稿→W3质检→W4精修")
    print("=" * 60)

    # 读取项目状态
    state_file = PROJECT_DIR / "state.json"
    if not state_file.exists():
        print("[ERROR] state.json 不存在！")
        return

    state = json.loads(state_file.read_text(encoding='utf-8'))
    info = state.get("project_info", {})

    # 第1章任务
    chapter_task = """开篇：蚀潮来袭，沈渊觉醒

场景：壁垒城下城，废墟拾荒区
时间：黄昏

核心事件：
1. 沈渊在下城废墟拾荒，发现一块疑似蚀物残核的碎片
2. 警报响起——蚀潮来袭，下城防线被突破
3. 沈渊在逃亡中被2阶蚀物追击，无路可退
4. 被逼入深渊裂缝边缘，坠入裂缝
5. 在裂缝中觉醒深渊之眼——左眼变黑，看到蚀物弱点
6. 一击秒杀2阶蚀物，救下被困的拾荒者
7. 但使用能力后，童年的一段记忆变得模糊

爽点：觉醒+秒杀
钩子：记忆模糊的暗示+深渊之眼上一任持有者已疯的传闻

要求：
- 对话率≥42%
- 主角说话≤10字
- 禁用"他感到""缓缓地""突然""瞳孔""嘴角勾起"
- 每300字一个微钩子
- 章末强钩子
- 字数2500-3000字"""

    # 构建流水线输入
    initial_input = {
        "title": info.get("title", "深渊猎人"),
        "chapter_task": chapter_task,
        "mode": info.get("mode", "urban_power"),
        "platform": info.get("platform", "qimao"),
        "current_chapter": 1,
        "context": "",
        "project_dir": str(PROJECT_DIR),
        "extra": {},
    }

    print(f"\n  作品: {initial_input['title']}")
    print(f"  模式: {initial_input['mode']}")
    print(f"  平台: {initial_input['platform']}")
    print(f"  章节: 第{initial_input['current_chapter']}章")
    print()

    # 初始化车间数据库
    wdb = init_workshop_db()

    # 运行五车间流水线
    result = run_workflow_pipeline(
        call_ai_func=call_ai,
        initial_input=initial_input,
        wdb=wdb,
        use_ai=True,
        collaborative_mode=None,  # 纯API流水线
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("  流水线执行结果")
    print("=" * 60)

    success = result.get("success", False)
    print(f"  状态: {'成功' if success else '失败'}")

    all_outputs = result.get("all_outputs", {})
    for stage_id, output in sorted(all_outputs.items()):
        content = output if isinstance(output, str) else str(output)
        print(f"  W{stage_id}: {len(content)}字")

    final_content = result.get("final_content", "")
    if final_content:
        print(f"\n  最终成品: {len(final_content)}字")

        # 保存章节
        chapter_file = PROJECT_DIR / "正文" / "第1章_蚀潮觉醒.txt"
        chapter_file.write_text(final_content, encoding='utf-8')
        print(f"  已保存: {chapter_file}")

        # 更新state.json
        state["progress"]["current_chapter"] = 1
        state["progress"]["total_words"] = len(final_content.replace('\n', '').replace(' ', ''))
        state["progress"]["last_update"] = "2026-06-10"
        state["chapter_meta"]["chapter_1"] = {
            "task": chapter_task[:50],
            "created_at": "2026-06-10",
            "ai_generated": True,
            "engine_version": "workflow_v2",
            "word_count": len(final_content.replace('\n', '').replace(' ', ''))
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  state.json 已更新")

        # 质量快检
        print("\n" + "-" * 40)
        print("  质量快检")
        print("-" * 40)

        # 对话率
        dialog_lines = [l for l in final_content.split('\n') if '「' in l or '」' in l or '"' in l or '"' in l or '"' in l]
        total_lines = [l for l in final_content.split('\n') if l.strip()]
        dialog_rate = len(dialog_lines) / max(len(total_lines), 1) * 100
        print(f"  对话率: {dialog_rate:.1f}% {'OK' if dialog_rate >= 42 else 'LOW'}")

        # 禁用词检查
        banned = ["他感到", "缓缓地", "突然", "瞳孔", "嘴角勾起"]
        found_banned = [w for w in banned if w in final_content]
        print(f"  禁用词: {'无' if not found_banned else found_banned}")

        # 字数
        wc = len(final_content.replace('\n', '').replace(' ', ''))
        print(f"  字数: {wc}")
        print(f"  字数范围: {'OK' if 2000 <= wc <= 3500 else 'OUT OF RANGE'}")

    else:
        print("\n  [ERROR] 未生成最终内容！")
        # 打印各阶段输出用于调试
        for stage_id, output in sorted(all_outputs.items()):
            content = output if isinstance(output, str) else str(output)
            print(f"\n  --- W{stage_id} 输出 (前200字) ---")
            print(content[:200])


if __name__ == "__main__":
    main()

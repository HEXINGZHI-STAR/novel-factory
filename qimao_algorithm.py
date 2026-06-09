#!/usr/bin/env python3
"""
七猫过稿算法 · 专坑编辑版
============================
基于七猫编辑审稿SOP逆向工程
15秒内决定签不签 -> 每一秒都要炸
"""

import re, json, sys
from pathlib import Path

# ═══════════════════════════════════════════
# 七猫过稿铁律（编辑不会告诉你的）
# ═══════════════════════════════════════════

class QimaoAlgorithm:
    def __init__(self):
        # 编辑审稿14秒拆解
        self.editor_timeline = [
            (0, 3, "扫第一段", "必须有人死/被打脸/被贬/收到噩耗/系统激活"),
            (3, 6, "扫前三段", "必须确认主角是谁+他遇到什么麻烦"),
            (6, 9, "扫中间段落", "看节奏——段落不能超过3行，对话不能连着三句以上没人说话"),
            (9, 12, "扫结尾", "必须有钩子——悬念/危机/打脸预告"),
            (12, 14, "扫书名+简介", "书名必须一眼知道卖什么，简介第一句必须出金手指"),
        ]

        # 七猫编辑直接拒稿暗语（看到就划走）
        self.instant_reject_patterns = [
            (r'^(春日|夏夜|秋风|冬雪|清晨|黄昏|夜幕).{0,30}[，,]', "写景开篇 死"),
            (r'^.{0,50}(从睡梦中|睁开眼睛|揉着眼睛|打了个哈欠)', "苏醒开篇 死"),
            (r'^.{0,100}(穿越|重生|附身)到了.{1,20}(年|朝代|世界)', "穿越自述开篇 死"),
            (r'^.{0,30}(是|叫).{2,4}的(大学生|高中生|上班族|普通人)', "身份介绍开篇 死"),
            (r'(瞳孔骤缩|倒吸一口凉气|嘴角勾起|冷哼一声|心中涌起)', "AI模板词 死"),
            (r'段落长度>60字', "长段落 扣分"),
            (r'连续5段以上没有对话', "没有对话 扣分"),
        ]

        # 七猫编辑爱看的开篇模式（看到就多看5秒）
        self.editor_loves = [
            "打架/死人/灾难/被扇耳光/被背叛/被当众羞辱/被开除/系统激活/看到不该看的/听到不该听的",
            "第一句话就是对话——而且是对骂",
            "主角第一句话就捅刀子——不是真捅就是准备捅",
            "开头有人笑，最后一行这个人哭了——或者死了",
        ]

    def check(self, filepath: str) -> dict:
        """对单章做七猫过稿诊断"""
        content = Path(filepath).read_text(encoding='utf-8')
        body = re.sub(r'^第.+?章.+\n', '', content).strip()
        lines = [l.strip() for l in body.split('\n') if l.strip()]

        report = {
            "file": filepath,
            "score": 100,
            "issues": [],
            "passes": [],
        }

        # 1. 开篇第一句检查
        first_line = lines[0] if lines else ""
        if re.match(r'^(春日|夏夜|秋风|冬雪|清晨|黄昏|夜幕|月光|阳光|微风)', first_line):
            report["issues"].append(f"[FAIL] 写景开篇: {first_line[:30]}")
            report["score"] -= 30
        elif re.match(r'^.{0,20}(从|在|睁开|揉|打了)', first_line):
            report["issues"].append(f"[FAIL] 苏醒/日常开篇: {first_line[:30]}")
            report["score"] -= 25
        elif '说' in first_line or '道' in first_line or '"' in first_line or '"' in first_line or '“' in first_line:
            report["passes"].append(f"[OK] 对话开篇: {first_line[:30]}")
            report["score"] += 10
        elif any(kw in first_line for kw in ['死','杀','血','死','炸','轰','裂','碎','崩','毁']):
            report["passes"].append(f"[OK] 冲突开篇: {first_line[:30]}")
            report["score"] += 15

        # 2. 前500字冲突检测
        first500 = body[:500]
        conflict_kw = ['死','杀','打','骂','摔','砸','滚','滚蛋','滚开','找死','贱','废物','垃圾','你配','你也配','我不服','为什么是我','凭什么','凭什么是我','我不信','不可能','你疯了','你骗我','你背叛我','离婚','分手','滚出去','开除','罢免','下旨','斩','砍','劈','剁','炸','轰','血','泪']
        conflict_count = sum(first500.count(kw) for kw in conflict_kw)
        if conflict_count < 3:
            report["issues"].append(f"[FAIL] 前500字冲突密度不足: 只有{conflict_count}个冲突词")
            report["score"] -= 20
        else:
            report["passes"].append(f"[OK] 前500字冲突密度: {conflict_count}个冲突词")

        # 3. 段落检查
        long_paras = sum(1 for l in body.split('\n\n') if len(l.replace('\n','')) > 60)
        if long_paras > 2:
            report["issues"].append(f"[FAIL] 长段落过多: {long_paras}个超过60字")
            report["score"] -= 15
        else:
            report["passes"].append("[OK] 段落节奏OK")

        # 4. 对话率
        dialogue_lines = sum(1 for l in lines if '“' in l or '"' in l or '”' in l)
        dr = dialogue_lines * 100 // max(1, len(lines))
        if dr < 30:
            report["issues"].append(f"[FAIL] 对话率不足: {dr}% (需≥30%)")
            report["score"] -= 15
        else:
            report["passes"].append(f"[OK] 对话率: {dr}%")

        # 5. AI高风险词
        ai_words = ['瞳孔骤缩','倒吸一口凉气','嘴角勾起','冷哼一声','冰冷的眼神','脸色大变','心中涌起','猛然','竟然','难以置信','不由的','心头一颤']
        hits = [(w, body.count(w)) for w in ai_words if body.count(w) > 0]
        if hits:
            report["issues"].append(f"[FAIL] AI痕迹词: {hits}")
            report["score"] -= 10 * len(hits)
        else:
            report["passes"].append("[OK] 无AI高风险词")

        # 6. 章末钩子
        last200 = body[-200:]
        hook_kw = ['突然','忽然','竟','竟然','居然','什么','谁','怎么','为什么','哪里','难道','莫非','不好','糟了','完了','不对']
        hook_count = sum(last200.count(kw) for kw in hook_kw)
        if hook_count < 2:
            report["issues"].append("[FAIL] 章末钩子不足")
            report["score"] -= 10
        else:
            report["passes"].append(f"[OK] 章末钩子: {hook_count}个关键词")

        return report

    def batch_check(self, project_dir: str) -> list:
        """检查整个项目的所有章节"""
        results = []
        wen_dir = Path(project_dir) / '正文'
        if not wen_dir.exists():
            return results
        for f in sorted(wen_dir.glob('第*.txt')):
            r = self.check(str(f))
            results.append(r)
        return results

    def print_report(self, report: dict):
        """打印单章报告"""
        print(f"\n{'='*60}")
        print(f"  七猫过稿诊断: {Path(report['file']).name}")
        print(f"  过稿分: {report['score']}/100")
        if report['score'] >= 80: print("  结论: [OK] 可以投稿")
        elif report['score'] >= 60: print("  结论: [WARN]️ 需要改")
        else: print("  结论: [FAIL] 编辑秒拒")
        print(f"{'='*60}")
        if report['passes']:
            for p in report['passes']:
                print(f"  {p}")
        if report['issues']:
            print(f"\n  【需要改】")
            for i in report['issues']:
                print(f"  {i}")

    def print_editor_guide(self):
        """打印七猫编辑审稿内部指南"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║              七猫编辑审稿 · 内部SOP（逆向工程）                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  [0-3秒]  看第一段 → 有没有人死/被打/被贬/被叛/系统激活      ║
║           [FAIL] 写景 → 秒拒                                      ║
║           [FAIL] 苏醒 → 秒拒                                      ║
║           [FAIL] 穿越自述 → 秒拒                                  ║
║           [OK] 对话开篇 → 多看3秒                                ║
║           [OK] 冲突开篇 → 多看5秒                                ║
║                                                              ║
║  [3-6秒]  扫前三段 → 主角是谁 + 他遇到什么麻烦                 ║
║  [6-9秒]  扫中间 → 段落不能超3行，对话不能断                   ║
║  [9-12秒] 扫结尾 → 必须有钩子（悬念/危机/打脸预告）           ║
║  [12-14秒] 扫书名+简介 → 一眼知道卖什么                        ║
║                                                              ║
║  七猫过稿铁律:                                                ║
║  1. 第一行必须在冲突里（死/打/骂/贬/叛/系统激活）              ║
║  2. 段落不超过3行，每段不超过60字                               ║
║  3. 对话率 > 35%                                              ║
║  4. 章末必须留钩子                                            ║
║  5. AI痕迹词一个都不能有                                       ║
║  6. 书名必须一眼知道卖什么                                     ║
║  7. 简介第一句必须出金手指                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════
if __name__ == "__main__":
    algo = QimaoAlgorithm()

    if len(sys.argv) < 2:
        algo.print_editor_guide()
        print("用法:")
        print("  python qimao_algorithm.py check <文件路径>      检查单章")
        print("  python qimao_algorithm.py batch <项目路径>      检查项目")
        print("  python qimao_algorithm.py guide                显示编辑SOP")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "guide":
        algo.print_editor_guide()

    elif cmd == "check" and len(sys.argv) >= 3:
        r = algo.check(sys.argv[2])
        algo.print_report(r)

    elif cmd == "batch" and len(sys.argv) >= 3:
        results = algo.batch_check(sys.argv[2])
        total = len(results)
        passed = sum(1 for r in results if r['score'] >= 80)
        avg = sum(r['score'] for r in results) / max(1, total)
        print(f"\n项目: {sys.argv[2]}")
        print(f"总章节: {total} | 通过: {passed} | 平均分: {avg:.0f}")
        for r in results:
            name = Path(r['file']).name
            status = "[OK]" if r['score'] >= 80 else ("[WARN]️" if r['score'] >= 60 else "[FAIL]")
            print(f"  {status} {name}: {r['score']}分")

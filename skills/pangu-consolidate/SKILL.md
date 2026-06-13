---
name: pangu-consolidate
description: 跨项目模式发现——扫描所有项目审查报告，自动发现"什么样的章节质量最高"
allowed-tools: Read Bash Grep
argument-hint: "[--genre 悬疑] [--metric 对话率]"
---

# 跨项目模式发现

## 目标

扫描所有22个项目的 intelligence 报告，自动发现写作模式和最佳实践。

## 执行流程

## 执行命令

```bash
cd D:\study\近思录\小说\盘古AI && python -c "
import json, sys, os, re
from pathlib import Path
from collections import defaultdict

results = defaultdict(list)

for root in [Path('projects'), Path('../webnovel-test')]:
    if not root.exists(): continue
    for child in root.iterdir():
        intel_dir = child / '.webnovel' / 'intelligence'
        if not intel_dir.exists(): continue
        for intel_file in sorted(intel_dir.glob('*.json')):
            try:
                data = json.loads(intel_file.read_text(encoding='utf-8'))
                proj_name = data.get('project', child.name)
                chapter = data.get('chapter', 0)
                
                # 提取关键指标
                sent = data.get('sentence_stats', {})
                tension = data.get('tension_envelope', {})
                
                results[proj_name].append({
                    'chapter': chapter,
                    'words': data.get('word_count', 0),
                    'mean_len': sent.get('mean_len', 0),
                    'cv': sent.get('cv', 0),
                    'ai_risk': data.get('ai_risk_score', 0),
                    'quality': data.get('quality_posterior', 0),
                    'dialogue': sent.get('dialogue_ratio', 0),
                    'pacing': tension.get('pacing_quality', 0),
                    'audit': data.get('audit_opinion', '?'),
                })
            except: pass

# 输出汇总
print(json.dumps({k: v for k, v in results.items() if v}, ensure_ascii=False, indent=2))
"
```

### Step 2：分析模式

Claude 读取 Step 1 的 JSON 输出，按以下维度分析：

1. **平台对质量的影响**：七猫 vs 起点 vs 知乎，哪个平台的章节评分最高？
2. **题材对句法的影响**：悬疑 vs 玄幻 vs 治愈的句均差异？
3. **质量拐点**：到第几章质量开始下降？（通常是第6-8章）
4. **最佳实践**：哪一章是"满分章节"？它有什么特征？
5. **问题模式**：哪些项目的对话率持续偏低？哪些AI风险波动大？

### Step 3：输出建议

Claude 生成一个 Markdown 报告，包含：
- **策略建议**："七猫悬疑的句均最优区间是18-22字，建议调整W4精修参数"
- **风险预警**："镇妖司第3章开始对话率持续下降，建议第5章加强对话要求"
- **可复用模式**："开门见尸第1章是满分章节，其章任务结构可复用"

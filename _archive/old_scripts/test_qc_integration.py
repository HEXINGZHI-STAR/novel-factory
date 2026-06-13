#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 QualityGate 增强版质检集成"""

from workflow_engine import QualityGate

# 测试1: 简单AI味文本
test_content = "他感到很伤心。他缓缓地转过身。突然，他听到了什么。他淡淡地笑了。"
result = QualityGate.check(2, test_content)
print("测试1 - 简单AI味文本:")
print(f"  pass={result['pass']}, score={result['score']}")
for issue in result['issues']:
    print(f"  - {issue}")

# 测试2: 较好的文本
good_text = ("陈默站在宗门后山的石阶上，月光把他的影子拉得很长，像一把斜插在地上的剑。"
             "他回头看了一眼山脚的灯火，那些温暖的光与他无关。"
             "三年了，他每天夜里都会来到这里，不是为了修炼，而是为了那个只有他知道的秘密——"
             "后山深处那扇不该存在的石门。"
             "石门上的纹路和三年前一样，只是他的手指已经能感受到门后传来的微弱震动。"
             "他深吸一口气，将灵力汇聚到掌心，缓缓按了上去。")
result2 = QualityGate.check(2, good_text, platform='qimao', chapter_num=1, mode='xianxia')
print(f"\n测试2 - 较好文本:")
print(f"  pass={result2['pass']}, score={result2['score']}")
for issue in result2['issues']:
    print(f"  - {issue}")

# 测试3: _statistical_check
stat_issues = QualityGate._statistical_check(good_text)
print(f"\n测试3 - 统计检测: {len(stat_issues)}个问题")
for issue in stat_issues:
    print(f"  - {issue}")

# 测试4: retry_hint 格式
bad_text = "他感到心中一惊。忽然，他看到了什么。他缓缓地走过去。突然，门开了。他微微地颤抖了一下。"
result3 = QualityGate.check(2, bad_text, platform='qimao', chapter_num=1, mode='general')
print(f"\n测试4 - retry_hint格式:")
print(f"  pass={result3['pass']}")
if result3['retry_hint']:
    print(result3['retry_hint'])

print("\n所有测试完成!")

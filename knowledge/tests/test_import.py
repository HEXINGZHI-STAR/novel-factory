#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件读取和章节分割
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).parent))

# 测试文件
test_file = Path(__file__).parent.parent / "素材库" / "网络文学" / "网络文学20年十大玄幻作家作品系列" / "斗破苍穹.txt"

print(f"测试文件: {test_file}")
print(f"文件存在: {test_file.exists()}")


def test_read_encodings():
    """测试不同编码读取"""
    encodings = ['gbk', 'gb18030', 'utf-8', 'latin1']
    
    for enc in encodings:
        try:
            with open(test_file, 'r', encoding=enc) as f:
                content = f.read(2000)
                print(f"\n编码 {enc}: 成功读取!")
                print(f"内容预览: {content[:300]}")
                return enc, content
        except Exception as e:
            print(f"编码 {enc} 失败: {e}")
    return None, None


def test_split_chapters(content):
    """测试章节分割"""
    print("\n\n测试章节分割:")
    
    # 先找章节标题的模式
    patterns = [
        r'(第[零一二三四五六七八九十百千万\d]+章\s+[^\n\r]*)',
        r'(第\s*\d+\s*章\s*[^\n]*)',
        r'^\s*第\s*\d+\s*章\s*[^\n]*',
    ]
    
    for i, pat in enumerate(patterns):
        matches = list(re.finditer(pat, content, re.MULTILINE))
        print(f"模式 {i}: {pat[:40]} -> 找到 {len(matches)} 个匹配")
        if len(matches) > 0:
            print(f"  示例: {matches[0].group(1)[:60]}")
    
    return len(matches) > 0


if __name__ == '__main__':
    enc, content = test_read_encodings()
    if content:
        test_split_chapters(content)

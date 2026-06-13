#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库整理脚本
1. 清空现有数据库
2. 按分类导入参考小说（完整章节）
3. 其他小说只导入前三章
4. 运行章节分析生成钩子和情绪锚点
"""
import sys
import os
from pathlib import Path
import re
import time

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from db_manager import NovelReferenceDB


# 分类配置
CATEGORY_CONFIG = {
    "玄幻": {
        "path": "网络文学20年十大玄幻作家作品系列",
        "reference": ["斗破苍穹.txt", "盘龙.txt"],  # 完整章节的参考小说
        "max_chapters": 50,  # 参考小说最多导入章节数
    },
    "仙侠": {
        "path": "网络文学20年十大仙侠作家作品系列",
        "reference": ["仙葫.txt", "寸芒.txt"],
        "max_chapters": 50,
    },
    "都市": {
        "path": "网络文学20年十大都市作家作品系列",
        "reference": ["邪气凛然.txt", "纨绔才子.txt"],
        "max_chapters": 50,
    },
    "言情": {
        "path": "网络文学20年十大言情作家作品系列",
        "reference": ["微微一笑很倾城.txt", "何以笙箫默.txt"],
        "max_chapters": 50,
    },
    "武侠": {
        "path": "网络文学20年十大武侠作家作品系列",
        "reference": ["昆仑.txt", "沧海.txt"],
        "max_chapters": 50,
    },
    "悬疑": {
        "path": "网络文学20年十大悬疑作家作品系列",
        "reference": ["无限恐怖.txt", "碎脸.txt"],
        "max_chapters": 50,
    },
    "历史": {
        "path": "网络文学20年十大历史作家作品系列",
        "reference": ["回到明朝当王爷.txt", "庆余年.txt"],
        "max_chapters": 50,
    },
    "军事": {
        "path": "网络文学20年十大军事作家作品系列",
        "reference": ["狙击王.txt", "终身制职业.txt"],
        "max_chapters": 50,
    },
    "科幻": {
        "path": "网络文学20年十大科幻作家作品系列",
        "reference": ["小兵传奇.txt", "机动风暴.txt"],
        "max_chapters": 50,
    },
    "游戏": {
        "path": "网络文学20年十大游戏作家作品系列",
        "reference": ["猛龙过江.txt", "网游之近战法师.txt"],
        "max_chapters": 50,
    },
}


def read_file_with_encoding(file_path):
    """尝试多种编码读取文件"""
    encodings = ['gbk', 'gb2312', 'utf-8', 'utf-16', 'latin1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            continue
    print(f"  无法读取文件: {file_path}")
    return None


def split_chapters(content):
    """分割章节，返回章节列表 [(title, content)]"""
    if not content:
        return []
    
    # 常见章节标题模式
    patterns = [
        r'(第[零一二三四五六七八九十百千万\d]+章\s+[^\n\r]*)',
        r'([第卷]\s*[零一二三四五六七八九十百千万\d]+\s*[^\n\r]*)',
        r'(\d+\s*[、\.]\s*[^\n\r]*)',
    ]
    
    for pattern in patterns:
        matches = list(re.finditer(pattern, content, re.MULTILINE))
        if len(matches) > 0:
            chapters = []
            for i, match in enumerate(matches):
                start = match.start()
                title = match.group(1).strip()
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                    chapter_content = content[start:end].strip()
                else:
                    chapter_content = content[start:].strip()
                chapters.append((title, chapter_content))
            return chapters
    
    # 如果没找到明显的章节，尝试按段落分割
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    if len(paragraphs) > 0:
        return [(f"段落{i+1}", p) for i, p in enumerate(paragraphs)]
    
    return []


def process_novel(novel_path, category, is_reference, max_chapters=3):
    """处理单个小说文件"""
    file_name = novel_path.name
    print(f"\n处理 {category}: {file_name} {'(参考小说)' if is_reference else ''}")
    
    # 读取内容
    content = read_file_with_encoding(novel_path)
    if not content:
        return 0
    
    # 分割章节
    chapters = split_chapters(content)
    if len(chapters) == 0:
        print(f"  未找到章节")
        return 0
    
    print(f"  找到 {len(chapters)} 章")
    
    # 限制章节数量
    if is_reference:
        chapters = chapters[:max_chapters]
        print(f"  参考小说导入前 {len(chapters)} 章")
    else:
        chapters = chapters[:3]
        print(f"  普通小说导入前 {len(chapters)} 章")
    
    return chapters


def organize_database(skip_confirm=False):
    """主函数：整理数据库"""
    print("="*60)
    print("数据库整理工具")
    print("="*60)
    
    # 初始化数据库
    db = NovelReferenceDB()
    
    # 清空现有数据（谨慎操作！）
    if not skip_confirm:
        print("\n警告：即将清空现有数据库！")
        confirm = input("确认清空？(yes/no): ").strip().lower()
        if confirm != 'yes':
            print("操作取消")
            return
    else:
        print("\n自动确认：清空现有数据库")
    
    print("清空数据库...")
    db.clear_all_data()
    
    # 素材库根目录
    material_root = Path(__file__).parent.parent / "素材库" / "网络文学"
    
    if not material_root.exists():
        print(f"素材库不存在: {material_root}")
        return
    
    total_chapters = 0
    total_novels = 0
    
    # 按分类处理
    for category, config in CATEGORY_CONFIG.items():
        category_path = material_root / config["path"]
        if not category_path.exists():
            print(f"\n分类不存在: {category} - {config['path']}")
            continue
        
        print(f"\n{'='*60}")
        print(f"处理分类: {category}")
        print('='*60)
        
        # 遍历目录下的txt文件
        txt_files = list(category_path.glob("*.txt"))
        if len(txt_files) == 0:
            # 尝试查找子目录
            txt_files = list(category_path.rglob("*.txt"))
        
        print(f"找到 {len(txt_files)} 个文件")
        
        for txt_file in txt_files:
            file_name = txt_file.name
            is_ref = file_name in config.get("reference", [])
            
            # 处理小说
            chapters = process_novel(txt_file, category, is_ref, config.get("max_chapters", 50))
            
            if len(chapters) > 0:
                # 添加到数据库
                book_title = file_name.replace(".txt", "")
                book_id = db.add_book(
                    title=book_title,
                    category=category,
                    is_reference=is_ref
                )
                
                for i, (chapter_title, chapter_content) in enumerate(chapters):
                    # 第一章设为开篇
                    is_opening = (i == 0)
                    # 钩子强度根据章节位置设
                    hook_strength = 8 if is_opening else 7
                    
                    db.add_chapter(
                        book_id=book_id,
                        chapter_num=i+1,
                        title=chapter_title[:100],
                        content=chapter_content,
                        is_opening=is_opening,
                        hook_strength=hook_strength
                    )
                
                total_chapters += len(chapters)
                total_novels += 1
                print(f"  ✓ 已导入: {book_title} ({len(chapters)}章)")
    
    print(f"\n{'='*60}")
    print("导入完成！")
    print(f"总计: {total_novels} 本小说，{total_chapters} 章")
    print('='*60)
    
    # 统计
    stats = db.get_stats()
    print(f"\n数据库统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库整理工具')
    parser.add_argument('--auto', action='store_true', help='自动执行，跳过确认')
    args = parser.parse_args()
    
    organize_database(skip_confirm=args.auto)

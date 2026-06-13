#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库功能 - 添加示例数据
"""

from db_manager import NovelReferenceDB


def main():
    print("="*60)
    print("测试盘古AI小说参考库")
    print("="*60)
    
    db = NovelReferenceDB()
    
    print("\n1. 添加示例书籍...")
    
    # 检查是否已经有数据了
    existing = db.list_books()
    if existing:
        print("   数据库已有数据，跳过添加示例")
    else:
        # 添加几本示例书籍
        book1_id = db.add_book(
            title="大医凌然",
            author="志鸟村",
            platform="qidian",
            genre="都市医疗",
            mode="general",
            word_count=5000000,
            notes="都市医疗文经典，开篇节奏很快"
        )
        
        book2_id = db.add_book(
            title="我的治愈系游戏",
            author="我会修空调",
            platform="qidian",
            genre="悬疑惊悚",
            mode="healing_life",
            word_count=3000000,
            notes="治愈系恐怖，情感描写细腻"
        )
        
        book3_id = db.add_book(
            title="大奉打更人",
            author="卖报小郎君",
            platform="qidian",
            genre="仙侠探案",
            mode="general",
            word_count=4000000,
            notes="轻松幽默，节奏明快"
        )
        
        print(f"   已添加 3 本示例书籍，ID: {book1_id}, {book2_id}, {book3_id}")
        
        # 添加一些示例章节
        print("\n2. 添加示例章节...")
        
        sample_chapter1 = """凌然走出手术室，摘下口罩，露出一张帅得惊人的脸。

"凌医生，这台手术太棒了！"护士小田满眼星星。

凌然微微颔首，没有说话。他的注意力已经放在了下一位病人身上。

系统提示：完成一例阑尾切除术，获得初级缝合术。

凌然心中一动，面上依旧淡定。这就是他的日常，在平凡的岗位上，做着不平凡的事。"""
        
        chapter1_id = db.add_chapter(
            book_id=book1_id,
            chapter_num=1,
            title="帅气的凌医生",
            content=sample_chapter1,
            is_opening=True,
            hook_strength=8
        )
        
        print(f"   已添加示例章节，ID: {chapter1_id}")
        
        # 给书籍打标签
        print("\n3. 添加风格标签...")
        
        db.tag_book(book1_id, "快节奏")
        db.tag_book(book1_id, "爽文")
        db.tag_book(book1_id, "第三人称")
        db.tag_book(book1_id, "起点风")
        
        db.tag_book(book2_id, "治愈")
        db.tag_book(book2_id, "压抑")
        db.tag_book(book2_id, "张弛有度")
        
        db.tag_book(book3_id, "轻松")
        db.tag_book(book3_id, "快节奏")
        db.tag_book(book3_id, "爽文")
        
        print("   已添加标签")
    
    # 显示统计信息
    print("\n4. 查询统计信息...")
    stats = db.get_stats()
    print(f"   总书籍数: {stats['total_books']}")
    print(f"   总章节数: {stats['total_chapters']}")
    print(f"   标签总数: {stats['total_tags']}")
    
    # 列出所有书籍
    print("\n5. 列出所有书籍...")
    books = db.list_books()
    for book in books:
        tags = db.get_book_tags(book['id'])
        tag_str = ', '.join([t['name'] for t in tags])
        print(f"\n   [{book['id']}] {book['title']}")
        print(f"      作者: {book['author']}")
        print(f"      平台: {book['platform']}")
        print(f"      标签: {tag_str}")
    
    print("\n" + "="*60)
    print("测试完成！数据库功能正常。")
    print("="*60)
    print("\n下一步:")
    print("  运行 'python reference_library.py status' 查看状态")
    print("  运行 'python reference_library.py list-books' 列出书籍")
    print("  运行 'python reference_library.py help' 查看更多命令")


if __name__ == '__main__':
    main()

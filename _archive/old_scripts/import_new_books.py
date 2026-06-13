#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入新增书籍：起点爆款小说和豆瓣读书
"""
import os
import sys
import re
import shutil
from pathlib import Path
from loguru import logger

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / "knowledge"))

try:
    from db_manager import NovelReferenceDB
except Exception as e:
    logger.error(f"数据库模块导入失败: {e}")
    sys.exit(1)

# 基础路径
BASE_PATH = Path(r"d:\study\近思录\小说")
NETWORK_LIT_PATH = BASE_PATH / "素材库" / "网络文学"

# 起点小说类型映射
QIDIAN_GENRE_MAP = {
    "玄幻": ["斗破", "斗罗", "星辰变", "盘龙", "长生界", "阳神", "亵渎", "紫川", "恶魔法则", "邪神传说", "无极魔道", "大魔王", "黑山老妖", "佛本是道"],
    "仙侠": ["仙葫", "仙路烟尘", "惟我独仙", "寸芒", "诛仙"],
    "都市": ["纨绔才子", "邪气凛然", "天王", "紫川", "我的分身在未来", "龙域", "混在三国当军阀"],
    "历史": ["回到明朝当王爷", "步步生莲", "江山美色", "大争之世", "三国之惟我独尊", "商业三国", "大汉帝国风云录", "庆余年", "迷失在康熙末年", "随波逐流之一代军师"],
    "军事": ["弹痕", "第五部队", "狼群", "狙击王", "终身制职业", "刺血", "纷舞妖姬"],
    "游戏": ["网游之格斗-战无不胜", "网游-屠龙巫师", "网游-梦幻现实", "网游之天地", "网游之模拟城市", "网游之职业人生", "网游之近战法师", "王牌进化", "法师传奇", "猛龙过江"],
    "科幻": ["星际之亡灵帝国", "小兵传奇", "机动风暴", "武装风暴", "天擎"],
    "言情": ["命运的抉择"],
    "体育": ["冠军教父", "我们是冠军", "校园篮球风云", "宇皇星首部曲—足球之恋"],
    "西方奇幻": ["佣兵天下", "兽血沸腾", "紫川", "冰火魔厨", "善良的死神", "空速星痕", "生肖守护神", "琴帝", "大魔王", "盘龙", "变脸武士", "召唤千军"],
    "悬疑": ["无限恐怖"],
}

# 豆瓣读书分类
DOUBAN_GENRE_MAP = {
    "科幻奇幻": "科幻",
    "推理悬疑": "悬疑",
    "中国文学-小说类": "都市",
    "外国文学-小说类": "都市",
    "历史文化": "历史",
    "商业经管": "都市",
    "社会纪实": "都市",
    "文学小说": "都市",
}

def normalize_filename(filename):
    """标准化文件名"""
    name = filename
    # 去掉后缀
    for ext in [".txt", ".epub", ".mobi", ".azw3", ".pdf"]:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    # 去掉校对版等标记
    for tag in ["（校对版全本）", "（精校版全本）", "（校对全本）", 
               "（全本）", "（连载）", "[21册][多看版]", ""]:
        if tag in name:
            name = name.replace(tag, "")
    return name.strip()

def guess_qidian_genre(filename):
    """根据文件名猜测起点小说类型"""
    name = normalize_filename(filename)
    for genre, keywords in QIDIAN_GENRE_MAP.items():
        for keyword in keywords:
            if keyword in name:
                return genre, "general"
    # 默认
    return "都市", "urban_power"

def copy_to_network_lit(source_file, target_dir):
    """复制到网络文学素材库目录"""
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / source_file.name
        if not target_file.exists():
            shutil.copy2(source_file, target_file)
            logger.info(f"复制: {source_file.name} -> {target_dir.name}")
        return target_file
    except Exception as e:
        logger.error(f"复制失败 {source_file}: {e}")
        return None

def process_qidian_books():
    """处理起点爆款小说120本"""
    logger.info("=" * 70)
    logger.info("处理起点爆款小说120本")
    logger.info("=" * 70)
    
    source_dir = BASE_PATH / "起点爆款小说120本"
    if not source_dir.exists():
        logger.warning(f"目录不存在: {source_dir}")
        return 0
    
    books = []
    for file in source_dir.iterdir():
        if file.is_file() and file.suffix.lower() in [".txt", ".epub", ".mobi", ".azw3"]:
            genre, mode = guess_qidian_genre(file.name)
            books.append({
                "file": file,
                "genre": genre,
                "mode": mode,
                "title": normalize_filename(file.name),
                "author": "未知"
            })
    
    logger.info(f"找到 {len(books)} 本起点小说")
    
    # 按类型分类并复制
    for book in books:
        target_dir = NETWORK_LIT_PATH / f"网络文学20年十大{book['genre']}作家作品系列"
        copy_to_network_lit(book["file"], target_dir)
    
    return len(books)

def process_douban_books():
    """处理豆瓣读书"""
    logger.info("=" * 70)
    logger.info("处理豆瓣读书")
    logger.info("=" * 70)
    
    source_dirs = [
        BASE_PATH / "豆瓣读书（2020-2025）",
        BASE_PATH / "豆瓣科幻书单300部+"
    ]
    
    total_books = 0
    for source_dir in source_dirs:
        if not source_dir.exists():
            logger.warning(f"目录不存在: {source_dir}")
            continue
        
        logger.info(f"扫描目录: {source_dir.name}")
        
        # 递归查找书籍文件
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith(('.txt', '.epub', '.mobi', '.azw3', '.pdf')):
                    file_path = Path(root) / file
                    # 推断类型
                    genre = "都市"
                    mode = "general"
                    for keyword, g in DOUBAN_GENRE_MAP.items():
                        if keyword in str(root):
                            genre = g
                            break
                    
                    # 复制到对应分类
                    target_dir = NETWORK_LIT_PATH / f"网络文学20年十大{genre}作家作品系列"
                    copy_to_network_lit(file_path, target_dir)
                    total_books += 1
    
    return total_books

def import_to_database():
    """导入到数据库"""
    logger.info("=" * 70)
    logger.info("导入到数据库")
    logger.info("=" * 70)
    
    try:
        db = NovelReferenceDB()
        stats_before = db.get_stats()
        logger.info(f"导入前 - 书籍: {stats_before['total_books']}, 章节: {stats_before['total_chapters']}")
        
        # 运行原有的扫描导入
        import importlib.util
        spec = importlib.util.spec_from_file_location("scan", str(Path(__file__).parent / "knowledge" / "scan_and_import.py"))
        scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan)
        scan.main()
        
        stats_after = db.get_stats()
        logger.info(f"导入后 - 书籍: {stats_after['total_books']}, 章节: {stats_after['total_chapters']}")
        
        return True
    except Exception as e:
        logger.error(f"数据库导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    logger.add("import_new_books.log", rotation="500 MB")
    logger.info("=" * 70)
    logger.info("盘古AI - 新增书籍导入工具")
    logger.info("=" * 70)
    
    # 处理起点
    qidian_count = process_qidian_books()
    
    # 处理豆瓣
    douban_count = process_douban_books()
    
    logger.info(f"\n完成分类 - 起点: {qidian_count}本, 豆瓣: {douban_count}本")
    
    # 自动导入到数据库
    logger.info("\n自动导入到数据库...")
    import_to_database()
    
    logger.info("=" * 70)
    logger.info("所有任务完成！")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()

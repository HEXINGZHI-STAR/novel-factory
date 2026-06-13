import os, sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from pangu_optimized import call_ai, CONFIG

print(f"CONFIG api_key: {CONFIG['api_key'][:10]}...")
print(f"CONFIG model: {CONFIG['model']}")
print(f"CONFIG base_url: {CONFIG['base_url']}")

print("\n测试API调用...")
result = call_ai("写一句话：深渊裂开了。", system_msg="你是小说作家，只写一句简短的描写。")
if result:
    print(f"成功: {result[:100]}")
else:
    print("失败: 返回None")

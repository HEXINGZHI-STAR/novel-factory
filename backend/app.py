"""
盘古V6.0写作AI - 后端API服务
基于Flask + OpenAI API / 本地模型
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests

app = Flask(__name__)
CORS(app)

# ============ 配置 ============
CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "model": os.getenv("MODEL_NAME", "gpt-4o"),
    "max_tokens": 4000,
    "temperature": 0.8
}

# ============ 路径工具 ============
def _project_path(*parts):
    """获取项目根目录的路径"""
    return os.path.join(os.path.dirname(__file__), '..', *parts)

def safe_read(path, default=""):
    """安全读取文件，不存在时返回默认值"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return default

# ============ 加载盘古知识库 ============
def load_pangu_knowledge():
    """加载盘古知识库，优先使用unified_knowledge_base.json"""
    # 优先加载统一知识库
    unified_path = _project_path('knowledge', 'unified_knowledge_base.json')
    data = safe_read(unified_path)
    if data:
        knowledge = json.loads(data)
        # 确保有必要的字段
        if 'hook_system' in knowledge and 'hook_types' not in knowledge:
            knowledge['hook_types'] = knowledge['hook_system'].get('hook_types', [])
        if 'platform_profiles' in knowledge and 'platform_rules' not in knowledge:
            knowledge['platform_rules'] = knowledge['platform_profiles'].get('summary', {})
        # 添加一些常用字段
        knowledge['title_formulas'] = [
            "【动作】+【名词】+【结果】",
            "【身份】+【反差】+【爽点】",
            "【规则】+【后果】+【主角行动】",
            "【重生/穿越】+【目标】+【金手指】",
            "【日常场景】+【异常元素】"
        ]
        return knowledge
    return {}

PANGU_KNOWLEDGE = load_pangu_knowledge()

# ============ 加载System Prompt ============
def load_system_prompt(prompt_type="novel_writer"):
    """加载System Prompt，支持按类型加载文件或使用内嵌默认值"""
    prompt_path = _project_path('system_prompts', f'{prompt_type}.txt')
    content = safe_read(prompt_path)
    if content:
        return content
    # 内嵌默认Prompt（当文件不存在时使用）
    defaults = {
        "novel_writer": "你是盘古V6.0叙事动力学写作AI，专为网文创作设计。",
        "title_expert": "你是盘古V6.0书名生成专家，精通网文书名心理学。",
        "hook_expert": "你是盘古V6.0钩子设计专家，精通读者心理学。",
        "quality_inspector": "你是盘古V6.0开篇质检专家，严格按平台标准评分。",
        "market_analyst": "你是盘古V6.0市场分析专家，精通网文平台编辑的审稿逻辑。",
    }
    return defaults.get(prompt_type, defaults["novel_writer"])

# ============ 核心API调用 ============
def call_llm(system_prompt, user_prompt, temperature=None, max_tokens=None):
    """调用大模型API，兼容 OpenAI / DeepSeek / Ollama 格式"""
    api_key = CONFIG["api_key"] or os.getenv("LLM_API_KEY", "")
    base_url = CONFIG["base_url"]
    model = CONFIG["model"]

    if not api_key:
        return "[模拟模式] 请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量以启用真实LLM调用。\n\n当前调用参数:\n" + \
               f"System: {system_prompt[:60]}...\nUser: {user_prompt[:120]}..."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens or CONFIG["max_tokens"],
        "temperature": temperature if temperature is not None else CONFIG["temperature"]
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=180
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "[ERROR] API调用超时（180秒），请检查网络或模型响应速度"
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if hasattr(e, 'response') else '?'
        return f"[ERROR] API返回HTTP {status}: {str(e)[:200]}"
    except Exception as e:
        return f"[ERROR] API调用失败: {str(e)}"

# ============ API路由 ============

@app.route('/api/generate/chapter', methods=['POST'])
def generate_chapter():
    """生成小说章节"""
    data = request.json
    platform = data.get('platform', 'fanqie')
    genre = data.get('genre', '都市赘婿')
    chapter_num = data.get('chapter_num', 1)
    outline = data.get('outline', '')
    prev_content = data.get('prev_content', '')
    word_count = data.get('word_count', 3000)
    
    # 获取平台规则
    platform_rules = PANGU_KNOWLEDGE.get('platform_profiles', {}).get('profiles', {}).get(platform, {})
    
    # 构建prompt
    system_prompt = load_system_prompt('novel_writer')
    
    user_prompt = f"""请根据以下信息生成第{chapter_num}章：

【平台】{platform_rules.get('name', '番茄小说')}
【题材】{genre}
【字数要求】{word_count}字
【大纲】{outline}
【前文内容】{prev_content[:500] if prev_content else '无'}

【平台规则】
{json.dumps(platform_rules, ensure_ascii=False, indent=2)}

【要求】
1. 严格遵循盘古V6.0叙事动力学
2. 第1句必须是具体动作+绝境/羞辱（仅限第1章）
3. 章末必须有强力钩子
4. 标注时距、聚焦、钩子类型、矛盾螺旋层级
"""
    
    content = call_llm(system_prompt, user_prompt)
    return jsonify({"success": True, "content": content, "chapter_num": chapter_num})

@app.route('/api/generate/title', methods=['POST'])
def generate_title():
    """智能书名生成"""
    data = request.json
    platform = data.get('platform', 'fanqie')
    action = data.get('action', '')
    noun = data.get('noun', '')
    result = data.get('result', '')
    
    formulas = PANGU_KNOWLEDGE.get('title_formulas', [
        "【动作】+【名词】+【结果】",
        "【身份】+【反差】+【爽点】"
    ])
    platform_rules = PANGU_KNOWLEDGE.get('platform_profiles', {}).get('profiles', {}).get(platform, {})
    
    system_prompt = load_system_prompt('title_expert')
    
    user_prompt = f"""请基于以下公式生成5个书名：

【关键词】动作:{action} | 名词:{noun} | 结果:{result}
【平台】{platform}
【可用公式】
{json.dumps(formulas, ensure_ascii=False, indent=2)}

【要求】
1. 每个书名必须说明使用的公式
2. 分析每个书名的吸引力（点击率预测）
3. 给出平台适配建议
"""
    
    content = call_llm(system_prompt, user_prompt, temperature=0.9)
    return jsonify({"success": True, "titles": content})

@app.route('/api/generate/hook', methods=['POST'])
def generate_hook():
    """生成章节钩子"""
    data = request.json
    scene = data.get('scene', 'chapter-end')
    emotion = data.get('emotion', 'anger')
    platform = data.get('platform', 'fanqie')
    context = data.get('context', '')
    
    hook_types = PANGU_KNOWLEDGE.get('hook_system', {}).get('hook_types', [])
    
    system_prompt = load_system_prompt('hook_expert')
    
    user_prompt = f"""请为以下场景设计3个钩子：

【场景】{scene}
【情绪基调】{emotion}
【平台】{platform}
【剧情上下文】{context}

【可用钩子类型】
{json.dumps(hook_types, ensure_ascii=False, indent=2)}

【要求】
1. 每个钩子必须标注类型
2. 分析为什么这个钩子有效
3. 给出下章开头的衔接建议
"""
    
    content = call_llm(system_prompt, user_prompt, temperature=0.9)
    return jsonify({"success": True, "hooks": content})

@app.route('/api/analyze/opening', methods=['POST'])
def analyze_opening():
    """分析开篇质量"""
    data = request.json
    chapter1 = data.get('chapter1', '')
    chapter2 = data.get('chapter2', '')
    chapter3 = data.get('chapter3', '')
    platform = data.get('platform', 'fanqie')
    
    platform_rules = PANGU_KNOWLEDGE.get('platform_profiles', {}).get('profiles', {}).get(platform, {})
    
    system_prompt = load_system_prompt('quality_inspector')
    
    user_prompt = f"""请分析以下三章的开篇质量：

【平台】{platform}
【平台规则】
{json.dumps(platform_rules, ensure_ascii=False, indent=2)}

【第一章】
{chapter1[:1500]}

【第二章】
{chapter2[:1500]}

【第三章】
{chapter3[:1500]}

【评分维度】
1. 开篇力（第1句是否动作+绝境）
2. 冲突密度（前300字是否有核心冲突）
3. 钩子强度（章末是否有强钩子）
4. 节奏感（时距控制是否合理）
5. 代入感（聚焦模式是否恰当）

【输出格式】
- 每项满分20分，总分100分
- 指出具体问题
- 给出修改建议
"""
    
    content = call_llm(system_prompt, user_prompt, temperature=0.3)
    return jsonify({"success": True, "analysis": content})

@app.route('/api/analyze/rejection', methods=['POST'])
def analyze_rejection():
    """分析拒稿原因"""
    data = request.json
    content = data.get('content', '')
    genre = data.get('genre', '')
    platform = data.get('platform', 'fanqie')
    rejection_reason = data.get('rejection_reason', '')
    
    system_prompt = load_system_prompt('market_analyst')
    
    user_prompt = f"""请分析以下作品被拒的原因：

【平台】{platform}
【题材】{genre}
【拒稿原因】{rejection_reason}

【作品内容】
{content[:2000]}

【分析框架】
1. 套路诊断：是否落入过时套路？
2. 爽点诊断：是否有足够情绪回报？
3. 节奏诊断：开篇是否太慢？
4. 人设诊断：主角是否有记忆点？
5. 世界观诊断：设定是否新颖？
6. 钩子诊断：是否有追更动力？

【输出要求】
- 每个维度给出具体评分（1-10分）
- 指出最严重的问题
- 给出可执行的修改方案
"""
    
    analysis = call_llm(system_prompt, user_prompt, temperature=0.3)
    return jsonify({"success": True, "analysis": analysis})

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """获取盘古知识库"""
    section = request.args.get('section', 'all')
    if section == 'all':
        return jsonify(PANGU_KNOWLEDGE)
    return jsonify(PANGU_KNOWLEDGE.get(section, {}))

# ============ 启动 ============
if __name__ == '__main__':
    api_key = CONFIG["api_key"] or os.getenv("LLM_API_KEY", "")
    mode = "模拟模式（未配置API Key）" if not api_key else "在线模式"

    print("=" * 50)
    print("  盘古V6.0写作AI服务")
    print("=" * 50)
    print(f"  状态: {mode}")
    if api_key:
        print(f"  模型: {CONFIG['model']}")
    print(f"  知识库: {len(PANGU_KNOWLEDGE)} 个顶层模块")
    print(f"  System Prompts: novel_writer / title_expert / hook_expert / quality_inspector / market_analyst")
    print(f"  API路由:")
    print(f"    POST /api/generate/chapter   生成章节")
    print(f"    POST /api/generate/title     生成书名")
    print(f"    POST /api/generate/hook      生成钩子")
    print(f"    POST /api/analyze/opening    开篇质检")
    print(f"    POST /api/analyze/rejection  拒稿分析")
    print(f"    GET  /api/knowledge          知识库查询")
    print("=" * 50)
    print(f"  启动地址: http://127.0.0.1:5001")
    print("=" * 50)
    app.run(host='127.0.0.1', port=5001, debug=False)

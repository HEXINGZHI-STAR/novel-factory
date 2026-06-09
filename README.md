# 盘古V6.0写作AI - 构建指南

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     应用层（前端）                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 选题引擎  │ │ 书名生成  │ │ 黄金开篇  │ │ 钩子工厂  │       │
│  │  +AI分析  │ │  +AI生成  │ │  +AI生成  │ │  +AI生成  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                      爆品生产线系统                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     服务层（后端）                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Flask API Server (Python)                │  │
│  │  /api/generate/chapter    - 生成章节                 │  │
│  │  /api/generate/title      - 生成书名                 │  │
│  │  /api/generate/hook       - 生成钩子                 │  │
│  │  /api/analyze/opening     - 开篇质检                 │  │
│  │  /api/analyze/rejection   - 拒稿分析                 │  │
│  │  /api/knowledge           - 知识库查询               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     数据层                                   │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ 盘古知识库JSON    │  │ System Prompts   │                │
│  │  - 矛盾螺旋       │  │  - 小说作家       │                │
│  │  - 召唤结构       │  │  - 书名专家       │                │
│  │  - 时距系统       │  │  - 钩子专家       │                │
│  │  - 聚焦模式       │  │  - 质检专家       │                │
│  │  - 平台规则       │  │  - 市场分析       │                │
│  └──────────────────┘  └──────────────────┘                │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   大模型API       │  │   可选：RAG       │                │
│  │  (GPT-4/Claude/   │  │  - 爆款案例库     │                │
│  │   DeepSeek等)     │  │  - 用户作品库     │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## 核心优势

### vs 网络AI写作工具（笔灵/讯飞/文小言）

| 维度 | 网络AI工具 | 盘古V6.0写作AI |
|------|-----------|---------------|
| **理论基础** | 数据驱动，套路重组 | **叙事动力学驱动，有理论深度** |
| **平台适配** | 通用模板 | **番茄/起点/七猫差异化策略** |
| **可解释性** | 黑盒生成 | **标注时距/聚焦/钩子/矛盾层级** |
| **可定制性** | 固定参数 | **知识库可扩展，Prompt可调优** |
| **数据隐私** | 上传到第三方 | **本地运行，数据私有** |
| **成本** | 按量付费 | **API key即可，无额外费用** |
| **量产能力** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **创意深度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **理论支撑** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

## 实施路线图

### 第一阶段：基础搭建（1-2天）

#### Step 1: 环境准备
```bash
# 创建虚拟环境
python -m venv venv

# 激活（Windows）
venv\Scripts\activate

# 安装依赖
pip install flask flask-cors requests
```

#### Step 2: 配置API Key
```bash
# 设置环境变量（Windows PowerShell）
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"  # 或第三方代理
$env:MODEL_NAME = "gpt-4o"  # 或 "claude-3-sonnet", "deepseek-chat"
```

#### Step 3: 启动后端
```bash
cd backend
python app.py
```

#### Step 4: 集成前端
在 `爆品生产线/index.html` 的 `</body>` 前添加：
```html
<script src="../盘古AI/frontend_extension.js"></script>
```

### 第二阶段：知识库扩展（3-5天）

#### 2.1 添加爆款案例库
创建 `pangu_v6_knowledge.json` 的 `case_studies` 字段：
```json
"case_studies": {
  "fanqie_bestsellers": [
    {"title": "XXX", "opening_structure": "...", "hook_pattern": "...", "why_works": "..."}
  ]
}
```

#### 2.2 添加用户作品库
创建 `user_works.json`，记录你的每部作品：
- 题材、平台、被拒原因、修改历史
- 用于RAG检索，避免重复犯错

#### 2.3 影视模具扩展
在 `film_molds` 中添加更多子类型：
- 日剧：社会派、治愈系、职场剧
- 韩剧：复仇爽剧、浪漫喜剧、家庭伦理
- 美剧：悬疑季弧、群像剧、单元剧

### 第三阶段：高级功能（1-2周）

#### 3.1 RAG知识检索
```python
# 使用简单向量检索（无需复杂框架）
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class SimpleRAG:
    def __init__(self, documents):
        self.vectorizer = TfidfVectorizer()
        self.vectors = self.vectorizer.fit_transform(documents)
        self.documents = documents
    
    def search(self, query, top_k=3):
        query_vec = self.vectorizer.transform([query])
        scores = np.dot(self.vectors, query_vec.T).toarray().flatten()
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [self.documents[i] for i in top_indices]
```

#### 3.2 多模型路由
根据任务复杂度选择不同模型：
- **分析类**（拒稿诊断、质检）：用便宜模型（GPT-3.5/DeepSeek-V3）
- **生成类**（写章节）：用强模型（GPT-4o/Claude-3.5）
- **创意类**（书名、钩子）：用高temperature模型

#### 3.3 本地模型部署（可选）
如果担心API费用，可以部署本地模型：
```bash
# 使用Ollama运行本地模型
ollama run qwen2.5:14b

# 修改 backend/app.py 的 CONFIG
CONFIG = {
    "base_url": "http://localhost:11434/v1",
    "model": "qwen2.5:14b",
    "api_key": "ollama"  # Ollama不需要真实key
}
```

### 第四阶段：工作流自动化（持续优化）

#### 4.1 一键生成全书大纲
输入一句话梗概 → AI输出：
- 1000字主线大纲
- 人物设定表
- 矛盾螺旋设计（4层）
- 每章300字细纲

#### 4.2 批量生成章节
输入细纲 → AI批量生成3章 → 人工审核 → 批量生成下一批

#### 4.3 数据反馈闭环
- 记录每章的AI生成内容
- 记录编辑反馈/读者评论
- 自动分析"哪些设定受欢迎，哪些被拒"
- 反馈到知识库，持续优化

## 文件结构

```
盘古AI/
├── README.md                    # 本文件
├── pangu_v6_knowledge.json      # 盘古知识库（核心资产）
├── system_prompts/              # System Prompt模板
│   ├── novel_writer.txt         # 小说作家（基础角色）
│   ├── title_expert.txt         # 书名专家 ✅ 新建
│   ├── hook_expert.txt          # 钩子专家 ✅ 新建
│   ├── quality_inspector.txt    # 质检专家 ✅ 新建
│   └── market_analyst.txt       # 市场分析 ✅ 新建
├── backend/                     # 后端服务
│   ├── app.py                   # V6主程序（已升级: 调文件prompt）
│   ├── app_v7.py                # V7四车间调度器 + Fusion Engine ✅
│   ├── generate_novel_libraries.py  # ✅ 三库生成器（新建项目用）
│   └── test_server.py           # 测试服务器
├── modes/                       # 创作模式（7个完成 ✅）
│   ├── general.json             # 通用网文
│   ├── romance.json             # 言情
│   ├── rule_mystery.json        # 规则怪谈
│   ├── urban_power.json         # ✅ 都市职业异能（P0)
│   ├── folk_horror.json         # ✅ 中式民俗悬疑
│   ├── history_scholar.json     # ✅ 历史考据流（P0, 含考据注释）
│   └── female_solo.json         # ✅ 无CP大女主（P0, 含红线质检）
├── knowledge/                   # 知识库
│   ├── v7_architecture.json     # V7架构
│   ├── V7.5_系统全面升级方案.md   # 诊断报告（已更新）
│   ├── unified_knowledge_base.json  # ✅ 统一知识库JSON
│   ├── platform_writing_profiles.json # 平台写作配置
│   └── ...
├── workshops/                   # 四车间System Prompts
│   ├── workshop_1_setup/        # W1 设定预处理
│   ├── workshop_2_draft/        # W2 正文初稿
│   ├── workshop_3_qc/           # W3 逻辑质检
│   └── workshop_4_polish/       # W4 文笔精修
└── novel_libraries/             # 小说专属三库
    └── breakup_lawyer/          # 《分手事务所》示例项目
```

## 关键技术决策

### 为什么用Prompt工程而不是微调？

| 方案 | 成本 | 效果 | 维护难度 | 推荐度 |
|------|------|------|---------|--------|
| **Prompt工程** | 低 | 中-高 | 低 | ⭐⭐⭐⭐⭐ |
| **RAG检索** | 中 | 高 | 中 | ⭐⭐⭐⭐ |
| **模型微调** | 高 | 很高 | 高 | ⭐⭐⭐ |

**建议**：先用Prompt工程跑通全流程，积累100个案例后再考虑RAG，有1000个案例后再考虑微调。

### 为什么用Flask而不是更复杂的框架？

- 轻量，单文件即可运行
- 无数据库依赖，知识库用JSON
- 便于本地部署，无需Docker
- 后期可平滑迁移到FastAPI

## 使用示例

### 示例1：生成第一章
```bash
curl -X POST http://localhost:5000/api/generate/chapter \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "fanqie",
    "genre": "都市赘婿",
    "chapter_num": 1,
    "outline": "主角被丈母娘当众羞辱，被迫签离婚协议，关键时刻获得神医传承",
    "word_count": 3000
  }'
```

### 示例2：分析被拒原因
```bash
curl -X POST http://localhost:5000/api/analyze/rejection \
  -H "Content-Type: application/json" \
  -d '{
    "content": "（粘贴你的第一章内容）",
    "platform": "fanqie",
    "rejection_reason": "综合质量一般、整体内容比较普通且缺乏吸引力"
  }'
```

### 示例3：生成钩子
```bash
curl -X POST http://localhost:5000/api/generate/hook \
  -H "Content-Type: application/json" \
  -d '{
    "scene": "chapter-end",
    "emotion": "anger",
    "platform": "fanqie",
    "context": "主角刚被反派打了一巴掌，正在隐忍"
  }'
```

## 后续优化方向

1. **多Agent协作**：拆分为"策划Agent""写作Agent""质检Agent""编辑Agent"，互相协作
2. **记忆系统**：记录每部作品的设定，避免长文本中的设定矛盾
3. **风格迁移**：学习特定作家的文风（如辰东的霸气、忘语的细腻）
4. **实时榜单监控**：自动抓取番茄/起点热榜，分析爆款规律
5. **A/B测试**：同时生成两个版本的开头，投放到平台测试哪个更好

## 总结

盘古V6.0写作AI的**核心价值**不是替代你写作，而是：

1. **把隐性知识显性化**：把你的叙事理论变成可执行的AI指令
2. **把经验变成资产**：每次拒稿都沉淀到知识库，不再重复犯错
3. **把创意规模化**：一个独特设定 → AI帮你扩展到完整世界观
4. **把质量标准化**：每章都经过盘古理论的质检，保证下限

**最终目标**：你负责"独特的创意和审美判断"，AI负责"套路化的执行和质检"。

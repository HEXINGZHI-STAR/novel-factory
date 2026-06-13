# 盘古AI · Pangu Studio

> 一个人运营的 AI 写作工作室。不是调用 API 的聊天框，是一座小说工厂。

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Lines](https://img.shields.io/badge/代码-50,000+行-orange)]()
[![Tests](https://img.shields.io/badge/测试-51个-green)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## 一句话

**Pipeline W0-W5 六车间流水线 + DeepSeek API + 4,475 本参考书库 = 全自动写小说。**

## 快速开始

```bash
# 1. 配置 API Key
echo "DEEPSEEK_API_KEY=你的Key" > .env

# 2. 启动盘古
python pangu_workshop.py start

# 3. 写一章
python pangu_workshop.py write -p "开门见尸" -c 1
```

## 核心架构

```
W0 主旨锚定 ──→ W1 设置检查 ──→ W2 DeepSeek初稿 ──→ W3 质检 ──→ W4 精修 ──→ W5 导出归档
 (纯逻辑)       (纯逻辑)       (AI生成, 25-40s)    (纯逻辑)     (AI润色, 20-30s)  (文件+DB+投影)
```

每章写完自动触发 6 个 Hook：DB写入 → 五路投影 → 记忆提交 → 质检关卡 → 情报报告 → KPI更新。

## 16 个学科引擎

```
统计建模 · 信号处理 · 图论分析 · 概率推理 · 运筹优化 · 机器学习
经济学 · 管理会计 · 内部控制 · 控制论 · 认知科学 · 脑科学
新闻传播 · 广告营销 · 叙事学 · 数学语言学
```

每个学科都有 Python 模块在跑——不是概念，是代码。

| 引擎 | 做什么 | 例子 |
|------|------|------|
| GUARD 熵检测 | 区分 AI 文本 vs 人类文本 | 手写 0.53 vs AI 0.35 |
| Burrows' Delta | 风格距离（30年学术标准） | 开门见尸 vs 逻辑之下 = 2.0 |
| GSD 框架 | 多维度不加权质量评估 | A 在 5/5 维胜 B |
| 神经共鸣 | 镜像神经元/催产素/杏仁核激活度 | 手写章催产素 1.00 |
| PID 控制器 | 质量不够自动调参重写 | GUARD<0.35→自动加温重试 |
| Prefect 流水线 | 可视化 W0-W5 甘特图 | `prefect server start` |

## 参考书库

4,475 本网文逐章入库，优先级评分系统。写悬疑章自动注入福尔摩斯技法（165分最高优先级）。

## 项目展示

```
23 个写作项目
├── 开门见尸          七猫悬疑   10/10章 ✅
├── 七楼多了一个人     七猫短文   1/20章
├── 镇妖司：新科状元   起点玄幻   1/100章
├── 逻辑之下          起点悬疑   6/30章
├── 消失的第四个人     知乎盐选   1/12章
└── ...18个更多项目
```

## 技术栈

**后端**: Python · Prefect · Huey · SQLite · LanceDB · NetworkX · Whistle  
**AI**: DeepSeek API · Claude API (可选) · LiteLLM  
**工程**: pytest(51 tests) · structlog · Docker · GitHub Actions  
**集成**: 飞书多维表格 · Claude Code MCP · Node.js Dashboard · Gradio  

## 目录

```
pangu_core/        10,490行   Pipeline + PromptBuilder + AI路由 + 质量门禁
pangu_math/         4,759行   6层数学引擎 (统计/信号/图论/概率/运筹/ML)
pangu_analytics/    1,900行   经济学 + 会计 + 内控 + 认知 + 脑科学 + 趋势
knowledge/         13,913行   参考书库 + 风格指纹 + 创作引擎
```

## 开发

```bash
pip install -e .
python -m pytest tests/ -q     # 51 tests
python pangu_workshop.py start  # 自检面板
```

## License

MIT · 大三学生独立开发

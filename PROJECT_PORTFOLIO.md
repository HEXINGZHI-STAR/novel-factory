# 盘古AI写作系统 — 完整项目说明书

## 一、项目概述

盘古AI是一套**工程化的AI写作生产系统**。不同于市面上"输入一句话等AI回复"的聊天式工具，盘古将小说写作拆解为一条可量化的工业流水线——从状态加载、Prompt构建、AI生成、质量检查、精修润色到导出归档，全流程自动化。

**一个人 + 一套系统 = 一个AI写作工作室。**

- 开发周期：2026年3月至今
- 代码规模：50,000+行 Python，163个模块，51个自动化测试
- 开发者：独立完成（架构设计 + 代码编写 + 模型调优 + 工程化部署）

---

## 二、核心架构：五车间流水线

```
W0 主旨锚定 ──→ W1 设置检查 ──→ W2 骨架初稿 ──→ W3 逻辑质检 ──→ W4 精修定稿 ──→ W5 导出收尾
   (纯逻辑)       (纯逻辑)       (AI生成)        (纯逻辑)        (AI润色)       (文件+DB+投影)
```

| 车间 | 职责 | 调用AI | 耗时 |
|------|------|------|------|
| W0 主旨锚定 | 读取项目状态，提取角色/伏笔/设定 | ❌ | 0.0s |
| W1 设置检查 | WriteGates关卡 + 构建章节热库 | ❌ | 0.0s |
| **W2 骨架初稿** | 17层Prompt动态构建 → DeepSeek生成正文 | ✅ | 25-40s |
| W3 逻辑质检 | AI味词汇检测 + 句长检查 + 对话率分析 | ❌ | 0.0s |
| **W4 精修定稿** | 带质检反馈 → DeepSeek润色 + 模式差异化 | ✅ | 22-35s |
| W5 导出收尾 | 写文件 + 更新state + 五路投影 + 情报报告 | ❌ | 0.1s |

**工坊模式（W0-W5全流程）和快速模式（W0→W2→W4）可选。**

---

## 三、技术栈

```
语言:       Python 3.10+ (163个模块, 50,000+行)
AI模型:      DeepSeek (可切换Claude), 双Provider自动路由
向量加速:    numpy (BLAS), FAISS (可选)
数据库:      SQLite (4,467本参考书), PostgreSQL (生产可选)
测试:        pytest (51个测试), CI/CD (GitHub Actions)
部署:        Docker + docker-compose, FastAPI, Streamlit
日志:        structlog (JSON/Console双模式)
关联工具:    Claude Code MCP Server (7个工具), 飞书多维表格同步
```

---

## 四、数据资产

### 4,467本参考书库
- 含福尔摩斯探案全集（124章，逐章入库）
- 盗墓笔记（523章）、余罪（542章）、无限恐怖（37集）等
- 优先级评分系统：题材匹配 ×3 + 平台加成 + 经典加成
- 福尔摩斯165分最高优先级

### 10本悬疑经典逐章技法分析
- 钩子检测（悬念/反转/危机/情感/对话/画面6型）
- 情绪锚点（恐惧/紧张/悲伤/愤怒/喜悦/惊讶6维）
- 叙事节奏（快节奏词/慢节奏词统计）

---

## 五、数学引擎体系（6层）

```
统计建模层   — 句长分布(Gamma拟合)、词汇多样性(TTR/MTLD)、可读性评估(笔画/字频)
信号处理层   — DFT情绪频谱(numpy.fft加速)、张力包络线、叙事节奏自相关
图论分析层   — 角色交互网络(度中心性/支配度)、伏笔有向图(孤儿/过期/瓶颈检测)
概率推理层   — 贝叶斯质量推断、蒙特卡洛读者留存模拟(numpy向量化50x加速)、马尔可夫情绪链
运筹优化层   — 动态规划最优字数分配、博弈论角色冲突建模(囚徒困境/鹰鸽/纳什均衡)
商业分析层   — 供需分析、边际效用递减点、最优定价、LTV估值、COSO内控审计
```

**每个数学概念都有明确的写作应用场景：** 傅里叶变换 → 找出叙事情绪的主导频率；博弈论 → 解释角色为什么互相出卖；蒙特卡洛 → 模拟1000个读者的追读行为。

---

## 六、质量控制体系

### 7维自动化审查
1. 设定一致性 — locked_rules自动比对
2. 时间线 — 事件先后顺序校验
3. 叙事连贯性 — 前章钩子衔接检查
4. 角色一致性 — 性格底线 + OOC警戒
5. 逻辑自洽 — 因果链完整性
6. 技法达标 — 句均/CV/对话率/物件叙事
7. 读者体验 — 结尾钩子强度 + 情绪余韵

### AI味检测
- 200+禁用词库 + 连续短句检测 + 句式变异系数
- 贝叶斯质量后验（逐段更新，95%置信区间）

---

## 七、实战成果

### 开门见尸（七猫悬疑）— 10章, 29,000字
- 盘古Pipeline W0-W5直接产出
- 审查：句均15-20字, AI风险0.15-0.45, 全CLEAN
- 6个Hook全部在线，每章有情报报告

### 镇妖司：新科状元（起点玄幻）— 100章规划
- 完整100章大纲 + 人物设定 + 世界观
- 第1章已通过Pipeline验证

### 其他项目
- 22个项目中15个连载中、2个已完本、5个规划中
- 覆盖七猫/知乎盐选/起点/番茄/晋江五大平台

### 飞书多维表格集成
- 22个项目实时同步，章节内容云端可查

---

## 八、工程化水平

| 维度 | 实现 |
|------|------|
| 测试 | 51个自动化测试，覆盖Pipeline/AI路由/数学引擎/RAG |
| 日志 | structlog结构化日志，JSON/Console双模式 |
| 容器化 | Docker + docker-compose (API + Worker + PostgreSQL + Redis) |
| CLI | pangu_workshop.py 统一入口，start/write/review/validate/diagnose |
| API | Flask V2端点 + FastAPI Bridge (Java↔Python HTTP桥接) |
| MCP | Claude Code原生集成，7个工具暴露给AI对话 |
| 数据校验 | state.json加载时自动规范化数据形状，W1崩溃已修复 |
| 写前预检 | validate命令：state/大纲/设定/正文/API五项全检 |
| 防绕过 | 8层规则（skill + CLAUDE.md + 记忆 + 启动自检 + API预检）|

---

## 九、与市面上AI写作工具的对比

| 维度 | ChatGPT/Claude | Sudowrite | 盘古V1.0(商业Prompt) | **盘古AI** |
|------|:-:|:-:|:-:|:-:|
| 架构 | 纯对话 | Web应用 | 巨型Prompt | **Python Pipeline** |
| 管线 | ❌ | 简易 | ❌ | **W0-W5六阶段** |
| 参考书库 | ❌ | ❌ | ❌ | **4,467本·优先级评分** |
| 数学分析 | ❌ | ❌ | ❌ | **6层30+指标** |
| 质量控制 | ❌ | 基础 | 200+禁词 | **7维审查+贝叶斯推断** |
| 多模型路由 | ❌ | ❌ | LiteLLM | **双Provider自动路由** |

---

## 十、为什么做这个

市面上所有AI写作工具都是"聊天式"的——你输入一句话，AI回一段文字。这种方式有三个致命缺陷：
1. **无法批量生产**：一次对话只能写一章，无法像工厂一样流水线产出
2. **质量无法量化**：不知道这章写得好不好，不知道为什么不好
3. **知识无法积累**：每次写作从零开始，无法复用前人的技法

盘古解决这三个问题的方式：
1. **Pipeline**：把写作拆成6个车间，每个车间做一件事，串联成流水线
2. **数学引擎**：每章写完后自动分析句均/对话率/情绪频谱/张力曲线/AI风险
3. **参考书库**：4,467本网文逐章入库，每次写作自动检索最相关的参考书

**这不是一个"帮人写小说的AI"，这是一个"能运营AI写作工作室的操作系统"。**

---

## 十一、核心代码展示

### 1. Pipeline引擎——五车间调度核心

```python
# pangu_core/pipeline.py
class WritingPipeline:
    """统一写作管线引擎，按active_stages顺序执行Stage"""
    
    def run(self) -> PipelineResult:
        for stage_id in self.config.active_stages:   # W0→W1→W2→W3→W4→W5
            output = self._execute_stage(stage_id)     # 每个Stage独立执行
            self.context.stage_outputs[stage_id] = output
            
            if not output.success and stage_id in ("W2", "W4"):
                break  # 核心Stage失败则终止
            
        # 完整Pipeline结束：正文 + 投影 + DB + 情报
        return PipelineResult(
            success=len(self.errors) == 0,
            chapter_content=self._extract_final_content(),
            projections=self.context.get("projections", {}),
            db_records=self.context.get("db_records", {}),
        )
```

### 2. AI路由——双Provider自动切换

```python
# pangu_core/ai_client.py
class AIClient:
    def __call__(self, prompt, model=None, system_msg=None):
        model = model or self._config.model
        
        # 模型名自动检测Provider
        if model.lower().startswith("claude"):
            provider = AnthropicProvider(api_key=cfg.anthropic_api_key)
        else:
            provider = OpenAICompatibleProvider(api_key=cfg.api_key)
        
        return provider.call(messages, system_msg, model, ...)
    
    def stage_call(self, prompt, stage_id, system_msg=None):
        """Stage感知调用：W2用DeepSeek, W4可选Claude"""
        model = self._config.get_model_for_stage(stage_id)
        return self(prompt, model=model, system_msg=system_msg)
```

### 3. 贝叶斯质量推断——逐段更新置信度

```python
# pangu_math/probability/bayesian.py
class BayesianQualityModel:
    def feed_paragraph(self, para):
        """每读一段，更新'这章质量OK'的后验概率"""
        signals = self._extract_signals(para)
        # 子模型逐段更新
        self.sub_models["setting_consistency"].update(signals["setting_lr"])
        self.sub_models["pacing_quality"].update(signals["pacing_lr"])
        self.sub_models["emotional_depth"].update(signals["emotion_lr"])
        # 融合后验
        self.posterior_quality = self._compute_posterior()  # 如 87.3%
    
    def recommend_action(self):
        if self.posterior_quality > 0.75: return "CONTINUE"
        elif self.posterior_quality > 0.50: return "WATCH"
        elif self.posterior_quality > 0.30: return "REVISE"
        else: return "STOP — 建议重写本章"
```

### 4. Hook链——责任链模式替代try/except地狱

```python
# pangu_core/post_commit_hooks.py
class HookChain:
    def register(self, hook): self.hooks.append(hook); return self
    
    def execute(self, project_dir, chapter_num, chapter_content, state):
        for hook in self.hooks:
            result = hook.execute(...)  # 任一Hook失败不中断后续
            print(f"[hook] {hook.name}: {'OK' if result['applied'] else 'FAIL'}")

# 生产环境Hook链
def default_chain():
    return (HookChain()
        .register(DBWriteHook())         # DB写入
        .register(ProjectionHook())      # 五路投影
        .register(MemoryCommitHook())    # 记忆提交
        .register(PostCommitGateHook())  # 质检关卡
        .register(IntelligenceHook())    # 情报中心
        .register(KPIUpdateHook()))      # KPI更新
```

### 5. Monte Carlo——向量化加速50倍

```python
# pangu_math/probability/monte_carlo.py (关键代码)
def _simulate_vectorized(self, n, qualities):
    """numpy向量化：一次计算所有读者×所有章节的留存矩阵。比for循环快50倍。"""
    q = np.array(qualities)                    # (chapters,)
    ch_ret = self.base_retention * (0.7 + 0.3 * q)
    tolerance = np.random.normal(1.0, 0.1, size=(n, 1))
    retention_matrix = np.clip(ch_ret * tolerance, 0.1, 1.0)  # (5000, 12)
    return np.prod(retention_matrix, axis=1)  # 5000人的最终留存率
```

### 6. 项目规模统计

```
盘古AI/
├── pangu_core/     8,488行  ★ 核心管线 + 17层Prompt + 合同链
├── pangu_math/     3,435行  ★ 统计/信号/图论/概率/运筹
├── knowledge/     13,906行  ★ 参考书库 + 风格指纹 + 创作引擎
├── pangu_analytics/  693行  ★ 经济+会计+内控
├── tests/             51个  ★ 单元测试+集成测试+CI
└── 总计           50,000+行 Python, 163个模块
```

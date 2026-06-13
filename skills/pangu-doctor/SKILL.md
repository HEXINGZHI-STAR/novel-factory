---
name: pangu-doctor
description: 盘古体检——诊断项目目录、文件、JSON、DB、Python 环境是否完整可用
allowed-tools: Read Grep Bash
argument-hint: "[项目路径，默认当前项目]"
---

# 盘古项目体检

## 核心理念

**快速诊断，不修不改。** 只报告问题，由用户决定是否修复。

## 检查清单

### 1. 目录结构

```bash
必需目录:
□ {project}/大纲/
□ {project}/设定集/
□ {project}/正文/
□ {project}/审查报告/
□ {project}/.webnovel/
```

任一缺失 → 报告。

### 2. 核心文件

```bash
□ {project}/.webnovel/state.json     → 存在性 + JSON 合法性
□ {project}/大纲/总纲.md              → 存在性 + 是否空模板
□ {project}/设定集/世界观.md          → 存在性 + 核心规则是否填写
□ {project}/设定集/主角卡.md          → 存在性 + 基本信息是否填写
```

state.json 校验：
```bash
cd {PANGU_ROOT}
python -c "
import json, sys
from pathlib import Path

state_path = Path('{project}/.webnovel/state.json')
if not state_path.exists():
    print('[MISSING] state.json')
    sys.exit(1)

try:
    state = json.loads(state_path.read_text(encoding='utf-8'))
    required_keys = ['project_info', 'progress', 'characters', 'foreshadowing']
    for k in required_keys:
        if k not in state:
            print(f'[MISSING KEY] state.json 缺少字段: {k}')
    print('[OK] state.json 格式正确')
    print(f'  作品: {state.get(\"project_info\",{}).get(\"title\",\"?\")}')
    print(f'  进度: 第{state.get(\"progress\",{}).get(\"current_chapter\",0)}章')
except json.JSONDecodeError as e:
    print(f'[CORRUPT] state.json JSON解析失败: {e}')
"
```

### 3. 正文完整性

```bash
□ 章节文件是否连续？（无跳章）
□ 每章文件大小是否合理？（不应为0字节或小于500字）
□ 章节号与 state.json 的 current_chapter 是否一致？
```

### 4. 盘古引擎

```bash
□ Python 环境：依赖是否可导入？
```

```bash
cd {PANGU_ROOT}
python -c "
errors = []
try:
    from pangu_core.config import get_config
    cfg = get_config()
    print(f'[OK] pangu_core.config → model={cfg.model}')
except Exception as e:
    errors.append(f'config: {e}')

try:
    from pangu_core.ai_client import call_ai, OpenAICompatibleProvider, AnthropicProvider
    print(f'[OK] pangu_core.ai_client → 双Provider就绪')
except Exception as e:
    errors.append(f'ai_client: {e}')

try:
    from pangu_core.pipeline import WritingPipeline
    print(f'[OK] pangu_core.pipeline → Pipeline就绪')
except Exception as e:
    errors.append(f'pipeline: {e}')

try:
    from pangu_core.stages import W0AnchorStage, W2DraftStage, W4PolishStage
    print(f'[OK] pangu_core.stages → W0/W2/W4就绪')
except Exception as e:
    errors.append(f'stages: {e}')

if errors:
    for e in errors:
        print(f'[ERROR] {e}')
else:
    print('[OK] 盘古引擎全部模块可用')
"
```

### 5. API 连接

```bash
□ DeepSeek API Key 是否配置？
□ DeepSeek API 是否可达？（发最小请求验证连通性，不消耗额度）
□ Anthropic API Key 是否配置？（如已配置，同样验证）
```

### 6. 参考库（如有）

```bash
□ knowledge/ 目录是否存在？
□ 数据库文件是否存在且可读？
```

### 7. 一致性校验

```
□ 总纲的章节目标与实际 chapter_meta 是否一致？
□ 伏笔表: 是否有 orphan foreshadowing（无回收章）？
□ 伏笔表: 是否有过期的（回收章<当前章但status=open）？
□ 角色: state.json 的 characters 与 主角卡.md 是否同步？
```

## 输出格式

```
盘古体检报告 — {project_name}
═════════════════════════════════

目录结构    [OK] / [ISSUES: ...]
核心文件    [OK] / [ISSUES: ...]
正文完整性  [OK] / [ISSUES: ...]
盘古引擎    [OK] / [ISSUES: ...]
API连接     [OK] / [ISSUES: ...]
参考库      [OK] / [ISSUES: ...]
一致性      [OK] / [ISSUES: ...]

总计: {pass_count}/{total} 项通过

需处理:
  1. ...
  2. ...
```

不主动修改任何文件。只诊断，不治疗。

# 贡献指南

盘古是一个人写的，但它不应该永远是一个人维护的。欢迎任何形式的贡献。

## 新手入门（5 分钟）

```bash
git clone https://github.com/HEXINGZHI-STAR/novel-factory.git
cd novel-factory
pip install -r requirements.txt
python pangu_workshop.py start   # 6/6 自检通过 = 环境OK
python -m pytest tests/ -q       # 51 tests 全绿 = 代码OK
```

## 项目结构速览

```
pangu_core/      Pipeline + AI路由 + Prompt构建    ← 核心，改动要小心
pangu_math/      统计/信号/图论/概率/运筹/ML        ← 欢迎贡献新指标
pangu_analytics/ 经济/会计/内控/认知/脑科学          ← 欢迎贡献新分析
Tests/           51个测试                            ← 改代码前先跑
```

## 怎么贡献

1. **找活干** → 看 [Issues](https://github.com/HEXINGZHI-STAR/novel-factory/issues) 里标 `good first issue` 的
2. **Fork** → 改代码 → 跑 `python -m pytest tests/ -q` → 全绿再提 PR
3. **PR 标题** → `[Fix] 修复了什么` 或 `[Feat] 新增了什么`
4. **不用太正式** → 这是大三学生的项目，不是 Google 的

## 什么活适合新手

- 修 Windows 终端中文乱码（GBK → UTF-8）
- 给模块加类型注解
- 写/修 docstring
- 补测试用例
- 翻译注释（中→英）
- 给 `pangu_math/` 加新的数学指标

## 什么活需要先讨论

- 改 Pipeline 架构
- 换 AI Provider
- 大改 PromptBuilder

## 本地开发

```bash
# 不需要 DeepSeek API Key 也能跑测试
python -m pytest tests/unit/ -q

# 需要 API Key 的集成测试单独跑
python -m pytest tests/integration/ -q
```

## 有问题？

去 [Issues](https://github.com/HEXINGZHI-STAR/novel-factory/issues) 发帖。或者直接提 PR——代码比讨论更有说服力。

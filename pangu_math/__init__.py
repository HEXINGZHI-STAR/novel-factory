"""
盘古数学引擎 (PanguMath)

企业级写作数学引擎，六层体系:
  - accelerated:    numpy加速的向量/矩阵运算
  - stats:          统计建模 (分布/多样性/可读性/风格指纹)
  - ml:             机器学习 (质量预测/风格分类/异常检测)
  - signal:         信号处理 (情绪频谱/张力包络/节奏自相关)
  - graph:          图论 (角色网络/情节依赖图/伏笔网络)
  - optimize:       优化算法 (节奏优化/钩子调度/情绪曲线)

设计原则:
  - 纯Python fallback: 所有模块在numpy不可用时降级到纯Python实现
  - 流式处理: 支持分段分析长文本 (内存可控)
  - 结果可解释: 每个指标输出人类可读的解释
  - 向后兼容: 不修改现有 pangu_core/ 的任何文件
"""

__version__ = "2.0.0"
__all__ = [
    "stats", "signal", "graph", "ml", "optimize",
]

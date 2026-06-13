"""
盘古数学 · 机器学习层

实用ML模型 (纯Python + numpy, 无GPU依赖):
  - quality_classifier:  章节质量二分类 (优质/需改)
  - genre_classifier:    题材自动识别 (悬疑/玄幻/都市/治愈)
  - style_matcher:       风格匹配——推荐最适配的写作模式
"""
from .quality_classifier import QualityClassifier, train_quality_model
from .genre_classifier import GenreClassifier, predict_genre
from .style_matcher import StyleMatcher, match_best_mode

__all__ = [
    "QualityClassifier", "train_quality_model",
    "GenreClassifier", "predict_genre",
    "StyleMatcher", "match_best_mode",
]

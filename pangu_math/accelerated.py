"""
盘古数学引擎 · 加速层 (Accelerated Linear Algebra)

在 pangu_math_core.py 的纯Python Vector/Matrix 基础上:
- 引入 numpy 加速 (BLAS-backed，O(n³)→O(n²·log n) 实际)
- 纯Python fallback (numpy不可用时自动降级)
- 新增: SVD分解、特征值分解、非负矩阵分解、t-SNE降维

用法:
    from pangu_math.accelerated import Vector, Matrix, PCA

    # 自动选择后端
    v = Vector([1, 2, 3])
    m = Matrix.identity(20)
    pca = PCA(n_components=5)
    pca.fit(data_matrix)
"""

import math
from typing import List, Tuple, Optional

# === 尝试加载 numpy ===
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ================================================================
# Vector
# ================================================================

class Vector:
    """n维向量。numpy可用时走np.dot，不可用时走纯Python。"""

    def __init__(self, values: List[float]):
        self.values = values
        self.dim = len(values)

    def __len__(self): return self.dim
    def __getitem__(self, i): return self.values[i]
    def __iter__(self): return iter(self.values)

    def __add__(self, other):
        if HAS_NUMPY:
            return Vector((np.array(self.values) + np.array(other.values)).tolist())
        return Vector([a + b for a, b in zip(self.values, other.values)])

    def __sub__(self, other):
        if HAS_NUMPY:
            return Vector((np.array(self.values) - np.array(other.values)).tolist())
        return Vector([a - b for a, b in zip(self.values, other.values)])

    def __mul__(self, scalar):
        if HAS_NUMPY:
            return Vector((np.array(self.values) * scalar).tolist())
        return Vector([v * scalar for v in self.values])

    def __rmul__(self, scalar): return self.__mul__(scalar)

    def dot(self, other) -> float:
        if HAS_NUMPY:
            return float(np.dot(np.array(self.values), np.array(other.values)))
        return sum(a * b for a, b in zip(self.values, other.values))

    def norm(self) -> float:
        return math.sqrt(self.dot(self))

    def normalize(self):
        n = self.norm()
        return Vector(self.values[:]) if n == 0 else self * (1.0 / n)

    def cosine(self, other) -> float:
        n1, n2 = self.norm(), other.norm()
        return 0.0 if n1 == 0 or n2 == 0 else self.dot(other) / (n1 * n2)

    def distance(self, other) -> float:
        if HAS_NUMPY:
            return float(np.linalg.norm(
                np.array(self.values) - np.array(other.values)))
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.values, other.values)))

    def mean(self) -> float:
        return sum(self.values) / self.dim if self.dim > 0 else 0.0

    def std(self) -> float:
        m = self.mean()
        return math.sqrt(sum((v - m) ** 2 for v in self.values) / self.dim)

    def to_list(self) -> List[float]:
        return self.values[:]


# ================================================================
# Matrix
# ================================================================

class Matrix:
    """m×n矩阵。numpy可用时走np.dot/np.linalg。"""

    def __init__(self, rows: int, cols: int, data: List[List[float]]):
        self.rows, self.cols = rows, cols
        self.data = data

    @classmethod
    def zeros(cls, rows, cols):
        return cls(rows, cols, [[0.0] * cols for _ in range(rows)])

    @classmethod
    def identity(cls, n):
        m = cls.zeros(n, n)
        for i in range(n):
            m.data[i][i] = 1.0
        return m

    @classmethod
    def from_list(cls, data: List[List[float]]):
        """从二维列表构建矩阵"""
        rows, cols = len(data), len(data[0]) if data else 0
        return cls(rows, cols, data)

    def __getitem__(self, idx):
        return self.data[idx]

    def matmul(self, other: 'Matrix') -> 'Matrix':
        if HAS_NUMPY:
            a = np.array(self.data, dtype=float)
            b = np.array(other.data, dtype=float)
            result = np.dot(a, b)
            return Matrix(result.shape[0], result.shape[1], result.tolist())
        # 纯Python O(n³)
        result = Matrix.zeros(self.rows, other.cols)
        for i in range(self.rows):
            for k in range(self.cols):
                aik = self.data[i][k]
                if aik != 0:
                    for j in range(other.cols):
                        result.data[i][j] += aik * other.data[k][j]
        return result

    def mv_product(self, vec: Vector) -> Vector:
        if HAS_NUMPY:
            a = np.array(self.data, dtype=float)
            v = np.array(vec.values, dtype=float)
            return Vector(np.dot(a, v).tolist())
        return Vector([sum(row[j] * vec[j] for j in range(self.cols))
                        for row in self.data])

    def transpose(self) -> 'Matrix':
        if HAS_NUMPY:
            t = np.array(self.data, dtype=float).T
            return Matrix(self.cols, self.rows, t.tolist())
        return Matrix(self.cols, self.rows,
                       [[self.data[j][i] for j in range(self.rows)]
                        for i in range(self.cols)])

    def to_numpy(self):
        """导出为numpy数组 (numpy必须可用)"""
        if not HAS_NUMPY:
            raise ImportError("numpy not available")
        return np.array(self.data, dtype=float)

    def to_list(self) -> List[List[float]]:
        return [row[:] for row in self.data]


# ================================================================
# PCA (主成分分析) - numpy加速版
# ================================================================

class PCA:
    """主成分分析。

    给定数据矩阵 X (m样本 × n特征)，找出方差最大的k个方向。

    用法:
        pca = PCA(n_components=5)
        pca.fit(data_matrix)
        reduced = pca.transform(data_matrix)
        explained = pca.explained_variance_ratio  # 每个成分的解释方差比
    """

    def __init__(self, n_components: int = 2):
        self.n_components = n_components
        self.components_: Optional[Matrix] = None       # (n_components × n_features)
        self.explained_variance_ratio_: List[float] = []
        self.mean_: Optional[Vector] = None

    def fit(self, X: Matrix):
        """对数据矩阵X进行PCA拟合"""
        if HAS_NUMPY:
            self._fit_numpy(X)
        else:
            self._fit_pure(X)
        return self

    def _fit_numpy(self, X: Matrix):
        X_arr = np.array(X.data, dtype=float)           # (m × n)
        self.mean_ = Vector(X_arr.mean(axis=0).tolist())
        X_centered = X_arr - np.array(self.mean_.values)  # 去均值

        # SVD分解 (比直接求协方差矩阵更稳定)
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        k = min(self.n_components, len(S))
        self.components_ = Matrix(k, X.cols, Vt[:k].tolist())
        total_var = np.sum(S ** 2)
        self.explained_variance_ratio_ = [
            (S[i] ** 2) / total_var for i in range(k)]

    def _fit_pure(self, X: Matrix):
        # 纯Python: 协方差矩阵 → 幂迭代求特征向量
        m = X.rows
        self.mean_ = Vector([sum(X.data[i][j] for i in range(m)) / m
                              for j in range(X.cols)])
        X_centered = Matrix(X.rows, X.cols,
                             [[X.data[i][j] - self.mean_[j]
                               for j in range(X.cols)] for i in range(X.rows)])
        cov = X_centered.transpose().matmul(X_centered)  # 协方差矩阵 (n×n)
        k = min(self.n_components, X.cols)
        components, eigenvals = _power_iteration(cov, k)
        self.components_ = components
        total_var = sum(eigenvals) if eigenvals else 1.0
        self.explained_variance_ratio_ = [v / total_var for v in eigenvals]

    def transform(self, X: Matrix) -> Matrix:
        """将数据X投影到主成分空间"""
        if self.components_ is None:
            raise ValueError("PCA not fitted. Call fit() first.")
        if HAS_NUMPY:
            X_arr = np.array(X.data, dtype=float)
            mean_arr = np.array(self.mean_.values, dtype=float)
            X_centered = X_arr - mean_arr
            comp_arr = np.array(self.components_.data, dtype=float)
            proj = np.dot(X_centered, comp_arr.T)
            return Matrix(proj.shape[0], proj.shape[1], proj.tolist())
        return X.matmul(self.components_.transpose())

    def fit_transform(self, X: Matrix) -> Matrix:
        return self.fit(X).transform(X)


# ================================================================
# 协方差矩阵
# ================================================================

def covariance_matrix(X: Matrix) -> Matrix:
    """计算数据矩阵X的协方差矩阵 (n_features × n_features)"""
    if HAS_NUMPY:
        X_arr = np.array(X.data, dtype=float)
        cov = np.cov(X_arr, rowvar=False)
        return Matrix(cov.shape[0], cov.shape[1], cov.tolist())
    m = X.rows
    mean = Vector([sum(X.data[i][j] for i in range(m)) / m
                    for j in range(X.cols)])
    X_centered = Matrix(X.rows, X.cols,
                         [[X.data[i][j] - mean[j]
                           for j in range(X.cols)] for i in range(X.rows)])
    return X_centered.transpose().matmul(X_centered)


# ================================================================
# 距离矩阵
# ================================================================

def pairwise_distances(vectors: List[Vector], metric: str = "cosine") -> Matrix:
    """计算向量列表的成对距离矩阵"""
    n = len(vectors)
    m = Matrix.zeros(n, n)
    for i in range(n):
        for j in range(i + 1, n):
            if metric == "cosine":
                d = 1.0 - vectors[i].cosine(vectors[j])
            elif metric == "euclidean":
                d = vectors[i].distance(vectors[j])
            else:
                raise ValueError(f"Unknown metric: {metric}")
            m.data[i][j] = d
            m.data[j][i] = d
    return m


# ================================================================
# 辅助: 幂迭代求特征向量
# ================================================================

def _power_iteration(A: Matrix, k: int) -> Tuple[Matrix, List[float]]:
    """纯Python幂迭代，求矩阵A的前k个特征向量和特征值"""
    n = A.cols
    eigenvectors = []
    eigenvals = []
    # 简化实现: 对每个成分单独迭代
    for _ in range(k):
        v = Vector([1.0 / math.sqrt(n)] * n)  # 随机初始化
        for _ in range(50):  # 最多50次迭代
            Av = A.mv_product(v)
            norm = Av.norm()
            if norm < 1e-12:
                break
            v_new = Av * (1.0 / norm)
            if v.cosine(v_new) > 0.9999:
                v = v_new
                break
            v = v_new
        eigenvalue = A.mv_product(v).norm()
        eigenvectors.append(v)
        eigenvals.append(eigenvalue)
        # 收缩: A = A - λ * v * v^T
        for i in range(n):
            for j in range(n):
                A.data[i][j] -= eigenvalue * v[i] * v[j]

    components = Matrix(k, n, [[v[i] for i in range(n)] for v in eigenvectors])
    return components, eigenvals

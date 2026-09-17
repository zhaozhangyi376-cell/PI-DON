# Algorithm 1 第7步：FDTD/Yee 旋度目标代码注释

本文用于汇报讲解：第7步训练目标是否为“让 PI-DON/DCO 输出的旋度场拟合 FDTD 算出的旋度场”。结论是：**是，但这里的 FDTD 目标不是预先跑完整条未来轨迹得到的场标签，而是对当前时间步的当前场，用 Yee/FDTD 差分公式即时计算出的离散旋度。**

## 一句话逻辑

```text
当前 E 场
  -> Yee/FDTD 差分公式 fdtd.curl_E(E)
  -> 得到当前步的真实离散旋度 target = ∇×E
  -> PI-DON/DCO 输出 pred = DCO(E)
  -> loss = ||pred - target||^2 / ||target||^2
  -> 用这个 pred 更新 H
```

对 H 也是同理：

```text
当前 H 场 -> fdtd.curl_H(H) -> target = ∇×H -> DCO(H) 拟合 target -> 用 pred 更新 E
```

## 1. FDTD/Yee 旋度公式在哪里

文件：[src/pidon/fdtd.py](C:/PI-DON/src/pidon/fdtd.py)

### 1.1 `curl_E`：由当前 E 场计算真实离散 curl(E)

```python
def curl_E(Ex, Ey, Ez, dx, dy, dz):
    """(curl E) evaluated at the H positions.  Returns (cx, cy, cz)."""
    cx = (Ez[:, 1:, :] - Ez[:, :-1, :]) / dy - (Ey[:, :, 1:] - Ey[:, :, :-1]) / dz
    cy = (Ex[:, :, 1:] - Ex[:, :, :-1]) / dz - (Ez[1:, :, :] - Ez[:-1, :, :]) / dx
    cz = (Ey[1:, :, :] - Ey[:-1, :, :]) / dx - (Ex[:, 1:, :] - Ex[:, :-1, :]) / dy
    return cx, cy, cz
```

逐行解释：

| 代码 | 物理含义 |
|---|---|
| `curl_E(Ex, Ey, Ez, dx, dy, dz)` | 输入当前时间步的三分量电场，以及网格步长。 |
| `cx = dEz/dy - dEy/dz` | 对应 Maxwell 中 `(∇×E)_x`。 |
| `cy = dEx/dz - dEz/dx` | 对应 `(∇×E)_y`。 |
| `cz = dEy/dx - dEx/dy` | 对应 `(∇×E)_z`。 |
| `return cx, cy, cz` | 输出的三个分量位于 Yee 网格的 H 位置，用于更新 H。 |

注意：这些差分就是 FDTD/Yee 格式的核心。它不是神经网络预测，而是传统数值电磁学里的标准离散旋度。

### 1.2 `curl_H`：由当前 H 场计算真实离散 curl(H)

```python
def curl_H(Hx, Hy, Hz, dx, dy, dz):
    """(curl H) evaluated at the interior E positions.  Returns (cx, cy, cz)
    shaped to match Ex[:,1:-1,1:-1], Ey[1:-1,:,1:-1], Ez[1:-1,1:-1,:]."""
    cx = ((Hz[:, 1:, 1:-1] - Hz[:, :-1, 1:-1]) / dy
          - (Hy[:, 1:-1, 1:] - Hy[:, 1:-1, :-1]) / dz)
    cy = ((Hx[1:-1, :, 1:] - Hx[1:-1, :, :-1]) / dz
          - (Hz[1:, :, 1:-1] - Hz[:-1, :, 1:-1]) / dx)
    cz = ((Hy[1:, 1:-1, :] - Hy[:-1, 1:-1, :]) / dx
          - (Hx[1:-1, 1:, :] - Hx[1:-1, :-1, :]) / dy)
    return cx, cy, cz
```

逐行解释：

| 代码 | 物理含义 |
|---|---|
| `curl_H(Hx, Hy, Hz, dx, dy, dz)` | 输入当前时间步的三分量磁场。 |
| `cx = dHz/dy - dHy/dz` | 对应 `(∇×H)_x`，用于更新 `Ex`。 |
| `cy = dHx/dz - dHz/dx` | 对应 `(∇×H)_y`，用于更新 `Ey`。 |
| `cz = dHy/dx - dHx/dy` | 对应 `(∇×H)_z`，用于更新 `Ez`。 |
| `1:-1` | 只更新 E 的内部点，边界 PEC 条件另行保持。 |

## 2. 标准 FDTD 是怎么用这些 curl 更新 E/H 的

仍在 [src/pidon/fdtd.py](C:/PI-DON/src/pidon/fdtd.py)。

```python
# H update from curl E
cx, cy, cz = curl_E(self.Ex, self.Ey, self.Ez, *d)
k = self.dt / self.mu
self.Hx -= k * cx
self.Hy -= k * cy
self.Hz -= k * cz

# E update from curl H
hx, hy, hz = curl_H(self.Hx, self.Hy, self.Hz, *d)
ke = self.dt / EPS0
self.Ex[:, 1:-1, 1:-1] += ke * hx
self.Ey[1:-1, :, 1:-1] += ke * hy
self.Ez[1:-1, 1:-1, :] += ke * hz
```

对应 Maxwell 时域方程：

```text
∂H/∂t = - (1/μ) ∇×E
∂E/∂t =   (1/ε) ∇×H
```

所以代码里的符号是：

```text
H_new = H_old - dt/μ * curl(E)
E_new = E_old + dt/ε * curl(H)
```

## 3. Algorithm 1 中“真实旋度目标”怎么生成

文件：[src/pidon/pidon_solve.py](C:/PI-DON/src/pidon/pidon_solve.py)

### 3.1 `yee_curl_E` 和 `yee_curl_H`

```python
def yee_curl_E(self):
    cx, cy, cz = fdtd.curl_E(*[t.cpu().numpy() for t in self.E],
                             self.cav.dx, self.cav.dy, self.cav.dz)
    return [to_t(c, self.dev, self.dtype) for c in (cx, cy, cz)]

def yee_curl_H(self):
    cx, cy, cz = fdtd.curl_H(*[t.cpu().numpy() for t in self.H],
                             self.cav.dx, self.cav.dy, self.cav.dz)
    return [to_t(c, self.dev, self.dtype) for c in (cx, cy, cz)]
```

逐行解释：

| 代码 | 含义 |
|---|---|
| `self.E` / `self.H` | 当前 Algorithm 1 正在推进的场。 |
| `fdtd.curl_E(...)` | 用传统 Yee/FDTD 差分公式算当前 `E` 的真实离散旋度。 |
| `fdtd.curl_H(...)` | 用传统 Yee/FDTD 差分公式算当前 `H` 的真实离散旋度。 |
| `to_t(...)` | 把 numpy 结果转回 PyTorch tensor，作为神经网络训练目标。 |

这一步就是“给 PI-DON/DCO 训练一个当前步的物理目标”。

## 4. 第7步的训练目标在哪里进入 loss

在 [src/pidon/pidon_solve.py](C:/PI-DON/src/pidon/pidon_solve.py) 的 `inner_train` 中：

```python
def evaluate(with_grad=False):
    pred = pred_slices(self.predict(core, which))
    sq_parts = [(p - t).pow(2).sum() for p, t in zip(pred, tgt)]
    sq = sum(sq_parts)
    loss = sq / den_t if self.a.tol_mode == "rel" else sq
    return pred, sq, loss
```

逐行解释：

| 代码 | 含义 |
|---|---|
| `self.predict(core, which)` | PI-DON/DCO 对当前 `E` 或 `H` 输出预测旋度。 |
| `pred_slices(...)` | 把网络输出裁到与 Yee 目标一致的网格支撑域。 |
| `p - t` | `p` 是网络预测旋度，`t` 是 FDTD/Yee 算出的真实离散旋度。 |
| `(p - t).pow(2).sum()` | 三个旋度分量分别计算平方误差。 |
| `sq = sum(sq_parts)` | 总平方误差。 |
| `loss = sq / den_t` | 当前实现默认使用相对误差形式，避免场幅值很小时绝对误差门槛失去意义。 |

所以第7步可以讲成：

```text
第7步不是直接拟合未来 E/H 场；
第7步是让网络输出的 curl(E) 拟合当前 E 场经 Yee/FDTD 差分算出的 curl(E)。
```

## 5. Algorithm 1 的一步完整流程在代码哪里

仍在 [src/pidon/pidon_solve.py](C:/PI-DON/src/pidon/pidon_solve.py)。

```python
fit_H = self.inner_train(self.H, self.yee_curl_H(), "H")
self._update_E_and_source(fit_H.prediction, g_t)

fit_E = self.inner_train(self.E, self.yee_curl_E(), "E")
self._update_H(fit_E.prediction)
```

逐行解释：

| 代码 | 对应 Algorithm 1 |
|---|---|
| `self.yee_curl_H()` | 用 FDTD/Yee 公式从当前 `H` 算出真实 `curl(H)`。 |
| `inner_train(self.H, ..., "H")` | 训练 PI-DON/DCO，使其输出拟合 `curl(H)`。 |
| `_update_E_and_source(...)` | 用预测的 `curl(H)` 更新 `E`，再加入源激励。 |
| `self.yee_curl_E()` | 用 FDTD/Yee 公式从更新后的当前 `E` 算出真实 `curl(E)`。 |
| `inner_train(self.E, ..., "E")` | 第7步：训练 PI-DON/DCO，使其输出拟合 `curl(E)`。 |
| `_update_H(...)` | 用预测的 `curl(E)` 更新 `H`。 |

## 6. PI-DON 用预测旋度更新场

```python
def _update_E_and_source(self, predicted_curl_H, g_t):
    ch = self._insert_prediction(self.yee_curl_H(), predicted_curl_H, "H")
    ke = self.dt / fdtd.EPS0
    self.E[0][:, 1:-1, 1:-1] += ke * ch[0]
    self.E[1][1:-1, :, 1:-1] += ke * ch[1]
    self.E[2][1:-1, 1:-1, :] += ke * ch[2]
    self.E[2][c, c, c] = g_t
    self.apply_pec()

def _update_H(self, predicted_curl_E):
    ce = self._insert_prediction(self.yee_curl_E(), predicted_curl_E, "E")
    kh = self.dt / self.cav.mu
    for k in range(3):
        self.H[k] -= kh * ce[k]
```

讲解重点：

- `predicted_curl_H` 和 `predicted_curl_E` 是网络输出。
- `_insert_prediction(...)` 把网络能预测的内部区域放回完整 Yee 网格。
- 边界或网络不覆盖的区域保留 Yee 公式/PEC 处理。
- 更新公式仍然是 Maxwell/FDTD 的时间推进公式，只是 curl 项由网络拟合后提供。

## 7. 给导师的准确表述

推荐汇报表述：

> Algorithm 1 第7步的训练目标，是让 PI-DON/DCO 在当前时间步输出的 `curl(E)`，拟合由当前 `E` 场通过 Yee/FDTD 差分公式即时计算出的离散 `curl(E)`。这里用 FDTD 的不是整条未来轨迹标签，而是 Maxwell 方程离散形式给出的当前局部物理目标。随后再用这个网络输出的 `curl(E)` 按 `H_new = H_old - dt/mu * curl(E)` 更新磁场。

更短版本：

> 第7步本质是“当前场的旋度拟合”：`DCO(E_now) ≈ YeeCurl(E_now)`，然后用拟合出来的旋度更新 `H`。

## 8. 容易被问到的问题

### Q1：如果已经用 FDTD 算了 curl，为什么还要训练 PI-DON？

因为论文的思路不是直接用 FDTD 推完整条轨迹，而是用物理损失在每个时间步适配神经算子，希望后续在更复杂参数、不确定性分析或复用场景中减少重新求解成本。但在当前复现证据中，这个收益还没有被证明。

### Q2：这是不是监督学习？

单步拟合形式上像监督学习，因为有目标 `YeeCurl(E/H)`；但目标不是人工数据集标签，而是由 Maxwell/Yee 物理方程在当前状态即时生成，所以论文称为 physics-informed。

### Q3：边界条件在哪里体现？

在两个地方：

1. `curl_H` 只更新内部 E 点，边界不直接由网络自由更新。
2. `_update_E_and_source` 后调用 `apply_pec()`，保持 PEC 边界的切向 E 为 0。

论文说边界条件作为 loss 的一部分；当前实现更偏硬约束/投影：先按内部支撑域训练，再把边界强制回 PEC 条件。

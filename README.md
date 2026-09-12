# PI-DON 复现

复现 Qi & Sarris, *"Physics-Informed Deep Operator Network for 3-D Time-Domain
Electromagnetic Modeling"*, IEEE T-MTT **73(7)**, 3800–3812, 2025。

把 FDTD 时间推进里的空间旋度算子 ∇× 换成神经算子（DCO），再用物理损失逐步求解
麦克斯韦方程组。卖点是"训一次、反复用"，对需要成百上千次仿真的不确定性量化最划算。

## 从哪读起

| 想知道 | 看这个 |
|---|---|
| **要动手改代码 / 接手这个项目** | **`AGENTS.md`（必读，红线全在里面）** |
| 现在做到哪一步、最新数字 | `STATUS.md` |
| 每条结论是否还成立、判据是什么 | `RESULTS.md`（由 `verify_claims.py` 生成） |
| 某次运行到底跑没跑、跑了什么 | `LAB_NOTEBOOK.md` / `lab_runs.jsonl` |
| 论文本身怎么读的 | `PAPER_NOTES.md` |
| 搬到服务器上跑 | `SERVER_SETUP.md` |

## 快速上手

```
py -3.11 gen_data.py --n 32 --samples 1000 --out data_32.npz     # 造数据
py -3.11 lab_log.py run -m "训练" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 300 --lr 1e-3 --batch 16
py -3.11 lab_log.py run -m "验收" -- py -3.11 test_dco.py --ckpt dco_lr1e3_300.pt
py -3.11 verify_claims.py --run --md                             # 刷新 RESULTS.md
```

依赖只有三个：`torch` `numpy` `matplotlib`。

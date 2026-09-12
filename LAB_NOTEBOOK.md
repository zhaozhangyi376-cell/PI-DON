# 实验记录

由 `lab_log.py` 自动追加。**不要手工编辑** —— 手写的记录证明不了任何事，自动记录才能。

每条记录包含：命令原文、git commit、机器、耗时、产生的文件及其 sha256。
别人可以拿磁盘上的文件算一遍哈希，对照这里，确认它确实是那条命令在那个 commit 下产生的。

---

## #1　2026-09-10T18:56:36　OK

**重测 EXP2 的 nMAE，核实悬空的「差 10x」结论**

```
py -3.11 test_dco.py --ckpt pidon_R2_all.pt --exp1-samples 20 --exp2-sizes 16 32 48 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
```

- 耗时 5s ｜ commit `759ff4f` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = ['7.134e-03', '6.743e-03', '9.216e-03', '8.113e-03', '8.991e-03']`　`blowup_step = 147`　`exp2_relL2 = ['1.886e-02', '2.450e-02', '4.119e-02', '3.146e-02', '3.139e-02']`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `test_results.npz` | 147 KB | `41a946c079357552` |
| `test_results_pidon_R2_all.npz` | 147 KB | `41a946c079357552` |
| `exp3_waveform.npz` | 13 KB | `9ea756d3e90422cc` |

<details><summary>输出末尾</summary>

```
[test_dco.py  version 2026-09-09g]
  trunk coord encoding: cellsize   input scaling: rms   training target: yee   test dirs: shared   head: direct   lam_div=1.0
loaded pidon_R2_all.pt: L=3 base=32 trained at 16^3, 2.25M params

[EXP 1] single-shot curl on 20 unseen 16^3 plane-wave samples, dirs=shared
  relative L2 over 20 samples:  mean 1.719e-02   median 1.686e-02   worst 2.624e-02   [target = yee]
    vs analytic curl 2.418e-02   vs Yee curl 1.719e-02   (the two targets differ by ~8e-3)
  nMAE (MAE/max, the paper's metric) mean 5.796e-03   <- THIS is what compares to paper Table I / III-D

[EXP 2] dimension invariance -- net was trained at 16^3 only
          16^3   relative L2 = 1.886e-02   nMAE = 7.134e-03
          32^3   relative L2 = 2.450e-02   nMAE = 6.743e-03
          48^3   relative L2 = 4.119e-02   nMAE = 9.216e-03
      64x96x16   relative L2 = 3.146e-02   nMAE = 8.113e-03
      32x64x16   relative L2 = 3.139e-02   nMAE = 8.991e-03

  paper III-D (32^3-trained): 64^3 4.1e-3, 64x96x16 3.8e-3, 32x64x16 4.7e-3
  COMPARE THOSE TO THE nMAE COLUMN, NOT THE relative L2 COLUMN.
  The paper reports MAE/max throughout -- that is the only reading under
  which its own Table I and section III-D agree.  On this data relative L2
  runs 30-40x larger than nMAE, so comparing the wrong column is not a
  small error: it flips the sign of the conclusion.  (This script printed
  only relative L2 next to those numbers until 2026-09-10, and the gap it
  seemed to show was an artefact of that.)

[EXP 3] DCO-in-the-loop cavity  22.4 mm / 32 cells -> dx = 0.700 mm   source=diff
  warm-up 300 FDTD steps done, |Ez|max = 2.116e-02
  handover state: k_eff*d = 0.4135   (training band 0.152 .. 0.491, clean TE101 mode 0.167)
  [3a] open loop -- DCO vs Yee curl on the warmed-up cavity field:
        cavity field, all 3 components relL2 4.918e-02   nMAE 5.749e-03   eq5 1.78e+12
  [3b] blew up at step 147 -- stopping early
  400 DCO-driven steps in 1.5s (4 ms/step)
  curl relL2 per step: first 4.213e-02  median 7.153e-01  last 6.967e-01
  Ez waveform error vs FDTD: mean 1.160e+02  max 3.957e+03
    exceeds    1% of peak at step 7
    exceeds    5% of peak at step 36
    exceeds   20% of peak at step 41
  saved exp3_waveform.npz  (plot rec_ref vs rec_dut for the slide)

saved test_results_pidon_R2_all.npz  ->  now run:  py -3.11 make_figs.py
```

</details>

## #2　2026-09-10T20:34:20　OK

**dco_paper32 acceptance: like-for-like vs paper III-D**

```
py -3.11 test_dco.py --ckpt dco_paper32.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
```

- 耗时 8s ｜ commit `3e56c35` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = ['4.738e-03', '4.821e-03', '2.875e-03', '5.687e-03', '6.266e-03']`　`blowup_step = 158`　`exp2_relL2 = ['2.751e-02', '3.045e-02', '2.316e-02', '3.019e-02', '2.917e-02']`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `test_results.npz` | 1,155 KB | `8f812530ecfc85fd` |
| `test_results_dco_paper32.npz` | 1,155 KB | `8f812530ecfc85fd` |
| `exp3_waveform.npz` | 13 KB | `3e5e8b66b0a2d52c` |

<details><summary>输出末尾</summary>

```
[test_dco.py  version 2026-09-09g]
  trunk coord encoding: cellsize   input scaling: rms   training target: analytic   test dirs: shared   head: direct
loaded dco_paper32.pt: L=4 base=32 trained at 32^3, 9.25M params

[EXP 1] single-shot curl on 20 unseen 32^3 plane-wave samples, dirs=shared
  relative L2 over 20 samples:  mean 2.272e-02   median 2.245e-02   worst 3.358e-02   [target = analytic]
    vs analytic curl 2.272e-02   vs Yee curl 1.567e-02   (the two targets differ by ~8e-3)
  nMAE (MAE/max, the paper's metric) mean 4.427e-03   <- THIS is what compares to paper Table I / III-D

[EXP 2] dimension invariance -- net was trained at 16^3 only
          32^3   relative L2 = 2.751e-02   nMAE = 4.738e-03
          48^3   relative L2 = 3.045e-02   nMAE = 4.821e-03
          64^3   relative L2 = 2.316e-02   nMAE = 2.875e-03
      64x96x16   relative L2 = 3.019e-02   nMAE = 5.687e-03
      32x64x16   relative L2 = 2.917e-02   nMAE = 6.266e-03

  paper III-D (32^3-trained): 64^3 4.1e-3, 64x96x16 3.8e-3, 32x64x16 4.7e-3
  COMPARE THOSE TO THE nMAE COLUMN, NOT THE relative L2 COLUMN.
  On THIS checkpoint's data relative L2 runs 4.7-8.1x larger than nMAE  (ratio measured now, not hard-coded).
  The paper reports MAE/max throughout -- that is the only reading under
  which its own Table I and section III-D agree.  So comparing the wrong
  column is not a small error: it flips the sign of the conclusion.  (This
  script printed only relative L2 next to those numbers until 2026-09-10,
  and the gap it seemed to show was an artefact of that.)

[EXP 3] DCO-in-the-loop cavity  22.4 mm / 32 cells -> dx = 0.700 mm   source=diff
  warm-up 300 FDTD steps done, |Ez|max = 2.116e-02
  handover state: k_eff*d = 0.4135   (training band 0.152 .. 0.491, clean TE101 mode 0.167)
  [3a] open loop -- DCO vs Yee curl on the warmed-up cavity field:
        cavity field, all 3 components relL2 7.125e-02   nMAE 7.419e-03   eq5 1.65e+12
  [3b] blew up at step 158 -- stopping early
  400 DCO-driven steps in 1.9s (5 ms/step)
  curl relL2 per step: first 6.451e-02  median 9.716e-01  last 9.788e-01
  Ez waveform error vs FDTD: mean 1.708e+02  max 3.675e+03
    exceeds    1% of peak at step 8
    exceeds    5% of peak at step 34
    exceeds   20% of peak at step 51
  saved exp3_waveform.npz  (plot rec_ref vs rec_dut for the slide)

saved test_results_dco_paper32.npz  ->  now run:  py -3.11 make_figs.py
```

</details>

## #3　2026-09-10T20:34:27　OK

**dco_L4b acceptance, control for dco_paper32**

```
py -3.11 test_dco.py --ckpt dco_L4b.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
```

- 耗时 6s ｜ commit `3e56c35` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = ['3.586e-02', '5.643e-02', '1.652e-02', '5.071e-02', '4.243e-02']`　`blowup_step = 86`　`exp2_relL2 = ['1.555e-01', '2.768e-01', '9.300e-02', '1.867e-01', '1.691e-01']`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `test_results.npz` | 147 KB | `ee626dfc4e13ba3d` |
| `test_results_dco_L4b.npz` | 147 KB | `ee626dfc4e13ba3d` |
| `exp3_waveform.npz` | 13 KB | `3c83901cb32ed6c4` |

<details><summary>输出末尾</summary>

```
[test_dco.py  version 2026-09-09g]
  trunk coord encoding: cellsize   input scaling: rms   training target: analytic   test dirs: shared   head: direct
loaded dco_L4b.pt: L=4 base=32 trained at 16^3, 9.25M params

[EXP 1] single-shot curl on 20 unseen 16^3 plane-wave samples, dirs=shared
  relative L2 over 20 samples:  mean 4.222e-02   median 4.173e-02   worst 5.997e-02   [target = analytic]
    vs analytic curl 4.222e-02   vs Yee curl 3.341e-02   (the two targets differ by ~8e-3)
  nMAE (MAE/max, the paper's metric) mean 1.316e-02   <- THIS is what compares to paper Table I / III-D

[EXP 2] dimension invariance -- net was trained at 16^3 only
          32^3   relative L2 = 1.555e-01   nMAE = 3.586e-02
          48^3   relative L2 = 2.768e-01   nMAE = 5.643e-02
          64^3   relative L2 = 9.300e-02   nMAE = 1.652e-02
      64x96x16   relative L2 = 1.867e-01   nMAE = 5.071e-02
      32x64x16   relative L2 = 1.691e-01   nMAE = 4.243e-02

  paper III-D (32^3-trained): 64^3 4.1e-3, 64x96x16 3.8e-3, 32x64x16 4.7e-3
  COMPARE THOSE TO THE nMAE COLUMN, NOT THE relative L2 COLUMN.
  On THIS checkpoint's data relative L2 runs 3.7-5.6x larger than nMAE  (ratio measured now, not hard-coded).
  The paper reports MAE/max throughout -- that is the only reading under
  which its own Table I and section III-D agree.  So comparing the wrong
  column is not a small error: it flips the sign of the conclusion.  (This
  script printed only relative L2 next to those numbers until 2026-09-10,
  and the gap it seemed to show was an artefact of that.)

[EXP 3] DCO-in-the-loop cavity  22.4 mm / 32 cells -> dx = 0.700 mm   source=diff
  warm-up 300 FDTD steps done, |Ez|max = 2.116e-02
  handover state: k_eff*d = 0.4135   (training band 0.152 .. 0.491, clean TE101 mode 0.167)
  [3a] open loop -- DCO vs Yee curl on the warmed-up cavity field:
        cavity field, all 3 components relL2 1.315e-01   nMAE 1.577e-02   eq5 3.33e+12
  [3b] blew up at step 86 -- stopping early
  400 DCO-driven steps in 1.0s (3 ms/step)
  curl relL2 per step: first 1.354e-01  median 1.036e+00  last 1.117e+00
  Ez waveform error vs FDTD: mean 1.923e+02  max 3.597e+03
    exceeds    1% of peak at step 1
    exceeds    5% of peak at step 28
    exceeds   20% of peak at step 33
  saved exp3_waveform.npz  (plot rec_ref vs rec_dut for the slide)

saved test_results_dco_L4b.npz  ->  now run:  py -3.11 make_figs.py
```

</details>

## #4　2026-09-10T20:36:26　OK

**pidon_R2_all denser CFL sweep, 5 CFL x 5 seeds, tightens C3**

```
py -3.11 spectral_dco.py --ckpt pidon_R2_all.pt --n 32 --cfl 0.99 0.85 0.70 0.60 0.30 --samples 5 --iters 160 --burn 55 --emp-steps 600
```

- 耗时 117s ｜ commit `3e56c35` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `spectral_pidon_R2_all.json` | 8 KB | `b62d87bfae81e413` |

<details><summary>输出末尾</summary>

```
    [2] k*d 0.3491  rms|E| 0.4894  eps0 4.355e-02  rho 1.11088615  rho_nl 1.06966941  pred     29.8  meas    140
    [3] k*d 0.4290  rms|E| 0.0903  eps0 4.468e-02  rho 1.11771118  rho_nl 1.05578776  pred     27.9  meas    124
    [4] k*d 0.4267  rms|E| 0.2937  eps0 6.105e-02  rho 1.15893694  rho_nl 1.06632189  pred     19.0  meas    127

  CFL 0.85   handover after 47 exact steps   (5 probe states)
    [0] k*d 0.4071  rms|E| 0.0802  eps0 3.152e-02  rho 1.09714949  rho_nl 1.04926826  pred     37.3  meas    150
    [1] k*d 0.3261  rms|E| 0.5708  eps0 5.234e-02  rho 1.09386114  rho_nl 1.05587570  pred     32.9  meas    159
    [2] k*d 0.3467  rms|E| 0.4805  eps0 4.351e-02  rho 1.09094153  rho_nl 1.05908824  pred     36.0  meas    164
    [3] k*d 0.4501  rms|E| 0.1040  eps0 4.246e-02  rho 1.10250268  rho_nl 1.04790917  pred     32.4  meas    147
    [4] k*d 0.4275  rms|E| 0.2825  eps0 6.235e-02  rho 1.12685750  rho_nl 1.05630705  pred     23.2  meas    148

  CFL 0.70   handover after 57 exact steps   (5 probe states)
    [0] k*d 0.4067  rms|E| 0.0820  eps0 2.951e-02  rho 1.07587345  rho_nl 1.04014215  pred     48.2  meas    183
    [1] k*d 0.3244  rms|E| 0.5683  eps0 5.250e-02  rho 1.07338408  rho_nl 1.04562827  pred     41.6  meas    195
    [2] k*d 0.3480  rms|E| 0.4848  eps0 4.353e-02  rho 1.07134989  rho_nl 1.04819488  pred     45.5  meas    200
    [3] k*d 0.4386  rms|E| 0.0940  eps0 4.397e-02  rho 1.07680076  rho_nl 1.03877529  pred     42.2  meas    178
    [4] k*d 0.4268  rms|E| 0.2880  eps0 6.150e-02  rho 1.09398545  rho_nl 1.04586535  pred     31.0  meas    181

  CFL 0.60   handover after 66 exact steps   (5 probe states)
    [0] k*d 0.3993  rms|E| 0.0902  eps0 2.876e-02  rho 1.06157884  rho_nl 1.03473743  pred     59.4  meas    217
    [1] k*d 0.3209  rms|E| 0.5633  eps0 5.306e-02  rho 1.05982818  rho_nl 1.03875858  pred     50.5  meas    228
    [2] k*d 0.3514  rms|E| 0.4954  eps0 4.355e-02  rho 1.05886124  rho_nl 1.04109198  pred     54.8  meas    234
    [3] k*d 0.4056  rms|E| 0.0824  eps0 4.610e-02  rho 1.06230616  rho_nl 1.03261318  pred     50.9  meas    206
    [4] k*d 0.4266  rms|E| 0.3044  eps0 6.004e-02  rho 1.07193692  rho_nl 1.03918218  pred     40.5  meas    213

  CFL 0.30   handover after 132 exact steps   (5 probe states)
    [0] k*d 0.3945  rms|E| 0.0952  eps0 3.005e-02  rho 1.02215184  rho_nl 1.01717040  pred    160.0  meas    438
    [1] k*d 0.3195  rms|E| 0.5601  eps0 5.341e-02  rho 1.02207852  rho_nl 1.01910267  pred    134.2  meas    460
    [2] k*d 0.3529  rms|E| 0.4995  eps0 4.354e-02  rho 1.02273874  rho_nl 1.02025073  pred    139.4  meas    471
    [3] k*d 0.3985  rms|E| 0.0839  eps0 4.738e-02  rho 1.02259130  rho_nl 1.01613927  pred    136.5  meas    416
    [4] k*d 0.4270  rms|E| 0.3127  eps0 5.963e-02  rho 1.02356857  rho_nl 1.01936172  pred    121.0  meas    431

  can a smaller time step rescue it?  (mean over probe states)
    CFL 0.99   rho = 1.12342065  (spread 4.81e-02 over 5 states)   UNSTABLE
    CFL 0.85   rho = 1.10226247  (spread 3.59e-02 over 5 states)   UNSTABLE
    CFL 0.70   rho = 1.07827873  (spread 2.26e-02 over 5 states)   UNSTABLE
    CFL 0.60   rho = 1.06290227  (spread 1.31e-02 over 5 states)   UNSTABLE
    CFL 0.30   rho = 1.02262580  (spread 1.49e-03 over 5 states)   UNSTABLE

saved spectral_pidon_R2_all.json
```

</details>

## #5　2026-09-10T20:38:50　OK

**dco_paper32 denser CFL sweep, 5 CFL x 5 seeds, tightens C3**

```
py -3.11 spectral_dco.py --ckpt dco_paper32.pt --n 32 --cfl 0.99 0.85 0.70 0.60 0.30 --samples 5 --iters 160 --burn 55 --emp-steps 600
```

- 耗时 142s ｜ commit `3e56c35` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `spectral_dco_paper32.json` | 8 KB | `b3851deda74e8c1c` |

<details><summary>输出末尾</summary>

```
    [2] k*d 0.3491  rms|E| 0.4894  eps0 5.826e-02  rho 1.11450310  rho_nl 1.07416077  pred     26.2  meas    130
    [3] k*d 0.4290  rms|E| 0.0903  eps0 5.538e-02  rho 1.11711935  rho_nl 1.07497612  pred     26.1  meas    106
    [4] k*d 0.4267  rms|E| 0.2937  eps0 1.223e-01  rho 1.11261572  rho_nl 1.06761667  pred     19.7  meas    120

  CFL 0.85   handover after 47 exact steps   (5 probe states)
    [0] k*d 0.4071  rms|E| 0.0802  eps0 3.606e-02  rho 1.09657249  rho_nl 1.05140097  pred     36.0  meas    135
    [1] k*d 0.3261  rms|E| 0.5708  eps0 7.502e-02  rho 1.09480412  rho_nl 1.06574252  pred     28.6  meas    148
    [2] k*d 0.3467  rms|E| 0.4805  eps0 5.792e-02  rho 1.09522044  rho_nl 1.06325465  pred     31.3  meas    152
    [3] k*d 0.4501  rms|E| 0.1040  eps0 5.285e-02  rho 1.09887601  rho_nl 1.06466261  pred     31.2  meas    124
    [4] k*d 0.4275  rms|E| 0.2825  eps0 1.227e-01  rho 1.09362633  rho_nl 1.05748165  pred     23.4  meas    140

  CFL 0.70   handover after 57 exact steps   (5 probe states)
    [0] k*d 0.4067  rms|E| 0.0820  eps0 3.403e-02  rho 1.07611028  rho_nl 1.04235336  pred     46.1  meas    165
    [1] k*d 0.3244  rms|E| 0.5683  eps0 7.458e-02  rho 1.07401920  rho_nl 1.05363576  pred     36.4  meas    180
    [2] k*d 0.3480  rms|E| 0.4848  eps0 5.812e-02  rho 1.07429360  rho_nl 1.05163647  pred     39.7  meas    185
    [3] k*d 0.4386  rms|E| 0.0940  eps0 5.481e-02  rho 1.07603906  rho_nl 1.05213333  pred     39.6  meas    150
    [4] k*d 0.4268  rms|E| 0.2880  eps0 1.225e-01  rho 1.07216976  rho_nl 1.04698454  pred     30.1  meas    171

  CFL 0.60   handover after 66 exact steps   (5 probe states)
    [0] k*d 0.3993  rms|E| 0.0902  eps0 3.381e-02  rho 1.06223497  rho_nl 1.03646014  pred     56.1  meas    195
    [1] k*d 0.3209  rms|E| 0.5633  eps0 7.365e-02  rho 1.06052046  rho_nl 1.04548422  pred     44.4  meas    211
    [2] k*d 0.3514  rms|E| 0.4954  eps0 5.849e-02  rho 1.06020751  rho_nl 1.04417785  pred     48.6  meas    216
    [3] k*d 0.4056  rms|E| 0.0824  eps0 5.242e-02  rho 1.06103458  rho_nl 1.04373789  pred     49.8  meas    174
    [4] k*d 0.4266  rms|E| 0.3044  eps0 1.216e-01  rho 1.05987164  rho_nl 1.04024477  pred     36.2  meas    200

  CFL 0.30   handover after 132 exact steps   (5 probe states)
    [0] k*d 0.3945  rms|E| 0.0952  eps0 3.560e-02  rho 1.02204783  rho_nl 1.01819116  pred    152.9  meas    394
    [1] k*d 0.3195  rms|E| 0.5601  eps0 7.329e-02  rho 1.02174738  rho_nl 1.02250168  pred    121.5  meas    424
    [2] k*d 0.3529  rms|E| 0.4995  eps0 5.861e-02  rho 1.02109690  rho_nl 1.02177757  pred    135.9  meas    434
    [3] k*d 0.3985  rms|E| 0.0839  eps0 5.092e-02  rho 1.02258078  rho_nl 1.02168023  pred    133.3  meas    351
    [4] k*d 0.4270  rms|E| 0.3127  eps0 1.212e-01  rho 1.02213682  rho_nl 1.01996688  pred     96.4  meas    404

  can a smaller time step rescue it?  (mean over probe states)
    CFL 0.99   rho = 1.11491494  (spread 4.50e-03 over 5 states)   UNSTABLE
    CFL 0.85   rho = 1.09581988  (spread 5.25e-03 over 5 states)   UNSTABLE
    CFL 0.70   rho = 1.07452638  (spread 3.94e-03 over 5 states)   UNSTABLE
    CFL 0.60   rho = 1.06077383  (spread 2.36e-03 over 5 states)   UNSTABLE
    CFL 0.30   rho = 1.02192194  (spread 1.48e-03 over 5 states)   UNSTABLE

saved spectral_dco_paper32.json
```

</details>

## #6　2026-09-10T20:40:25　OK

**dco_L3d denser CFL sweep, 5 CFL x 5 seeds, tightens C3**

```
py -3.11 spectral_dco.py --ckpt dco_L3d.pt --n 32 --cfl 0.99 0.85 0.70 0.60 0.30 --samples 5 --iters 160 --burn 55 --emp-steps 600
```

- 耗时 94s ｜ commit `3e56c35` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `spectral_dco_L3d.json` | 8 KB | `63bd71cd3f227ae0` |

<details><summary>输出末尾</summary>

```
    [2] k*d 0.3491  rms|E| 0.4894  eps0 7.538e-02  rho 1.26536016  rho_nl 1.20212359  pred     11.0  meas     53
    [3] k*d 0.4290  rms|E| 0.0903  eps0 8.432e-02  rho 1.24528502  rho_nl 1.18771949  pred     11.3  meas     46
    [4] k*d 0.4267  rms|E| 0.2937  eps0 1.536e-01  rho 1.22335891  rho_nl 1.19765153  pred      9.3  meas     50

  CFL 0.85   handover after 47 exact steps   (5 probe states)
    [0] k*d 0.4071  rms|E| 0.0802  eps0 5.550e-02  rho 1.17895673  rho_nl 1.18386237  pred     17.6  meas     50
    [1] k*d 0.3261  rms|E| 0.5708  eps0 9.824e-02  rho 1.23055901  rho_nl 1.17314652  pred     11.2  meas     59
    [2] k*d 0.3467  rms|E| 0.4805  eps0 7.540e-02  rho 1.22673817  rho_nl 1.17122479  pred     12.6  meas     61
    [3] k*d 0.4501  rms|E| 0.1040  eps0 7.690e-02  rho 1.14967997  rho_nl 1.16179677  pred     18.4  meas     54
    [4] k*d 0.4275  rms|E| 0.2825  eps0 1.541e-01  rho 1.19169358  rho_nl 1.16791124  pred     10.7  meas     58

  CFL 0.70   handover after 57 exact steps   (5 probe states)
    [0] k*d 0.4067  rms|E| 0.0820  eps0 5.232e-02  rho 1.14185729  rho_nl 1.14945824  pred     22.2  meas     61
    [1] k*d 0.3244  rms|E| 0.5683  eps0 9.812e-02  rho 1.18821075  rho_nl 1.14073342  pred     13.5  meas     72
    [2] k*d 0.3480  rms|E| 0.4848  eps0 7.538e-02  rho 1.18203573  rho_nl 1.13801970  pred     15.5  meas     74
    [3] k*d 0.4386  rms|E| 0.0940  eps0 8.167e-02  rho 1.14973967  rho_nl 1.13160537  pred     18.0  meas     66
    [4] k*d 0.4268  rms|E| 0.2880  eps0 1.537e-01  rho 1.15327417  rho_nl 1.13634848  pred     13.1  meas     71

  CFL 0.60   handover after 66 exact steps   (5 probe states)
    [0] k*d 0.3993  rms|E| 0.0902  eps0 5.176e-02  rho 1.12763748  rho_nl 1.12739234  pred     24.7  meas     72
    [1] k*d 0.3209  rms|E| 0.5633  eps0 9.840e-02  rho 1.16370642  rho_nl 1.11627950  pred     15.3  meas     85
    [2] k*d 0.3514  rms|E| 0.4954  eps0 7.528e-02  rho 1.15140710  rho_nl 1.11631061  pred     18.3  meas     87
    [3] k*d 0.4056  rms|E| 0.0824  eps0 8.879e-02  rho 1.16970182  rho_nl 1.11098196  pred     15.4  meas     77
    [4] k*d 0.4266  rms|E| 0.3044  eps0 1.530e-01  rho 1.11983196  rho_nl 1.11557236  pred     16.6  meas     83

  CFL 0.30   handover after 132 exact steps   (5 probe states)
    [0] k*d 0.3945  rms|E| 0.0952  eps0 5.393e-02  rho 1.04525802  rho_nl 1.06208515  pred     66.0  meas    146
    [1] k*d 0.3195  rms|E| 0.5601  eps0 9.878e-02  rho 1.07205779  rho_nl 1.05632387  pred     33.3  meas    171
    [2] k*d 0.3529  rms|E| 0.4995  eps0 7.519e-02  rho 1.06697996  rho_nl 1.05670596  pred     39.9  meas    175
    [3] k*d 0.3985  rms|E| 0.0839  eps0 8.904e-02  rho 1.06985188  rho_nl 1.05382559  pred     35.8  meas    154
    [4] k*d 0.4270  rms|E| 0.3127  eps0 1.528e-01  rho 1.04245063  rho_nl 1.05643891  pred     45.2  meas    168

  can a smaller time step rescue it?  (mean over probe states)
    CFL 0.99   rho = 1.24790865  (spread 5.65e-02 over 5 states)   UNSTABLE
    CFL 0.85   rho = 1.19552549  (spread 8.09e-02 over 5 states)   UNSTABLE
    CFL 0.70   rho = 1.16302352  (spread 4.64e-02 over 5 states)   UNSTABLE
    CFL 0.60   rho = 1.14645695  (spread 4.99e-02 over 5 states)   UNSTABLE
    CFL 0.30   rho = 1.05931966  (spread 2.96e-02 over 5 states)   UNSTABLE

saved spectral_dco_L3d.json
```

</details>

## #7　2026-09-10T21:06:10　OK

**rerun EXP2 with train_n recorded, for claim C9**

```
py -3.11 test_dco.py --ckpt dco_paper32.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
```

- 耗时 10s ｜ commit `755f536` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = ['4.738e-03', '4.821e-03', '2.875e-03', '5.687e-03', '6.266e-03']`　`blowup_step = 158`　`exp2_relL2 = ['2.751e-02', '3.045e-02', '2.316e-02', '3.019e-02', '2.917e-02']`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `test_results.npz` | 1,156 KB | `dc6912655419b4b1` |
| `test_results_dco_paper32.npz` | 1,156 KB | `dc6912655419b4b1` |
| `exp3_waveform.npz` | 13 KB | `3e5e8b66b0a2d52c` |

<details><summary>输出末尾</summary>

```
[test_dco.py  version 2026-09-09g]
  trunk coord encoding: cellsize   input scaling: rms   training target: analytic   test dirs: shared   head: direct
loaded dco_paper32.pt: L=4 base=32 trained at 32^3, 9.25M params

[EXP 1] single-shot curl on 20 unseen 32^3 plane-wave samples, dirs=shared
  relative L2 over 20 samples:  mean 2.272e-02   median 2.245e-02   worst 3.358e-02   [target = analytic]
    vs analytic curl 2.272e-02   vs Yee curl 1.567e-02   (the two targets differ by ~8e-3)
  nMAE (MAE/max, the paper's metric) mean 4.427e-03   <- THIS is what compares to paper Table I / III-D

[EXP 2] dimension invariance -- net was trained at 32^3 only
          32^3   relative L2 = 2.751e-02   nMAE = 4.738e-03
          48^3   relative L2 = 3.045e-02   nMAE = 4.821e-03
          64^3   relative L2 = 2.316e-02   nMAE = 2.875e-03
      64x96x16   relative L2 = 3.019e-02   nMAE = 5.687e-03
      32x64x16   relative L2 = 2.917e-02   nMAE = 6.266e-03

  paper III-D (32^3-trained): 64^3 4.1e-3, 64x96x16 3.8e-3, 32x64x16 4.7e-3
  COMPARE THOSE TO THE nMAE COLUMN, NOT THE relative L2 COLUMN.
  On THIS checkpoint's data relative L2 runs 4.7-8.1x larger than nMAE  (ratio measured now, not hard-coded).
  The paper reports MAE/max throughout -- that is the only reading under
  which its own Table I and section III-D agree.  So comparing the wrong
  column is not a small error: it flips the sign of the conclusion.  (This
  script printed only relative L2 next to those numbers until 2026-09-10,
  and the gap it seemed to show was an artefact of that.)

[EXP 3] DCO-in-the-loop cavity  22.4 mm / 32 cells -> dx = 0.700 mm   source=diff
  warm-up 300 FDTD steps done, |Ez|max = 2.116e-02
  handover state: k_eff*d = 0.4135   (training band 0.152 .. 0.491, clean TE101 mode 0.167)
  [3a] open loop -- DCO vs Yee curl on the warmed-up cavity field:
        cavity field, all 3 components relL2 7.125e-02   nMAE 7.419e-03   eq5 1.65e+12
  [3b] blew up at step 158 -- stopping early
  400 DCO-driven steps in 3.1s (8 ms/step)
  curl relL2 per step: first 6.451e-02  median 9.716e-01  last 9.788e-01
  Ez waveform error vs FDTD: mean 1.708e+02  max 3.675e+03
    exceeds    1% of peak at step 8
    exceeds    5% of peak at step 34
    exceeds   20% of peak at step 51
  saved exp3_waveform.npz  (plot rec_ref vs rec_dut for the slide)

saved test_results_dco_paper32.npz  ->  now run:  py -3.11 make_figs.py
```

</details>

## #8　2026-09-10T22:34:11　OK

**refresh all figures after run_meal**

```
py -3.11 make_figs.py
```

- 耗时 2s ｜ commit `7f04c0f` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
writing into figs/ ...
  fig1_cavity_spectrum.png
  fig2_training.png
  fig3_curl_slices.png
  [error] fig4: ValueError: x and y must have same first dimension, but have shapes (3,) and (5,)
  fig5_dco_in_loop.png
  fig6_gap.png
  fig8_rollout.png
  [error] fig11: KeyError: np.float64(0.3)
done.
```

</details>

## #9　2026-09-10T23:20:41　OK

**refresh figures, fig4 and fig11 fixed**

```
py -3.11 make_figs.py
```

- 耗时 4s ｜ commit `8f75af2` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/fig11_spectral.png` | 396 KB | `a7ceb2a43354ee20` |
| `figs/fig2_training.png` | 343 KB | `7e6058bdd27c5058` |
| `figs/fig4_dimension.png` | 177 KB | `187a27d4e5b06808` |
| `figs/fig6_gap.png` | 170 KB | `2128b0958b2dd6bc` |
| `figs/fig1_cavity_spectrum.png` | 160 KB | `4887ab722d8fcc9a` |
| `figs/fig8_rollout.png` | 130 KB | `8ed318f66fad4486` |
| `figs/fig3_curl_slices.png` | 100 KB | `6df378efddfb6283` |
| `figs/fig5_dco_in_loop.png` | 68 KB | `b795cb2eef397c21` |

<details><summary>输出末尾</summary>

```
writing into figs/ ...
  fig1_cavity_spectrum.png
  fig2_training.png
  fig3_curl_slices.png
  fig4_dimension.png
  fig5_dco_in_loop.png
  fig6_gap.png
  fig8_rollout.png
  fig11_spectral.png   (192 rows from 17 checkpoints)
done.
```

</details>

## #10　2026-09-10T23:23:32　OK

**structured operator: separable vs anisotropic vs adjoint-pair**

```
py -3.11 structured_scale.py --steps 300 --batch 24 --radius 2 --poly 4 --pair 1
```

- 耗时 168s ｜ commit `8f75af2` (claude/neural-operator-paper-study-3n1dv1) ⚠ **工作区有未提交改动**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
  Sep3D -- the 12-parameter separable version (structured3d.py)
    step  100   train relL2 3.3260e-02   val 3.5145e-02
    step  200   train relL2 3.1941e-02   val 3.3766e-02
    step  300   train relL2 3.1134e-02   val 3.2917e-02

  AdjPair r=1 -- curl_E'=T curl_E and curl_H'=curl_H T^T, T mixes components
    step  100   train relL2 9.4632e-03   val 2.0108e-02
    step  200   train relL2 9.0793e-03   val 1.9254e-02
    step  300   train relL2 9.0497e-03   val 1.9111e-02
    sandwich check: asym 1.2e-16  |Im| 3.1e-15  lam_min -5.3e-15  ->  symmetric PSD, rho<=1 guaranteed

  PolyM J=4 -- S = P(M)^2, matrix-valued, 5 parameters
    step  100   train relL2 3.7173e-02   val 3.9492e-02
    step  200   train relL2 3.6703e-02   val 3.9107e-02
    step  300   train relL2 3.6321e-02   val 3.8830e-02

  Auto3D r=2 -- S = t (*) t, 125 parameters
    step  100   train relL2 2.6559e-02   val 3.5999e-02
    step  200   train relL2 2.6250e-02   val 3.5912e-02
    step  300   train relL2 2.6147e-02   val 3.5879e-02

==================================================================================
  operator                 params      train        val  val/Yee             rho
  --------------------------------------------------------------------------------
  plain Yee                     0  1.116e-01  1.116e-01    1.00x       1 (exact)
  Sep3D (separable, 12p)       12  3.113e-02  3.292e-02    3.39x   (same family)
  AdjPair r=1 (pair)          243  9.050e-03  1.911e-02    5.84x  1.000000000000
  PolyM J=4 (matrix)            5  3.632e-02  3.883e-02    2.87x  1.000000000000
  Auto3D r=2                  125  2.615e-02  3.588e-02    3.11x  1.000000000000
==================================================================================

  success criteria, fixed before the run:
    rho <= 1+1e-9   MET
    >=2x over Yee   MET  (best AdjPair r=1 (pair), 5.84x)
    beats Sep3D     MET  (1.72x on validation)

  how much is anisotropy worth?  Compare TRAINING error, which
  bounds the family from below -- more data can only raise it:
    Sep3D (separable)        3.113e-02
    AdjPair r=1 (pair)       9.050e-03   = 3.44x
```

</details>

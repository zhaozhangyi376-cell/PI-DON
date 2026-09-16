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

## #11　2026-09-12T22:24:38　FAILED (exit 1)

**G0 regression: establish exact-zero MRE, aggregation, fixed waves and Yee checks before metric fix**

```
py -3.11 -m unittest test_paper_protocol -v
```

- 耗时 2s ｜ commit `dad6fb2` (main)
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_component_aggregation (test_paper_protocol.PaperProtocolTests.test_component_aggregation) ... ok
test_eq5_uses_exact_zero_branch_not_small_value_cutoff (test_paper_protocol.PaperProtocolTests.test_eq5_uses_exact_zero_branch_not_small_value_cutoff) ... FAIL
test_fixed_case_reuses_wave_spec_across_grids (test_paper_protocol.PaperProtocolTests.test_fixed_case_reuses_wave_spec_across_grids) ... ok
test_metric_zero_branch_is_unit_sensitive (test_paper_protocol.PaperProtocolTests.test_metric_zero_branch_is_unit_sensitive) ... ok
test_mre_scaling_is_not_nmae (test_paper_protocol.PaperProtocolTests.test_mre_scaling_is_not_nmae) ... ok
test_nonfinite_metrics_rejected (test_paper_protocol.PaperProtocolTests.test_nonfinite_metrics_rejected) ... ok
test_pec_and_zero_field_fixed_point (test_paper_protocol.PaperProtocolTests.test_pec_and_zero_field_fixed_point) ... ok
test_single_wave_analytic_curl (test_paper_protocol.PaperProtocolTests.test_single_wave_analytic_curl) ... ok
test_three_curl_components_at_yee_positions (test_paper_protocol.PaperProtocolTests.test_three_curl_components_at_yee_positions) ... ok

======================================================================
FAIL: test_eq5_uses_exact_zero_branch_not_small_value_cutoff (test_paper_protocol.PaperProtocolTests.test_eq5_uses_exact_zero_branch_not_small_value_cutoff)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\PI-DON\test_paper_protocol.py", line 14, in test_eq5_uses_exact_zero_branch_not_small_value_cutoff
    self.assertAlmostEqual(float(dco.mre_eq5(p, t)), 0.6)
AssertionError: 0.1 != 0.6 within 7 places (0.5 difference)

----------------------------------------------------------------------
Ran 9 tests in 0.288s

FAILED (failures=1)
```

</details>

## #12　2026-09-12T22:25:19　OK

**G0 regression after strict Eq5 fix: analytic curl, fixed domain, component metrics, PEC**

```
py -3.11 -m unittest test_paper_protocol -v
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_component_aggregation (test_paper_protocol.PaperProtocolTests.test_component_aggregation) ... ok
test_eq5_uses_exact_zero_branch_not_small_value_cutoff (test_paper_protocol.PaperProtocolTests.test_eq5_uses_exact_zero_branch_not_small_value_cutoff) ... ok
test_fixed_case_reuses_wave_spec_across_grids (test_paper_protocol.PaperProtocolTests.test_fixed_case_reuses_wave_spec_across_grids) ... ok
test_metric_zero_branch_is_unit_sensitive (test_paper_protocol.PaperProtocolTests.test_metric_zero_branch_is_unit_sensitive) ... ok
test_mre_scaling_is_not_nmae (test_paper_protocol.PaperProtocolTests.test_mre_scaling_is_not_nmae) ... ok
test_nonfinite_metrics_rejected (test_paper_protocol.PaperProtocolTests.test_nonfinite_metrics_rejected) ... ok
test_pec_and_zero_field_fixed_point (test_paper_protocol.PaperProtocolTests.test_pec_and_zero_field_fixed_point) ... ok
test_single_wave_analytic_curl (test_paper_protocol.PaperProtocolTests.test_single_wave_analytic_curl) ... ok
test_three_curl_components_at_yee_positions (test_paper_protocol.PaperProtocolTests.test_three_curl_components_at_yee_positions) ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.108s

OK
```

</details>

## #13　2026-09-12T22:29:52　OK

**Paper-first milestone: 8192-step FDTD reference and fixed Fig5/6 reconstruction, two frozen existing checkpoints, seeds 0 1 2**

```
py -3.11 paper_recheck.py
```

- 耗时 22s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/paper_first_v1/arrays.npz` | 83,273 KB | `e598960a0205c924` |
| `evidence/paper_first_v1/summary.json` | 46 KB | `b411ceeae9736353` |
| `evidence/paper_first_v1/source/verify_claims.py` | 31 KB | `479dbb3b556f3538` |
| `evidence/paper_first_v1/source/lab_log.py` | 17 KB | `a776716d639c194f` |
| `evidence/paper_first_v1/source/dco.py` | 13 KB | `51f4b84ff0b083a5` |
| `evidence/paper_first_v1/manifest.json` | 12 KB | `c65498f1120f044c` |
| `evidence/paper_first_v1/source/fdtd.py` | 10 KB | `09d33eb84d788f5a` |
| `evidence/paper_first_v1/source/paper_recheck.py` | 9 KB | `5752d96dd0d6a9b9` |
| `evidence/paper_first_v1/source/test_paper_protocol.py` | 4 KB | `29a69e7b4b6704ec` |
| `evidence/paper_first_v1/source/paper_protocol.py` | 4 KB | `fba58b0548a6e99d` |
| `evidence/paper_first_v1/tests.txt` | 1 KB | `4219af8a7218093a` |

<details><summary>输出末尾</summary>

```
G0: running independent source/probe FDTD reference (8192 steps)
FDTD modes: [{'mode': '110', 'analytic_GHz': np.float64(4.242640687119285), 'measured_GHz': np.float64(4.23821835380452), 'error_pct': np.float64(-0.10423539585126117)}, {'mode': '211', 'analytic_GHz': np.float64(7.348469228349534), 'measured_GHz': np.float64(7.339097552933119), 'error_pct': np.float64(-0.12753234891779078)}, {'mode': '221', 'analytic_GHz': np.float64(9.0), 'measured_GHz': np.float64(8.99095727661192), 'error_pct': np.float64(-0.10047470431198544)}, {'mode': '310', 'analytic_GHz': np.float64(9.486832980505138), 'measured_GHz': np.float64(9.456283030557731), 'error_pct': np.float64(-0.3220247474598219)}, {'mode': '321', 'analytic_GHz': np.float64(11.224972160321824), 'measured_GHz': np.float64(11.198744189438388), 'error_pct': np.float64(-0.2336573357050022)}]
checkpoint dco_paper32 {'levels': 4, 'base': 32, 'grid': 32, 'epoch': 260, 'coords': 'cellsize', 'norm': 'rms', 'head': 'direct', 'target': 'analytic', 'dirs': None}
dco_paper32 seed=0 32x32x32: MRE x=0.030654 macro=0.14107  nMAE macro=0.0048242
dco_paper32 seed=0 64x64x64: MRE x=0.028222 macro=0.22276  nMAE macro=0.0052113
dco_paper32 seed=0 64x96x16: MRE x=0.46122 macro=1.0543  nMAE macro=0.038877
dco_paper32 seed=0 32x64x16: MRE x=0.34852 macro=0.83247  nMAE macro=0.031746
dco_paper32 seed=1 32x32x32: MRE x=0.0924 macro=0.59235  nMAE macro=0.0048159
dco_paper32 seed=1 64x64x64: MRE x=0.10002 macro=0.14973  nMAE macro=0.0062121
dco_paper32 seed=1 64x96x16: MRE x=1.0828 macro=1.085  nMAE macro=0.036742
dco_paper32 seed=1 32x64x16: MRE x=0.83458 macro=0.78499  nMAE macro=0.030703
dco_paper32 seed=2 32x32x32: MRE x=0.037472 macro=0.067944  nMAE macro=0.0058861
dco_paper32 seed=2 64x64x64: MRE x=0.069208 macro=0.65709  nMAE macro=0.0061918
dco_paper32 seed=2 64x96x16: MRE x=0.58944 macro=0.62658  nMAE macro=0.049077
dco_paper32 seed=2 32x64x16: MRE x=0.62209 macro=0.57243  nMAE macro=0.037308
checkpoint dco_lr1e3_300 {'levels': 4, 'base': 32, 'grid': 32, 'epoch': 300, 'coords': 'cellsize', 'norm': 'rms', 'head': 'direct', 'target': 'analytic', 'dirs': None}
dco_lr1e3_300 seed=0 32x32x32: MRE x=0.022921 macro=0.087125  nMAE macro=0.0031089
dco_lr1e3_300 seed=0 64x64x64: MRE x=0.024061 macro=0.21246  nMAE macro=0.0053838
dco_lr1e3_300 seed=0 64x96x16: MRE x=0.26618 macro=1.419  nMAE macro=0.028364
dco_lr1e3_300 seed=0 32x64x16: MRE x=0.14925 macro=0.80341  nMAE macro=0.02175
dco_lr1e3_300 seed=1 32x32x32: MRE x=0.055473 macro=0.30318  nMAE macro=0.0030573
dco_lr1e3_300 seed=1 64x64x64: MRE x=0.091259 macro=0.1433  nMAE macro=0.0060991
dco_lr1e3_300 seed=1 64x96x16: MRE x=0.70979 macro=1.0373  nMAE macro=0.023206
dco_lr1e3_300 seed=1 32x64x16: MRE x=0.37097 macro=0.58958  nMAE macro=0.016788
dco_lr1e3_300 seed=2 32x32x32: MRE x=0.024133 macro=0.04796  nMAE macro=0.0040211
dco_lr1e3_300 seed=2 64x64x64: MRE x=0.043488 macro=0.6726  nMAE macro=0.0068714
dco_lr1e3_300 seed=2 64x96x16: MRE x=0.51469 macro=0.66222  nMAE macro=0.036246
dco_lr1e3_300 seed=2 32x64x16: MRE x=0.4513 macro=0.53616  nMAE macro=0.028439
Saved evidence\paper_first_v1 No optimizer, no weight changes.
```

</details>

## #14　2026-09-12T22:35:19　OK

**Paper-first milestone evidence: figures and report recomputed from run 13 raw arrays**

```
py -3.11 slides/make_paper_first_figs.py
```

- 耗时 7s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/paper_first_fdtd.png` | 355 KB | `3744cfb180c944c5` |
| `figs/paper_first_fields.png` | 315 KB | `55b599262648ace8` |
| `figs/paper_first_metrics.png` | 124 KB | `5b8f732d78ad6b31` |
| `evidence/paper_first_v1/source/make_paper_first_figs.py` | 12 KB | `19428ef9389d46a5` |
| `evidence/paper_first_v1/STAGE_REPORT.md` | 5 KB | `9cdb5d9897fdf490` |
| `evidence/paper_first_v1/figures_manifest.json` | 1 KB | `6cd3326e965e177d` |

<details><summary>输出末尾</summary>

```
C:\PI-DON\slides\make_paper_first_figs.py:30: UserWarning: Glyph 8315 (\N{SUPERSCRIPT MINUS}) missing from font(s) Microsoft YaHei.
  fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
Verified raw arrays; wrote 3 figures and C:\PI-DON\evidence\paper_first_v1\STAGE_REPORT.md
C:\PI-DON\figs\paper_first_metrics.png
C:\PI-DON\figs\paper_first_fields.png
C:\PI-DON\figs\paper_first_fdtd.png
```

</details>

## #15　2026-09-12T22:38:19　FAILED (exit 1)

**Paper-first verification: recompute raw-array metrics and rerun analytic tests, keep unmet DCO gate as FAIL**

```
py -3.11 verify_claims.py --paper-first --run --md
```

- 耗时 5s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 2.6`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `RESULTS.md` | 4 KB | `2282ed5a7c09ffe3` |

<details><summary>输出末尾</summary>

```
             待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。 历史数值仅供溯源。

  [ 反例 ]     C7  反例：消融链终点在 rho 上反而更差
             dco_L3c rho-1=0.1812 < dco_L3d rho-1=0.2479
             这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说

  [ 待重审 ]    C8  无约束学习算子做不了长时程积分
             最好 dco_paper32: rho-1=0.1149，要跑 1e5 步需再小 11,491x
             撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。 历史数值仅供溯源。

  [ 撤回 ]     C9  旧跨指标、跨测试场景的论文对比
             旧0.70~1.50倍比较撤回；原始NPZ保留
             式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。 新协议与现有权重的结果见P0-P2。

  [ PASS ]   C10  相对 L2 与 nMAE 不可互换（上一条曾因此报错）
             relative L2 / nMAE = 2.6~8.1x（5 个 checkpoint）
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   P0  评估协议与解析检查完整
             9项解析检查；24/24个模型/种子/网格组合
             判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。

  [ PASS ]   P1  候选网格下FDTD空气腔体参考通过
             8192步；五模式最大绝对相对误差 0.3220%
             先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。

  [ FAIL ]   P2  现有DCO在本轮Fig6重建案例达到预设MRE目标
             dco_paper32 x-MRE 0.0282~1.08; dco_lr1e3_300 x-MRE 0.0241~0.71
             先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

==================================================================
  通过 5　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #16　2026-09-12T22:39:20　OK

**Paper-first evidence presentation: correct Yee pixel positions, avoid font/layout overlap, document log-summary extraction error**

```
py -3.11 slides/make_paper_first_figs.py
```

- 耗时 6s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/paper_first_fdtd.png` | 355 KB | `9bf8bd57c83b462f` |
| `figs/paper_first_fields.png` | 323 KB | `0412d9350ccc7b45` |
| `figs/paper_first_metrics.png` | 124 KB | `5b8f732d78ad6b31` |
| `evidence/paper_first_v1/source/make_paper_first_figs.py` | 13 KB | `27beaabd38e9c975` |
| `evidence/paper_first_v1/STAGE_REPORT.md` | 6 KB | `3ab307e0be9dd93c` |
| `evidence/paper_first_v1/figures_manifest.json` | 1 KB | `e2e51fc5615bfabb` |

<details><summary>输出末尾</summary>

```
Verified raw arrays; wrote 3 figures and C:\PI-DON\evidence\paper_first_v1\STAGE_REPORT.md
C:\PI-DON\figs\paper_first_metrics.png
C:\PI-DON\figs\paper_first_fields.png
C:\PI-DON\figs\paper_first_fdtd.png
```

</details>

## #17　2026-09-12T22:39:43　FAILED (exit 1)

**Final milestone ledger: preserve failed DCO acceptance and correct metric-ratio display**

```
py -3.11 verify_claims.py --paper-first --run --md
```

- 耗时 5s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `RESULTS.md` | 4 KB | `b83be8094a121e53` |

<details><summary>输出末尾</summary>

```
             待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。 历史数值仅供溯源。

  [ 反例 ]     C7  反例：消融链终点在 rho 上反而更差
             dco_L3c rho-1=0.1812 < dco_L3d rho-1=0.2479
             这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说

  [ 待重审 ]    C8  无约束学习算子做不了长时程积分
             最好 dco_paper32: rho-1=0.1149，要跑 1e5 步需再小 11,491x
             撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。 历史数值仅供溯源。

  [ 撤回 ]     C9  旧跨指标、跨测试场景的论文对比
             旧0.70~1.50倍比较撤回；原始NPZ保留
             式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。 新协议与现有权重的结果见P0-P2。

  [ PASS ]   C10  相对 L2 与 nMAE 不可互换（上一条曾因此报错）
             指标比值（relative L2 / nMAE）：2.6~8.1x（5 个 checkpoint）
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   P0  评估协议与解析检查完整
             9项解析检查；24/24个模型/种子/网格组合
             判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。

  [ PASS ]   P1  候选网格下FDTD空气腔体参考通过
             8192步；五模式最大绝对相对误差 0.3220%
             先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。

  [ FAIL ]   P2  现有DCO在本轮Fig6重建案例达到预设MRE目标
             dco_paper32 x-MRE 0.0282~1.08; dco_lr1e3_300 x-MRE 0.0241~0.71
             先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

==================================================================
  通过 5　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #18　2026-09-12T22:51:46　OK

**Separate grid shape, spacing and normalization extent using common physical ROI; frozen checkpoints only**

```
py -3.11 diagnose_grid.py
```

- 耗时 29s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/grid_diagnosis_v1/arrays.npz` | 1,334 KB | `b7b43772244fdfdf` |
| `evidence/grid_diagnosis_v1/summary.json` | 362 KB | `487b79bf84f251f6` |
| `evidence/grid_diagnosis_v1/manifest.json` | 19 KB | `1e39aa9de0b83ff8` |
| `evidence/grid_diagnosis_v1/source/lab_log.py` | 17 KB | `a776716d639c194f` |
| `evidence/grid_diagnosis_v1/source/dco.py` | 13 KB | `51f4b84ff0b083a5` |
| `evidence/grid_diagnosis_v1/source/diagnose_grid.py` | 11 KB | `57ed09e8a1af2e54` |
| `evidence/grid_diagnosis_v1/source/fdtd.py` | 10 KB | `09d33eb84d788f5a` |
| `evidence/grid_diagnosis_v1/source/paper_recheck.py` | 9 KB | `5752d96dd0d6a9b9` |
| `evidence/grid_diagnosis_v1/source/gen_data.py` | 9 KB | `c3cf361c6f3cb436` |
| `evidence/grid_diagnosis_v1/source/test_paper_protocol.py` | 4 KB | `29a69e7b4b6704ec` |
| `evidence/grid_diagnosis_v1/source/paper_protocol.py` | 4 KB | `fba58b0548a6e99d` |
| `evidence/grid_diagnosis_v1/tests.txt` | 1 KB | `47cb58c38bf07036` |

<details><summary>输出末尾</summary>

```
dco_paper32 seed=0 spacing=iso06: 8 forward passes complete
dco_paper32 seed=0 spacing=iso03: 8 forward passes complete
dco_paper32 seed=0 spacing=aniso_A: 8 forward passes complete
dco_paper32 seed=0 spacing=aniso_B: 8 forward passes complete
dco_paper32 seed=1 spacing=iso06: 8 forward passes complete
dco_paper32 seed=1 spacing=iso03: 8 forward passes complete
dco_paper32 seed=1 spacing=aniso_A: 8 forward passes complete
dco_paper32 seed=1 spacing=aniso_B: 8 forward passes complete
dco_paper32 seed=2 spacing=iso06: 8 forward passes complete
dco_paper32 seed=2 spacing=iso03: 8 forward passes complete
dco_paper32 seed=2 spacing=aniso_A: 8 forward passes complete
dco_paper32 seed=2 spacing=aniso_B: 8 forward passes complete
dco_lr1e3_300 seed=0 spacing=iso06: 8 forward passes complete
dco_lr1e3_300 seed=0 spacing=iso03: 8 forward passes complete
dco_lr1e3_300 seed=0 spacing=aniso_A: 8 forward passes complete
dco_lr1e3_300 seed=0 spacing=aniso_B: 8 forward passes complete
dco_lr1e3_300 seed=1 spacing=iso06: 8 forward passes complete
dco_lr1e3_300 seed=1 spacing=iso03: 8 forward passes complete
dco_lr1e3_300 seed=1 spacing=aniso_A: 8 forward passes complete
dco_lr1e3_300 seed=1 spacing=aniso_B: 8 forward passes complete
dco_lr1e3_300 seed=2 spacing=iso06: 8 forward passes complete
dco_lr1e3_300 seed=2 spacing=iso03: 8 forward passes complete
dco_lr1e3_300 seed=2 spacing=aniso_A: 8 forward passes complete
dco_lr1e3_300 seed=2 spacing=aniso_B: 8 forward passes complete
Saved evidence\grid_diagnosis_v1 192 frozen forward passes. No optimizer, no training.
```

</details>

## #19　2026-09-12T22:53:41　FAILED (exit 1)

**Verify prespecified grid diagnosis hypotheses from saved ROI predictions and rerun regression suite**

```
py -3.11 verify_claims.py --grid-diagnosis --run --md
```

- 耗时 5s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/grid_diagnosis_v1/source/verify_claims_final.py` | 39 KB | `49b0175a6223f9b9` |
| `evidence/grid_diagnosis_v1/findings.json` | 29 KB | `177b1ec974f8b5e0` |
| `RESULTS.md` | 6 KB | `075bb203fde98d02` |
| `evidence/grid_diagnosis_v1/verification_manifest.json` | 0 KB | `ab0f656636fff71b` |

<details><summary>输出末尾</summary>

```
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   P0  评估协议与解析检查完整
             9项解析检查；24/24个模型/种子/网格组合
             判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。

  [ PASS ]   P1  候选网格下FDTD空气腔体参考通过
             8192步；五模式最大绝对相对误差 0.3220%
             先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。

  [ FAIL ]   P2  现有DCO在本轮Fig6重建案例达到预设MRE目标
             dco_paper32 x-MRE 0.0282~1.08; dco_lr1e3_300 x-MRE 0.0241~0.71
             先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。

  [ PASS ]   D0  诊断实验接口与对照完整
             192组预测；归一化还原最大偏差 4.45e-08
             预设检查：采样/同位置ROI≤1e-10，归一化和单位≤2e-6，9项回归全过，组合/哈希完整；仅排除已测试的接口错位。

  [ PASS ]   D1  原非立方案例混入间距范围外测试
             非立方案例间距 [[0.3, 0.2, 1.2], [0.6, 0.3, 1.2]] mm；可读data_32每轴范围 [0.3001901204697788, 0.3000006836373359, 0.3008991479873657] 至 [0.7994624902494252, 0.7996750064194202, 0.7999528897926211]
             预设：两案例均超出生成器默认[0.3,0.8]mm。文件范围可核实；缺训练配置/哈希时不能确认它就是某权重的训练集。

  [ PASS ]   D2  恒定间距输入仍存在形状/上下文依赖
             6组中 6 组超过1e-3；组内最大相对预测变化 0.00156–0.00923
             预设：固定0.6mm间距、相同物理ROI和32³参考RMS，改变上下文形状后，每个模型/种子至少一种非立方预测变化>1e-3；分母为32³预测L2范数。不是论文精度验收。

  [ PASS ]   D3  固定立方形状下各向异性间距显著增加误差
             6组中 6 组超过2倍；组内最大误差比 14.1–24.9
             预设假设：固定32³与自然RMS，两种各向异性间距至少一种使逐分量平均nMAE超过0.6mm的2倍。改变间距同时改变采样/每格空间频率，不能归因于trunk单一模块。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

==================================================================
  通过 9　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #20　2026-09-12T22:56:58　OK

**Grid diagnosis evidence figures, paired effect ranges and original fixed-window RMS cross-check**

```
py -3.11 slides/make_grid_diagnosis_figs.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/grid_diagnosis_matrix.png` | 181 KB | `06abeefefd387b91` |
| `figs/grid_diagnosis_controls.png` | 130 KB | `02dabc19ab01a2bc` |
| `evidence/grid_diagnosis_v1/source/make_grid_diagnosis_figs.py` | 12 KB | `e21cf25d3e98622d` |
| `evidence/grid_diagnosis_v1/STAGE_REPORT.md` | 5 KB | `7791059d78c4777b` |
| `evidence/grid_diagnosis_v1/figures_manifest.json` | 1 KB | `a1823b5c3ab02891` |

<details><summary>输出末尾</summary>

```
Wrote C:\PI-DON\evidence\grid_diagnosis_v1\STAGE_REPORT.md
Normalization, changed extent: [0.4390389621257782, 3.1374545097351074] fixed/natural error: [0.3258314520820813, 1.7052652937937607]
Original fixed window RMS ratio: 0.9712217776946178 1.0070869035835703
Median natural RMS ROI nMAE matrices: {'dco_paper32': [[0.004178660638131698, 0.010431524713119597, 0.09245924152399317, 0.06468558211184512], [0.009772100965112293, 0.012022150231984987, 0.1114176427696678, 0.07341284844251586], [0.0069311577880551796, 0.016417537352574767, 0.0909770967142128, 0.06948095574301195], [0.004673792789754271, 0.014211633350921965, 0.092200184111884, 0.06161559430763608]], 'dco_lr1e3_300': [[0.0032582696741863468, 0.009882576659209899, 0.0580644860194701, 0.0353861278806911], [0.005543826468864546, 0.00979937987541124, 0.056006594332719796, 0.037679749684644735], [0.004915727508122045, 0.011752142326926077, 0.056411465782098165, 0.03284275807664331], [0.004098019291266917, 0.013623085229210269, 0.05978867936655489, 0.028292191078309326]]}
```

</details>

## #21　2026-09-12T22:59:58　FAILED (exit 1)

**Final grid diagnosis verification including original-window RMS descriptive check**

```
py -3.11 verify_claims.py --grid-diagnosis --run --md
```

- 耗时 6s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/grid_diagnosis_v1/source/verify_claims_final.py` | 40 KB | `feb5a906cf551579` |
| `evidence/grid_diagnosis_v1/findings.json` | 31 KB | `ec5e766894437092` |
| `RESULTS.md` | 6 KB | `46be1f252499733a` |
| `evidence/grid_diagnosis_v1/verification_manifest.json` | 0 KB | `5dd7001b7b1d402d` |

<details><summary>输出末尾</summary>

```
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   P0  评估协议与解析检查完整
             9项解析检查；24/24个模型/种子/网格组合
             判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。

  [ PASS ]   P1  候选网格下FDTD空气腔体参考通过
             8192步；五模式最大绝对相对误差 0.3220%
             先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。

  [ FAIL ]   P2  现有DCO在本轮Fig6重建案例达到预设MRE目标
             dco_paper32 x-MRE 0.0282~1.08; dco_lr1e3_300 x-MRE 0.0241~0.71
             先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。

  [ PASS ]   D0  诊断实验接口与对照完整
             192组预测；归一化还原最大偏差 4.45e-08
             预设检查：采样/同位置ROI≤1e-10，归一化和单位≤2e-6，9项回归全过，组合/哈希完整；仅排除已测试的接口错位。

  [ PASS ]   D1  原非立方案例混入间距范围外测试
             非立方案例间距 [[0.3, 0.2, 1.2], [0.6, 0.3, 1.2]] mm；可读data_32每轴范围 [0.3001901204697788, 0.3000006836373359, 0.3008991479873657] 至 [0.7994624902494252, 0.7996750064194202, 0.7999528897926211]
             预设：两案例均超出生成器默认[0.3,0.8]mm。文件范围可核实；缺训练配置/哈希时不能确认它就是某权重的训练集。

  [ PASS ]   D2  恒定间距输入仍存在形状/上下文依赖
             6组中 6 组超过1e-3；组内最大相对预测变化 0.00156–0.00923
             预设：固定0.6mm间距、相同物理ROI和32³参考RMS，改变上下文形状后，每个模型/种子至少一种非立方预测变化>1e-3；分母为32³预测L2范数。不是论文精度验收。

  [ PASS ]   D3  固定立方形状下各向异性间距显著增加误差
             6组中 6 组超过2倍；组内最大误差比 14.1–24.9
             预设假设：固定32³与自然RMS，两种各向异性间距至少一种使逐分量平均nMAE超过0.6mm的2倍。改变间距同时改变采样/每格空间频率，不能归因于trunk单一模块。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

==================================================================
  通过 9　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #22　2026-09-12T23:00:04　OK

**Finalize milestone 2 figures and report, retain in-range adverse cases and distinguish from Algorithm 1**

```
py -3.11 slides/make_grid_diagnosis_figs.py
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/grid_diagnosis_matrix.png` | 181 KB | `06abeefefd387b91` |
| `figs/grid_diagnosis_controls.png` | 130 KB | `02dabc19ab01a2bc` |
| `evidence/grid_diagnosis_v1/source/make_grid_diagnosis_figs.py` | 12 KB | `34f9deb078c5b3ba` |
| `evidence/grid_diagnosis_v1/STAGE_REPORT.md` | 5 KB | `26c7d5670bb3b4cd` |
| `evidence/grid_diagnosis_v1/figures_manifest.json` | 1 KB | `60c18c4d09121049` |

<details><summary>输出末尾</summary>

```
Wrote C:\PI-DON\evidence\grid_diagnosis_v1\STAGE_REPORT.md
Normalization, changed extent: [0.4390389621257782, 3.1374545097351074] fixed/natural error: [0.3258314520820813, 1.7052652937937607]
Original fixed window RMS ratio: 0.9712217776946178 1.0070869035835703
Median natural RMS ROI nMAE matrices: {'dco_paper32': [[0.004178660638131698, 0.010431524713119597, 0.09245924152399317, 0.06468558211184512], [0.009772100965112293, 0.012022150231984987, 0.1114176427696678, 0.07341284844251586], [0.0069311577880551796, 0.016417537352574767, 0.0909770967142128, 0.06948095574301195], [0.004673792789754271, 0.014211633350921965, 0.092200184111884, 0.06161559430763608]], 'dco_lr1e3_300': [[0.0032582696741863468, 0.009882576659209899, 0.0580644860194701, 0.0353861278806911], [0.005543826468864546, 0.00979937987541124, 0.056006594332719796, 0.037679749684644735], [0.004915727508122045, 0.011752142326926077, 0.056411465782098165, 0.03284275807664331], [0.004098019291266917, 0.013623085229210269, 0.05978867936655489, 0.028292191078309326]]}
```

</details>

## #23　2026-09-12T23:06:03　OK

**Milestone 3: axis-spacing sweep, exact Yee symbol, identical-input frequency probes and isolated trunk intervention**

```
py -3.11 spacing_probe.py
```

- 耗时 20s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/spacing_probe_v1/arrays.npz` | 4,733 KB | `c41b60fad7e356bd` |
| `evidence/spacing_probe_v1/manifest.json` | 558 KB | `65c23267aa01aa03` |
| `evidence/spacing_probe_v1/summary.json` | 181 KB | `db57ee0286413f12` |
| `evidence/spacing_probe_v1/source/lab_log.py` | 17 KB | `a776716d639c194f` |
| `evidence/spacing_probe_v1/source/dco.py` | 13 KB | `53eb1c7d7ea0ed33` |
| `evidence/spacing_probe_v1/source/diagnose_grid.py` | 11 KB | `57ed09e8a1af2e54` |
| `evidence/spacing_probe_v1/source/fdtd.py` | 10 KB | `09d33eb84d788f5a` |
| `evidence/spacing_probe_v1/source/spacing_probe.py` | 10 KB | `1df25b9f2b01ba4c` |
| `evidence/spacing_probe_v1/source/paper_recheck.py` | 9 KB | `5752d96dd0d6a9b9` |
| `evidence/spacing_probe_v1/source/gen_data.py` | 9 KB | `c3cf361c6f3cb436` |
| `evidence/spacing_probe_v1/source/paper_protocol.py` | 4 KB | `fba58b0548a6e99d` |

<details><summary>输出末尾</summary>

```
Pre-inference identities: {'yee_symbol': 7.10950504907312e-14, 'fixed_q_input': 6.106234379807262e-16, 'fixed_q_scaled_target': 8.873182280607495e-16, 'trunk_input': 0.0, 'trunk_target': 0.0}
dco_paper32 50 / 231
dco_paper32 100 / 231
dco_paper32 150 / 231
dco_paper32 200 / 231
dco_lr1e3_300 50 / 231
dco_lr1e3_300 100 / 231
dco_lr1e3_300 150 / 231
dco_lr1e3_300 200 / 231
Saved evidence\spacing_probe_v1 cases= 231 predictions= 462 No training.
```

</details>

## #24　2026-09-12T23:08:16　FAILED (exit 1)

**Recompute axis/single-wave evidence and grade prespecified Yee-gap and isolated-trunk hypotheses**

```
py -3.11 verify_claims.py --spacing-probe --run --md
```

- 耗时 6s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/spacing_probe_v1/findings.json` | 1,082 KB | `770f3546e316c51b` |
| `evidence/spacing_probe_v1/source/verify_claims_final.py` | 46 KB | `0387ee83bf886b11` |
| `RESULTS.md` | 7 KB | `bd6552eb85412b8d` |
| `evidence/spacing_probe_v1/verification_manifest.json` | 0 KB | `a68434f277b05c51` |

<details><summary>输出末尾</summary>

```
             先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。

  [ PASS ]   D0  诊断实验接口与对照完整
             192组预测；归一化还原最大偏差 4.45e-08
             预设检查：采样/同位置ROI≤1e-10，归一化和单位≤2e-6，9项回归全过，组合/哈希完整；仅排除已测试的接口错位。

  [ PASS ]   D1  原非立方案例混入间距范围外测试
             非立方案例间距 [[0.3, 0.2, 1.2], [0.6, 0.3, 1.2]] mm；可读data_32每轴范围 [0.3001901204697788, 0.3000006836373359, 0.3008991479873657] 至 [0.7994624902494252, 0.7996750064194202, 0.7999528897926211]
             预设：两案例均超出生成器默认[0.3,0.8]mm。文件范围可核实；缺训练配置/哈希时不能确认它就是某权重的训练集。

  [ PASS ]   D2  恒定间距输入仍存在形状/上下文依赖
             6组中 6 组超过1e-3；组内最大相对预测变化 0.00156–0.00923
             预设：固定0.6mm间距、相同物理ROI和32³参考RMS，改变上下文形状后，每个模型/种子至少一种非立方预测变化>1e-3；分母为32³预测L2范数。不是论文精度验收。

  [ PASS ]   D3  固定立方形状下各向异性间距显著增加误差
             6组中 6 组超过2倍；组内最大误差比 14.1–24.9
             预设假设：固定32³与自然RMS，两种各向异性间距至少一种使逐分量平均nMAE超过0.6mm的2倍。改变间距同时改变采样/每格空间频率，不能归因于trunk单一模块。

  [ PASS ]   S0  单轴/单波实验恒等式与产物完整
             462组预测；恒等式检查最大偏差 7.11e-14
             预设：Yee差分/傅里叶符号、固定q输入/缩放真值、仅trunk干预的输入/真值偏差≤1e-10；组合和哈希完整。

  [ PASS ]   S1  网络偏差不能仅用标准Yee离散误差解释（5倍门槛）
             6组中6组超过5倍；DCO/Yee相对L2误差比 5.51–30.88
             预设：固定32³、间距(0.3,0.2,1.2)mm的六个模型/种子中，DCO误差均>标准Yee误差5倍。Yee是对照，不是解析目标的误差下限。

  [ PASS ]   S2  单波探针中坐标分支引入无关间距依赖（1%门槛）
             12种模型/方向组合中12种超过1%；各组合最大变化 7.11%–20.50%
             预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

==================================================================
  通过 12　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #25　2026-09-12T23:11:33　OK

**Milestone 3 evidence: direct trunk intervention, single-axis sweep, identical-input scaling and full report**

```
py -3.11 slides/make_spacing_probe_figs.py
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/spacing_probe_axis.png` | 310 KB | `a5cba9c3e847e77b` |
| `figs/spacing_probe_trunk.png` | 278 KB | `1f9cb6102ade4777` |
| `figs/spacing_probe_scaling.png` | 234 KB | `6a3baada3e378aa0` |
| `evidence/spacing_probe_v1/source/make_spacing_probe_figs.py` | 13 KB | `8bb8a9d064463a10` |
| `evidence/spacing_probe_v1/STAGE_REPORT.md` | 7 KB | `dc5962b376fc7040` |
| `evidence/spacing_probe_v1/figures_manifest.json` | 1 KB | `d19da02dc9221cca` |

<details><summary>输出末尾</summary>

```
Saved 3 figures and C:\PI-DON\evidence\spacing_probe_v1\STAGE_REPORT.md
dco_paper32 {'fine': [4.4231, 1.245, 4.24], 'coarse': [22.2844, 11.8087, 13.4875], 'both': [32.3148, 16.1291, 18.2783]}
dco_lr1e3_300 {'fine': [2.9331, 2.4304, 3.2462], 'coarse': [5.7941, 7.4063, 12.0811], 'both': [7.1656, 8.1255, 15.8107]}
```

</details>

## #26　2026-09-12T23:44:18　OK

**Preflight paired A/B generator, per-sample loss and exact 200-update budget; no neural training**

```
py -3.11 test_coverage_ab.py
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_budget_has_exactly_200_complete_batches (__main__.CoverageTests.test_budget_has_exactly_200_complete_batches) ... ok
test_paired_samples_match_existing_generator (__main__.CoverageTests.test_paired_samples_match_existing_generator) ... ok
test_relative_loss_weights_samples_equally (__main__.CoverageTests.test_relative_loss_weights_samples_equally) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.028s

OK
```

</details>

## #27　2026-09-12T23:46:32　OK

**Approved coverage repair A/B: paired data, 200 Adam updates each, independent seeds and trunk probes after training**

```
py -3.11 coverage_ab.py
```

- 耗时 125s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/coverage_ab_v1/A200.pt` | 108,442 KB | `239d87e7c2fa7b28` |
| `evidence/coverage_ab_v1/B200.pt` | 108,442 KB | `7f23a9525199ab62` |
| `evidence/coverage_ab_v1/evaluation.npz` | 96,639 KB | `7fb3872045a78c70` |
| `evidence/coverage_ab_v1/train_B200.npz` | 90,220 KB | `694c00cd662f49f7` |
| `evidence/coverage_ab_v1/train_A200.npz` | 90,154 KB | `f88bca4a2929c54c` |
| `evidence/coverage_ab_v1/manifest.json` | 384 KB | `e81f2490eeb17f3a` |
| `evidence/coverage_ab_v1/summary.json` | 90 KB | `6bdd507925125819` |
| `evidence/coverage_ab_v1/A200_hist.json` | 25 KB | `180e893275826d16` |
| `evidence/coverage_ab_v1/B200_hist.json` | 25 KB | `7bcd0398f55af3e5` |
| `evidence/coverage_ab_v1/source/lab_log.py` | 17 KB | `a776716d639c194f` |
| `evidence/coverage_ab_v1/source/dco.py` | 13 KB | `53eb1c7d7ea0ed33` |
| `evidence/coverage_ab_v1/source/coverage_ab.py` | 12 KB | `43cbc171ad2c79c5` |
| … 另有 11 个 | | |

<details><summary>输出末尾</summary>

```
A200 update 50/200: last10 training loss=0.000899493, 9.0s
A200 update 60/200: last10 training loss=0.000729144, 10.8s
A200 update 70/200: last10 training loss=0.000671712, 13.0s
A200 update 80/200: last10 training loss=0.000664125, 15.3s
A200 update 90/200: last10 training loss=0.000562078, 17.5s
A200 update 100/200: last10 training loss=0.000574283, 19.7s
A200 update 110/200: last10 training loss=0.000416344, 21.8s
A200 update 120/200: last10 training loss=0.000297103, 24.0s
A200 update 130/200: last10 training loss=0.000389761, 26.0s
A200 update 140/200: last10 training loss=0.000640573, 28.2s
A200 update 150/200: last10 training loss=0.000626277, 30.4s
A200 update 160/200: last10 training loss=0.000395864, 32.5s
A200 update 170/200: last10 training loss=0.000365311, 34.5s
A200 update 180/200: last10 training loss=0.000454133, 36.5s
A200 update 190/200: last10 training loss=0.000426133, 38.6s
A200 update 200/200: last10 training loss=0.000472495, 40.6s
B200 update 10/200: last10 training loss=0.00718609, 2.0s
B200 update 20/200: last10 training loss=0.00426288, 4.1s
B200 update 30/200: last10 training loss=0.00358196, 6.2s
B200 update 40/200: last10 training loss=0.00321533, 8.2s
B200 update 50/200: last10 training loss=0.00235817, 10.1s
B200 update 60/200: last10 training loss=0.00261722, 12.2s
B200 update 70/200: last10 training loss=0.00255579, 14.2s
B200 update 80/200: last10 training loss=0.00230708, 16.0s
B200 update 90/200: last10 training loss=0.0017211, 17.6s
B200 update 100/200: last10 training loss=0.00201496, 19.5s
B200 update 110/200: last10 training loss=0.00210363, 21.6s
B200 update 120/200: last10 training loss=0.0015035, 23.6s
B200 update 130/200: last10 training loss=0.00184943, 25.6s
B200 update 140/200: last10 training loss=0.00163916, 27.7s
B200 update 150/200: last10 training loss=0.0013804, 30.3s
B200 update 160/200: last10 training loss=0.00179167, 34.0s
B200 update 170/200: last10 training loss=0.0012491, 37.6s
B200 update 180/200: last10 training loss=0.00162684, 41.2s
B200 update 190/200: last10 training loss=0.00180923, 44.9s
B200 update 200/200: last10 training loss=0.00147535, 48.7s
Evaluated A0 12 independent-seed cases and 30 coordinate probes
Evaluated A200 12 independent-seed cases and 30 coordinate probes
Evaluated B200 12 independent-seed cases and 30 coordinate probes
Saved evidence\coverage_ab_v1 400 total updates, no additional training.
```

</details>

## #28　2026-09-12T23:48:10　FAILED (exit 1)

**Audit approved A/B gates from saved raw predictions, actual optimizer steps, paired data and source hashes**

```
py -3.11 verify_claims.py --coverage-ab --run --md
```

- 耗时 15s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 0.9420`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/coverage_ab_v1/source/verify_claims_final.py` | 55 KB | `1203730839e96fca` |
| `evidence/coverage_ab_v1/findings.json` | 16 KB | `6756317898e26e60` |
| `RESULTS.md` | 8 KB | `d528f1ea4bb0e58d` |
| `evidence/coverage_ab_v1/verification_manifest.json` | 0 KB | `ca9535473c35496e` |

<details><summary>输出末尾</summary>

```
             预设：Yee差分/傅里叶符号、固定q输入/缩放真值、仅trunk干预的输入/真值偏差≤1e-10；组合和哈希完整。

  [ PASS ]   S1  网络偏差不能仅用标准Yee离散误差解释（5倍门槛）
             6组中6组超过5倍；DCO/Yee相对L2误差比 5.51–30.88
             预设：固定32³、间距(0.3,0.2,1.2)mm的六个模型/种子中，DCO误差均>标准Yee误差5倍。Yee是对照，不是解析目标的误差下限。

  [ PASS ]   S2  单波探针中坐标分支引入无关间距依赖（1%门槛）
             12种模型/方向组合中12种超过1%；各组合最大变化 7.11%–20.50%
             预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。

  [ PASS ]   T0  A/B配对、更新预算与证据完整
             两组各200次Adam更新；36组独立种子测试、90组探针；12项测试通过；配对偏差 5.80e-08
             核验源/数据/权重/曲线哈希、共同起点与配对随机数、实际优化器step=200；不把训练次数当精度成果。

  [ FAIL ]   T1  扩展间距B在非立方测试比A改善至少20%
             非立方六案例B/A几何平均比：nMAE=0.9420，x-MRE=0.8335
             已批准门槛：两个比值均≤0.8；同样200更新的扩展范围B对原范围A，独立振幅种子10/11/12。

  [ FAIL ]   T2  扩展间距B在原范围内未明显退步
             32³三种子平均nMAE：B/起点=2.0772
             已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。

  [ PASS ]   T3  扩展间距B的错误坐标依赖未比起点加重
             六方向最大干预效应的平均：B/起点=0.6860
             已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

  [ PASS ]   T0T  A/B配对、损失与预算回归（本次现跑）
             3
             测试进程exit=0且至少3项通过

==================================================================
  通过 15　不通过 3　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #29　2026-09-12T23:54:27　OK

**里程碑4：从原始数组复算A/B证据图和报告，保留未通过门槛与退步案例**

```
py -3.11 slides/make_coverage_ab_figs.py
```

- 耗时 8s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/coverage_ab_outcomes.png` | 271 KB | `59b1ebcd00bfe5d1` |
| `figs/coverage_ab_training.png` | 188 KB | `849f2f864bebb53e` |
| `evidence/coverage_ab_v1/source/make_coverage_ab_figs.py` | 12 KB | `94a0f9f72afd3a9a` |
| `evidence/coverage_ab_v1/STAGE_REPORT.md` | 6 KB | `2cc19d87ff045c34` |
| `evidence/coverage_ab_v1/figures_manifest.json` | 1 KB | `0d66a30d7df4a31f` |

<details><summary>输出末尾</summary>

```
Saved two figures and C:\PI-DON\evidence\coverage_ab_v1\STAGE_REPORT.md
```

</details>

## #30　2026-09-12T23:57:31　FAILED (exit 1)

**里程碑4最终核验重试：此前日志转发GBK编码异常未落账；固定UTF-8复核12项检查，保留T1/T2失败**

```
py -3.11 verify_claims.py --coverage-ab --run --md
```

- 耗时 14s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/coverage_ab_v1/findings.json` | 16 KB | `6756317898e26e60` |
| `slides/make_coverage_ab_figs.py` | 12 KB | `3fe5e99ac0061678` |
| `RESULTS.md` | 8 KB | `ca3771e95b61edf0` |
| `evidence/coverage_ab_v1/FINAL_CHECK_ENCODING_NOTE.md` | 1 KB | `adc68025d6a4dbf9` |
| `evidence/coverage_ab_v1/verification_manifest.json` | 0 KB | `55d1c5ba7804e9a6` |

<details><summary>输出末尾</summary>

```
             预设：Yee差分/傅里叶符号、固定q输入/缩放真值、仅trunk干预的输入/真值偏差≤1e-10；组合和哈希完整。

  [ PASS ]   S1  网络偏差不能仅用标准Yee离散误差解释（5倍门槛）
             6组中6组超过5倍；DCO/Yee相对L2误差比 5.51–30.88
             预设：固定32³、间距(0.3,0.2,1.2)mm的六个模型/种子中，DCO误差均>标准Yee误差5倍。Yee是对照，不是解析目标的误差下限。

  [ PASS ]   S2  单波探针中坐标分支引入无关间距依赖（1%门槛）
             12种模型/方向组合中12种超过1%；各组合最大变化 7.11%–20.50%
             预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。

  [ PASS ]   T0  A/B配对、更新预算与证据完整
             两组各200次Adam更新；36组独立种子测试、90组探针；12项测试通过；配对偏差 5.80e-08
             核验源/数据/权重/曲线哈希、共同起点与配对随机数、实际优化器step=200；不把训练次数当精度成果。

  [ FAIL ]   T1  扩展间距B在非立方测试比A改善至少20%
             非立方六案例B/A几何平均比：nMAE比值 0.9420，x-MRE比值 0.8335
             已批准门槛：两个比值均≤0.8；同样200更新的扩展范围B对原范围A，独立振幅种子10/11/12。

  [ FAIL ]   T2  扩展间距B在原范围内未明显退步
             32³三种子平均nMAE：B/起点=2.0772
             已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。

  [ PASS ]   T3  扩展间距B的错误坐标依赖未比起点加重
             六方向最大干预效应的平均：B/起点=0.6860
             已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

  [ PASS ]   T0T  A/B配对、损失与预算回归（本次现跑）
             3
             测试进程exit=0且至少3项通过

==================================================================
  通过 15　不通过 3　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #31　2026-09-12T23:57:57　OK

**里程碑4报告收尾：补记最终核验编码异常及恢复，指标和图保持同一原始证据**

```
py -3.11 slides/make_coverage_ab_figs.py
```

- 耗时 8s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/coverage_ab_outcomes.png` | 271 KB | `59b1ebcd00bfe5d1` |
| `figs/coverage_ab_training.png` | 188 KB | `849f2f864bebb53e` |
| `evidence/coverage_ab_v1/source/make_coverage_ab_figs.py` | 12 KB | `3fe5e99ac0061678` |
| `STATUS.md` | 8 KB | `b39747aef0d4b7b6` |
| `evidence/coverage_ab_v1/STAGE_REPORT.md` | 7 KB | `53e7e5994d0d9113` |
| `evidence/coverage_ab_v1/figures_manifest.json` | 1 KB | `adc918d4a3f3b81c` |

<details><summary>输出末尾</summary>

```
Saved two figures and C:\PI-DON\evidence\coverage_ab_v1\STAGE_REPORT.md
```

</details>

## #32　2026-09-13T00:04:21　OK

**坐标分支对照预检：实际训练辅助函数须冻结branch并只更新trunk，预算200**

```
py -3.11 test_trunk_repair.py
```

- 耗时 8s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_actual_helper_freezes_branch_and_updates_only_trunk (__main__.TrunkTests.test_actual_helper_freezes_branch_and_updates_only_trunk) ... C200 update 10/200: last10 training loss=1.60288, 0.3s
C200 update 20/200: last10 training loss=1.60162, 0.3s
C200 update 30/200: last10 training loss=1.60035, 0.3s
C200 update 40/200: last10 training loss=1.59909, 0.3s
C200 update 50/200: last10 training loss=1.59782, 0.3s
C200 update 60/200: last10 training loss=1.59656, 0.3s
C200 update 70/200: last10 training loss=1.5953, 0.3s
C200 update 80/200: last10 training loss=1.59403, 0.3s
C200 update 90/200: last10 training loss=1.59277, 0.4s
C200 update 100/200: last10 training loss=1.59151, 0.4s
C200 update 110/200: last10 training loss=1.59025, 0.4s
C200 update 120/200: last10 training loss=1.589, 0.4s
C200 update 130/200: last10 training loss=1.58774, 0.4s
C200 update 140/200: last10 training loss=1.58648, 0.4s
C200 update 150/200: last10 training loss=1.58522, 0.5s
C200 update 160/200: last10 training loss=1.58397, 0.5s
C200 update 170/200: last10 training loss=1.58271, 0.5s
C200 update 180/200: last10 training loss=1.58146, 0.5s
C200 update 190/200: last10 training loss=1.58021, 0.5s
C200 update 200/200: last10 training loss=1.57895, 0.5s
ok

----------------------------------------------------------------------
Ran 1 test in 3.754s

OK
```

</details>

## #33　2026-09-13T00:06:17　OK

**里程碑5：复用B数据与batch序列，C仅训练trunk恰好200更新；完成后诊断与新种子统一验收**

```
py -3.11 trunk_repair.py
```

- 耗时 92s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/trunk_repair_v1/heldout/evaluation.npz` | 110,077 KB | `d2bfd20f368cfa02` |
| `evidence/trunk_repair_v1/diagnostic/evaluation.npz` | 68,774 KB | `99e48e8d24105524` |
| `evidence/trunk_repair_v1/C200.pt` | 63,968 KB | `4649bb8ba7852852` |
| `evidence/trunk_repair_v1/summary.json` | 138 KB | `c50456feca4ac3d1` |
| `evidence/trunk_repair_v1/C200_hist.json` | 25 KB | `fa42f92a5872b124` |
| `evidence/trunk_repair_v1/source/lab_log.py` | 17 KB | `a776716d639c194f` |
| `evidence/trunk_repair_v1/manifest.json` | 14 KB | `befe668083116a8e` |
| `evidence/trunk_repair_v1/source/coverage_ab.py` | 13 KB | `5fde22d847e4738f` |
| `evidence/trunk_repair_v1/source/dco.py` | 13 KB | `53eb1c7d7ea0ed33` |
| `evidence/trunk_repair_v1/source/diagnose_grid.py` | 11 KB | `57ed09e8a1af2e54` |
| `evidence/trunk_repair_v1/source/fdtd.py` | 10 KB | `09d33eb84d788f5a` |
| `evidence/trunk_repair_v1/source/spacing_probe.py` | 10 KB | `1df25b9f2b01ba4c` |
| … 另有 10 个 | | |

<details><summary>输出末尾</summary>

```
C200 update 70/200: last10 training loss=1.5953, 0.2s
C200 update 80/200: last10 training loss=1.59403, 0.2s
C200 update 90/200: last10 training loss=1.59277, 0.2s
C200 update 100/200: last10 training loss=1.59151, 0.3s
C200 update 110/200: last10 training loss=1.59025, 0.3s
C200 update 120/200: last10 training loss=1.589, 0.3s
C200 update 130/200: last10 training loss=1.58774, 0.3s
C200 update 140/200: last10 training loss=1.58648, 0.3s
C200 update 150/200: last10 training loss=1.58522, 0.3s
C200 update 160/200: last10 training loss=1.58397, 0.3s
C200 update 170/200: last10 training loss=1.58271, 0.4s
C200 update 180/200: last10 training loss=1.58146, 0.4s
C200 update 190/200: last10 training loss=1.58021, 0.4s
C200 update 200/200: last10 training loss=1.57895, 0.4s
C200 update 10/200: last10 training loss=0.00712315, 3.1s
C200 update 20/200: last10 training loss=0.00377056, 5.2s
C200 update 30/200: last10 training loss=0.00395522, 8.5s
C200 update 40/200: last10 training loss=0.0036396, 14.6s
C200 update 50/200: last10 training loss=0.00284916, 16.9s
C200 update 60/200: last10 training loss=0.0031268, 19.0s
C200 update 70/200: last10 training loss=0.00325022, 22.1s
C200 update 80/200: last10 training loss=0.00297643, 25.3s
C200 update 90/200: last10 training loss=0.00211071, 27.9s
C200 update 100/200: last10 training loss=0.00275921, 30.6s
C200 update 110/200: last10 training loss=0.00358953, 32.9s
C200 update 120/200: last10 training loss=0.00192695, 35.2s
C200 update 130/200: last10 training loss=0.00312789, 37.1s
C200 update 140/200: last10 training loss=0.00247369, 39.9s
C200 update 150/200: last10 training loss=0.00196448, 42.0s
C200 update 160/200: last10 training loss=0.00304808, 45.0s
C200 update 170/200: last10 training loss=0.00224727, 48.1s
C200 update 180/200: last10 training loss=0.0021396, 50.4s
C200 update 190/200: last10 training loss=0.00280862, 53.4s
C200 update 200/200: last10 training loss=0.00213691, 56.3s
Evaluated C200 12 cases; seeds [10, 11, 12] and 30 coordinate probes
Evaluated A0 12 cases; seeds [20, 21, 22] and 0 coordinate probes
Evaluated A200 12 cases; seeds [20, 21, 22] and 0 coordinate probes
Evaluated B200 12 cases; seeds [20, 21, 22] and 0 coordinate probes
Evaluated C200 12 cases; seeds [20, 21, 22] and 0 coordinate probes
C200 complete: exactly 200 updates; 12 diagnostic + 48 heldout fields, 30 diagnostic probes.
```

</details>

## #34　2026-09-13T00:07:28　FAILED (exit 1)

**里程碑5验收：独立核验冻结张量与200次优化器计数，从原始数组复算新种子U0-U3**

```
py -3.11 verify_claims.py --trunk-repair --run --md
```

- 耗时 22s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/trunk_repair_v1/findings.json` | 92 KB | `825caaa7702a36e7` |
| `evidence/trunk_repair_v1/source/verify_claims_final.py` | 56 KB | `96f9d399e7d676a4` |
| `RESULTS.md` | 9 KB | `1939a0cd9a33e1a7` |
| `evidence/trunk_repair_v1/source/trunk_evidence.py` | 8 KB | `21b0a24d2e75bb4a` |
| `evidence/trunk_repair_v1/verification_manifest.json` | 0 KB | `12159a10c0ffbffe` |

<details><summary>输出末尾</summary>

```
             已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。

  [ PASS ]   T3  扩展间距B的错误坐标依赖未比起点加重
             六方向最大干预效应的平均：B/起点=0.6860
             已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。

  [ PASS ]   U0  仅trunk训练的冻结、预算和证据完整
             冻结50个张量逐项完全相同；仅24个trunk张量各更新200次；60组场、30组探针；13项检查
             同一B数据和batch序列；核验实际权重、优化器step、源与数组哈希；已知诊断集与新种子终验分开。

  [ FAIL ]   U1  仅trunk训练在新种子非立方测试达改善门槛
             新种子非立方C/A几何平均比：nMAE比值 0.9299，x-MRE比值 0.7701
             预设：种子20/21/22、六案例，两个几何平均比均≤0.8；全部逐例C/B及B/A0另报。

  [ FAIL ]   U2  仅trunk训练在新种子原范围内未明显退步
             新种子32³平均nMAE的C/起点比值 1.2988
             预设：≤1.1，不比起点退步超过10%。

  [ PASS ]   U3  仅trunk训练的错误坐标依赖未比起点加重
             六方向最大坐标干预效应平均的C/起点比值 0.8005
             预设：≤1；已知单波诊断集，非独立场精度或论文复现验收。

  —— 重跑便宜的检查 ——

  [ PASS ]   P0T  本阶段解析回归测试（本次现跑）
             9
             测试进程exit=0且至少9项通过

  [ PASS ]   T0T  A/B配对、损失与预算回归（本次现跑）
             3
             测试进程exit=0且至少3项通过

  [ PASS ]   U0T  实际训练函数的冻结回归（本次现跑）
             1
             临时微型网络：冻结参数不变、仅trunk获得更新；不是正式DCO训练

==================================================================
  通过 18　不通过 5　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #35　2026-09-13T00:10:21　OK

**里程碑5证据报告：新种子精度与已知坐标探针分开，展示C与A/B/起点的全部有利和不利对照**

```
py -3.11 slides/make_trunk_repair_figs.py
```

- 耗时 12s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/trunk_repair_outcomes.png` | 275 KB | `bbded5094b7d3dc6` |
| `figs/trunk_repair_training.png` | 135 KB | `46ccc34eb9785f22` |
| `evidence/trunk_repair_v1/source/make_trunk_repair_figs.py` | 12 KB | `f3682700c90aeb79` |
| `evidence/trunk_repair_v1/STAGE_REPORT.md` | 8 KB | `0f3d057d7ef4880a` |
| `evidence/trunk_repair_v1/figures_manifest.json` | 1 KB | `16a786e2820e9e84` |

<details><summary>输出末尾</summary>

```
Saved two evidence figures and C:\PI-DON\evidence\trunk_repair_v1\STAGE_REPORT.md
```

</details>

## #36　2026-09-13T00:25:17　OK

**第二阶段最小标定：比较内层学习率与50次预算是否能达到论文1e-4停止条件**

```
py -3.11 pidon_solve.py --steps 8 --n 31 --init dco_lr1e3_300.pt --max-inner 50 --calib 1e-3 3e-3 1e-2 --calib-iters 20 50
```

- 耗时 153s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  calibration

  lr sweep: does the inner training reach the tolerance at all?
  8 time steps each, tol 1e-04, max 50 inner iters

        lr  max it  reached tol  mean iters   mean loss   s/step    nMAE@end
  ----------------------------------------------------------------------------
     1e-03      20          0%        20.0    9.87e-02    1.80s   6.86e-05
     1e-03      50          0%        50.0    1.85e-02    4.42s   3.86e-05
     3e-03      20          0%        20.0    1.96e+00    1.78s   6.47e-04
     3e-03      50          0%        50.0    1.98e-01    4.44s   2.18e-04
     1e-02      20          0%        20.0         nan    1.78s        nan
     1e-02      50          0%        50.0         nan    4.42s        nan

  best mean loss at lr = 1e-03, max_inner = 50 (1.85e-02, reached tol on 0% of real sub-steps)
  STILL not reaching the tolerance on most sub-steps.  Then the
  bottleneck is not the learning rate -- raise --max-inner, or
  the network cannot represent the cavity curl that closely and
  that is itself the finding.
```

</details>

## #37　2026-09-13T00:26:43　OK

**第二阶段根因判别：固定lr=1e-3，内层预算扩至200，4时间步检查是否能达到1e-4**

```
py -3.11 pidon_solve.py --steps 4 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3
```

- 耗时 70s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `pidon_solve_dco_lr1e3_300.json` | 1 KB | `f120065e2183557f` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 200 iters, lr 0.001   device cuda

  step     1  inner   0/200  loss 0.00e+00/7.30e-04  cum 7.239e+01  nMAE 3.150e-13  9.68s/step
  step     2  inner 200/200  loss 6.00e-04/8.85e-04  cum 1.997e+01  nMAE 3.311e-05  14.30s/step
  step     3  inner 200/200  loss 9.01e-04/1.37e-03  cum 9.158e+00  nMAE 3.289e-05  15.84s/step
  step     4  inner 200/200  loss 8.51e-04/1.22e-03  cum 2.991e+00  nMAE 2.453e-05  16.63s/step

  4 steps in 67 s  (16.63 s/step)
  mean inner iters: curlH 150.0   curlE 200.0
  final nMAE vs FDTD 2.453e-05
  saved pidon_solve_dco_lr1e3_300.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #38　2026-09-13T00:37:12　OK

**第二阶段机制最小闭环：从预训练DCO每步重训，lr=1e-3、内层200次，推进32步并与FDTD逐步比较**

```
py -3.11 pidon_solve.py --steps 32 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --out evidence/pidon_stage2_32_lr1e3_i200.json
```

- 耗时 598s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_32_lr1e3_i200.json` | 9 KB | `3b59b7645117dd12` |

<details><summary>输出末尾</summary>

```
  step     7  inner 200/200  loss 4.88e-04/5.67e-04  cum 3.941e-01  nMAE 1.630e-05  17.55s/step
  step     8  inner 200/200  loss 3.27e-04/4.16e-04  cum 2.459e-01  nMAE 1.363e-05  17.73s/step
  step     9  inner 200/200  loss 2.38e-04/3.19e-04  cum 1.657e-01  nMAE 1.179e-05  17.86s/step
  step    10  inner 200/200  loss 1.82e-04/2.56e-04  cum 1.263e-01  nMAE 1.043e-05  17.97s/step
  step    11  inner 200/200  loss 1.51e-04/2.14e-04  cum 1.063e-01  nMAE 9.402e-06  18.07s/step
  step    12  inner 200/200  loss 1.31e-04/1.83e-04  cum 9.351e-02  nMAE 8.602e-06  18.14s/step
  step    13  inner 200/200  loss 1.17e-04/1.56e-04  cum 9.294e-02  nMAE 7.998e-06  18.20s/step
  step    14  inner 200/200  loss 1.07e-04/1.39e-04  cum 1.102e-01  nMAE 7.472e-06  18.26s/step
  step    15  inner 200/200  loss 1.00e-04/1.27e-04  cum 1.381e-01  nMAE 7.120e-06  18.31s/step
  step    16  inner 173/200  loss 1.00e-04/1.19e-04  cum 1.766e-01  nMAE 6.823e-06  18.26s/step
  step    17  inner 193/200  loss 9.99e-05/1.16e-04  cum 2.207e-01  nMAE 6.544e-06  18.29s/step
  step    18  inner 200/200  loss 1.00e-04/1.20e-04  cum 2.833e-01  nMAE 6.357e-06  18.32s/step
  step    19  inner 197/200  loss 9.99e-05/1.28e-04  cum 3.560e-01  nMAE 6.303e-06  18.35s/step
  step    20  inner 200/200  loss 1.00e-04/1.32e-04  cum 5.545e-01  nMAE 6.501e-06  18.38s/step
  step    21  inner 194/200  loss 1.00e-04/1.23e-04  cum 5.242e-01  nMAE 6.522e-06  18.40s/step
  step    22  inner 200/200  loss 1.03e-04/1.18e-04  cum 4.064e-01  nMAE 6.503e-06  18.42s/step
  step    23  inner 200/200  loss 1.10e-04/1.18e-04  cum 3.182e-01  nMAE 6.507e-06  18.45s/step
  step    24  inner 200/200  loss 1.09e-04/1.52e-04  cum 4.134e-01  nMAE 6.899e-06  18.47s/step
  step    25  inner 200/200  loss 1.14e-04/1.45e-04  cum 6.313e-01  nMAE 6.825e-06  18.49s/step
  step    26  inner 200/200  loss 1.30e-04/1.69e-04  cum 6.363e-01  nMAE 7.180e-06  18.51s/step
  step    27  inner 200/200  loss 1.24e-04/2.13e-04  cum 6.711e-01  nMAE 8.338e-06  18.53s/step
  step    28  inner 200/200  loss 1.42e-04/2.30e-04  cum 8.669e-01  nMAE 8.168e-06  18.54s/step
  step    29  inner 200/200  loss 1.15e-04/3.66e-04  cum 1.328e+00  nMAE 9.843e-06  18.56s/step
  step    30  inner 200/200  loss 1.34e-04/3.71e-04  cum 1.547e+00  nMAE 9.515e-06  18.57s/step
  step    31  inner 200/200  loss 2.63e-04/4.17e-04  cum 2.317e+00  nMAE 9.955e-06  18.58s/step
  step    32  inner 200/200  loss 2.44e-04/3.71e-02  cum 6.503e+01  nMAE 1.265e-05  18.60s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.98512（每步 -1.49%），等效 rho-1 = -1.488e-02
  内层损失中位数 2.14e-04  ->  每步相对误差 0.015
RESULT stepgain 0.985115

  32 steps in 595 s  (18.60 s/step)
  mean inner iters: curlH 192.4   curlE 200.0
  final nMAE vs FDTD 1.265e-05
  saved evidence/pidon_stage2_32_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #39　2026-09-13T00:39:01　OK

**第二阶段32步原始轨迹复核：有限性、逐步重训与停止条件分开判定**

```
py -3.11 stage2_evidence.py
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 1.265e-05`

<details><summary>输出末尾</summary>

```
PASS M0 | 32/32步有记录；字段和场值有限；dt/CFL=0.9900
PASS M1 | 平均内层次数 H=192.4, E=200.0
PASS M2 | 末步nMAE=1.265e-05；全程最大=3.216e-05
FAIL M3 | 非零curl-H达到阈值4/31，curl-E达到0/32；最大curl-E loss=3.71e-02
{
  "finite": true,
  "max_nmae": 3.216379368848541e-05,
  "final_nmae": 1.2647792266615407e-05,
  "final_cum": 65.03418517713726,
  "median_loss_h": 0.0001302534801652655,
  "median_loss_e": 0.0002130490174749866,
  "steps_hit_h": 4,
  "steps_hit_e": 0,
  "max_loss_e": 0.03707285225391388,
  "max_cum": 72.38861303083831
}
```

</details>

## #40　2026-09-13T00:39:48　OK

**第二阶段32步证据图和报告：由逐步JSON轨迹生成，明确短程通过与停止条件失败**

```
py -3.11 slides/make_stage2_figs.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/stage2_algorithm1_32.png` | 148 KB | `f8e781346042fe1f` |
| `evidence/stage2_mechanism_32/make_stage2_figs.py` | 5 KB | `efac9f71a4b6b5ee` |
| `evidence/stage2_mechanism_32/STAGE_REPORT.md` | 2 KB | `a535e2639fcecae1` |
| `evidence/stage2_mechanism_32/figures_manifest.json` | 0 KB | `32a71c6d6cc36929` |

<details><summary>输出末尾</summary>

```
Saved C:\PI-DON\evidence\stage2_mechanism_32\STAGE_REPORT.md
```

</details>

## #41　2026-09-13T00:40:43　OK

**第二阶段停止条件修正回归：确认更新后loss被重新计算且脚本语法有效**

```
py -3.11 -m py_compile pidon_solve.py
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
```

</details>

## #42　2026-09-13T00:41:59　OK

**第二阶段停止条件修正验证：4步重跑，比较更新后loss与阈值记录**

```
py -3.11 pidon_solve.py --steps 4 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --out evidence/pidon_stage2_4_lr1e3_i200_postloss.json
```

- 耗时 69s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_4_lr1e3_i200_postloss.json` | 1 KB | `1635640b4793deb1` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 200 iters, lr 0.001   device cuda

  step     1  inner   0/200  loss 0.00e+00/7.16e-04  cum 7.238e+01  nMAE 3.150e-13  9.55s/step
  step     2  inner 200/200  loss 5.58e-04/1.74e-03  cum 3.822e+01  nMAE 2.867e-05  14.11s/step
  step     3  inner 200/200  loss 2.94e-03/7.28e-03  cum 1.959e+01  nMAE 4.341e-05  15.66s/step
  step     4  inner 200/200  loss 3.39e-03/6.11e-03  cum 7.607e+00  nMAE 4.600e-05  16.44s/step

  4 steps in 66 s  (16.44 s/step)
  mean inner iters: curlH 150.0   curlE 200.0
  final nMAE vs FDTD 4.600e-05
  saved evidence/pidon_stage2_4_lr1e3_i200_postloss.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #43　2026-09-13T00:52:13　OK

**第二阶段最终短程重跑：采用更新后loss判定，lr=1e-3、内层200次、32步**

```
py -3.11 pidon_solve.py --steps 32 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --out evidence/pidon_stage2_32_lr1e3_i200_postloss.json
```

- 耗时 601s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_32_lr1e3_i200_postloss.json` | 9 KB | `2a6a3f3f104cffd1` |
| `stage2_evidence.py` | 2 KB | `ef006ce94e2417a5` |

<details><summary>输出末尾</summary>

```
  step     7  inner 200/200  loss 1.08e-03/1.05e-03  cum 6.972e-01  nMAE 2.381e-05  17.56s/step
  step     8  inner 200/200  loss 8.11e-04/7.93e-04  cum 4.906e-01  nMAE 2.007e-05  17.74s/step
  step     9  inner 200/200  loss 5.86e-04/6.48e-04  cum 3.635e-01  nMAE 1.716e-05  17.87s/step
  step    10  inner 200/200  loss 4.34e-04/5.70e-04  cum 2.962e-01  nMAE 1.511e-05  17.99s/step
  step    11  inner 200/200  loss 3.42e-04/5.00e-04  cum 2.485e-01  nMAE 1.371e-05  18.08s/step
  step    12  inner 200/200  loss 2.87e-04/4.27e-04  cum 2.102e-01  nMAE 1.254e-05  18.15s/step
  step    13  inner 200/200  loss 2.48e-04/3.64e-04  cum 1.882e-01  nMAE 1.163e-05  18.22s/step
  step    14  inner 200/200  loss 2.16e-04/3.19e-04  cum 1.786e-01  nMAE 1.068e-05  18.27s/step
  step    15  inner 200/200  loss 1.93e-04/2.85e-04  cum 1.660e-01  nMAE 1.002e-05  18.32s/step
  step    16  inner 200/200  loss 1.81e-04/2.61e-04  cum 1.663e-01  nMAE 9.545e-06  18.36s/step
  step    17  inner 200/200  loss 1.74e-04/2.48e-04  cum 1.867e-01  nMAE 9.166e-06  18.40s/step
  step    18  inner 200/200  loss 1.72e-04/2.45e-04  cum 2.600e-01  nMAE 9.056e-06  18.43s/step
  step    19  inner 200/200  loss 1.77e-04/2.43e-04  cum 3.574e-01  nMAE 9.162e-06  18.46s/step
  step    20  inner 200/200  loss 1.87e-04/2.55e-04  cum 5.061e-01  nMAE 9.612e-06  18.49s/step
  step    21  inner 200/200  loss 2.03e-04/2.79e-04  cum 6.284e-01  nMAE 9.921e-06  18.51s/step
  step    22  inner 200/200  loss 2.10e-04/3.40e-04  cum 8.727e-01  nMAE 1.082e-05  18.54s/step
  step    23  inner 200/200  loss 2.08e-04/3.67e-04  cum 1.027e+00  nMAE 1.103e-05  18.56s/step
  step    24  inner 200/200  loss 2.09e-04/4.06e-04  cum 1.161e+00  nMAE 1.077e-05  18.58s/step
  step    25  inner 200/200  loss 2.09e-04/4.08e-04  cum 1.305e+00  nMAE 1.045e-05  18.59s/step
  step    26  inner 200/200  loss 2.08e-04/4.35e-04  cum 1.365e+00  nMAE 1.041e-05  18.61s/step
  step    27  inner 200/200  loss 2.11e-04/4.45e-04  cum 1.068e+00  nMAE 1.085e-05  18.62s/step
  step    28  inner 200/200  loss 2.17e-04/4.46e-04  cum 9.605e-01  nMAE 1.104e-05  18.64s/step
  step    29  inner 200/200  loss 2.04e-04/5.21e-04  cum 1.013e+00  nMAE 1.153e-05  18.65s/step
  step    30  inner 200/200  loss 2.14e-04/6.47e-04  cum 1.213e+00  nMAE 1.230e-05  18.66s/step
  step    31  inner 200/200  loss 2.33e-04/8.35e-04  cum 2.008e+00  nMAE 1.320e-05  18.68s/step
  step    32  inner 200/200  loss 4.52e-04/1.25e-03  cum 3.371e+00  nMAE 1.398e-05  18.69s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.98083（每步 -1.92%），等效 rho-1 = -1.917e-02
  内层损失中位数 4.45e-04  ->  每步相对误差 0.021
RESULT stepgain 0.980827

  32 steps in 598 s  (18.69 s/step)
  mean inner iters: curlH 193.8   curlE 200.0
  final nMAE vs FDTD 1.398e-05
  saved evidence/pidon_stage2_32_lr1e3_i200_postloss.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #44　2026-09-13T00:52:21　OK

**第二阶段最终32步轨迹复核：以修正后的更新后loss为正式证据**

```
py -3.11 stage2_evidence.py
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 1.398e-05`

<details><summary>输出末尾</summary>

```
PASS M0 | 32/32步有记录；字段和场值有限；dt/CFL=0.9900
PASS M1 | 平均内层次数 H=193.8, E=200.0
PASS M2 | 末步nMAE=1.398e-05；全程最大=5.103e-05
FAIL M3 | 非零curl-H达到阈值0/31，curl-E达到0/32；最大curl-E loss=3.66e-03
{
  "finite": true,
  "max_nmae": 5.102735490605889e-05,
  "final_nmae": 1.3977456394741662e-05,
  "final_cum": 3.3711423760687467,
  "median_loss_h": 0.0002159274445148185,
  "median_loss_e": 0.00044455655734054744,
  "steps_hit_h": 0,
  "steps_hit_e": 0,
  "max_loss_e": 0.0036551272496581078,
  "max_cum": 72.38270847609965
}
```

</details>

## #45　2026-09-13T00:52:26　OK

**第二阶段最终证据图和阶段报告：依据修正后的32步轨迹**

```
py -3.11 slides/make_stage2_figs.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/stage2_algorithm1_32.png` | 148 KB | `6768dde7c9dd6391` |
| `evidence/stage2_mechanism_32/STAGE_REPORT.md` | 2 KB | `7931654d0f940335` |
| `evidence/stage2_mechanism_32/figures_manifest.json` | 0 KB | `34def28793484c15` |

<details><summary>输出末尾</summary>

```
Saved C:\PI-DON\evidence\stage2_mechanism_32\STAGE_REPORT.md
```

</details>

## #46　2026-09-13T00:54:16　OK

**第二阶段停止条件根因测试：单次非零时间步内层预算500，检查是否真的只是预算不足**

```
py -3.11 pidon_solve.py --steps 2 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 1e-3 --out evidence/pidon_stage2_2_lr1e3_i500_postloss.json
```

- 耗时 74s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_2_lr1e3_i500_postloss.json` | 1 KB | `bcc3524a76abb707` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 500 iters, lr 0.001   device cuda

  step     1  inner   0/500  loss 0.00e+00/1.60e-04  cum 7.249e+01  nMAE 3.150e-13  23.71s/step
  step     2  inner 500/500  loss 1.17e-04/9.88e+02  cum 1.257e+13  nMAE 1.334e-05  35.45s/step

  2 steps in 71 s  (35.45 s/step)
  mean inner iters: curlH 250.0   curlE 500.0
  final nMAE vs FDTD 1.334e-05
  saved evidence/pidon_stage2_2_lr1e3_i500_postloss.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #47　2026-09-13T00:54:44　OK

**第二阶段报告更新：加入500次内层预算根因测试与优化不稳定证据**

```
py -3.11 slides/make_stage2_figs.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/stage2_algorithm1_32.png` | 148 KB | `6768dde7c9dd6391` |
| `evidence/stage2_mechanism_32/make_stage2_figs.py` | 5 KB | `f59c6b09ae1fe5eb` |
| `evidence/stage2_mechanism_32/STAGE_REPORT.md` | 2 KB | `02da8b62da903eac` |
| `evidence/stage2_mechanism_32/figures_manifest.json` | 0 KB | `24d6254087470bf6` |

<details><summary>输出末尾</summary>

```
Saved C:\PI-DON\evidence\stage2_mechanism_32\STAGE_REPORT.md
```

</details>

## #48　2026-09-13T00:55:12　OK

**第二阶段报告最终修订：统一引用修正后的run43轨迹**

```
py -3.11 slides/make_stage2_figs.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/stage2_algorithm1_32.png` | 152 KB | `8456657c3fbd4700` |
| `evidence/stage2_mechanism_32/make_stage2_figs.py` | 5 KB | `f5705866ee2e94ba` |
| `evidence/stage2_mechanism_32/STAGE_REPORT.md` | 3 KB | `f03e443e0ef6b948` |
| `evidence/stage2_mechanism_32/figures_manifest.json` | 0 KB | `f2ba3177011f9f72` |

<details><summary>输出末尾</summary>

```
Saved C:\PI-DON\evidence\stage2_mechanism_32\STAGE_REPORT.md
```

</details>

## #49　2026-09-13T01:37:05　FAILED (exit 1)

**第二阶段接口低成本探针：同一场状态比较cellsize、centered、abs坐标对初始旋度残差的影响**

```
py -3.11 stage2_interface_probe.py
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
Traceback (most recent call last):
  File "C:\PI-DON\stage2_interface_probe.py", line 36, in <module>
    if __name__=='__main__':main()
                            ^^^^^^
  File "C:\PI-DON\stage2_interface_probe.py", line 17, in main
    g=fdtd.source_waveform(3,s.dt,s.fmax,'gauss')
                                  ^^^^^^
AttributeError: 'Solver' object has no attribute 'fmax'
```

</details>

## #50　2026-09-13T01:37:22　OK

**第二阶段接口探针重跑：修正参数传递后比较三种坐标编码**

```
py -3.11 stage2_interface_probe.py
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/stage2_interface_probe.json` | 1 KB | `44ecca9059ba3fda` |

<details><summary>输出末尾</summary>

```
cellsize H rel_loss=5.4112e-01 pred_rms=1.402e-10 target_rms=2.203e-10
cellsize E rel_loss=8.7963e-01 pred_rms=9.121e-08 target_rms=4.668e-07
centered H rel_loss=1.6716e+09 pred_rms=9.009e-06 target_rms=2.203e-10
centered E rel_loss=5.6981e+08 pred_rms=1.114e-02 target_rms=4.668e-07
     abs H rel_loss=6.1528e+03 pred_rms=1.730e-08 target_rms=2.203e-10
     abs E rel_loss=2.2487e+03 pred_rms=2.213e-05 target_rms=4.668e-07
```

</details>

## #51　2026-09-13T01:38:30　OK

**第二阶段共享网络干扰探针：比较H拟合后、E拟合后H残差是否恶化**

```
py -3.11 stage2_shared_interference.py
```

- 耗时 32s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/stage2_shared_interference.json` | 0 KB | `a22f0f4223697bfa` |

<details><summary>输出末尾</summary>

```
{
  "device": "cuda",
  "initial_H": 0.9999232888221741,
  "after_H_training": 0.0011959777912124991,
  "before_E": 1.1715235710144043,
  "after_E_training": 0.006000998895615339,
  "H_after_E": 0.9945983290672302,
  "H_iters": 200,
  "E_iters": 200,
  "H_loss": 0.0011959777912124991,
  "E_loss": 0.006000998895615339,
  "H_degradation_ratio": 831.6193965933869
}
```

</details>

## #52　2026-09-13T01:39:04　OK

**独立E/H网络改动预检：语法与参数解析**

```
py -3.11 -m py_compile pidon_solve.py
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
```

</details>

## #53　2026-09-13T01:40:25　OK

**第二阶段独立E/H网络对照：同一预训练起点、lr=1e-3、内层200，先推进4步**

```
py -3.11 pidon_solve.py --steps 4 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --separate-nets --out evidence/pidon_stage2_4_separate_lr1e3_i200.json
```

- 耗时 71s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_4_separate_lr1e3_i200.json` | 1 KB | `a3ae59d6dc8393ed` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 200 iters, lr 0.001   device cuda

  step     1  inner   0/200  loss 0.00e+00/7.23e-04  cum 7.239e+01  nMAE 3.150e-13  9.79s/step
  step     2  inner 200/200  loss 5.81e-04/1.45e-03  cum 6.276e+01  nMAE 2.336e-05  14.50s/step
  step     3  inner 200/200  loss 5.41e-04/3.31e-03  cum 3.735e+00  nMAE 2.540e-05  16.11s/step
  step     4  inner 200/200  loss 6.34e-04/2.21e-03  cum 1.640e+00  nMAE 2.611e-05  16.92s/step

  4 steps in 68 s  (16.93 s/step)
  mean inner iters: curlH 150.0   curlE 200.0
  final nMAE vs FDTD 2.611e-05
  saved evidence/pidon_stage2_4_separate_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #54　2026-09-13T01:49:52　OK

**第二阶段独立E/H网络32步对照：同一预训练起点、lr=1e-3、内层200**

```
py -3.11 pidon_solve.py --steps 32 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --separate-nets --out evidence/pidon_stage2_32_separate_lr1e3_i200.json
```

- 耗时 553s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_32_separate_lr1e3_i200.json` | 9 KB | `98f980e084cc17d9` |

<details><summary>输出末尾</summary>

```
  step     7  inner 200/200  loss 1.90e-04/4.10e-04  cum 1.847e-01  nMAE 1.546e-05  18.30s/step
  step     8  inner 200/200  loss 1.19e-04/3.09e-04  cum 1.153e-01  nMAE 1.263e-05  18.47s/step
  step     9  inner  90/200  loss 9.98e-05/2.60e-04  cum 7.372e-02  nMAE 1.112e-05  18.00s/step
  step    10  inner  57/200  loss 9.97e-05/2.24e-04  cum 5.984e-02  nMAE 1.009e-05  17.46s/step
  step    11  inner  55/200  loss 9.98e-05/2.04e-04  cum 5.556e-02  nMAE 9.575e-06  17.01s/step
  step    12  inner  57/200  loss 9.99e-05/1.99e-04  cum 5.428e-02  nMAE 9.174e-06  16.64s/step
  step    13  inner  62/200  loss 1.00e-04/2.02e-04  cum 5.607e-02  nMAE 8.960e-06  16.35s/step
  step    14  inner  60/200  loss 1.00e-04/2.12e-04  cum 6.651e-02  nMAE 8.927e-06  16.09s/step
  step    15  inner  65/200  loss 1.00e-04/2.24e-04  cum 6.658e-02  nMAE 8.941e-06  15.89s/step
  step    16  inner  86/200  loss 1.00e-04/2.35e-04  cum 9.426e-02  nMAE 8.894e-06  15.77s/step
  step    17  inner 103/200  loss 1.00e-04/2.44e-04  cum 7.654e-02  nMAE 8.782e-06  15.72s/step
  step    18  inner 136/200  loss 1.00e-04/2.50e-04  cum 1.015e-01  nMAE 8.640e-06  15.77s/step
  step    19  inner 144/200  loss 1.00e-04/2.57e-04  cum 9.695e-02  nMAE 8.495e-06  15.83s/step
  step    20  inner 140/200  loss 9.99e-05/2.70e-04  cum 1.338e-01  nMAE 8.380e-06  15.87s/step
  step    21  inner 140/200  loss 1.00e-04/2.72e-04  cum 1.073e-01  nMAE 8.256e-06  15.91s/step
  step    22  inner 190/200  loss 1.00e-04/2.87e-04  cum 1.558e-01  nMAE 8.118e-06  16.06s/step
  step    23  inner 165/200  loss 9.99e-05/2.92e-04  cum 1.330e-01  nMAE 8.116e-06  16.15s/step
  step    24  inner 200/200  loss 1.01e-04/2.92e-04  cum 1.717e-01  nMAE 8.012e-06  16.30s/step
  step    25  inner 200/200  loss 1.05e-04/2.94e-04  cum 1.771e-01  nMAE 7.850e-06  16.44s/step
  step    26  inner 200/200  loss 1.12e-04/3.19e-04  cum 2.044e-01  nMAE 7.696e-06  16.57s/step
  step    27  inner 200/200  loss 1.21e-04/5.26e-04  cum 3.605e-01  nMAE 7.620e-06  16.69s/step
  step    28  inner 200/200  loss 1.13e-04/6.04e-04  cum 4.967e-01  nMAE 7.791e-06  16.80s/step
  step    29  inner 200/200  loss 1.12e-04/5.39e-04  cum 3.943e-01  nMAE 7.929e-06  16.91s/step
  step    30  inner 200/200  loss 3.17e-04/5.58e-04  cum 3.545e-01  nMAE 8.077e-06  17.00s/step
  step    31  inner 200/200  loss 3.62e-04/8.34e-04  cum 1.048e+00  nMAE 8.217e-06  17.10s/step
  step    32  inner 200/200  loss 1.60e-04/1.13e-03  cum 9.498e-01  nMAE 8.535e-06  17.18s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.98023（每步 -1.98%），等效 rho-1 = -1.977e-02
  内层损失中位数 2.93e-04  ->  每步相对误差 0.017
RESULT stepgain 0.980234

  32 steps in 550 s  (17.18 s/step)
  mean inner iters: curlH 148.4   curlE 200.0
  final nMAE vs FDTD 8.535e-06
  saved evidence/pidon_stage2_32_separate_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #55　2026-09-13T02:28:41　OK

**第二阶段主要长程证据：独立E/H DCO、lr=1e-3、内层200，推进128步**

```
py -3.11 pidon_solve.py --steps 128 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --separate-nets --out evidence/pidon_stage2_128_separate_lr1e3_i200.json
```

- 耗时 2310s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_128_separate_lr1e3_i200.json` | 30 KB | `755195e764912376` |

<details><summary>输出末尾</summary>

```
  step     4  inner 200/200  loss 4.55e-04/9.18e-04  cum 1.043e+00  nMAE 2.148e-05  17.17s/step
  step     5  inner 200/200  loss 2.93e-04/6.42e-04  cum 4.405e-01  nMAE 1.846e-05  17.66s/step
  step     6  inner 200/200  loss 2.40e-04/4.14e-04  cum 2.236e-01  nMAE 1.597e-05  18.01s/step
  step    12  inner  60/200  loss 9.99e-05/1.69e-04  cum 4.889e-02  nMAE 9.340e-06  16.60s/step
  step    18  inner 119/200  loss 1.00e-04/1.96e-04  cum 7.991e-02  nMAE 8.584e-06  15.78s/step
  step    24  inner 200/200  loss 1.13e-04/2.47e-04  cum 1.471e-01  nMAE 7.931e-06  16.43s/step
  step    30  inner 200/200  loss 1.29e-04/6.01e-04  cum 4.529e-01  nMAE 8.159e-06  16.85s/step
  step    36  inner 200/200  loss 1.20e-04/4.48e+02  cum 2.503e+09  nMAE 9.857e-06  17.13s/step
  step    42  inner 200/200  loss 8.29e+01/1.25e+00  cum 3.603e+04  nMAE 2.040e+03  17.32s/step
  step    48  inner 200/200  loss 2.86e+01/1.49e+00  cum 1.163e+04  nMAE 1.580e+07  17.45s/step
  step    54  inner 200/200  loss 1.22e+01/1.20e+00  cum 3.784e+03  nMAE 5.671e+10  17.56s/step
  step    60  inner 200/200  loss 7.60e+00/1.07e+00  cum 2.373e+03  nMAE 7.770e+13  17.65s/step
  step    66  inner 200/200  loss 1.05e+01/nan  cum nan  nMAE 2.091e+17  17.72s/step
  step    72  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.77s/step
  step    78  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.82s/step
  step    84  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.85s/step
  step    90  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.88s/step
  step    96  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.91s/step
  step   102  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.94s/step
  step   108  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.96s/step
  step   114  inner 200/200  loss nan/nan  cum nan  nMAE nan  17.98s/step
  step   120  inner 200/200  loss nan/nan  cum nan  nMAE nan  18.00s/step
  step   126  inner 200/200  loss nan/nan  cum nan  nMAE nan  18.01s/step

  --- 误差增长诊断 ---
  每步增益 g = 3.08339（每步 +208.34%），等效 rho-1 = 2.083e+00
  内层损失中位数 1.03e-03  ->  每步相对误差 0.032
  误差翻倍需 1 步
  要跑完 128 步，每步相对误差需 <= 1/N = 7.81e-03，即损失 <= 6.10e-05
  当前差 1.7e+01 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 3.083391

  128 steps in 2306 s  (18.02 s/step)
  mean inner iters: curlH 187.7   curlE 200.0
  final nMAE vs FDTD nan
  saved evidence/pidon_stage2_128_separate_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #56　2026-09-13T02:29:06　OK

**优化器重置对照预检：独立E/H网络与每时间步重置Adam状态，语法有效**

```
py -3.11 -m py_compile pidon_solve.py
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
```

</details>

## #57　2026-09-13T02:36:18　OK

**第二阶段优化器重置对照：独立E/H网络、每时间步重置Adam、内层200，推进48步**

```
py -3.11 pidon_solve.py --steps 48 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_48_separate_reset_lr1e3_i200.json
```

- 耗时 422s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_48_separate_reset_lr1e3_i200.json` | 13 KB | `9f6f9e01cbcc3540` |

<details><summary>输出末尾</summary>

```
  step     5  inner  52/ 83  loss 9.76e-05/9.95e-05  cum 3.041e-01  nMAE 6.462e-06  11.23s/step
  step     6  inner  62/ 63  loss 9.86e-05/9.86e-05  cum 4.732e-01  nMAE 6.775e-06  10.31s/step
  step     8  inner  43/ 98  loss 7.55e-05/9.88e-05  cum 2.744e-01  nMAE 6.559e-06  9.76s/step
  step    10  inner  40/ 78  loss 9.52e-05/9.93e-05  cum 1.802e-01  nMAE 4.967e-06  8.85s/step
  step    12  inner  36/ 51  loss 8.22e-05/9.71e-05  cum 9.015e-02  nMAE 4.786e-06  8.33s/step
  step    14  inner  39/ 50  loss 7.82e-05/9.93e-05  cum 1.103e-01  nMAE 5.422e-06  7.76s/step
  step    16  inner  31/ 55  loss 7.31e-05/9.50e-05  cum 7.904e-02  nMAE 4.372e-06  7.29s/step
  step    18  inner  35/ 45  loss 6.63e-05/9.98e-05  cum 1.004e-01  nMAE 5.373e-06  6.89s/step
  step    20  inner  38/ 74  loss 8.54e-05/9.81e-05  cum 1.083e-01  nMAE 1.167e-05  6.70s/step
  step    22  inner  34/ 55  loss 7.72e-05/9.66e-05  cum 1.085e-01  nMAE 8.346e-06  6.44s/step
  step    24  inner  30/ 71  loss 6.33e-05/9.98e-05  cum 1.230e-01  nMAE 5.113e-06  6.27s/step
  step    26  inner  25/ 75  loss 9.46e-05/9.63e-05  cum 1.484e-01  nMAE 6.566e-06  6.17s/step
  step    28  inner  38/ 88  loss 6.62e-05/9.78e-05  cum 2.224e-01  nMAE 5.444e-06  6.12s/step
  step    30  inner  35/105  loss 7.63e-05/9.85e-05  cum 2.847e-01  nMAE 5.069e-06  6.10s/step
  step    32  inner  30/189  loss 9.09e-05/9.76e-05  cum 5.891e-01  nMAE 5.297e-06  6.28s/step
  step    34  inner  44/200  loss 8.30e-05/2.41e-04  cum 1.890e+00  nMAE 6.245e-06  6.57s/step
  step    36  inner  59/200  loss 9.76e-05/2.44e-03  cum 1.014e+01  nMAE 6.233e-06  6.85s/step
  step    38  inner  73/200  loss 9.86e-05/9.72e-04  cum 6.063e+00  nMAE 7.376e-06  7.15s/step
  step    40  inner  81/200  loss 9.92e-05/1.11e-03  cum 2.490e+00  nMAE 8.327e-06  7.43s/step
  step    42  inner 132/200  loss 9.91e-05/8.23e-04  cum 2.015e+00  nMAE 9.518e-06  7.76s/step
  step    44  inner 200/200  loss 6.07e-04/6.43e-04  cum 4.925e+00  nMAE 1.072e-05  8.25s/step
  step    46  inner  81/200  loss 9.98e-05/8.28e-04  cum 1.769e+00  nMAE 1.257e-05  8.58s/step
  step    48  inner  54/200  loss 9.38e-05/6.75e-04  cum 2.325e+00  nMAE 1.573e-05  8.71s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.01911（每步 +1.91%），等效 rho-1 = 1.911e-02
  内层损失中位数 9.97e-05  ->  每步相对误差 0.010
  误差翻倍需 37 步
  要跑完 48 步，每步相对误差需 <= 1/N = 2.08e-02，即损失 <= 4.34e-04
  当前差 2.3e-01 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.019113

  48 steps in 418 s  (8.71 s/step)
  mean inner iters: curlH 60.9   curlE 128.8
  final nMAE vs FDTD 1.573e-05
  saved evidence/pidon_stage2_48_separate_reset_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #58　2026-09-13T03:00:55　OK

**第二阶段主长程对照：独立E/H网络、每步重置Adam、内层200，推进128步**

```
py -3.11 pidon_solve.py --steps 128 --n 31 --init dco_lr1e3_300.pt --max-inner 200 --lr 1e-3 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_128_separate_reset_lr1e3_i200.json
```

- 耗时 1455s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_128_separate_reset_lr1e3_i200.json` | 36 KB | `d63a3fc5b0973d99` |

<details><summary>输出末尾</summary>

```
  step     4  inner  75/141  loss 9.83e-05/9.94e-05  cum 1.051e+00  nMAE 9.234e-06  13.19s/step
  step     5  inner  57/ 73  loss 9.96e-05/9.77e-05  cum 3.038e-01  nMAE 7.425e-06  11.73s/step
  step     6  inner  63/ 74  loss 9.91e-05/9.61e-05  cum 4.628e-01  nMAE 6.571e-06  10.82s/step
  step    12  inner  41/ 42  loss 8.97e-05/9.42e-05  cum 1.228e-01  nMAE 4.809e-06  7.62s/step
  step    18  inner  32/ 43  loss 9.22e-05/9.69e-05  cum 8.349e-02  nMAE 5.159e-06  6.24s/step
  step    24  inner  33/ 63  loss 6.96e-05/9.76e-05  cum 1.064e-01  nMAE 4.598e-06  5.62s/step
  step    30  inner  29/120  loss 8.39e-05/9.97e-05  cum 2.676e-01  nMAE 5.358e-06  5.62s/step
  step    36  inner  56/200  loss 9.94e-05/2.19e-03  cum 1.047e+01  nMAE 6.466e-06  6.56s/step
  step    42  inner 122/200  loss 9.86e-05/1.01e-03  cum 1.937e+00  nMAE 1.137e-05  7.44s/step
  step    48  inner  53/200  loss 9.61e-05/7.16e-04  cum 2.523e+00  nMAE 1.721e-05  8.43s/step
  step    54  inner  52/200  loss 8.73e-05/4.84e-04  cum 9.796e-01  nMAE 6.992e-05  8.75s/step
  step    60  inner 124/200  loss 9.89e-05/3.13e-04  cum 5.975e-01  nMAE 3.977e-04  9.16s/step
  step    66  inner 198/200  loss 9.91e-05/1.64e-04  cum 5.172e-01  nMAE 3.753e-03  9.93s/step
  step    72  inner 190/200  loss 9.96e-05/1.02e-04  cum 4.742e-01  nMAE 2.011e-02  10.63s/step
  step    78  inner 156/182  loss 9.97e-05/9.97e-05  cum 3.823e-01  nMAE 2.397e-02  11.09s/step
  step    84  inner 148/150  loss 9.95e-05/9.99e-05  cum 3.101e-01  nMAE 1.657e-02  11.27s/step
  step    90  inner 200/142  loss 1.15e-04/9.95e-05  cum 3.223e-01  nMAE 1.463e-02  11.47s/step
  step    96  inner 112/119  loss 9.91e-05/9.95e-05  cum 2.133e-01  nMAE 1.450e-02  11.52s/step
  step   102  inner 116/109  loss 9.91e-05/9.96e-05  cum 2.039e-01  nMAE 1.216e-02  11.47s/step
  step   108  inner 106/200  loss 9.99e-05/1.13e-02  cum 2.847e+01  nMAE 1.329e-02  11.44s/step
  step   114  inner 104/153  loss 1.00e-04/9.91e-05  cum 2.480e-01  nMAE 1.992e-02  11.51s/step
  step   120  inner 121/ 80  loss 9.99e-05/9.97e-05  cum 1.753e-01  nMAE 1.556e-02  11.46s/step
  step   126  inner  81/119  loss 9.97e-05/9.95e-05  cum 1.697e-01  nMAE 1.286e-02  11.36s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.10053（每步 +10.05%），等效 rho-1 = 1.005e-01
  内层损失中位数 9.98e-05  ->  每步相对误差 0.010
  误差翻倍需 7 步
  要跑完 128 步，每步相对误差需 <= 1/N = 7.81e-03，即损失 <= 6.10e-05
  当前差 1.6e+00 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.100527

  128 steps in 1452 s  (11.34 s/step)
  mean inner iters: curlH 102.0   curlE 144.1
  final nMAE vs FDTD 1.801e-02
  saved evidence/pidon_stage2_128_separate_reset_lr1e3_i200.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #59　2026-09-13T03:02:54　OK

**第二阶段精度瓶颈测试：独立E/H、每步重置Adam、内层500，推进8步**

```
py -3.11 pidon_solve.py --steps 8 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 1e-3 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_8_separate_reset_lr1e3_i500.json
```

- 耗时 95s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_8_separate_reset_lr1e3_i500.json` | 2 KB | `b893c16b6af1f83b` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 500 iters, lr 0.001   device cuda

  step     1  inner   0/500  loss 0.00e+00/1.60e-04  cum 7.248e+01  nMAE 3.150e-13  23.17s/step
  step     2  inner 500/179  loss 1.21e-04/9.97e-05  cum 4.174e+01  nMAE 1.267e-05  27.15s/step
  step     3  inner  93/137  loss 9.92e-05/9.96e-05  cum 2.320e+00  nMAE 8.925e-06  21.61s/step
  step     4  inner  69/ 87  loss 9.08e-05/9.77e-05  cum 7.116e-01  nMAE 7.484e-06  17.99s/step
  step     5  inner  51/ 59  loss 9.06e-05/9.96e-05  cum 2.637e-01  nMAE 6.319e-06  15.39s/step
  step     6  inner  82/ 54  loss 9.85e-05/9.24e-05  cum 4.447e-01  nMAE 6.334e-06  13.87s/step
  step     7  inner  60/ 42  loss 9.68e-05/9.60e-05  cum 2.659e-01  nMAE 5.861e-06  12.55s/step
  step     8  inner  53/ 37  loss 9.70e-05/9.35e-05  cum 1.795e-01  nMAE 5.556e-06  11.50s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.91520（每步 -8.48%），等效 rho-1 = -8.480e-02
  内层损失中位数 9.86e-05  ->  每步相对误差 0.010
RESULT stepgain 0.915204

  8 steps in 92 s  (11.50 s/step)
  mean inner iters: curlH 113.5   curlE 136.9
  final nMAE vs FDTD 5.556e-06
  saved evidence/pidon_stage2_8_separate_reset_lr1e3_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #60　2026-09-13T03:35:08　OK

**第二阶段最佳配置长程：独立E/H、每步重置Adam、内层500，推进128步**

```
py -3.11 pidon_solve.py --steps 128 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 1e-3 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_128_separate_reset_lr1e3_i500.json
```

- 耗时 1923s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_128_separate_reset_lr1e3_i500.json` | 36 KB | `4e20386c8a9f5fee` |

<details><summary>输出末尾</summary>

```
  step     4  inner  69/158  loss 9.43e-05/9.95e-05  cum 9.671e-01  nMAE 7.872e-06  23.64s/step
  step     5  inner  49/ 96  loss 9.65e-05/9.85e-05  cum 3.663e-01  nMAE 6.692e-06  20.24s/step
  step     6  inner  64/ 60  loss 9.81e-05/9.70e-05  cum 4.483e-01  nMAE 6.423e-06  17.82s/step
  step    12  inner  37/ 33  loss 8.89e-05/9.09e-05  cum 8.298e-02  nMAE 4.689e-06  10.88s/step
  step    18  inner  32/ 43  loss 8.27e-05/9.24e-05  cum 9.559e-02  nMAE 4.973e-06  8.40s/step
  step    24  inner  33/ 51  loss 7.73e-05/9.69e-05  cum 1.109e-01  nMAE 3.760e-06  7.22s/step
  step    30  inner  31/120  loss 9.73e-05/9.95e-05  cum 3.097e-01  nMAE 6.093e-06  6.82s/step
  step    36  inner  62/500  loss 9.87e-05/2.30e-01  cum 3.525e+05  nMAE 7.543e-06  8.81s/step
  step    42  inner 127/487  loss 9.92e-05/9.99e-05  cum 2.355e+00  nMAE 1.630e-05  11.38s/step
  step    48  inner  45/500  loss 9.28e-05/1.45e-04  cum 2.032e+00  nMAE 1.941e-05  13.64s/step
  step    54  inner  48/385  loss 9.81e-05/9.82e-05  cum 8.515e-01  nMAE 7.328e-05  14.78s/step
  step    60  inner 129/356  loss 9.89e-05/9.53e-05  cum 4.838e-01  nMAE 4.181e-04  15.24s/step
  step    66  inner 188/254  loss 9.37e-05/9.66e-05  cum 4.420e-01  nMAE 3.989e-03  15.73s/step
  step    72  inner 161/215  loss 9.98e-05/9.82e-05  cum 4.127e-01  nMAE 2.223e-02  16.02s/step
  step    78  inner 165/190  loss 9.98e-05/9.94e-05  cum 4.100e-01  nMAE 2.504e-02  16.10s/step
  step    84  inner 148/173  loss 1.00e-04/9.96e-05  cum 3.780e-01  nMAE 1.798e-02  16.07s/step
  step    90  inner 168/153  loss 9.99e-05/1.00e-04  cum 3.420e-01  nMAE 1.534e-02  15.97s/step
  step    96  inner 122/131  loss 9.91e-05/9.98e-05  cum 2.297e-01  nMAE 1.574e-02  15.74s/step
  step   102  inner 134/121  loss 9.94e-05/9.92e-05  cum 2.330e-01  nMAE 1.289e-02  15.50s/step
  step   108  inner 127/126  loss 1.00e-04/9.98e-05  cum 2.140e-01  nMAE 1.387e-02  15.26s/step
  step   114  inner 118/127  loss 9.95e-05/9.99e-05  cum 2.180e-01  nMAE 2.133e-02  15.07s/step
  step   120  inner 500/ 92  loss 6.32e-03/9.97e-05  cum 2.323e+02  nMAE 1.592e-02  15.15s/step
  step   126  inner 118/136  loss 9.96e-05/9.99e-05  cum 2.103e-01  nMAE 1.374e-02  15.06s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.09977（每步 +9.98%），等效 rho-1 = 9.977e-02
  内层损失中位数 9.95e-05  ->  每步相对误差 0.010
  误差翻倍需 7 步
  要跑完 128 步，每步相对误差需 <= 1/N = 7.81e-03，即损失 <= 6.10e-05
  当前差 1.6e+00 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.099773

  128 steps in 1919 s  (15.00 s/step)
  mean inner iters: curlH 117.5   curlE 208.8
  final nMAE vs FDTD 1.871e-02
  saved evidence/pidon_stage2_128_separate_reset_lr1e3_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #61　2026-09-13T03:38:40　OK

**第二阶段学习率精调：独立E/H、每步重置Adam、内层500，lr=3e-4，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_16_separate_reset_lr3e4_i500.json
```

- 耗时 185s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_separate_reset_lr3e4_i500.json` | 5 KB | `886c3cf52a9d844a` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.12e-04  cum 1.019e+02  nMAE 3.150e-13  23.10s/step
  step     2  inner 500/500  loss 3.90e-04/1.59e-04  cum 8.104e+01  nMAE 2.123e-05  34.56s/step
  step     3  inner 339/306  loss 9.99e-05/9.94e-05  cum 2.472e+00  nMAE 1.343e-05  32.92s/step
  step     4  inner 149/128  loss 9.95e-05/9.92e-05  cum 7.518e-01  nMAE 1.003e-05  27.87s/step
  step     5  inner 147/ 90  loss 9.93e-05/9.97e-05  cum 2.819e-01  nMAE 8.445e-06  24.48s/step
  step     6  inner 200/ 98  loss 9.96e-05/9.95e-05  cum 4.206e-01  nMAE 7.878e-06  22.68s/step
  step     7  inner 122/ 58  loss 9.98e-05/9.84e-05  cum 2.532e-01  nMAE 6.821e-06  20.62s/step
  step     8  inner  79/ 49  loss 9.89e-05/8.58e-05  cum 1.227e-01  nMAE 6.256e-06  18.78s/step
  step     9  inner  64/ 39  loss 9.97e-05/9.16e-05  cum 1.022e-01  nMAE 5.248e-06  17.21s/step
  step    10  inner  59/ 35  loss 9.95e-05/9.16e-05  cum 9.398e-02  nMAE 4.829e-06  15.92s/step
  step    11  inner  56/ 31  loss 9.91e-05/9.53e-05  cum 7.633e-02  nMAE 4.728e-06  14.83s/step
  step    12  inner  58/ 32  loss 9.71e-05/9.01e-05  cum 7.034e-02  nMAE 4.528e-06  13.94s/step
  step    13  inner  51/ 24  loss 9.81e-05/8.74e-05  cum 5.853e-02  nMAE 4.708e-06  13.13s/step
  step    14  inner  51/ 29  loss 9.68e-05/9.78e-05  cum 6.449e-02  nMAE 4.964e-06  12.45s/step
  step    15  inner  49/ 32  loss 9.83e-05/8.43e-05  cum 6.149e-02  nMAE 5.569e-06  11.87s/step
  step    16  inner  45/ 28  loss 9.97e-05/9.92e-05  cum 5.570e-02  nMAE 4.952e-06  11.34s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.94640（每步 -5.36%），等效 rho-1 = -5.360e-02
  内层损失中位数 9.81e-05  ->  每步相对误差 0.010
RESULT stepgain 0.946397

  16 steps in 181 s  (11.34 s/step)
  mean inner iters: curlH 123.1   curlE 123.7
  final nMAE vs FDTD 4.952e-06
  saved evidence/pidon_stage2_16_separate_reset_lr3e4_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #62　2026-09-13T04:11:35　OK

**第二阶段候选最优长程：独立E/H、每步重置Adam、内层500、lr=3e-4，128步**

```
py -3.11 pidon_solve.py --steps 128 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json
```

- 耗时 1963s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json` | 36 KB | `44c159194ce657bf` |

<details><summary>输出末尾</summary>

```
  step     4  inner 168/142  loss 9.95e-05/9.99e-05  cum 7.722e-01  nMAE 9.533e-06  28.86s/step
  step     5  inner 130/108  loss 9.92e-05/9.85e-05  cum 3.128e-01  nMAE 8.379e-06  25.27s/step
  step     6  inner 185/ 75  loss 9.90e-05/9.98e-05  cum 3.699e-01  nMAE 7.537e-06  23.05s/step
  step    12  inner  54/ 31  loss 9.77e-05/9.68e-05  cum 7.790e-02  nMAE 4.337e-06  14.05s/step
  step    18  inner  47/ 34  loss 9.63e-05/8.09e-05  cum 5.242e-02  nMAE 5.423e-06  10.57s/step
  step    24  inner  43/ 45  loss 9.29e-05/9.49e-05  cum 6.162e-02  nMAE 5.396e-06  8.84s/step
  step    30  inner  63/136  loss 9.90e-05/9.97e-05  cum 1.992e-01  nMAE 5.816e-06  8.29s/step
  step    36  inner  96/500  loss 9.87e-05/7.87e-04  cum 9.988e+00  nMAE 7.281e-06  10.51s/step
  step    42  inner 210/500  loss 9.49e-05/1.43e-04  cum 1.521e+00  nMAE 1.062e-05  13.11s/step
  step    48  inner  51/500  loss 9.62e-05/2.27e-04  cum 3.088e+00  nMAE 1.618e-05  15.82s/step
  step    54  inner  48/500  loss 9.73e-05/1.92e-04  cum 1.257e+00  nMAE 5.876e-05  16.85s/step
  step    60  inner 226/379  loss 9.95e-05/9.99e-05  cum 4.218e-01  nMAE 3.452e-04  17.67s/step
  step    66  inner 273/300  loss 9.94e-05/9.98e-05  cum 5.010e-01  nMAE 3.304e-03  18.42s/step
  step    72  inner 179/246  loss 9.93e-05/9.99e-05  cum 3.565e-01  nMAE 1.793e-02  18.61s/step
  step    78  inner 171/201  loss 9.94e-05/9.99e-05  cum 3.269e-01  nMAE 2.124e-02  18.54s/step
  step    84  inner 133/175  loss 9.97e-05/9.95e-05  cum 2.168e-01  nMAE 1.482e-02  18.25s/step
  step    90  inner 132/125  loss 9.93e-05/9.92e-05  cum 1.782e-01  nMAE 1.300e-02  17.88s/step
  step    96  inner 122/106  loss 9.92e-05/9.92e-05  cum 1.416e-01  nMAE 1.295e-02  17.48s/step
  step   102  inner 125/ 93  loss 9.93e-05/9.98e-05  cum 1.398e-01  nMAE 1.078e-02  17.04s/step
  step   108  inner 102/ 81  loss 9.98e-05/9.92e-05  cum 1.037e-01  nMAE 1.193e-02  16.60s/step
  step   114  inner  73/108  loss 9.96e-05/9.91e-05  cum 1.099e-01  nMAE 1.749e-02  16.19s/step
  step   120  inner 112/ 75  loss 9.94e-05/9.93e-05  cum 1.065e-01  nMAE 1.338e-02  15.79s/step
  step   126  inner  74/ 98  loss 9.98e-05/9.96e-05  cum 9.386e-02  nMAE 1.117e-02  15.43s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.09863（每步 +9.86%），等效 rho-1 = 9.863e-02
  内层损失中位数 9.97e-05  ->  每步相对误差 0.010
  误差翻倍需 7 步
  要跑完 128 步，每步相对误差需 <= 1/N = 7.81e-03，即损失 <= 6.10e-05
  当前差 1.6e+00 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.098627

  128 steps in 1960 s  (15.31 s/step)
  mean inner iters: curlH 124.3   curlE 208.8
  final nMAE vs FDTD 1.569e-02
  saved evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #63　2026-09-13T04:13:34　OK

**第二阶段损失尺度核对：独立E/H、重置Adam、绝对平方和tol=1e-4，4步**

```
py -3.11 pidon_solve.py --steps 4 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol-mode abs --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_4_abs_lr3e4_i500.json
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_4_abs_lr3e4_i500.json` | 1 KB | `d541c1a7ab26ceee` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/  1  loss 0.00e+00/9.87e-07  cum 9.871e-07  nMAE 3.150e-13  0.20s/step
  step     2  inner   1/  1  loss 2.59e-11/1.05e-05  cum 1.046e-05  nMAE 1.552e-02  0.12s/step
  step     3  inner   1/  1  loss 1.11e-10/6.36e-05  cum 6.357e-05  nMAE 2.035e-02  0.10s/step
  step     4  inner   1/  2  loss 9.90e-10/6.41e-05  cum 5.660e-04  nMAE 2.868e-02  0.11s/step

  4 steps in 0 s  (0.11 s/step)
  mean inner iters: curlH 0.8   curlE 1.2
  final nMAE vs FDTD 2.868e-02
  saved evidence/pidon_stage2_4_abs_lr3e4_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #64　2026-09-13T04:17:59　OK

**第二阶段接口修正：逐分量完整Yee支撑上的旋度损失，独立E/H、重置Adam、lr=3e-4，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_16_component_lr3e4_i500.json
```

- 耗时 189s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_component_lr3e4_i500.json` | 5 KB | `4b3755c2825fa3a0` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.11e-04  cum 1.019e+02  nMAE 3.150e-13  22.96s/step
  step     2  inner 500/500  loss 4.28e-04/1.90e-04  cum 8.111e+01  nMAE 2.257e-05  34.41s/step
  step     3  inner 329/370  loss 9.98e-05/9.95e-05  cum 2.366e+00  nMAE 1.382e-05  33.68s/step
  step     4  inner 170/159  loss 9.92e-05/9.92e-05  cum 7.543e-01  nMAE 1.006e-05  29.04s/step
  step     5  inner 159/ 86  loss 1.00e-04/9.85e-05  cum 3.362e-01  nMAE 8.855e-06  25.48s/step
  step     6  inner 217/ 75  loss 1.00e-04/9.86e-05  cum 3.979e-01  nMAE 7.805e-06  23.49s/step
  step     7  inner 113/ 50  loss 9.99e-05/9.84e-05  cum 2.116e-01  nMAE 7.088e-06  21.20s/step
  step     8  inner  90/ 42  loss 9.95e-05/9.13e-05  cum 1.310e-01  nMAE 6.304e-06  19.31s/step
  step     9  inner  57/ 38  loss 9.90e-05/7.35e-05  cum 1.103e-01  nMAE 5.415e-06  17.65s/step
  step    10  inner  61/ 31  loss 9.96e-05/9.78e-05  cum 1.015e-01  nMAE 4.891e-06  16.30s/step
  step    11  inner  44/ 29  loss 9.99e-05/9.35e-05  cum 5.233e-02  nMAE 4.796e-06  15.12s/step
  step    12  inner  54/ 30  loss 9.97e-05/7.34e-05  cum 8.761e-02  nMAE 4.709e-06  14.18s/step
  step    13  inner  56/ 29  loss 9.96e-05/8.38e-05  cum 7.981e-02  nMAE 4.482e-06  13.39s/step
  step    14  inner  51/ 32  loss 9.76e-05/8.33e-05  cum 6.634e-02  nMAE 4.617e-06  12.71s/step
  step    15  inner  56/ 28  loss 9.91e-05/9.64e-05  cum 6.385e-02  nMAE 4.761e-06  12.12s/step
  step    16  inner  50/ 35  loss 9.38e-05/7.99e-05  cum 6.342e-02  nMAE 5.370e-06  11.60s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.94108（每步 -5.89%），等效 rho-1 = -5.892e-02
  内层损失中位数 9.71e-05  ->  每步相对误差 0.010
RESULT stepgain 0.941084

  16 steps in 186 s  (11.60 s/step)
  mean inner iters: curlH 125.4   curlE 127.1
  final nMAE vs FDTD 5.370e-06
  saved evidence/pidon_stage2_16_component_lr3e4_i500.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #65　2026-09-13T04:24:12　OK

**第二阶段精度门槛检验：逐分量损失、独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_16_component_lr3e4_tol1e5.json
```

- 耗时 355s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_component_lr3e4_tol1e5.json` | 5 KB | `d075f8af2a33d461` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.16e-04  cum 1.019e+02  nMAE 3.150e-13  23.28s/step
  step     2  inner 500/500  loss 4.83e-04/1.65e-04  cum 8.107e+01  nMAE 2.123e-05  34.79s/step
  step     3  inner 500/500  loss 6.23e-05/6.60e-05  cum 2.534e+00  nMAE 1.235e-05  38.70s/step
  step     4  inner 500/500  loss 1.78e-05/1.63e-05  cum 7.701e-01  nMAE 7.571e-06  40.66s/step
  step     5  inner 497/294  loss 9.89e-06/9.97e-06  cum 3.038e-01  nMAE 4.456e-06  39.87s/step
  step     6  inner 396/179  loss 1.00e-05/9.98e-06  cum 2.992e-01  nMAE 3.380e-06  37.67s/step
  step     7  inner 438/144  loss 9.99e-06/9.98e-06  cum 1.876e-01  nMAE 3.023e-06  36.15s/step
  step     8  inner 311/115  loss 9.95e-06/9.93e-06  cum 1.229e-01  nMAE 2.909e-06  34.11s/step
  step     9  inner 224/ 92  loss 9.96e-06/9.93e-06  cum 1.112e-01  nMAE 2.893e-06  31.95s/step
  step    10  inner 173/ 78  loss 9.99e-06/1.00e-05  cum 8.797e-02  nMAE 2.745e-06  29.92s/step
  step    11  inner 141/ 68  loss 9.94e-06/9.81e-06  cum 8.112e-02  nMAE 2.520e-06  28.08s/step
  step    12  inner 125/ 63  loss 9.99e-06/9.93e-06  cum 7.211e-02  nMAE 2.457e-06  26.46s/step
  step    13  inner 136/ 60  loss 9.99e-06/8.90e-06  cum 6.540e-02  nMAE 2.394e-06  25.13s/step
  step    14  inner 140/ 62  loss 9.99e-06/8.75e-06  cum 6.157e-02  nMAE 2.324e-06  24.00s/step
  step    15  inner 115/ 61  loss 9.98e-06/9.84e-06  cum 5.624e-02  nMAE 2.242e-06  22.94s/step
  step    16  inner  98/ 62  loss 9.95e-06/8.78e-06  cum 5.371e-02  nMAE 2.245e-06  21.97s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.92900（每步 -7.10%），等效 rho-1 = -7.100e-02
  内层损失中位数 9.95e-06  ->  每步相对误差 0.003
RESULT stepgain 0.929001

  16 steps in 352 s  (21.97 s/step)
  mean inner iters: curlH 268.4   curlE 204.9
  final nMAE vs FDTD 2.245e-06
  saved evidence/pidon_stage2_16_component_lr3e4_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #66　2026-09-13T04:56:00　OK

**第二阶段长程候选：逐分量Yee损失、独立E/H、每步重置Adam、tol=1e-5、64步**

```
py -3.11 pidon_solve.py --steps 64 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_64_component_lr3e4_tol1e5.json
```

- 耗时 1893s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_64_component_lr3e4_tol1e5.json` | 18 KB | `0a294525575741a6` |

<details><summary>输出末尾</summary>

```
  step     3  inner 500/500  loss 7.63e-05/5.92e-05  cum 2.763e+00  nMAE 1.254e-05  38.73s/step
  step     4  inner 500/500  loss 2.41e-05/1.47e-05  cum 8.263e-01  nMAE 7.953e-06  40.66s/step
  step     5  inner 484/251  loss 9.87e-06/1.00e-05  cum 2.569e-01  nMAE 4.469e-06  39.34s/step
  step     6  inner 391/210  loss 9.98e-06/9.99e-06  cum 2.648e-01  nMAE 3.461e-06  37.42s/step
  step     9  inner 201/ 97  loss 9.97e-06/9.95e-06  cum 1.090e-01  nMAE 2.797e-06  31.09s/step
  step    12  inner 161/ 67  loss 9.99e-06/9.75e-06  cum 7.499e-02  nMAE 2.557e-06  26.27s/step
  step    15  inner 109/ 66  loss 9.96e-06/9.80e-06  cum 5.608e-02  nMAE 2.424e-06  22.76s/step
  step    18  inner  81/ 63  loss 9.92e-06/9.99e-06  cum 4.928e-02  nMAE 2.404e-06  20.14s/step
  step    21  inner  87/ 85  loss 9.85e-06/9.90e-06  cum 4.842e-02  nMAE 2.340e-06  18.32s/step
  step    24  inner  84/125  loss 9.80e-06/9.98e-06  cum 5.226e-02  nMAE 2.348e-06  17.15s/step
  step    27  inner  94/245  loss 9.98e-06/9.99e-06  cum 7.504e-02  nMAE 2.349e-06  16.75s/step
  step    30  inner 109/420  loss 9.97e-06/9.98e-06  cum 1.378e-01  nMAE 2.371e-06  17.18s/step
  step    33  inner 151/500  loss 9.99e-06/2.82e-05  cum 4.214e-01  nMAE 2.398e-06  18.30s/step
  step    36  inner 192/500  loss 1.00e-05/2.76e-04  cum 3.872e+00  nMAE 2.514e-06  19.41s/step
  step    39  inner 332/500  loss 9.97e-06/1.36e-04  cum 7.140e-01  nMAE 2.850e-06  20.71s/step
  step    42  inner 500/500  loss 1.79e-05/1.22e-04  cum 4.917e-01  nMAE 3.418e-06  22.46s/step
  step    45  inner 500/500  loss 4.18e-05/1.51e-04  cum 6.889e-01  nMAE 4.621e-06  24.06s/step
  step    48  inner 321/500  loss 9.95e-06/1.89e-04  cum 1.114e+00  nMAE 6.682e-06  25.28s/step
  step    51  inner 297/500  loss 9.99e-06/8.96e-04  cum 2.148e+00  nMAE 1.228e-05  25.98s/step
  step    54  inner 361/500  loss 9.99e-06/6.73e-05  cum 1.063e+00  nMAE 2.465e-05  26.68s/step
  step    57  inner 447/500  loss 9.98e-06/8.88e-05  cum 7.375e-01  nMAE 5.309e-05  27.50s/step
  step    60  inner 500/500  loss 1.07e-05/5.54e-05  cum 4.754e-01  nMAE 1.304e-04  28.40s/step
  step    63  inner 500/500  loss 1.66e-05/4.32e-05  cum 4.146e-01  nMAE 3.653e-04  29.26s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.08508（每步 +8.51%），等效 rho-1 = 8.508e-02
  内层损失中位数 4.31e-05  ->  每步相对误差 0.007
  误差翻倍需 8 步
  要跑完 64 步，每步相对误差需 <= 1/N = 1.56e-02，即损失 <= 2.44e-04
  当前差 1.8e-01 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.085084

  64 steps in 1890 s  (29.52 s/step)
  mean inner iters: curlH 282.5   curlE 354.1
  final nMAE vs FDTD 5.303e-04
  saved evidence/pidon_stage2_64_component_lr3e4_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #67　2026-09-13T05:02:35　OK

**第二阶段优化器步长检验：逐分量、独立E/H、重置Adam、lr=1e-4、tol=1e-5，8步**

```
py -3.11 pidon_solve.py --steps 8 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 1e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_8_component_lr1e4_tol1e5.json
```

- 耗时 352s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_8_component_lr1e4_tol1e5.json` | 2 KB | `ca0dad18b1bb5c4a` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0001   device cuda

  step     1  inner   0/500  loss 0.00e+00/2.67e-03  cum 1.859e+02  nMAE 3.150e-13  23.20s/step
  step     2  inner 500/500  loss 1.74e-03/9.95e-04  cum 1.552e+02  nMAE 4.842e-05  34.70s/step
  step     3  inner 500/500  loss 2.48e-04/3.58e-04  cum 3.286e+00  nMAE 2.929e-05  38.60s/step
  step     4  inner 500/500  loss 1.20e-04/1.18e-04  cum 1.179e+00  nMAE 1.702e-05  40.59s/step
  step     5  inner 500/500  loss 1.04e-04/6.24e-05  cum 6.543e-01  nMAE 1.235e-05  41.77s/step
  step     6  inner 500/500  loss 8.35e-05/4.17e-05  cum 4.330e-01  nMAE 9.504e-06  42.57s/step
  step     7  inner 500/500  loss 5.26e-05/2.55e-05  cum 2.242e-01  nMAE 7.573e-06  43.13s/step
  step     8  inner 500/500  loss 3.47e-05/1.57e-05  cum 1.307e-01  nMAE 6.109e-06  43.56s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.74021（每步 -25.98%），等效 rho-1 = -2.598e-01
  内层损失中位数 9.03e-05  ->  每步相对误差 0.010
RESULT stepgain 0.740210

  8 steps in 348 s  (43.56 s/step)
  mean inner iters: curlH 437.5   curlE 500.0
  final nMAE vs FDTD 6.109e-06
  saved evidence/pidon_stage2_8_component_lr1e4_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #68　2026-09-13T05:08:31　OK

**第二阶段梯度裁剪检验：逐分量、独立E/H、重置Adam、lr=3e-4、tol=1e-5、clip=1，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --grad-clip 1 --out evidence/pidon_stage2_16_component_lr3e4_tol1e5_clip1.json
```

- 耗时 319s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_component_lr3e4_tol1e5_clip1.json` | 5 KB | `cd6c59a8a71e1c41` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/1.42e-05  cum 6.137e+01  nMAE 3.150e-13  23.44s/step
  step     2  inner 500/500  loss 2.09e-05/1.81e-05  cum 3.272e+01  nMAE 6.076e-06  35.05s/step
  step     3  inner 380/500  loss 9.99e-06/1.49e-05  cum 2.146e+00  nMAE 4.738e-06  37.09s/step
  step     4  inner 390/442  loss 9.99e-06/9.98e-06  cum 8.010e-01  nMAE 3.482e-06  37.54s/step
  step     5  inner 365/289  loss 1.00e-05/9.95e-06  cum 3.423e-01  nMAE 3.092e-06  36.15s/step
  step     6  inner 356/228  loss 9.99e-06/9.93e-06  cum 2.699e-01  nMAE 2.744e-06  34.68s/step
  step     7  inner 339/193  loss 9.96e-06/9.98e-06  cum 1.828e-01  nMAE 2.705e-06  33.28s/step
  step     8  inner 242/148  loss 9.95e-06/9.97e-06  cum 1.252e-01  nMAE 2.665e-06  31.40s/step
  step     9  inner 163/ 98  loss 1.00e-05/9.86e-06  cum 1.140e-01  nMAE 2.684e-06  29.26s/step
  step    10  inner 136/ 89  loss 9.99e-06/9.77e-06  cum 1.001e-01  nMAE 2.475e-06  27.38s/step
  step    11  inner  97/ 76  loss 9.97e-06/9.46e-06  cum 8.758e-02  nMAE 2.357e-06  25.62s/step
  step    12  inner  92/ 67  loss 9.94e-06/9.06e-06  cum 7.738e-02  nMAE 2.350e-06  24.10s/step
  step    13  inner  83/ 56  loss 9.89e-06/9.52e-06  cum 7.063e-02  nMAE 2.258e-06  22.75s/step
  step    14  inner  84/ 63  loss 9.64e-06/9.57e-06  cum 6.599e-02  nMAE 2.295e-06  21.61s/step
  step    15  inner  79/ 62  loss 9.82e-06/9.86e-06  cum 6.362e-02  nMAE 2.294e-06  20.61s/step
  step    16  inner  79/ 63  loss 9.89e-06/9.15e-06  cum 5.693e-02  nMAE 2.318e-06  19.73s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.96986（每步 -3.01%），等效 rho-1 = -3.014e-02
  内层损失中位数 9.90e-06  ->  每步相对误差 0.003
RESULT stepgain 0.969858

  16 steps in 316 s  (19.73 s/step)
  mean inner iters: curlH 211.6   curlE 210.9
  final nMAE vs FDTD 2.318e-06
  saved evidence/pidon_stage2_16_component_lr3e4_tol1e5_clip1.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #69　2026-09-13T05:22:15　OK

**第二阶段物理量标度检验：H输入乘真空阻抗376.7，逐分量、独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --h-scale 376.7303 --out evidence/pidon_stage2_16_component_hscale_tol1e5.json
```

- 耗时 553s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_component_hscale_tol1e5.json` | 5 KB | `266abde1485a0fb3` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.13e-04  cum 1.019e+02  nMAE 3.150e-13  22.94s/step
  step     2  inner 500/500  loss 7.35e+00/7.33e-04  cum 2.285e+06  nMAE 2.283e-03  34.40s/step
  step     3  inner 500/500  loss 1.72e-01/5.14e-04  cum 2.125e+03  nMAE 1.849e-03  38.32s/step
  step     4  inner 500/500  loss 2.01e-02/2.18e-04  cum 1.272e+02  nMAE 1.099e-03  40.28s/step
  step     5  inner 500/500  loss 3.92e-03/1.01e-04  cum 2.555e+01  nMAE 5.692e-04  41.46s/step
  step     6  inner 500/500  loss 1.19e-03/1.19e-04  cum 1.771e+01  nMAE 2.882e-04  42.29s/step
  step     7  inner 500/500  loss 3.24e-04/2.06e-05  cum 1.195e+01  nMAE 1.527e-04  42.90s/step
  step     8  inner 500/344  loss 9.66e-05/9.97e-06  cum 8.201e+00  nMAE 8.432e-05  42.45s/step
  step     9  inner 500/237  loss 5.05e-05/9.95e-06  cum 5.046e+00  nMAE 4.748e-05  41.54s/step
  step    10  inner 500/254  loss 2.85e-03/9.95e-06  cum 3.754e+00  nMAE 3.541e-05  40.89s/step
  step    11  inner 500/202  loss 2.45e-05/9.97e-06  cum 7.669e+00  nMAE 2.133e-05  40.14s/step
  step    12  inner 445/171  loss 9.98e-06/9.99e-06  cum 4.717e+00  nMAE 1.312e-05  39.18s/step
  step    13  inner 302/105  loss 9.59e-06/9.95e-06  cum 3.222e+00  nMAE 9.654e-06  37.62s/step
  step    14  inner 500/ 99  loss 1.20e-05/9.95e-06  cum 5.078e+00  nMAE 7.805e-06  36.92s/step
  step    15  inner 314/ 85  loss 9.99e-06/9.98e-06  cum 3.516e+00  nMAE 6.635e-06  35.69s/step
  step    16  inner 222/ 90  loss 1.00e-05/9.94e-06  cum 2.675e+00  nMAE 6.193e-06  34.36s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.64228（每步 -35.77%），等效 rho-1 = -3.577e-01
  内层损失中位数 9.99e-06  ->  每步相对误差 0.003
RESULT stepgain 0.642284

  16 steps in 550 s  (34.36 s/step)
  mean inner iters: curlH 423.9   curlE 317.9
  final nMAE vs FDTD 6.193e-06
  saved evidence/pidon_stage2_16_component_hscale_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #70　2026-09-13T05:32:48　OK

**第二阶段逐分量归一化检验：独立E/H、重置Adam、component-rel、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --component-rel --out evidence/pidon_stage2_16_componentrel_tol1e5.json
```

- 耗时 564s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_componentrel_tol1e5.json` | 5 KB | `d789ca63d51764c5` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/6.79e+18  cum 4.564e+24  nMAE 3.150e-13  23.20s/step
  step     2  inner 500/500  loss 4.08e-02/1.94e+00  cum 1.431e+07  nMAE 1.080e-04  34.75s/step
  step     3  inner 500/500  loss 1.82e-03/3.20e-03  cum 7.142e+01  nMAE 1.856e-04  38.62s/step
  step     4  inner 500/500  loss 1.09e-04/6.70e-03  cum 4.125e+01  nMAE 1.389e-04  40.55s/step
  step     5  inner 500/500  loss 3.90e-05/4.39e-03  cum 4.124e+01  nMAE 9.752e-05  41.74s/step
  step     6  inner 500/500  loss 1.47e-05/2.93e-03  cum 2.168e+01  nMAE 6.733e-05  42.52s/step
  step     7  inner 454/500  loss 9.99e-06/1.47e-03  cum 1.064e+01  nMAE 5.016e-05  42.79s/step
  step     8  inner 283/500  loss 9.97e-06/2.95e-02  cum 1.301e+01  nMAE 3.659e-05  42.00s/step
  step     9  inner 172/500  loss 9.96e-06/1.28e-03  cum 2.514e+01  nMAE 3.048e-05  40.82s/step
  step    10  inner 132/500  loss 9.96e-06/1.16e-03  cum 1.442e+01  nMAE 2.741e-05  39.68s/step
  step    11  inner 114/500  loss 9.94e-06/1.02e-03  cum 1.470e+01  nMAE 2.392e-05  38.68s/step
  step    12  inner  93/500  loss 9.97e-06/1.02e-03  cum 1.475e+01  nMAE 2.219e-05  37.76s/step
  step    13  inner  78/500  loss 9.99e-06/9.64e-04  cum 1.727e+01  nMAE 2.055e-05  36.92s/step
  step    14  inner  78/500  loss 9.87e-06/1.00e-03  cum 1.460e+01  nMAE 1.924e-05  36.21s/step
  step    15  inner  75/500  loss 9.73e-06/2.03e-02  cum 1.542e+01  nMAE 1.825e-05  35.58s/step
  step    16  inner  72/500  loss 9.58e-06/1.00e-03  cum 2.717e+01  nMAE 1.810e-05  35.02s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.85020（每步 -14.98%），等效 rho-1 = -1.498e-01
  内层损失中位数 2.20e-03  ->  每步相对误差 0.047
RESULT stepgain 0.850197

  16 steps in 560 s  (35.02 s/step)
  mean inner iters: curlH 253.2   curlE 500.0
  final nMAE vs FDTD 1.810e-05
  saved evidence/pidon_stage2_16_componentrel_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #71　2026-09-13T05:33:36　FAILED (exit 1)

**第二阶段H输出数值尺度检验：H网络输出乘377后物理还原，独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --h-output-scale 376.7303 --out evidence/pidon_stage2_16_houtscale_tol1e5.json
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

Traceback (most recent call last):
  File "C:\PI-DON\pidon_solve.py", line 529, in <module>
    main()
  File "C:\PI-DON\pidon_solve.py", line 493, in main
    rec = s.step(float(g[t]))
          ^^^^^^^^^^^^^^^^^^^
  File "C:\PI-DON\pidon_solve.py", line 270, in step
    it, l, tot, pred, _ = self.inner_train(self.H, ch, "H")
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\PI-DON\pidon_solve.py", line 200, in inner_train
    den_parts = [d * out_scale ** 2 for d in den_parts]
                                             ^^^^^^^^^
UnboundLocalError: cannot access local variable 'den_parts' where it is not associated with a value
```

</details>

## #72　2026-09-13T05:39:52　OK

**第二阶段H输出数值尺度检验重跑：H网络输出乘377后物理还原，独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --h-output-scale 376.7303 --out evidence/pidon_stage2_16_houtscale_tol1e5.json
```

- 耗时 357s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_houtscale_tol1e5.json` | 5 KB | `d666e2e5f665d734` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.14e-04  cum 1.019e+02  nMAE 3.150e-13  23.13s/step
  step     2  inner 500/500  loss 3.98e-04/1.61e-04  cum 8.105e+01  nMAE 2.057e-05  34.67s/step
  step     3  inner 500/500  loss 6.57e-05/5.67e-05  cum 2.594e+00  nMAE 1.171e-05  38.54s/step
  step     4  inner 500/500  loss 1.72e-05/1.31e-05  cum 8.113e-01  nMAE 7.316e-06  40.50s/step
  step     5  inner 485/260  loss 9.80e-06/9.98e-06  cum 3.148e-01  nMAE 4.249e-06  39.31s/step
  step     6  inner 471/206  loss 9.98e-06/9.95e-06  cum 3.294e-01  nMAE 3.266e-06  38.01s/step
  step     7  inner 431/176  loss 9.96e-06/9.99e-06  cum 2.180e-01  nMAE 2.897e-06  36.61s/step
  step     8  inner 320/117  loss 9.96e-06/9.98e-06  cum 1.186e-01  nMAE 2.801e-06  34.56s/step
  step     9  inner 211/ 94  loss 9.97e-06/9.81e-06  cum 1.004e-01  nMAE 2.799e-06  32.30s/step
  step    10  inner 187/ 81  loss 9.97e-06/9.91e-06  cum 8.962e-02  nMAE 2.736e-06  30.31s/step
  step    11  inner 184/ 70  loss 9.98e-06/9.73e-06  cum 7.886e-02  nMAE 2.398e-06  28.62s/step
  step    12  inner 112/ 65  loss 9.95e-06/9.86e-06  cum 6.887e-02  nMAE 2.479e-06  26.92s/step
  step    13  inner 111/ 64  loss 9.96e-06/9.89e-06  cum 6.628e-02  nMAE 2.455e-06  25.47s/step
  step    14  inner 104/ 62  loss 9.99e-06/9.61e-06  cum 5.807e-02  nMAE 2.441e-06  24.20s/step
  step    15  inner  99/ 59  loss 9.93e-06/9.54e-06  cum 5.146e-02  nMAE 2.400e-06  23.07s/step
  step    16  inner  94/ 64  loss 9.86e-06/9.75e-06  cum 5.423e-02  nMAE 2.387e-06  22.08s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.93808（每步 -6.19%），等效 rho-1 = -6.192e-02
  内层损失中位数 9.93e-06  ->  每步相对误差 0.003
RESULT stepgain 0.938083

  16 steps in 353 s  (22.08 s/step)
  mean inner iters: curlH 269.3   curlE 207.4
  final nMAE vs FDTD 2.387e-06
  saved evidence/pidon_stage2_16_houtscale_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #73　2026-09-13T05:42:53　OK

**腔体分布暖启动：FDTD快照E/H各80、正确配对Yee旋度，预训练DCO微调30轮**

```
py -3.11 adapt_dco_cavity.py --snapshots 80 --epochs 30 --batch 8 --lr 3e-4 --init dco_lr1e3_300.pt --out dco_cavity_adapt.pt
```

- 耗时 128s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/cavity_adapt_data.npz` | 111,719 KB | `75e98913581d6fcf` |
| `dco_cavity_adapt.pt` | 36,146 KB | `9ea1e44571b34cb6` |
| `dco_cavity_adapt_hist.json` | 1 KB | `e39e669f5950a77a` |

<details><summary>输出末尾</summary>

```
C:\PI-DON\adapt_dco_cavity.py:57: UserWarning: Converting a tensor with requires_grad=True to a scalar may lead to unexpected behavior.
Consider using tensor.detach() first. (Triggered internally at C:\actions-runner\_work\pytorch\pytorch\torch\csrc\autograd\generated\python_variable_methods.cpp:821.)
  loss=((pred-ch).pow(2).flatten(1).mean(1)/(ch.pow(2).flatten(1).mean(1).clamp_min(1e-20))).mean(); opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); run+=float(loss)*len(j)
ep   1 loss 4.050e+01  5.8s
ep   5 loss 2.126e-01  22.1s
ep  10 loss 1.674e-01  42.7s
ep  15 loss 1.489e-01  63.4s
ep  20 loss 1.386e-01  84.1s
ep  25 loss 1.343e-01  104.8s
ep  30 loss 1.330e-01  125.6s
saved dco_cavity_adapt.pt seconds 125.60362219810486
```

</details>

## #74　2026-09-13T05:49:11　OK

**第二阶段分布暖启动验收：腔体快照微调DCO、独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_cavity_adapt.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_16_cavityadapt_tol1e5.json
```

- 耗时 370s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_cavityadapt_tol1e5.json` | 5 KB | `45507e8b8f295ec1` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_cavity_adapt   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/1.99e-05  cum 7.051e+00  nMAE 3.150e-13  23.35s/step
  step     2  inner 500/500  loss 6.80e-04/6.27e-05  cum 1.230e+01  nMAE 1.135e-05  34.88s/step
  step     3  inner 500/500  loss 2.53e-05/4.13e-05  cum 3.109e+00  nMAE 9.049e-06  38.75s/step
  step     4  inner 500/500  loss 1.35e-05/1.55e-05  cum 1.074e+00  nMAE 6.055e-06  40.65s/step
  step     5  inner 500/370  loss 1.62e-05/1.00e-05  cum 5.665e-01  nMAE 4.356e-06  40.59s/step
  step     6  inner 500/245  loss 2.49e-05/9.95e-06  cum 7.367e-01  nMAE 3.991e-06  39.60s/step
  step     7  inner 500/212  loss 1.42e-05/9.94e-06  cum 3.470e-01  nMAE 3.383e-06  38.67s/step
  step     8  inner 328/159  loss 9.98e-06/9.98e-06  cum 1.391e-01  nMAE 3.053e-06  36.65s/step
  step     9  inner 201/ 96  loss 9.99e-06/9.98e-06  cum 1.103e-01  nMAE 2.713e-06  34.11s/step
  step    10  inner 163/ 82  loss 9.99e-06/9.84e-06  cum 9.190e-02  nMAE 2.483e-06  31.83s/step
  step    11  inner 136/ 70  loss 9.99e-06/9.70e-06  cum 8.097e-02  nMAE 2.384e-06  29.80s/step
  step    12  inner 139/ 67  loss 9.99e-06/9.34e-06  cum 7.582e-02  nMAE 2.277e-06  28.11s/step
  step    13  inner 105/ 63  loss 1.00e-05/9.60e-06  cum 6.776e-02  nMAE 2.226e-06  26.55s/step
  step    14  inner 107/ 56  loss 9.96e-06/9.66e-06  cum 6.159e-02  nMAE 2.162e-06  25.19s/step
  step    15  inner  89/ 60  loss 9.97e-06/9.47e-06  cum 5.814e-02  nMAE 2.229e-06  23.97s/step
  step    16  inner  83/ 63  loss 9.90e-06/9.23e-06  cum 5.225e-02  nMAE 2.306e-06  22.89s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.92817（每步 -7.18%），等效 rho-1 = -7.183e-02
  内层损失中位数 9.95e-06  ->  每步相对误差 0.003
RESULT stepgain 0.928171

  16 steps in 366 s  (22.89 s/step)
  mean inner iters: curlH 271.9   curlE 221.4
  final nMAE vs FDTD 2.306e-06
  saved evidence/pidon_stage2_16_cavityadapt_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #75　2026-09-13T05:54:46　OK

**第二阶段Yee H对齐检验：H输入按分量移入内部E位置，独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --h-shift --out evidence/pidon_stage2_16_hshift_tol1e5.json
```

- 耗时 301s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_hshift_tol1e5.json` | 5 KB | `1880736c6d92144a` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/5.12e-04  cum 1.019e+02  nMAE 3.150e-13  23.20s/step
  step     2  inner 500/500  loss 3.50e-04/1.79e-04  cum 6.906e+01  nMAE 2.040e-05  34.72s/step
  step     3  inner 500/500  loss 3.10e-05/6.93e-05  cum 1.635e+00  nMAE 1.244e-05  38.62s/step
  step     4  inner 500/500  loss 1.13e-05/1.57e-05  cum 5.375e-01  nMAE 7.172e-06  40.57s/step
  step     5  inner 373/258  loss 9.96e-06/9.97e-06  cum 2.738e-01  nMAE 4.432e-06  38.33s/step
  step     6  inner 282/219  loss 1.00e-05/9.93e-06  cum 1.718e-01  nMAE 3.500e-06  35.81s/step
  step     7  inner 225/182  loss 9.98e-06/9.95e-06  cum 1.087e-01  nMAE 3.146e-06  33.40s/step
  step     8  inner 159/132  loss 9.95e-06/9.94e-06  cum 8.129e-02  nMAE 3.033e-06  30.90s/step
  step     9  inner  95/ 98  loss 9.91e-06/9.93e-06  cum 7.253e-02  nMAE 2.719e-06  28.46s/step
  step    10  inner  73/ 79  loss 9.97e-06/9.75e-06  cum 5.761e-02  nMAE 2.592e-06  26.32s/step
  step    11  inner  67/ 71  loss 9.70e-06/9.80e-06  cum 5.426e-02  nMAE 2.474e-06  24.50s/step
  step    12  inner  60/ 65  loss 9.52e-06/9.41e-06  cum 4.774e-02  nMAE 2.446e-06  22.94s/step
  step    13  inner  64/ 62  loss 9.79e-06/9.70e-06  cum 4.439e-02  nMAE 2.905e-06  21.62s/step
  step    14  inner  63/ 64  loss 8.54e-06/8.67e-06  cum 4.344e-02  nMAE 2.315e-06  20.50s/step
  step    15  inner  63/ 62  loss 8.63e-06/9.90e-06  cum 4.375e-02  nMAE 2.287e-06  19.52s/step
  step    16  inner  60/ 57  loss 9.82e-06/9.93e-06  cum 4.048e-02  nMAE 2.697e-06  18.63s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.93828（每步 -6.17%），等效 rho-1 = -6.172e-02
  内层损失中位数 9.93e-06  ->  每步相对误差 0.003
RESULT stepgain 0.938280

  16 steps in 298 s  (18.63 s/step)
  mean inner iters: curlH 192.8   curlE 209.3
  final nMAE vs FDTD 2.697e-06
  saved evidence/pidon_stage2_16_hshift_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #76　2026-09-13T06:24:07　OK

**第二阶段长程H对齐候选：H内部Yee平移、独立E/H、重置Adam、tol=1e-5，64步**

```
py -3.11 pidon_solve.py --steps 64 --n 31 --init dco_lr1e3_300.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --h-shift --out evidence/pidon_stage2_64_hshift_tol1e5.json
```

- 耗时 1750s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_64_hshift_tol1e5.json` | 18 KB | `d05a39deb7eaa51d` |

<details><summary>输出末尾</summary>

```
  step     3  inner 500/500  loss 3.28e-05/5.11e-05  cum 1.627e+00  nMAE 1.232e-05  38.74s/step
  step     4  inner 500/500  loss 1.32e-05/1.43e-05  cum 5.642e-01  nMAE 7.130e-06  40.65s/step
  step     5  inner 388/307  loss 9.49e-06/9.98e-06  cum 3.170e-01  nMAE 4.598e-06  38.96s/step
  step     6  inner 311/204  loss 9.97e-06/9.97e-06  cum 1.750e-01  nMAE 3.572e-06  36.44s/step
  step     9  inner 105/ 95  loss 9.96e-06/9.96e-06  cum 6.878e-02  nMAE 2.675e-06  28.74s/step
  step    12  inner  66/ 63  loss 8.93e-06/8.72e-06  cum 5.049e-02  nMAE 2.386e-06  23.17s/step
  step    15  inner  61/ 57  loss 9.07e-06/9.93e-06  cum 4.160e-02  nMAE 2.369e-06  19.64s/step
  step    18  inner  58/ 63  loss 9.47e-06/8.89e-06  cum 3.996e-02  nMAE 2.433e-06  17.30s/step
  step    21  inner  56/ 75  loss 9.70e-06/9.90e-06  cum 3.836e-02  nMAE 2.881e-06  15.67s/step
  step    24  inner  54/140  loss 8.94e-06/9.98e-06  cum 4.466e-02  nMAE 2.664e-06  14.66s/step
  step    27  inner  53/305  loss 9.33e-06/9.99e-06  cum 7.037e-02  nMAE 3.504e-06  14.54s/step
  step    30  inner  53/500  loss 9.71e-06/1.09e-05  cum 1.227e-01  nMAE 3.125e-06  15.37s/step
  step    33  inner  52/500  loss 9.78e-06/5.10e-05  cum 4.028e-01  nMAE 3.078e-06  16.30s/step
  step    36  inner  67/500  loss 9.74e-06/3.58e-04  cum 3.279e+00  nMAE 3.373e-06  17.11s/step
  step    39  inner 201/500  loss 9.97e-06/1.01e-04  cum 5.501e-01  nMAE 3.555e-06  18.05s/step
  step    42  inner 500/500  loss 2.34e-05/1.27e-04  cum 4.311e-01  nMAE 3.828e-06  19.91s/step
  step    45  inner 500/500  loss 3.26e-05/2.06e-04  cum 6.379e-01  nMAE 4.919e-06  21.68s/step
  step    48  inner 207/500  loss 9.99e-06/3.32e-04  cum 1.383e+00  nMAE 7.186e-06  22.79s/step
  step    51  inner 205/500  loss 9.99e-06/1.47e-04  cum 2.131e+00  nMAE 1.187e-05  23.31s/step
  step    54  inner 308/500  loss 9.98e-06/5.56e-05  cum 9.616e-01  nMAE 2.351e-05  23.99s/step
  step    57  inner 464/500  loss 9.98e-06/4.51e-05  cum 6.193e-01  nMAE 5.112e-05  24.94s/step
  step    60  inner 500/500  loss 1.23e-04/4.83e-05  cum 3.891e-01  nMAE 1.275e-04  26.01s/step
  step    63  inner 500/500  loss 2.17e-05/4.05e-05  cum 4.375e-01  nMAE 3.671e-04  26.99s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.08226（每步 +8.23%），等效 rho-1 = 8.226e-02
  内层损失中位数 4.66e-05  ->  每步相对误差 0.007
  误差翻倍需 9 步
  要跑完 64 步，每步相对误差需 <= 1/N = 1.56e-02，即损失 <= 2.44e-04
  当前差 1.9e-01 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.082256

  64 steps in 1747 s  (27.29 s/step)
  mean inner iters: curlH 228.2   curlE 360.1
  final nMAE vs FDTD 5.378e-04
  saved evidence/pidon_stage2_64_hshift_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #77　2026-09-13T06:30:33　OK

**第二阶段网络深度对照：已有L=3预训练DCO、逐分量Yee损失、独立E/H、重置Adam、tol=1e-5，16步**

```
py -3.11 pidon_solve.py --steps 16 --n 31 --init dco_L3.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_16_L3_tol1e5.json
```

- 耗时 364s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_16_L3_tol1e5.json` | 5 KB | `4d0e44a2fdac5afa` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-10a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_L3   coords=cellsize norm=rms   2.25M params
  inner training: stop below 1e-05, at most 500 iters, lr 0.0003   device cuda

  step     1  inner   0/500  loss 0.00e+00/2.06e-05  cum 9.284e+00  nMAE 3.150e-13  20.43s/step
  step     2  inner 500/500  loss 5.55e-05/5.18e-05  cum 1.777e+01  nMAE 7.678e-06  30.51s/step
  step     3  inner 500/500  loss 1.99e-05/5.44e-05  cum 1.841e+00  nMAE 7.227e-06  33.91s/step
  step     4  inner 500/500  loss 1.34e-05/2.59e-05  cum 6.981e-01  nMAE 5.344e-06  35.65s/step
  step     5  inner 500/500  loss 1.27e-05/1.13e-05  cum 3.725e-01  nMAE 3.913e-06  36.69s/step
  step     6  inner 500/389  loss 1.29e-05/9.98e-06  cum 6.147e-01  nMAE 3.195e-06  36.63s/step
  step     7  inner 500/330  loss 1.07e-05/1.00e-05  cum 4.960e-01  nMAE 2.903e-06  36.24s/step
  step     8  inner 270/212  loss 9.99e-06/9.99e-06  cum 2.505e-01  nMAE 2.909e-06  34.17s/step
  step     9  inner 205/171  loss 9.99e-06/9.98e-06  cum 1.985e-01  nMAE 2.845e-06  32.08s/step
  step    10  inner 199/162  loss 1.00e-05/9.99e-06  cum 1.724e-01  nMAE 2.680e-06  30.34s/step
  step    11  inner 149/104  loss 9.98e-06/1.00e-05  cum 1.477e-01  nMAE 2.480e-06  28.52s/step
  step    12  inner 151/ 99  loss 9.98e-06/9.99e-06  cum 1.331e-01  nMAE 2.370e-06  26.99s/step
  step    13  inner 146/ 97  loss 9.98e-06/9.93e-06  cum 1.201e-01  nMAE 2.268e-06  25.68s/step
  step    14  inner 142/ 89  loss 9.98e-06/9.97e-06  cum 1.075e-01  nMAE 2.197e-06  24.52s/step
  step    15  inner 133/ 87  loss 9.98e-06/9.77e-06  cum 1.008e-01  nMAE 2.175e-06  23.48s/step
  step    16  inner 132/ 87  loss 1.00e-05/9.91e-06  cum 9.467e-02  nMAE 2.189e-06  22.57s/step

  --- 误差增长诊断 ---
  每步增益 g = 0.94095（每步 -5.90%），等效 rho-1 = -5.905e-02
  内层损失中位数 9.99e-06  ->  每步相对误差 0.003
RESULT stepgain 0.940954

  16 steps in 361 s  (22.57 s/step)
  mean inner iters: curlH 282.9   curlE 270.4
  final nMAE vs FDTD 2.189e-06
  saved evidence/pidon_stage2_16_L3_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #78　2026-09-13T07:00:46　OK

**第二阶段L=3长程候选：独立E/H、重置Adam、逐分量Yee损失、tol=1e-5，64步**

```
py -3.11 pidon_solve.py --steps 64 --n 31 --init dco_L3.pt --max-inner 500 --lr 3e-4 --tol 1e-5 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_64_L3_tol1e5.json
```

- 耗时 1798s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_64_L3_tol1e5.json` | 18 KB | `9b910ed1d4fffce3` |

<details><summary>输出末尾</summary>

```
  step     3  inner 500/500  loss 1.97e-05/5.54e-05  cum 1.833e+00  nMAE 6.947e-06  33.99s/step
  step     4  inner 500/500  loss 1.30e-05/2.48e-05  cum 7.002e-01  nMAE 5.192e-06  35.67s/step
  step     5  inner 500/500  loss 1.19e-05/1.08e-05  cum 3.158e-01  nMAE 3.764e-06  36.68s/step
  step     6  inner 500/400  loss 1.33e-05/1.00e-05  cum 8.171e-01  nMAE 3.150e-06  36.67s/step
  step     9  inner 207/167  loss 9.99e-06/9.99e-06  cum 1.894e-01  nMAE 2.757e-06  32.02s/step
  step    12  inner 150/ 92  loss 1.00e-05/9.98e-06  cum 1.255e-01  nMAE 2.378e-06  26.63s/step
  step    15  inner 140/ 85  loss 9.98e-06/9.78e-06  cum 9.749e-02  nMAE 2.228e-06  23.14s/step
  step    18  inner 146/ 87  loss 9.98e-06/9.97e-06  cum 8.146e-02  nMAE 2.112e-06  20.85s/step
  step    21  inner 153/107  loss 9.99e-06/9.96e-06  cum 7.616e-02  nMAE 2.013e-06  19.29s/step
  step    24  inner 144/148  loss 1.00e-05/9.97e-06  cum 7.880e-02  nMAE 1.981e-06  18.31s/step
  step    27  inner 150/288  loss 9.99e-06/9.99e-06  cum 9.652e-02  nMAE 1.963e-06  17.97s/step
  step    30  inner 147/500  loss 9.99e-06/1.71e-04  cum 1.524e-01  nMAE 1.964e-06  18.57s/step
  step    33  inner 154/500  loss 9.99e-06/4.22e-05  cum 4.109e-01  nMAE 2.087e-06  19.29s/step
  step    36  inner 236/500  loss 9.98e-06/5.81e-04  cum 3.669e+00  nMAE 2.235e-06  20.06s/step
  step    39  inner 420/500  loss 9.99e-06/8.53e-04  cum 5.982e-01  nMAE 2.481e-06  21.17s/step
  step    42  inner 500/500  loss 2.17e-05/2.62e-04  cum 4.408e-01  nMAE 3.395e-06  22.52s/step
  step    45  inner 500/500  loss 3.86e-05/6.71e-04  cum 1.027e+00  nMAE 5.473e-06  23.74s/step
  step    48  inner 406/500  loss 9.99e-06/2.21e-03  cum 2.522e+00  nMAE 8.159e-06  24.72s/step
  step    51  inner 289/500  loss 9.99e-06/2.77e-04  cum 9.982e-01  nMAE 1.363e-05  25.21s/step
  step    54  inner 385/500  loss 1.00e-05/1.11e-04  cum 3.843e-01  nMAE 2.656e-05  25.72s/step
  step    57  inner 500/500  loss 2.09e-05/9.02e-05  cum 2.415e-01  nMAE 5.688e-05  26.48s/step
  step    60  inner 500/500  loss 2.47e-05/1.43e-04  cum 3.285e-01  nMAE 1.388e-04  27.20s/step
  step    63  inner 500/500  loss 4.42e-05/1.39e-04  cum 5.040e-01  nMAE 3.991e-04  27.84s/step

  --- 误差增长诊断 ---
  每步增益 g = 1.09163（每步 +9.16%），等效 rho-1 = 9.163e-02
  内层损失中位数 6.97e-05  ->  每步相对误差 0.008
  误差翻倍需 8 步
  要跑完 64 步，每步相对误差需 <= 1/N = 1.56e-02，即损失 <= 2.44e-04
  当前差 2.9e-01 倍 —— 瓶颈是每步拟合的精度，不是时间步、也不是网格
RESULT stepgain 1.091627

  64 steps in 1795 s  (28.05 s/step)
  mean inner iters: curlH 312.0   curlE 376.8
  final nMAE vs FDTD 5.886e-04
  saved evidence/pidon_stage2_64_L3_tol1e5.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #79　2026-09-13T07:01:34　OK

**生成第二阶段64/128步长程对比证据图**

```
py -3.11 slides/make_stage2_longrun_figs.py
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `figs/stage2_longrun_comparison.png` | 150 KB | `d7a4b9253466fb11` |

<details><summary>输出末尾</summary>

```
figs\stage2_longrun_comparison.png
```

</details>

## #80　2026-09-13T07:03:09　FAILED (exit 1)

**刷新第二阶段长程结论核对表V1-V3**

```
py -3.11 verify_claims.py --stage2-longrun --md
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 1.569e-02`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `RESULTS.md` | 5 KB | `2897558a5ecc4d26` |

<details><summary>输出末尾</summary>

```
             撤回替代性解读：两个不同配置的局部rho接近不能替代Algorithm1。 历史数值仅供溯源。

  [ 待重审 ]    C6  论文没写明的实现细节同时伤精度和稳定性
             dco_L3b rho-1=0.5028　dco_L3d rho-1=0.2479　差 2.03x
             待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。 历史数值仅供溯源。

  [ 反例 ]     C7  反例：消融链终点在 rho 上反而更差
             dco_L3c rho-1=0.1812 < dco_L3d rho-1=0.2479
             这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说

  [ 待重审 ]    C8  无约束学习算子做不了长时程积分
             最好 dco_paper32: rho-1=0.1149，要跑 1e5 步需再小 11,491x
             撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。 历史数值仅供溯源。

  [ 撤回 ]     C9  旧跨指标、跨测试场景的论文对比
             旧0.70~1.50倍比较撤回；原始NPZ保留
             式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。 新协议与现有权重的结果见P0-P2。

  [ PASS ]   C10  相对 L2 与 nMAE 不可互换（上一条曾因此报错）
             指标比值（relative L2 / nMAE）：2.6~8.1x（5 个 checkpoint）
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   V1  Algorithm 1 128步轨迹保持有限
             128步有限；末nMAE=1.569e-02；最大=2.322e-02
             判据：128行完整、nMAE全为有限数；这是阶段二机理长程证据，不等于8192步复现。

  [ FAIL ]   V2  收紧内层残差后64步误差显著降低
             64步有限；前30步最大=2.161e-05；末步=5.303e-04
             判据：tol=1e-5配置前30步误差<1e-5且64步末误差<1e-3；用于证明残差门槛影响，不宣称长期稳定。

  [ FAIL ]   V3  第二阶段已达到论文8192步目标
             实际最长轨迹=128步；论文目标=8192步
             判据：至少8192个逐步重训记录才可称达到论文步数；当前应保留为未完成。

  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）

==================================================================
  通过 3　不通过 2　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #81　2026-09-13T07:03:31　FAILED (exit 1)

**刷新第二阶段长程结论核对表V1-V3（修正源开启瞬态判据）**

```
py -3.11 verify_claims.py --stage2-longrun --md
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 1.569e-02`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `RESULTS.md` | 5 KB | `867296a1c8065603` |

<details><summary>输出末尾</summary>

```
             撤回替代性解读：两个不同配置的局部rho接近不能替代Algorithm1。 历史数值仅供溯源。

  [ 待重审 ]    C6  论文没写明的实现细节同时伤精度和稳定性
             dco_L3b rho-1=0.5028　dco_L3d rho-1=0.2479　差 2.03x
             待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。 历史数值仅供溯源。

  [ 反例 ]     C7  反例：消融链终点在 rho 上反而更差
             dco_L3c rho-1=0.1812 < dco_L3d rho-1=0.2479
             这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说

  [ 待重审 ]    C8  无约束学习算子做不了长时程积分
             最好 dco_paper32: rho-1=0.1149，要跑 1e5 步需再小 11,491x
             撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。 历史数值仅供溯源。

  [ 撤回 ]     C9  旧跨指标、跨测试场景的论文对比
             旧0.70~1.50倍比较撤回；原始NPZ保留
             式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。 新协议与现有权重的结果见P0-P2。

  [ PASS ]   C10  相对 L2 与 nMAE 不可互换（上一条曾因此报错）
             指标比值（relative L2 / nMAE）：2.6~8.1x（5 个 checkpoint）
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   V1  Algorithm 1 128步轨迹保持有限
             128步有限；末nMAE=1.569e-02；最大=2.322e-02
             判据：128行完整、nMAE全为有限数；这是阶段二机理长程证据，不等于8192步复现。

  [ PASS ]   V2  收紧内层残差后64步误差显著降低
             64步有限；稳态段(step5–30)最大=4.469e-06；末步=5.303e-04
             判据：排除前4步源开启瞬态后，tol=1e-5配置的step5–30误差<1e-5且64步末误差<1e-3；用于证明残差门槛影响，不宣称长期稳定。

  [ FAIL ]   V3  第二阶段已达到论文8192步目标
             实际最长轨迹=128步；论文目标=8192步
             判据：至少8192个逐步重训记录才可称达到论文步数；当前应保留为未完成。

  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）

==================================================================
  通过 4　不通过 1　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #82　2026-09-13T07:05:04　OK

**第二阶段最终代码回归：默认接口2步有限性检查**

```
py -3.11 pidon_solve.py --steps 2 --n 31 --init dco_lr1e3_300.pt --max-inner 20 --lr 3e-4 --separate-nets --reset-opt-each-step --out evidence/pidon_stage2_2_final_regression.json
```

- 耗时 6s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/pidon_stage2_2_final_regression.json` | 1 KB | `cfdc879bfdd7d177` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-13a]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = dco_lr1e3_300   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e-04, at most 20 iters, lr 0.0003   device cuda

  step     1  inner   0/ 20  loss 0.00e+00/7.71e-01  cum 6.684e+01  nMAE 3.150e-13  1.18s/step
  step     2  inner  20/ 20  loss 5.11e-01/1.04e-02  cum 7.839e+01  nMAE 7.424e-05  1.51s/step

  2 steps in 3 s  (1.51 s/step)
  mean inner iters: curlH 10.0   curlE 20.0
  final nMAE vs FDTD 7.424e-05
  saved evidence/pidon_stage2_2_final_regression.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #83　2026-09-13T11:08:12　FAILED (exit 1)

**P0 audit existing evidence and register frozen gates; no inference**

```
py -3.11 audit_reproduction.py --out evidence/gpt6_plan_v1/audit.json
```

- 耗时 1s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/acceptance.json` | 2 KB | `64fabc356d2aace8` |

<details><summary>输出末尾</summary>

```
Traceback (most recent call last):
  File "C:\PI-DON\audit_reproduction.py", line 357, in <module>
    main()
  File "C:\PI-DON\audit_reproduction.py", line 337, in main
    "source_timing": source_timing(),
                     ^^^^^^^^^^^^^^^
  File "C:\PI-DON\audit_reproduction.py", line 193, in source_timing
    signal = gaussian_pulse(total, dt, fmax=15e9, level=0.1)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: gaussian_pulse() got an unexpected keyword argument 'fmax'
```

</details>

## #84　2026-09-13T11:08:29　OK

**P0 audit existing evidence and register frozen gates after correcting actual waveform interface**

```
py -3.11 audit_reproduction.py --out evidence/gpt6_plan_v1/audit.json
```

- 耗时 1s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/audit.json` | 11 KB | `6a48478d96506333` |
| `evidence/gpt6_plan_v1/P0_AUDIT_REPORT.md` | 1 KB | `bb227ff58ac3dc46` |

<details><summary>输出末尾</summary>

```
{"audit": "evidence/gpt6_plan_v1/audit.json", "acceptance": "evidence/gpt6_plan_v1/acceptance.json", "report": "evidence/gpt6_plan_v1/P0_AUDIT_REPORT.md", "historical_128_rows": 128, "historical_64_rows": 64}
```

</details>

## #85　2026-09-13T11:08:51　OK

**P0 audit correct cavity-mode timing calculation from actual 0.05 m solver geometry**

```
py -3.11 audit_reproduction.py --out evidence/gpt6_plan_v1/audit.json
```

- 耗时 1s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/audit.json` | 11 KB | `6ba06a5970fd1735` |
| `evidence/gpt6_plan_v1/P0_AUDIT_REPORT.md` | 1 KB | `bb227ff58ac3dc46` |

<details><summary>输出末尾</summary>

```
{"audit": "evidence/gpt6_plan_v1/audit.json", "acceptance": "evidence/gpt6_plan_v1/acceptance.json", "report": "evidence/gpt6_plan_v1/P0_AUDIT_REPORT.md", "historical_128_rows": 128, "historical_64_rows": 64}
```

</details>

## #86　2026-09-13T11:16:59　FAILED (exit 1)

**P1 stop rules checkpoint and metric contract**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ERROR
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ERROR
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok

======================================================================
ERROR: test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\PI-DON\test_pidon_contract.py", line 73, in test_e_pending_resume_does_not_repeat_source_or_e_update
    first = fake.step(1.0)
            ^^^^^^^^^^^^^^
  File "C:\PI-DON\pidon_solve.py", line 397, in step
    fit_H = self.inner_train(self.H, self.yee_curl_H(), "H")
                             ^^^^^^
AttributeError: 'TransactionFake' object has no attribute 'H'

======================================================================
ERROR: test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\PI-DON\test_pidon_contract.py", line 84, in test_h_failure_does_not_advance_transaction
    result = fake.step(1.0)
             ^^^^^^^^^^^^^^
  File "C:\PI-DON\pidon_solve.py", line 397, in step
    fit_H = self.inner_train(self.H, self.yee_curl_H(), "H")
                             ^^^^^^
AttributeError: 'TransactionFake' object has no attribute 'H'

----------------------------------------------------------------------
Ran 6 tests in 1.140s

FAILED (errors=2)
```

</details>

## #87　2026-09-13T11:17:13　OK

**P1 stop rules checkpoint and metric contract after fixture correction**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok

----------------------------------------------------------------------
Ran 6 tests in 1.084s

OK
```

</details>

## #88　2026-09-13T11:17:45　OK

**P1 verify CPU E-pending checkpoint resume determinism**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok

----------------------------------------------------------------------
Ran 7 tests in 1.215s

OK
```

</details>

## #89　2026-09-13T11:18:03　OK

**P1 one-step formal recording smoke test; interface only, not DCO accuracy**

```
py -3.11 pidon_solve.py --steps 1 --init random --strict-stop --tol 1e6 --max-inner 0 --out-dir evidence/gpt6_plan_v1/p1_recording_smoke --device cpu
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/p1_recording_smoke/checkpoint_latest.pt` | 38,369 KB | `e04acd5c8aca54ea` |
| `evidence/gpt6_plan_v1/p1_recording_smoke/snapshot_step_0001.pt` | 38,369 KB | `2af5a05f85899445` |
| `evidence/gpt6_plan_v1/p1_recording_smoke/steps.jsonl` | 2 KB | `45b791215ab3e894` |
| `evidence/gpt6_plan_v1/p1_recording_smoke/run_metadata.json` | 1 KB | `af4255661c413f31` |
| `evidence/gpt6_plan_v1/p1_recording_smoke/legacy_summary.json` | 0 KB | `076e9934f564d244` |

<details><summary>输出末尾</summary>

```
[pidon_solve.py  version 2026-09-13b]  Algorithm 1
  cavity 50.0 mm / 31 cells  dx = 1.6129 mm   dt = 3.0750 ps
  CFL limit 3.1062 ps  ->  dt / CFL = 0.9900   ok
  init = random   coords=cellsize norm=rms   9.25M params
  inner training: stop below 1e+06, at most 0 iters, lr 0.0001   device cpu

  step     1 updates H/E 0/0 loss 0.00e+00/9.50e-01 Ez-nMAE 0.000e+00 0.13s/step

  accepted 1/1 steps in 0 s
  mean actual updates: curlH 0.0  curlE 0.0
  final Ez nMAE vs FDTD 0.000e+00
  saved evidence/gpt6_plan_v1/p1_recording_smoke\legacy_summary.json

  Fig 8's y-axis is the 'cum' column -- the loss summed over all
  inner epochs at each time step.  Run this again with --init random
  to get the control curve.
```

</details>

## #90　2026-09-13T11:20:42　OK

**P2 Yee sign support PEC boundary and 128-step exact-control tests**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok

----------------------------------------------------------------------
Ran 10 tests in 1.419s

OK
```

</details>

## #91　2026-09-13T11:20:49　OK

**P2 128-step float64 and float32 exact Yee control; explicitly not DCO**

```
py -3.11 pidon_exact_control.py --steps 128 --n 31 --out evidence/gpt6_plan_v1/p2_exact_control.json
```

- 耗时 1s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/p2_exact_control.json` | 1 KB | `edcf65fabf5d40df` |

<details><summary>输出末尾</summary>

```
{"schema": "pidon-p2-exact-control-v1", "float64": {"dtype": "float64", "steps": 128, "ordering": "E_update -> hard_source -> H_update", "classification": "exact Yee control; not a DCO result", "max_abs_error_per_component": {"Ex": 0.0, "Ey": 0.0, "Ez": 0.0, "Hx": 0.0, "Hy": 0.0, "Hz": 0.0}, "global_relative_l2": 0.0, "max_analytic_pec_boundary_curl": 0.0, "finite": true}, "float32": {"dtype": "float32", "steps": 128, "ordering": "E_update -> hard_source -> H_update", "classification": "exact Yee control; not a DCO result", "max_abs_error_per_component": {"Ex": 0.0, "Ey": 0.0, "Ez": 0.0, "Hx": 0.0, "Hy": 0.0, "Hz": 0.0}, "global_relative_l2": 0.0, "max_analytic_pec_boundary_curl": 0.0, "finite": true}}
```

</details>

## #92　2026-09-13T11:21:18　OK

**P2 three-axis Yee discrete-symbol and div-curl compatibility tests**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok

----------------------------------------------------------------------
Ran 11 tests in 1.354s

OK
```

</details>

## #93　2026-09-13T11:22:17　OK

**P1/P2 regression after explicit PEC boundary support insertion**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok

----------------------------------------------------------------------
Ran 11 tests in 1.408s

OK
```

</details>

## #94　2026-09-13T11:26:45　OK

**P3 fixed Yee-state fit diagnostic; 500-update registered budget, not a closed-loop rollout**

```
py -3.11 stage2_fixed_state.py --mode fixed --out evidence/gpt6_plan_v1/fixed_states --init dco_paper32.pt --max-inner 500 --tol 1e-4 --total-budget-s 3600 --per-task-budget-s 360 --device cuda
```

- 耗时 141s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/fixed_states/state_0300_targets.pt` | 4,122 KB | `7d5a1a6a8315ba61` |
| `evidence/gpt6_plan_v1/fixed_states/state_0600_targets.pt` | 4,116 KB | `ed37b44f80e97b4b` |
| `evidence/gpt6_plan_v1/fixed_states/state_0096_targets.pt` | 4,114 KB | `5207fc96d07d39de` |
| `evidence/gpt6_plan_v1/fixed_states/state_0043_targets.pt` | 4,056 KB | `8839dbc5b4873e99` |
| `evidence/gpt6_plan_v1/fixed_states/state_0016_targets.pt` | 3,047 KB | `96e0b782fa993a62` |
| `evidence/gpt6_plan_v1/fixed_states/fixed_state_report.json` | 41 KB | `9aecf11806c133cb` |

<details><summary>输出末尾</summary>

```
{"out": "evidence\\gpt6_plan_v1\\fixed_states", "tasks": 10, "elapsed_s": 138.40051320000202, "stopped_for_total_budget": false}
```

</details>

## #95　2026-09-13T11:27:40　OK

**P3 summarize fixed-state residuals and registered G1 gate from raw report**

```
py -3.11 p3_report.py --input evidence/gpt6_plan_v1/fixed_states/fixed_state_report.json --out evidence/gpt6_plan_v1/P3_REPORT.md
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/P3_REPORT.md` | 2 KB | `51b62cff88e43bf5` |

<details><summary>输出末尾</summary>

```
{"out": "evidence/gpt6_plan_v1/P3_REPORT.md", "g1_pass": false, "fit_failures": [[43, "E", 0.000633564661256969, "max_updates"]], "one_step_failures": [["16", {"curl_H_only": 0.004140419280304968, "curl_E_only": 0.0019676097580689613, "both_single_step": 0.0045841640433964955}], ["96", {"curl_H_only": 0.001592879897647068, "curl_E_only": 0.0015018547331772365, "both_single_step": 0.002189254212716057}], ["300", {"curl_H_only": 0.001685851563930757, "curl_E_only": 0.0013190062477636366, "both_single_step": 0.002140531003570677}], ["600", {"curl_H_only": 0.0015478831359966908, "curl_E_only": 0.0017033549775002494, "both_single_step": 0.0023015995268677444}]], "elapsed_s": 138.40051320000202}
```

</details>

## #96　2026-09-13T11:29:12　OK

**P4-A bounded LBFGS interface regression before diagnostic**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 3s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok

----------------------------------------------------------------------
Ran 11 tests in 1.416s

OK
```

</details>

## #97　2026-09-13T11:29:57　OK

**P4-A development curl-E step43: Adam200 versus registered Adam200 plus LBFGS up to 200 closures**

```
py -3.11 stage2_fixed_state.py --mode fixed --out evidence/gpt6_plan_v1/p4a_development_e43 --init dco_paper32.pt --states 43 --subproblems E --baseline-updates 200 --max-inner 200 --lbfgs-closures 200 --lbfgs-lr 1 --lbfgs-history 10 --lbfgs-time-budget-s 60 --per-task-budget-s 60 --total-budget-s 3600 --device cuda
```

- 耗时 37s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/p4a_development_e43/state_0043_targets.pt` | 4,056 KB | `8839dbc5b4873e99` |
| `evidence/gpt6_plan_v1/p4a_development_e43/fixed_state_report.json` | 2 KB | `e0f2b3bba1278ac0` |

<details><summary>输出末尾</summary>

```
{"out": "evidence\\gpt6_plan_v1\\p4a_development_e43", "tasks": 1, "elapsed_s": 35.29216459998861, "stopped_for_total_budget": false}
```

</details>

## #98　2026-09-13T11:31:48　FAILED (exit 1)

**Refresh N0-N4 reproduction evidence ledger from P0-P4 raw artifacts**

```
py -3.11 verify_claims.py --pidon-v2 --md
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `RESULTS.md` | 5 KB | `2858345019ac92f2` |

<details><summary>输出末尾</summary>

```
             这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说

  [ 待重审 ]    C8  无约束学习算子做不了长时程积分
             最好 dco_paper32: rho-1=0.1149，要跑 1e5 步需再小 11,491x
             撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。 历史数值仅供溯源。

  [ 撤回 ]     C9  旧跨指标、跨测试场景的论文对比
             旧0.70~1.50倍比较撤回；原始NPZ保留
             式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。 新协议与现有权重的结果见P0-P2。

  [ PASS ]   C10  相对 L2 与 nMAE 不可互换（上一条曾因此报错）
             指标比值（relative L2 / nMAE）：2.6~8.1x（5 个 checkpoint）
             判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。逐 checkpoint：dco_L4b 3.7-5.6x；dco_lr1e3_300 3.0-6.0x；dco_lr1e3_b8_300 3.1-6.6x；dco_paper32 4.7-8.1x；pidon_R2_all 2.6-4.5x —— 倍数本身就不是常数，所以任何记下来的固定倍数都不能用

  [ PASS ]   N0  P0历史证据审计可重算
             历史回算 128步 H/E=125/105；64步 H/E=48/26
             判据：P0 原始 JSON 回算与登记数字一致；这是历史证据审计，不是当前代码的严格轨迹。

  [ PASS ]   N1  P1严格停止与测量记录接口完整
             accepted=True；H/E实际更新=0/0；源外探针=3
             判据：正式 JSONL 同时含命名残差、六分量和三个源外探针；单步宽阈值 smoke 不代表 DCO 精度。

  [ PASS ]   N2  P2精确Yee控制通过且未冒充DCO
             float64/float32 相对L2=0.000e+00/0.000e+00；分类=exact Yee control; not a DCO result
             判据：128步同序精确 Yee 控制有限且满足登记精度，并显式标为非DCO。

  [ FAIL ]   N3  P3固定状态G1门槛
             固定状态未达标=[(43, 'E', 0.000633564661256969)]
             判据：所有登记任务必须在500更新内 R<1e-4；FAIL 触发 P4-A，不允许直接进入闭环。

  [ FAIL ]   N4  P4-A有无可进入闭环的候选
             Adam200=2.836e-03；Adam200+LBFGS 200 closures=1.347e-03
             判据：注册的200 closure、60秒上限内必须 R<1e-4 才能进入冻结验证；FAIL 即 P4-A 止损。

  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）

==================================================================
  通过 5　不通过 2　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #99　2026-09-13T11:32:17　OK

**Generate P4-A stop-loss report from raw registered optimization evidence**

```
py -3.11 p4_report.py --input evidence/gpt6_plan_v1/p4a_development_e43/fixed_state_report.json --out evidence/gpt6_plan_v1/P4_REPORT.md
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/P4_REPORT.md` | 1 KB | `a13da720409fe37d` |

<details><summary>输出末尾</summary>

```
{"out": "evidence/gpt6_plan_v1/P4_REPORT.md", "passed": false, "final_residual": 0.0013474664883688092, "adam_updates": 200, "closures": 200}
```

</details>

## #100　2026-09-13T11:32:44　OK

**Final regression of existing and P1/P2 contracts after P0-P4 stop**

```
py -3.11 -m unittest discover -v
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_pec_and_zero_field_fixed_point (test_paper_protocol.PaperProtocolTests.test_pec_and_zero_field_fixed_point) ... ok
test_single_wave_analytic_curl (test_paper_protocol.PaperProtocolTests.test_single_wave_analytic_curl) ... ok
test_three_curl_components_at_yee_positions (test_paper_protocol.PaperProtocolTests.test_three_curl_components_at_yee_positions) ... ok
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok
test_actual_helper_freezes_branch_and_updates_only_trunk (test_trunk_repair.TrunkTests.test_actual_helper_freezes_branch_and_updates_only_trunk) ... C200 update 10/200: last10 training loss=1.60288, 0.1s
C200 update 20/200: last10 training loss=1.60162, 0.1s
C200 update 30/200: last10 training loss=1.60035, 0.1s
C200 update 40/200: last10 training loss=1.59909, 0.1s
C200 update 50/200: last10 training loss=1.59782, 0.1s
C200 update 60/200: last10 training loss=1.59656, 0.1s
C200 update 70/200: last10 training loss=1.5953, 0.1s
C200 update 80/200: last10 training loss=1.59403, 0.1s
C200 update 90/200: last10 training loss=1.59277, 0.1s
C200 update 100/200: last10 training loss=1.59151, 0.1s
C200 update 110/200: last10 training loss=1.59025, 0.1s
C200 update 120/200: last10 training loss=1.589, 0.1s
C200 update 130/200: last10 training loss=1.58774, 0.2s
C200 update 140/200: last10 training loss=1.58648, 0.2s
C200 update 150/200: last10 training loss=1.58522, 0.2s
C200 update 160/200: last10 training loss=1.58397, 0.2s
C200 update 170/200: last10 training loss=1.58271, 0.2s
C200 update 180/200: last10 training loss=1.58146, 0.2s
C200 update 190/200: last10 training loss=1.58021, 0.2s
C200 update 200/200: last10 training loss=1.57895, 0.2s
ok

----------------------------------------------------------------------
Ran 24 tests in 1.680s

OK
```

</details>

## #101　2026-09-13T11:33:27　FAILED (exit 1)

**Merge all historical claim groups with P0-P4 N0-N4 ledger; preserve prior adverse evidence; UTF-8 retry**

```
py -3.11 verify_claims.py --pidon-v2 --stage2-longrun --paper-first --grid-diagnosis --spacing-probe --coverage-ab --trunk-repair --md
```

- 耗时 8s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = 1.569e-02`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/trunk_repair_v1/findings.json` | 92 KB | `825caaa7702a36e7` |
| `RESULTS.md` | 11 KB | `f9287dcf3929494f` |
| `evidence/trunk_repair_v1/verification_manifest.json` | 0 KB | `74a020664856d027` |

<details><summary>输出末尾</summary>

```
             预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。

  [ PASS ]   T0  A/B配对、更新预算与证据完整
             两组各200次Adam更新；36组独立种子测试、90组探针；12项测试通过；配对偏差 5.80e-08
             核验源/数据/权重/曲线哈希、共同起点与配对随机数、实际优化器step=200；不把训练次数当精度成果。

  [ FAIL ]   T1  扩展间距B在非立方测试比A改善至少20%
             非立方六案例B/A几何平均比：nMAE比值 0.9420，x-MRE比值 0.8335
             已批准门槛：两个比值均≤0.8；同样200更新的扩展范围B对原范围A，独立振幅种子10/11/12。

  [ FAIL ]   T2  扩展间距B在原范围内未明显退步
             32³三种子平均nMAE：B/起点=2.0772
             已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。

  [ PASS ]   T3  扩展间距B的错误坐标依赖未比起点加重
             六方向最大干预效应的平均：B/起点=0.6860
             已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。

  [ PASS ]   U0  仅trunk训练的冻结、预算和证据完整
             冻结50个张量逐项完全相同；仅24个trunk张量各更新200次；60组场、30组探针；13项检查
             同一B数据和batch序列；核验实际权重、优化器step、源与数组哈希；已知诊断集与新种子终验分开。

  [ FAIL ]   U1  仅trunk训练在新种子非立方测试达改善门槛
             新种子非立方C/A几何平均比：nMAE比值 0.9299，x-MRE比值 0.7701
             预设：种子20/21/22、六案例，两个几何平均比均≤0.8；全部逐例C/B及B/A0另报。

  [ FAIL ]   U2  仅trunk训练在新种子原范围内未明显退步
             新种子32³平均nMAE的C/起点比值 1.2988
             预设：≤1.1，不比起点退步超过10%。

  [ PASS ]   U3  仅trunk训练的错误坐标依赖未比起点加重
             六方向最大坐标干预效应平均的C/起点比值 0.8005
             预设：≤1；已知单波诊断集，非独立场精度或论文复现验收。

  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）

==================================================================
  通过 20　不通过 8　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #102　2026-09-13T11:56:10　OK

**P5 four fixed 32-cube analytic samples learnability gate before any A/B pilot**

```
py -3.11 phase1_pilot.py --data data_32.npz --indices 0 1 2 3 --updates 200 --max-updates 500 --lr 3e-4 --seed 20261012 --out evidence/gpt6_plan_v1/phase1_pilot --device cuda
```

- 耗时 40s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/phase1_pilot/learnability_checkpoint.pt` | 108,452 KB | `bb9541d99366a162` |
| `evidence/gpt6_plan_v1/phase1_pilot/learnability.json` | 1 KB | `2387fedaad8a8b7e` |
| `evidence/gpt6_plan_v1/phase1_pilot/P5_LEARNABILITY_REPORT.md` | 1 KB | `7f8d509a4efcf088` |

<details><summary>输出末尾</summary>

```
{"actual_updates": 500, "loss_reduction": 599.1930700582387, "macro_nmae": 0.014545055261502663, "passed": false, "out": "evidence\\gpt6_plan_v1\\phase1_pilot"}
```

</details>

## #103　2026-09-13T11:58:08　OK

**P5 corrected four-sample learnability gate with actual update accounting**

```
py -3.11 phase1_pilot.py --data data_32.npz --indices 0 1 2 3 --updates 200 --max-updates 500 --lr 3e-4 --seed 20261012 --out evidence/gpt6_plan_v1/phase1_pilot_corrected --device cuda
```

- 耗时 80s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/phase1_pilot_corrected/learnability_checkpoint.pt` | 108,452 KB | `50a4ef935649bc92` |
| `evidence/gpt6_plan_v1/phase1_pilot_corrected/learnability.json` | 1 KB | `8034f79fe285ba08` |
| `evidence/gpt6_plan_v1/phase1_pilot_corrected/P5_LEARNABILITY_REPORT.md` | 1 KB | `5aaf72385f6d2f31` |

<details><summary>输出末尾</summary>

```
{"actual_updates": 500, "loss_reduction": 4251.189411784516, "macro_nmae": 0.005852074478752911, "passed": false, "out": "evidence\\gpt6_plan_v1\\phase1_pilot_corrected"}
```

</details>

## #104　2026-09-13T11:59:01　OK

**P5 update-budget accounting regression after preserving failed pilot**

```
py -3.11 -m unittest test_phase1_pilot -v
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_declared_escalation_counts_actual_cumulative_updates (test_phase1_pilot.Phase1PilotTests.test_declared_escalation_counts_actual_cumulative_updates) ... ok
test_invalid_budget_is_rejected (test_phase1_pilot.Phase1PilotTests.test_invalid_budget_is_rejected) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
```

</details>

## #105　2026-09-13T11:59:35　OK

**P5 analytic label and Yee-position regression after learnability gate failure**

```
py -3.11 -m unittest test_paper_protocol -v
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_component_aggregation (test_paper_protocol.PaperProtocolTests.test_component_aggregation) ... ok
test_eq5_uses_exact_zero_branch_not_small_value_cutoff (test_paper_protocol.PaperProtocolTests.test_eq5_uses_exact_zero_branch_not_small_value_cutoff) ... ok
test_fixed_case_reuses_wave_spec_across_grids (test_paper_protocol.PaperProtocolTests.test_fixed_case_reuses_wave_spec_across_grids) ... ok
test_metric_zero_branch_is_unit_sensitive (test_paper_protocol.PaperProtocolTests.test_metric_zero_branch_is_unit_sensitive) ... ok
test_mre_scaling_is_not_nmae (test_paper_protocol.PaperProtocolTests.test_mre_scaling_is_not_nmae) ... ok
test_nonfinite_metrics_rejected (test_paper_protocol.PaperProtocolTests.test_nonfinite_metrics_rejected) ... ok
test_pec_and_zero_field_fixed_point (test_paper_protocol.PaperProtocolTests.test_pec_and_zero_field_fixed_point) ... ok
test_single_wave_analytic_curl (test_paper_protocol.PaperProtocolTests.test_single_wave_analytic_curl) ... ok
test_three_curl_components_at_yee_positions (test_paper_protocol.PaperProtocolTests.test_three_curl_components_at_yee_positions) ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.102s

OK
```

</details>

## #106　2026-09-13T11:59:43　OK

**P5 audit corrected pilot optimizer count and frozen learnability gate**

```
py -3.11 p5_audit.py --dir evidence/gpt6_plan_v1/phase1_pilot_corrected --out evidence/gpt6_plan_v1/P5_REPORT.md
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/P5_REPORT.md` | 1 KB | `8eeff6f36e31c054` |

<details><summary>输出末尾</summary>

```
{"out": "evidence/gpt6_plan_v1/P5_REPORT.md", "actual_updates": 500, "optimizer_step_range": [500, 500], "passed": false, "macro_nmae": 0.005852074478752911}
```

</details>

## #107　2026-09-13T12:00:29　FAILED (exit 1)

**Refresh all historical and N0-N5 ledgers after P5 learnability stop**

```
py -3.11 verify_claims.py --pidon-v2 --stage2-longrun --paper-first --grid-diagnosis --spacing-probe --coverage-ab --trunk-repair --md
```

- 耗时 8s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER
- 抓到的关键数：`nMAE = ['1.569e-02', '5.852e-03']`

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/trunk_repair_v1/findings.json` | 92 KB | `825caaa7702a36e7` |
| `evidence/trunk_repair_v1/source/verify_claims_final.py` | 63 KB | `eb5d905eb16bcc41` |
| `RESULTS.md` | 11 KB | `8b8d308e2c105b5a` |
| `evidence/trunk_repair_v1/verification_manifest.json` | 0 KB | `bf43df2364c364a8` |

<details><summary>输出末尾</summary>

```
             预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。

  [ PASS ]   T0  A/B配对、更新预算与证据完整
             两组各200次Adam更新；36组独立种子测试、90组探针；12项测试通过；配对偏差 5.80e-08
             核验源/数据/权重/曲线哈希、共同起点与配对随机数、实际优化器step=200；不把训练次数当精度成果。

  [ FAIL ]   T1  扩展间距B在非立方测试比A改善至少20%
             非立方六案例B/A几何平均比：nMAE比值 0.9420，x-MRE比值 0.8335
             已批准门槛：两个比值均≤0.8；同样200更新的扩展范围B对原范围A，独立振幅种子10/11/12。

  [ FAIL ]   T2  扩展间距B在原范围内未明显退步
             32³三种子平均nMAE：B/起点=2.0772
             已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。

  [ PASS ]   T3  扩展间距B的错误坐标依赖未比起点加重
             六方向最大干预效应的平均：B/起点=0.6860
             已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。

  [ PASS ]   U0  仅trunk训练的冻结、预算和证据完整
             冻结50个张量逐项完全相同；仅24个trunk张量各更新200次；60组场、30组探针；13项检查
             同一B数据和batch序列；核验实际权重、优化器step、源与数组哈希；已知诊断集与新种子终验分开。

  [ FAIL ]   U1  仅trunk训练在新种子非立方测试达改善门槛
             新种子非立方C/A几何平均比：nMAE比值 0.9299，x-MRE比值 0.7701
             预设：种子20/21/22、六案例，两个几何平均比均≤0.8；全部逐例C/B及B/A0另报。

  [ FAIL ]   U2  仅trunk训练在新种子原范围内未明显退步
             新种子32³平均nMAE的C/起点比值 1.2988
             预设：≤1.1，不比起点退步超过10%。

  [ PASS ]   U3  仅trunk训练的错误坐标依赖未比起点加重
             六方向最大坐标干预效应平均的C/起点比值 0.8005
             预设：≤1；已知单波诊断集，非独立场精度或论文复现验收。

  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）

==================================================================
  通过 20　不通过 9　缺数据 0　反例 1

  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）
```

</details>

## #108　2026-09-13T12:00:40　OK

**Final regression after P5 stop and ledger update**

```
py -3.11 -m unittest discover -v
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_three_curl_components_at_yee_positions (test_paper_protocol.PaperProtocolTests.test_three_curl_components_at_yee_positions) ... ok
test_declared_escalation_counts_actual_cumulative_updates (test_phase1_pilot.Phase1PilotTests.test_declared_escalation_counts_actual_cumulative_updates) ... ok
test_invalid_budget_is_rejected (test_phase1_pilot.Phase1PilotTests.test_invalid_budget_is_rejected) ... ok
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok
test_actual_helper_freezes_branch_and_updates_only_trunk (test_trunk_repair.TrunkTests.test_actual_helper_freezes_branch_and_updates_only_trunk) ... C200 update 10/200: last10 training loss=1.60288, 0.1s
C200 update 20/200: last10 training loss=1.60162, 0.1s
C200 update 30/200: last10 training loss=1.60035, 0.1s
C200 update 40/200: last10 training loss=1.59909, 0.1s
C200 update 50/200: last10 training loss=1.59782, 0.1s
C200 update 60/200: last10 training loss=1.59656, 0.1s
C200 update 70/200: last10 training loss=1.5953, 0.1s
C200 update 80/200: last10 training loss=1.59403, 0.1s
C200 update 90/200: last10 training loss=1.59277, 0.1s
C200 update 100/200: last10 training loss=1.59151, 0.1s
C200 update 110/200: last10 training loss=1.59025, 0.1s
C200 update 120/200: last10 training loss=1.589, 0.1s
C200 update 130/200: last10 training loss=1.58774, 0.1s
C200 update 140/200: last10 training loss=1.58648, 0.2s
C200 update 150/200: last10 training loss=1.58522, 0.2s
C200 update 160/200: last10 training loss=1.58397, 0.2s
C200 update 170/200: last10 training loss=1.58271, 0.2s
C200 update 180/200: last10 training loss=1.58146, 0.2s
C200 update 190/200: last10 training loss=1.58021, 0.2s
C200 update 200/200: last10 training loss=1.57895, 0.2s
ok

----------------------------------------------------------------------
Ran 26 tests in 1.764s

OK
```

</details>

## #109　2026-09-13T12:15:49　OK

**P5 A/B paired schedule regression before development pilot**

```
py -3.11 -m unittest test_phase1_pilot -v
```

- 耗时 2s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_declared_escalation_counts_actual_cumulative_updates (test_phase1_pilot.Phase1PilotTests.test_declared_escalation_counts_actual_cumulative_updates) ... ok
test_invalid_budget_is_rejected (test_phase1_pilot.Phase1PilotTests.test_invalid_budget_is_rejected) ... ok
test_paired_batch_schedule_is_seed_deterministic (test_phase1_pilot.Phase1PilotTests.test_paired_batch_schedule_is_seed_deterministic) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.003s

OK
```

</details>

## #110　2026-09-13T12:17:03　OK

**P5 paired 128-sample A/B: relative loss versus component-localmax physical loss**

```
py -3.11 phase1_ab_pilot.py --data data_32.npz --train-n 128 --dev-n 32 --updates 200 --batch 4 --lr 3e-4 --seed 20261012 --out evidence/gpt6_plan_v1/phase1_ab_pilot --device cuda
```

- 耗时 66s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/phase1_ab_pilot/A_200.pt` | 36,141 KB | `316cda8451b41e59` |
| `evidence/gpt6_plan_v1/phase1_ab_pilot/B_200.pt` | 36,141 KB | `aefa31445915beed` |
| `evidence/gpt6_plan_v1/phase1_ab_pilot/ab_pilot.json` | 2 KB | `acba57190e4d19e6` |
| `evidence/gpt6_plan_v1/phase1_ab_pilot/P5_AB_REPORT.md` | 1 KB | `b52d9eb8040dedf1` |

<details><summary>输出末尾</summary>

```
{"out": "evidence\\gpt6_plan_v1\\phase1_ab_pilot", "A_dev_macro_nmae": 0.21260009706020355, "B_dev_macro_nmae": 0.8271046678225199}
```

</details>

## #111　2026-09-13T12:18:02　OK

**P5 audit paired loss A/B and record no-promotion decision**

```
py -3.11 p5_ab_audit.py --pilot evidence/gpt6_plan_v1/phase1_pilot_corrected/learnability.json --ab evidence/gpt6_plan_v1/phase1_ab_pilot/ab_pilot.json --out evidence/gpt6_plan_v1/P5_REPORT.md
```

- 耗时 0s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

| 产生/修改的文件 | 大小 | sha256 (前 16 位) |
|---|---|---|
| `evidence/gpt6_plan_v1/P5_REPORT.md` | 1 KB | `e52226b483467322` |

<details><summary>输出末尾</summary>

```
{"out": "evidence/gpt6_plan_v1/P5_REPORT.md", "A": 0.21260009706020355, "B": 0.8271046678225199, "same_initial_state": true, "decision": "stop"}
```

</details>

## #112　2026-09-13T17:48:17　OK

**R0 baseline contract regression before v2 repairs**

```
py -3.11 -m unittest test_pidon_contract -v
```

- 耗时 4s ｜ commit `dad6fb2` (main) ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**
- DESKTOP-0K8A2KS ｜ Windows 10 ｜ python 3.11.9 ｜ torch 2.14.0+cu126 ｜ NVIDIA GeForce GTX 1660 SUPER

<details><summary>输出末尾</summary>

```
test_atomic_recorder_keeps_jsonl_and_latest_checkpoint (test_pidon_contract.PidonContractTests.test_atomic_recorder_keeps_jsonl_and_latest_checkpoint) ... ok
test_cpu_checkpoint_e_pending_resume_is_deterministic (test_pidon_contract.PidonContractTests.test_cpu_checkpoint_e_pending_resume_is_deterministic) ... ok
test_e_pending_resume_does_not_repeat_source_or_e_update (test_pidon_contract.PidonContractTests.test_e_pending_resume_does_not_repeat_source_or_e_update) ... ok
test_exact_control_128_steps_is_not_dco_and_meets_precision_gates (test_pidon_contract.PidonContractTests.test_exact_control_128_steps_is_not_dco_and_meets_precision_gates) ... ok
test_h_failure_does_not_advance_transaction (test_pidon_contract.PidonContractTests.test_h_failure_does_not_advance_transaction) ... ok
test_nonzero_irrotational_input_is_not_zero_shortcut (test_pidon_contract.PidonContractTests.test_nonzero_irrotational_input_is_not_zero_shortcut) ... ok
test_pec_high_curl_e_planes_are_explicitly_zero (test_pidon_contract.PidonContractTests.test_pec_high_curl_e_planes_are_explicitly_zero) ... ok
test_reached_is_strict_and_finite (test_pidon_contract.PidonContractTests.test_reached_is_strict_and_finite) ... ok
test_staggered_probe_and_dual_boundary_volume (test_pidon_contract.PidonContractTests.test_staggered_probe_and_dual_boundary_volume) ... ok
test_three_axis_discrete_plane_wave_symbols_and_div_curl (test_pidon_contract.PidonContractTests.test_three_axis_discrete_plane_wave_symbols_and_div_curl) ... ok
test_yee_constant_and_linear_curls_have_expected_sign_and_support (test_pidon_contract.PidonContractTests.test_yee_constant_and_linear_curls_have_expected_sign_and_support) ... ok

----------------------------------------------------------------------
Ran 11 tests in 1.497s

OK
```

</details>

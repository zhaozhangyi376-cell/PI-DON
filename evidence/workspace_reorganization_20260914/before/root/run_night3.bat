@echo off
REM ===================================================================
REM  run_night3.bat -- overnight, about 9 hours, GPU, serial.
REM
REM  PURE ASCII, no cmd metacharacters. See FILE_MAP.md for why.
REM
REM  QUESTION THIS CAMPAIGN ANSWERS
REM  Warm-starting dco_paper32 from epoch 260 and training 270 more
REM  epochs bought only 1.25x, with the test loss bouncing between
REM  7.4e-4 and 2.5e-3. So "just train to 1000 epochs" does not look
REM  like the answer. Instead of spending another 10 hours on more of
REM  the same, change ONE thing at a time and see which direction
REM  actually moves the test loss.
REM
REM  Every run starts FROM SCRATCH so the comparison is fair, and every
REM  run gets the same budget. Only one knob differs per run.
REM
REM  The most interesting one is F. gen_data's own docstring says that
REM  with dirs=shared every wave in a sample travels the same way, so
REM  the field is a 1-D profile extruded along the other two axes --
REM  the network may never have seen genuine 3-D variation. If that is
REM  the ceiling, no amount of extra epochs can help.
REM ===================================================================
setlocal
cd /d %~dp0
echo   started %DATE% %TIME%

echo.
echo === 0/10  build the per-wave dataset (needed by run F) ============
if exist data_32_pw.npz (
  echo   data_32_pw.npz already here, skipping
) else (
  py -3.11 lab_log.py run -m "per-wave 32-cubed dataset for the direction ablation" -- py -3.11 gen_data.py --n 32 --samples 1000 --seed 5 --dirs per-wave --out data_32_pw.npz
)

echo.
echo === A  baseline: lr 1e-4, batch 16, shared dirs, rel loss =========
py -3.11 lab_log.py run -m "sweep A baseline" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-4 --batch 16 --loss rel --ckpt-every 40 --out sweep_baseline.pt

echo.
echo === B  learning rate 3e-4 ========================================
py -3.11 lab_log.py run -m "sweep B lr 3e-4" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 3e-4 --batch 16 --loss rel --ckpt-every 40 --out sweep_lr3e4.pt

echo.
echo === C  learning rate 1e-3 ========================================
py -3.11 lab_log.py run -m "sweep C lr 1e-3" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-3 --batch 16 --loss rel --ckpt-every 40 --out sweep_lr1e3.pt

echo.
echo === D  batch 8 ===================================================
py -3.11 lab_log.py run -m "sweep D batch 8" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-4 --batch 8 --loss rel --ckpt-every 40 --out sweep_batch8.pt

echo.
echo === E  batch 32, the paper's value ===============================
py -3.11 lab_log.py run -m "sweep E batch 32, the paper value" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-4 --batch 32 --loss rel --ckpt-every 40 --out sweep_batch32.pt

echo.
echo === F  per-wave directions -- the main hypothesis =================
if exist data_32_pw.npz (
  py -3.11 lab_log.py run -m "sweep F per-wave directions, the main hypothesis" -- py -3.11 train_dco.py --data data_32_pw.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-4 --batch 16 --loss rel --ckpt-every 40 --out sweep_perwave.pt
) else (
  echo   data_32_pw.npz missing, skipping F
)

echo.
echo === G  input normalisation max instead of rms =====================
py -3.11 lab_log.py run -m "sweep G norm max" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm max --epochs 80 --lr 1e-4 --batch 16 --loss rel --ckpt-every 40 --out sweep_normmax.pt

echo.
echo === H  plain mse loss instead of relative =========================
py -3.11 lab_log.py run -m "sweep H mse loss" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 1e-4 --batch 16 --loss mse --ckpt-every 40 --out sweep_mse.pt

echo.
echo === I  ranking ====================================================
py -3.11 sweep_report.py

echo.
echo === J  whatever time is left: the main hypothesis, long ===========
if exist data_32_pw.npz (
  py -3.11 lab_log.py run -m "per-wave, long run, 300 epochs" -- py -3.11 train_dco.py --data data_32_pw.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 300 --lr 1e-4 --batch 16 --ckpt-every 50 --out dco_pw300.pt
)

echo.
echo   finished %DATE% %TIME%
echo.
echo   in the morning:
echo     py -3.11 sweep_report.py
echo     py -3.11 lab_log.py show -n 12

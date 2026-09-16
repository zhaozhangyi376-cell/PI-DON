@echo off
REM ===================================================================
REM  run_day4.bat -- about 4.5 hours, GPU, serial.
REM
REM  PURE ASCII, no cmd metacharacters. See FILE_MAP.md for why.
REM
REM  WHAT run_night3 ACTUALLY SHOWED (after the ranking was corrected
REM  to use nMAE instead of the training loss, which is not comparable
REM  across --loss rel and --loss mse):
REM
REM      lr1e3    2.32x better than baseline
REM      lr3e4    1.66x
REM      batch8   1.40x
REM      mse      1.05x   noise
REM      perwave  0.97x   noise
REM      normmax  0.77x   worse
REM      batch32  0.71x   worse
REM
REM  Higher lr is better and smaller batch is better, monotonically.
REM  Both knobs do the same thing: more, or bigger, gradient steps in a
REM  fixed 80-epoch budget. So at 80 epochs these runs are limited by
REM  OPTIMISATION, not by capacity or by data. Every run was still
REM  improving 20-44x from head to tail when it stopped.
REM
REM  THREE QUESTIONS THIS CAMPAIGN ANSWERS
REM   1. Does the lr trend keep going? Probe lr 3e-3 at the same
REM      80-epoch budget. If it is worse than lr 1e-3 we have bracketed
REM      the optimum; if it is better the trend is not yet exhausted.
REM   2. What does the best knob setting reach with a real budget?
REM      300 epochs at lr 1e-3, batch 16 and batch 8.
REM   3. THE DECIDING ONE: does better open-loop accuracy buy closed-
REM      loop lifetime? EXP 3 on the new checkpoint versus the 158
REM      steps dco_paper32 managed. If accuracy doubles and lifetime
REM      does not move, the bottleneck is not accuracy.
REM ===================================================================
setlocal
cd /d %~dp0
echo   started %DATE% %TIME%

echo.
echo === P  probe lr 3e-3, same 80-epoch budget, brackets the optimum ==
py -3.11 lab_log.py run -m "day4 P probe lr 3e-3" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 80 --lr 3e-3 --batch 16 --loss rel --ckpt-every 40 --out sweep_lr3e3.pt

echo.
echo === Q  the winner, real budget: lr 1e-3, batch 16, 300 epochs =====
py -3.11 lab_log.py run -m "day4 Q lr 1e-3 batch 16 300 epochs" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 300 --lr 1e-3 --batch 16 --loss rel --ckpt-every 50 --out dco_lr1e3_300.pt

echo.
echo === R  both knobs together: lr 1e-3, batch 8, 300 epochs ==========
REM  The two knobs may not add up. batch 8 at lr 1e-3 doubles the number
REM  of steps AND keeps the big step size, so this is the run most
REM  likely to go unstable. That is why Q runs first and is kept.
py -3.11 lab_log.py run -m "day4 R lr 1e-3 batch 8 300 epochs" -- py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --coords cellsize --norm rms --epochs 300 --lr 1e-3 --batch 8 --loss rel --ckpt-every 50 --out dco_lr1e3_b8_300.pt

echo.
echo === S  re-rank including the lr 3e-3 probe ========================
py -3.11 sweep_report.py

echo.
echo === T  DECIDING TEST: closed-loop lifetime of the new checkpoint ==
REM  Baseline to beat: dco_paper32 diverged at 158 steps in EXP 3.
py -3.11 lab_log.py run -m "day4 T closed-loop lifetime, lr1e3 batch16 300" -- py -3.11 test_dco.py --ckpt dco_lr1e3_300.pt --steps 400

echo.
echo === U  same test for the batch-8 variant =========================
py -3.11 lab_log.py run -m "day4 U closed-loop lifetime, lr1e3 batch8 300" -- py -3.11 test_dco.py --ckpt dco_lr1e3_b8_300.pt --steps 400

echo.
echo   finished %DATE% %TIME%
echo.
echo   send me:
echo     py -3.11 sweep_report.py
echo     py -3.11 lab_log.py show -n 6

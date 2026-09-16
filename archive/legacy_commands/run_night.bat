@echo off
REM ===================================================================
REM  run_night.bat -- the 9-hour unattended campaign (2026-09-09 night)
REM
REM  Ordered so the most valuable result lands FIRST.  If the machine
REM  dies at hour 2 you still have stage 2, which is the one that
REM  closes the hole in the whole argument.
REM
REM    stage 0   smoke gates            ~5 min   aborts on failure
REM    stage 1   spectral self-test     ~2 min   exact curl must give rho=1
REM    stage 2   rho of EVERY trained    ~1 h    <== the capstone
REM              checkpoint + CFL sweep
REM    stage 3   32^3 paper parity       ~3-5 h  removes the "different
REM              (L=4, the paper's own            configuration" caveat
REM              depth)
REM    stage 4   PINN at 32^3 from        ~2-3 h  tests "physics loss
REM              stage 3's weights               compresses rho"
REM    stage 5   rho + full test suite   ~30 min on the new checkpoints
REM    stage 6   figures
REM
REM  IMPORTANT -- keep a log this time.  In PowerShell:
REM      .\run_night.bat 2>&1 | Tee-Object night.log
REM  keeps everything on screen AND writes night.log, so a reboot does not
REM  lose the run.  Every stage also writes its real output to disk, and
REM  night_report.py reads all of that back if the scrollback is gone.
REM
REM ===================================================================
setlocal enabledelayedexpansion
cd /d %~dp0
echo.
echo ###################################################################
echo #  night campaign starting   %DATE% %TIME%
echo ###################################################################

REM ---------------------------------------------------------------- 0
echo.
echo === stage 0 : smoke gates ==========================================
py -3.11 -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
if errorlevel 1 goto :dead
py -3.11 -c "import ast,sys;[ast.parse(open(f,encoding='utf-8').read()) for f in ['spectral_dco.py','train_dco.py','train_pidon.py','test_dco.py','rollout.py','make_figs.py']];print('syntax ok')"
if errorlevel 1 goto :dead
if not exist data_32.npz (
  echo   data_32.npz missing -- generating it now
  py -3.11 gen_data.py --n 32 --samples 1000 --out data_32.npz --seed 5
  if errorlevel 1 goto :dead
)
echo   1-epoch training smoke test:
py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --epochs 1 --batch 4 --coords cellsize --norm rms --out _smoke32.pt
if errorlevel 1 (
  echo   *** batch 4 failed at 32^^3 -- the rest of the night would fail too.
  echo   *** Most likely out of GPU memory.  Re-run this file after editing
  echo   *** the two --batch 4 below down to --batch 2.
  goto :dead
)
del /q _smoke32.pt _smoke32_hist.json 2>nul
echo   smoke gates PASSED

REM ---------------------------------------------------------------- 1
echo.
echo === stage 1 : spectral self-test ===================================
echo   (the exact Yee curl must come back rho = 1.0000; a deliberately
echo    skewed curl must come back greater than 1.  If this fails, every
echo    number stage 2 prints is meaningless.)
py -3.11 spectral_dco.py --selftest
if errorlevel 1 (
  echo   *** self-test FAILED -- skipping stage 2, going straight to training
  goto :stage3
)

REM ---------------------------------------------------------------- 2
echo.
echo === stage 2 : spectral radius of every trained checkpoint ==========
echo   THIS IS THE ONE THAT MATTERS.  We have claimed all week that the
echo   closed-loop blow-up is set by the spectral radius, but we only ever
echo   measured rho on toy operators.  This measures it on the real
echo   2.25M-parameter network, and prints the blow-up step it predicts
echo   next to the blow-up step actually measured in the same run.
echo.
for %%F in (dco_*.pt pidon_*.pt) do (
  echo -------------------------------------------------------------------
  echo   %%F
  py -3.11 spectral_dco.py --ckpt %%F --n 16 --cfl 0.99 0.70 0.50 0.30 0.15 --iters 200 --burn 70 --emp-steps 400
)
echo.
echo   stage 2 done -- one spectral_*.json per checkpoint.
echo   Read them like this:
echo     rho = 1.0000000  -^> neutral, the loop could run forever
echo     rho ^> 1          -^> multiplied every step; if it stays ^> 1 all the
echo                         way down the CFL sweep, no time step rescues it
echo                         and the fix has to be structural.

REM ---------------------------------------------------------------- 3
:stage3
echo.
echo === stage 3 : 32^^3 paper parity, L=4 (the paper's own depth) =======
echo   %DATE% %TIME%
echo   Checkpoints are written every 20 epochs, so killing this at any
echo   point still leaves a usable dco_paper32.pt.
py -3.11 train_dco.py --data data_32.npz --levels 4 --base 32 --epochs 300 --batch 4 --lr 1e-4 --coords cellsize --norm rms --ckpt-every 20 --out dco_paper32.pt
if errorlevel 1 echo   *** stage 3 failed or was killed -- continuing with whatever it saved

REM ---------------------------------------------------------------- 4
echo.
echo === stage 4 : PINN at 32^^3, warm-started from stage 3 ==============
echo   %DATE% %TIME%
echo   Yee target + divergence penalty + 6-step rollout penalty.  This is
echo   the low-rent version of the paper's Algorithm 1, at the paper's own
echo   grid size.  The question it answers: does the physics loss push rho
echo   down, or only push the single-step error down?
if not exist dco_paper32.pt (
  echo   dco_paper32.pt missing -- skipping stage 4
  goto :stage5
)
py -3.11 train_pidon.py --data data_32.npz --init dco_paper32.pt --levels 4 --base 32 --epochs 150 --batch 4 --lr 5e-5 --target yee --lam-div 1.0 --roll 6 --lam-roll 1.0 --roll-n 32 --roll-batch 1 --roll-samples 4 --roll-warm 40 --coords cellsize --norm rms --ckpt-every 15 --out pidon_paper32.pt
if errorlevel 1 echo   *** stage 4 failed or was killed -- continuing

REM ---------------------------------------------------------------- 5
:stage5
echo.
echo === stage 5 : evaluate the new checkpoints =========================
echo   %DATE% %TIME%
for %%F in (dco_paper32.pt pidon_paper32.pt) do (
  if exist %%F (
    echo -------------------------------------------------------------------
    echo   %%F
    py -3.11 spectral_dco.py --ckpt %%F --n 32 --cfl 0.99 0.70 0.50 0.30 --iters 200 --burn 70 --emp-steps 400
    py -3.11 test_dco.py --ckpt %%F --exp1-samples 20 --exp2-sizes 16 32 48 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
  )
)

REM ---------------------------------------------------------------- 6
echo.
echo === stage 6 : figures ==============================================
py -3.11 make_figs.py

echo.
echo ###################################################################
echo #  night campaign finished   %DATE% %TIME%
echo #
echo #  In the morning, read in this order:
echo #    1. the stage-2 block -- rho for each checkpoint, and whether
echo #       any CFL makes it neutral
echo #    2. spectral_*.json  -- same numbers, machine readable
echo #    3. the stage-3 FINAL relative L2 -- vs paper Table I (L=4,
echo #       32^^3, 1000 samples: 7.7e-4)
echo #    4. the stage-5 EXP 3b blow-up step vs the stage-5 rho
echo ###################################################################
goto :eof

:dead
echo.
echo *** a smoke gate failed -- nothing long was started.  Fix the line
echo *** above and re-run.  No time was wasted.
exit /b 1

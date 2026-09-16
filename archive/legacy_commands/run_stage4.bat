@echo off
REM ===================================================================
REM  Stage 4 -- EXP 3 works now, so re-measure everything through it.
REM
REM  The old EXP 3 excited the cavity with an additive plain Gaussian.
REM  Its area (16.3) was deposited as a permanent electrostatic blob at
REM  the source cell -- curl free, so it added nothing to curl E while
REM  dominating |E|.  Handover state: k_eff*d = 0.006 against a training
REM  band of 0.152..0.491.  Every checkpoint scored ~20 on EXP 3a no
REM  matter how it was trained, because the test was broken, not them.
REM  --src-mode diff (zero DC) puts the handover at 0.41.  See
REM  diag_exp3.py and test_dco.source_waveform.__doc__.
REM
REM  PHASE 1 costs no training: three checkpoints whose loss was never
REM          affected by the boundary-face bug, re-tested through the
REM          fixed harness.  ~10 min.  THIS IS THE HEADLINE NUMBER.
REM  PHASE 2 retrains the three that WERE affected, then tests them.
REM          ~50 min.
REM
REM    .\run_stage4.bat            data_16.npz + data_16_pw.npz
REM ===================================================================
setlocal
set SW=--exp1-samples 20 --exp2-sizes 16 32 48 --steps 300 --warm 300 --src-mode diff

echo === version check -- catches a file that was not overwritten ====
py -3.11 check_files.py
if errorlevel 1 exit /b 1
echo.

echo === the evidence, 10 s ==========================================
py -3.11 diag_exp3.py
if errorlevel 1 exit /b 1

echo. & echo ################  PHASE 1 -- no training  ####################
echo (dco_L3d, pidon_B_div and pidon_D_perwave all used the analytic
echo  target, so the unsupervised-face bug never touched them.)
for %%K in (dco_L3d pidon_B_div pidon_D_perwave) do (
  if exist %%K.pt (
    echo. & echo ---- %%K ----
    py -3.11 test_dco.py --ckpt %%K.pt %SW%
  ) else ( echo. & echo ---- %%K.pt not found, skipping ---- )
)

echo. & echo ################  PHASE 2 -- retrain the affected three  #####
set C1=--init dco_L3d.pt --levels 3 --base 32 --epochs 200 --batch 16 --coords cellsize --norm rms

if exist data_16.npz (
  echo. & echo --- A2: Yee target, fixed loss ---
  py -3.11 train_pidon.py --data data_16.npz    %C1% --target yee --lam-div 0.0 --out pidon_A2.pt
  echo. & echo --- C2: Yee target + physics loss, fixed ---
  py -3.11 train_pidon.py --data data_16.npz    %C1% --target yee --lam-div 1.0 --out pidon_C2.pt
)
if exist data_16_pw.npz (
  echo. & echo --- E2: per-wave + both, fixed ---
  py -3.11 train_pidon.py --data data_16_pw.npz %C1% --target yee --lam-div 1.0 --out pidon_E2.pt
)

for %%K in (pidon_A2 pidon_C2 pidon_E2) do (
  if exist %%K.pt (
    echo. & echo ---- %%K ----
    py -3.11 test_dco.py --ckpt %%K.pt %SW%
  )
)

py -3.11 make_figs.py
echo. & echo ALL DONE
endlocal

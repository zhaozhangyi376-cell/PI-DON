@echo off
REM ===================================================================
REM  Stage 2 (PI-DON step 1) -- three fine-tuning runs, one ablation.
REM  Baseline = dco_L3d.pt itself (analytic target, no physics loss).
REM
REM    A   target swap only          analytic -> Yee curl
REM    B   physics loss only         + lambda * ||div(curl)||^2
REM    C   both
REM
REM    .\run_stage2.bat            uses data_16.npz
REM    .\run_stage2.bat my.npz     uses my.npz
REM
REM  Output goes to the SCREEN, not into a log file.  An earlier version
REM  redirected everything into stage2.log, so when the runs failed on a
REM  missing data file all you saw was three empty section headers.  Use
REM     .\run_stage2.bat 2>&1 | tee-object stage2.log     (PowerShell)
REM  if you want a transcript as well.
REM ===================================================================
setlocal
set DATA=%1
if "%DATA%"=="" set DATA=data_16.npz

echo === checking prerequisites =====================================
if not exist "%DATA%" (
  echo   MISSING: %DATA%
  echo   .npz files actually present here:
  dir /b *.npz 2>nul
  echo.
  echo   Re-run as:  .^\run_stage2.bat ^<the right file^>.npz
  echo   or regenerate:  py -3.11 gen_data.py --n 16 --samples 1500 --out %DATA%
  exit /b 1
)
if not exist "dco_L3d.pt" (
  echo   MISSING: dco_L3d.pt   ^(.pt files present:^)
  dir /b *.pt 2>nul
  exit /b 1
)
for %%F in (gap_analysis.py train_pidon.py test_dco.py dco.py gen_data.py) do (
  if not exist "%%F" ( echo   MISSING: %%F & exit /b 1 )
)
echo   ok: %DATA%, dco_L3d.pt, all scripts present
echo.

echo === smoke test: 1 epoch, must finish in well under a minute =====
py -3.11 train_pidon.py --data %DATA% --init dco_L3d.pt --levels 3 --base 32 ^
    --epochs 1 --batch 16 --coords cellsize --norm rms --target yee ^
    --lam-div 1.0 --ckpt-every 0 --out _smoke.pt
if errorlevel 1 (
  echo.
  echo   SMOKE TEST FAILED -- the error is right above.  Nothing else was run.
  exit /b 1
)
del _smoke.pt 2>nul
echo   smoke test passed.
echo.

set COMMON=--data %DATA% --init dco_L3d.pt --levels 3 --base 32 --epochs 200 --batch 16 --coords cellsize --norm rms

echo === baseline diagnosis (no training, ~2 min) ===================
py -3.11 gap_analysis.py --ckpt dco_L3d.pt

echo. & echo === A: target swap only =========================================
py -3.11 train_pidon.py %COMMON% --target yee      --lam-div 0.0 --out pidon_A_yee.pt
echo. & echo === B: physics loss only =======================================
py -3.11 train_pidon.py %COMMON% --target analytic --lam-div 1.0 --out pidon_B_div.pt
echo. & echo === C: both ====================================================
py -3.11 train_pidon.py %COMMON% --target yee      --lam-div 1.0 --out pidon_C_both.pt

echo. & echo === acceptance tests, EXP 3b is the one that matters ===========
for %%K in (pidon_A_yee pidon_B_div pidon_C_both) do (
  if exist %%K.pt (
    echo. & echo ---- %%K ----
    py -3.11 test_dco.py --ckpt %%K.pt --exp1-samples 20 --exp2-sizes 16 32 48 --steps 150 --warm 300
  ) else ( echo. & echo ---- %%K.pt was never produced, skipping ---- )
)

py -3.11 make_figs.py
echo. & echo ALL DONE
endlocal

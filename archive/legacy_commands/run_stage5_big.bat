@echo off
REM ===================================================================
REM  Stage 5 for a big card.  Same experiment as run_stage5.bat, but K
REM  and the rollout batch are raised.
REM
REM  Rollout memory grows linearly in roll * roll-batch.  A 6 GB card
REM  manages K=8, batch 1; a 24-32 GB card manages K=16, batch 4.
REM  K IS THE POINT OF THE EXPERIMENT: it is how far ahead the loss can
REM  see, and the failure it targets (about 2.9% amplification per step)
REM  only becomes visible over many steps.
REM
REM    run_stage5_big.bat          K=16, roll-batch 4
REM    run_stage5_big.bat 24 4     K=24, roll-batch 4
REM ===================================================================
setlocal
set PY=py -3.11
set K=%1
if "%K%"=="" set K=16
set RB=%2
if "%RB%"=="" set RB=4

echo === 0. versions and hardware ===================================
%PY% check_files.py
if errorlevel 1 exit /b 1
%PY% -c "import torch;print('cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

echo. & echo === 1. the rollout harness must be exact before training through it
%PY% rollout.py --selftest
if errorlevel 1 (
  echo   SELF-TEST FAILED -- stopping.  Do not train through a broken scheme.
  exit /b 1
)

echo. & echo === 2. baseline: how far does dco_L3d get, iterated? ===========
%PY% rollout.py --ckpt dco_L3d.pt --steps 400

set COMMON=--data data_16.npz --init dco_L3d.pt --levels 3 --base 32 ^
 --epochs 200 --batch 16 --coords cellsize --norm rms --ckpt-every 25 ^
 --roll %K% --roll-batch %RB% --roll-samples 16 --roll-n 32

echo. & echo === 3. R1: rollout only, K=%K% =================================
%PY% train_pidon.py %COMMON% --target analytic --lam-div 0.0 --out pidon_R1_roll.pt

echo. & echo === 4. R2: rollout + both stage-2 fixes ========================
%PY% train_pidon.py %COMMON% --target yee --lam-div 1.0 --out pidon_R2_all.pt

echo. & echo === 5. measure both, periodic box and PEC cavity ===============
for %%K2 in (pidon_R1_roll pidon_R2_all) do (
  if exist %%K2.pt (
    echo. & echo ---- %%K2, periodic rollout ----
    %PY% rollout.py --ckpt %%K2.pt --steps 400
    echo. & echo ---- %%K2, PEC cavity end-to-end ----
    %PY% test_dco.py --ckpt %%K2.pt --exp1-samples 20 --exp2-sizes 16 32 48 ^
        --steps 300 --warm 300 --src-mode diff
  )
)

%PY% make_figs.py
echo. & echo ALL DONE
endlocal

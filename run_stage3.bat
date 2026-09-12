@echo off
REM ===================================================================
REM  Stage 3 -- the training distribution, not the loss.
REM
REM  EXP 3a says the DCO is wrong by 1900% on a cavity field OPEN LOOP,
REM  so no stability argument can explain it.  manifold_check.py says
REM  why: the paper's eq.(2) gives every sample ONE propagation
REM  direction, so every training field is a 1-D profile extruded in 3-D
REM  (dominant-direction share 0.97), while the cavity field is nearly
REM  isotropic (0.35).  This runs the fix and measures it.
REM
REM    .\run_stage3.bat            regenerates 1500 samples at 16^3
REM    .\run_stage3.bat 800        fewer samples if you are short of time
REM ===================================================================
setlocal
set NS=%1
if "%NS%"=="" set NS=1500

if not exist "dco_L3d.pt" ( echo MISSING dco_L3d.pt & exit /b 1 )

echo === where the training set sits vs the cavity (20 s) ============
py -3.11 manifold_check.py
if errorlevel 1 exit /b 1

echo. & echo === regenerate with an independent direction per wave =========
py -3.11 gen_data.py --n 16 --samples %NS% --dirs per-wave --seed 11 --out data_16_pw.npz
if errorlevel 1 exit /b 1

echo. & echo === retrain from dco_L3d.pt on the wider distribution =========
REM analytic target + no physics loss, so this isolates the DATA change
REM against the stage-4 baseline exactly.
py -3.11 train_pidon.py --data data_16_pw.npz --init dco_L3d.pt --levels 3 ^
    --base 32 --epochs 200 --batch 16 --coords cellsize --norm rms ^
    --target analytic --lam-div 0.0 --out pidon_D_perwave.pt
if errorlevel 1 exit /b 1

echo. & echo === and the same plus both stage-2 fixes ======================
py -3.11 train_pidon.py --data data_16_pw.npz --init dco_L3d.pt --levels 3 ^
    --base 32 --epochs 200 --batch 16 --coords cellsize --norm rms ^
    --target yee --lam-div 1.0 --out pidon_E_all.pt

echo. & echo === acceptance -- watch EXP 3a, not just 3b ===================
for %%K in (pidon_D_perwave pidon_E_all) do (
  if exist %%K.pt (
    echo. & echo ---- %%K ----
    py -3.11 test_dco.py --ckpt %%K.pt --exp1-samples 20 --exp2-sizes 16 32 48 --steps 150 --warm 300
  )
)

py -3.11 make_figs.py
echo. & echo ALL DONE
endlocal

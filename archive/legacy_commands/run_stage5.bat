@echo off
REM ===================================================================
REM  Stage 5 -- rollout training.  The first term that optimises what
REM  we actually care about: does the learned operator survive being
REM  ITERATED?
REM
REM  The stage-2 terms are both single step.  A network can fit the
REM  curl to 2e-2 and satisfy div(curl)=0 and still be useless after
REM  fifty leapfrog steps, because nothing in either loss ever saw a
REM  second step.  --roll K unrolls K steps inside the training loop
REM  and penalises the drift from the exact-curl rollout.
REM
REM  The rollout runs on a PERIODIC box (rollout.py), not the PEC
REM  cavity: uniform shapes, no source, nothing accumulates, and k*d is
REM  in band by construction.  The cavity stays as the end-to-end test.
REM
REM  Expect 1-2 h per run.  Checkpoints every 25 epochs, so Ctrl-C at
REM  any point still leaves usable weights.
REM ===================================================================
setlocal
set SW=--exp1-samples 20 --exp2-sizes 16 32 48 --steps 300 --warm 300 --src-mode diff

echo === 0. versions =================================================
py -3.11 check_files.py
if errorlevel 1 exit /b 1

echo. & echo === 1. the rollout harness must be exact before training through it
py -3.11 rollout.py --selftest
if errorlevel 1 (
  echo   SELF-TEST FAILED -- stopping.  Do not train through a broken scheme.
  exit /b 1
)

echo. & echo === 2. baseline: how far does dco_L3d get, iterated? ===========
py -3.11 rollout.py --ckpt dco_L3d.pt --steps 400
if errorlevel 1 exit /b 1

set C1=--data data_16.npz --init dco_L3d.pt --levels 3 --base 32 --epochs 200 ^
 --batch 16 --coords cellsize --norm rms --ckpt-every 25 ^
 --roll 8 --roll-batch 1 --roll-samples 8 --roll-n 32

echo. & echo === 3. R1: rollout only (isolates the new term) =================
py -3.11 train_pidon.py %C1% --target analytic --lam-div 0.0 --out pidon_R1_roll.pt

echo. & echo === 4. R2: rollout + both stage-2 fixes ========================
py -3.11 train_pidon.py %C1% --target yee --lam-div 1.0 --out pidon_R2_all.pt

echo. & echo === 5. measure both, periodic box and PEC cavity ===============
for %%K in (pidon_R1_roll pidon_R2_all) do (
  if exist %%K.pt (
    echo. & echo ---- %%K, periodic rollout ----
    py -3.11 rollout.py --ckpt %%K.pt --steps 400
    echo. & echo ---- %%K, PEC cavity end-to-end ----
    py -3.11 test_dco.py --ckpt %%K.pt %SW%
  )
)

py -3.11 make_figs.py
echo. & echo ALL DONE
endlocal

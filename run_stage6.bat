@echo off
REM ===================================================================
REM  Stage 6 -- make div(curl) = 0 STRUCTURAL instead of penalised.
REM
REM  Stage 5's hard result: a CNN cannot satisfy an exact differential
REM  identity through a loss term.  Measured on the periodic box,
REM  div(DCO curl) / div(exact curl):
REM      baseline                     6.69e+05
REM      + explicit ||div||^2 penalty 4.41e+05     <- only 1.5x
REM
REM  --head potential outputs a vector potential A and applies the EXACT
REM  discrete curl to it, so div(curl(A)) = 0 holds by construction.
REM  Verified on an untrained network: relative divergence 4.6e-17 for
REM  the potential head against 1.14 for the direct one.
REM
REM  THE JUDGMENT EXPERIMENT
REM  R2 (stage 5, direct head + Yee target + div penalty + rollout) is
REM  the incumbent.  P1 below is identical in every respect except the
REM  head, and needs no div penalty because the identity is exact.  If
REM  the divergence really was what limited closed-loop survival, P1's
REM  step count jumps; if it does not, the limit is elsewhere and that
REM  is worth knowing too.
REM
REM  ~90 min on a 6 GB card, same as R2.
REM ===================================================================
setlocal
set PY=py -3.11

echo === 0. versions =================================================
%PY% check_files.py
if errorlevel 1 exit /b 1

echo. & echo === 1. rollout harness =========================================
%PY% rollout.py --selftest
if errorlevel 1 exit /b 1

set COMMON=--data data_16.npz --levels 3 --base 32 --epochs 200 --batch 16 ^
 --coords cellsize --norm rms --ckpt-every 25 ^
 --roll 8 --roll-batch 1 --roll-samples 8 --roll-n 32 --target yee

REM No --init: the potential head's weights mean something different from
REM the direct head's (they are a vector potential, not a curl), so warm
REM starting from dco_L3d.pt would be worse than useless.
echo. & echo === 2. P1: potential head, otherwise identical to R2 ===========
%PY% train_pidon.py %COMMON% --head potential --lam-div 0.0 --out pidon_P1_pot.pt

echo. & echo === 3. measure, periodic box and PEC cavity ====================
if exist pidon_P1_pot.pt (
  %PY% rollout.py --ckpt pidon_P1_pot.pt --steps 400
  %PY% test_dco.py --ckpt pidon_P1_pot.pt --exp1-samples 20 ^
      --exp2-sizes 16 32 48 --steps 300 --warm 300 --src-mode diff
)

%PY% make_figs.py
echo. & echo ALL DONE
echo   Compare against R2: rollout.py reported "div of the DCO curl /
echo   div of the exact curl = 2.222e+04 / 5.035e-02" for R2.  P1 should
echo   report a numerator at or below the denominator.
endlocal

@echo off
REM ===================================================================
REM  run_rho32.bat -- redo stage 2 with the probe set up correctly.
REM
REM  Last night's stage 2 used --n 16.  rollout.allowed_m's own docstring
REM  says that grid has exactly ONE in-band lattice wavenumber, so the
REM  probe state collapsed to a single-wavelength axis-aligned
REM  superposition: eps0 came out 3-5x worse than EXP 1 and barely moved
REM  with the seed.  On top of that --warm was a fixed step count, so the
REM  five CFL rows handed over at different points of the standing-wave
REM  cycle (rms|E| swung 6x) and were never comparable to each other.
REM
REM  Fixed here: n=32 (six distinct k*d), warm-up at fixed physical time,
REM  three independent probe states per CFL, spread reported.
REM
REM  ~2 h.  Run it as:
REM      .\run_rho32.bat 2>&1 | Tee-Object rho32.log
REM ===================================================================
setlocal
cd /d %~dp0
echo.
echo === self-test first: the exact curl must give rho = 1 ==============
py -3.11 spectral_dco.py --selftest
if errorlevel 1 (
  echo   *** self-test FAILED -- stop, everything below would be meaningless
  exit /b 1
)
echo.
echo === re-probing every checkpoint at n=32 ============================
echo   started %DATE% %TIME%
del /q _rho32_failed.txt 2>nul
for %%F in (dco_*.pt pidon_*.pt) do (
  echo -------------------------------------------------------------------
  echo   %%F
  py -3.11 spectral_dco.py --ckpt %%F --n 32 --cfl 0.99 0.70 0.50 --samples 3 --iters 160 --burn 55 --emp-steps 400
  if errorlevel 1 echo %%F>> _rho32_failed.txt
)
echo.
echo   finished %DATE% %TIME%
if exist _rho32_failed.txt (
  echo.
  echo   *** these checkpoints FAILED and produced no json:
  type _rho32_failed.txt
  echo   *** a crashed checkpoint is silently absent from the report, so
  echo   *** always read this list -- that is how dco_L3 and dco_L3b went
  echo   *** missing from the 2026-09-09 sweep without anyone noticing.
) else (
  echo   every checkpoint produced a json.
)
echo.
echo === the verdict ====================================================
py -3.11 night_report.py

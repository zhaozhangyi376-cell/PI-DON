@echo off
REM ===================================================================
REM  run_night2.bat -- overnight, stage 2 of the paper (Algorithm 1).
REM
REM  PURE ASCII, no cmd metacharacters. See FILE_MAP.md for why.
REM
REM  This is the part we had never built. Algorithm 1 re-optimises the
REM  DCO at EVERY time step until the physics-informed loss drops below
REM  the tolerance, which is what keeps the paper's solver stable. See
REM  PAPER_NOTES.md and CLAUDE.md in this directory.
REM
REM  Four steps:
REM    1  calibration, 20 steps, so the seconds-per-step is on record
REM       before committing to the long runs
REM    2  Algorithm 1 from the pretrained DCO
REM    3  Algorithm 1 from random init -- the Fig 8 control
REM    4  EXP2 again, now recording eq.(5) MRE, so claim C9 can finally
REM       be judged on the paper's own metric, then refresh RESULTS.md
REM ===================================================================
setlocal
cd /d %~dp0
echo   started %DATE% %TIME%

echo.
echo === 1/4  calibration: 20 steps, measure seconds per step ==========
py -3.11 lab_log.py run -m "Algorithm 1 calibration, 20 steps" -- py -3.11 pidon_solve.py --steps 20 --init dco_paper32.pt --max-inner 20

echo.
echo === 2/4  Algorithm 1, pretrained DCO init =========================
py -3.11 lab_log.py run -m "Algorithm 1, pretrained DCO init, 800 steps" -- py -3.11 pidon_solve.py --steps 800 --init dco_paper32.pt --max-inner 20 --out pidon_solve_pretrained.json

echo.
echo === 3/4  Algorithm 1, random init (the Fig 8 control) =============
py -3.11 lab_log.py run -m "Algorithm 1, random init, 800 steps, Fig 8 control" -- py -3.11 pidon_solve.py --steps 800 --init random --max-inner 20 --out pidon_solve_random.json

echo.
echo === 4/4  EXP2 with eq.(5) MRE, then refresh the claim table =======
py -3.11 lab_log.py run -m "EXP2 recording eq.(5) MRE, to re-judge C9 on the paper metric" -- py -3.11 test_dco.py --ckpt dco_paper32.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
py -3.11 verify_claims.py --run --md

echo.
echo   finished %DATE% %TIME%
echo.
echo   in the morning, look at:
echo     py -3.11 lab_log.py show
echo     type RESULTS.md

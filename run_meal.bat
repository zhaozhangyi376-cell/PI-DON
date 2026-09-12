@echo off
REM ===================================================================
REM  run_meal.bat -- about one hour of work, every step logged.
REM
REM  PURE ASCII ONLY, and no cmd metacharacters anywhere in this file.
REM  cmd.exe reads it in the OEM codepage. UTF-8 Chinese text gets
REM  mis-decoded, the byte stream slips out of alignment, and a stray
REM  separator byte can surface and cut a command in half. That is what
REM  silently truncated every command after the double dash in the
REM  2026-09-10 19:03 run: lab_log reported "nothing to run" five times.
REM  The caret is the other trap: cmd eats it as its escape character, so
REM  32 cubed written with a caret comes out as 323. Spell it out.
REM
REM  WHAT IT IS FOR
REM  C9 currently compares pidon_R2_all against the paper's section III-D
REM  and gets 2.14x.  But that net was trained on a 16-cubed grid and the
REM  paper trained on 32-cubed, so we extrapolate further and the contest
REM  is not even.  dco_paper32 is the one trained at 32-cubed in the
REM  paper's own configuration; comparing THAT is the like-for-like test.
REM
REM  C3's slope b rests on only 3 CFL points (0.99/0.70/0.50, a 2x span)
REM  and 3 seeds.  Widen to 5 points (0.99..0.30, a 3.3x span) and 5 seeds
REM  so the error bar on b actually narrows.
REM
REM  Launch it from PowerShell, teeing the output to meal.log -- the
REM  exact line is in the chat message that shipped this file.
REM ===================================================================
setlocal
cd /d %~dp0
echo   started %DATE% %TIME%

echo.
echo === 1/4  dco_paper32 acceptance suite (paper parity: 32-cubed) =====
if not exist dco_paper32.pt (
  echo   dco_paper32.pt not here, skipping
) else (
  py -3.11 lab_log.py run -m "dco_paper32 acceptance: like-for-like vs paper III-D" -- py -3.11 test_dco.py --ckpt dco_paper32.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
)

echo.
echo === 2/4  dco_L4b, same suite, as a control ========================
if not exist dco_L4b.pt (
  echo   dco_L4b.pt not here, skipping
) else (
  py -3.11 lab_log.py run -m "dco_L4b acceptance, control for dco_paper32" -- py -3.11 test_dco.py --ckpt dco_L4b.pt --exp1-samples 20 --exp2-sizes 32 48 64 64x96x16 32x64x16 --steps 400 --warm 300 --src-mode diff
)

echo.
echo === 3/4  denser CFL sweep on the three main checkpoints ============
echo   5 CFL points x 5 seeds, to tighten the slope b behind claim C3
echo   this is the long step
for %%F in (pidon_R2_all dco_paper32 dco_L3d) do (
  if not exist %%F.pt (
    echo   %%F.pt not here, skipping
  ) else (
    echo -------------------------------------------------------------------
    echo   %%F
    py -3.11 lab_log.py run -m "%%F denser CFL sweep, 5 CFL x 5 seeds, tightens C3" -- py -3.11 spectral_dco.py --ckpt %%F.pt --n 32 --cfl 0.99 0.85 0.70 0.60 0.30 --samples 5 --iters 160 --burn 55 --emp-steps 600
  )
)

echo.
echo === 4/4  rebuild the claim table ==================================
py -3.11 verify_claims.py --run --md

echo.
echo   finished %DATE% %TIME%
echo.
echo   next, look at these three:
echo     py -3.11 lab_log.py show
echo     type RESULTS.md
echo     git add -A  then commit and push
endlocal

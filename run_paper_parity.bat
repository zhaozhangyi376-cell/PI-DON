@echo off
REM ===================================================================
REM  The paper's own training configuration -- needs a big card.
REM
REM  Everything measured so far was 16^3 / 400 epochs / L=3, so every row
REM  of the comparison against the paper carries a "configuration differs"
REM  caveat.  This run removes that whole column: 32^3, 1000 samples,
REM  L=4, 1000 epochs, batch 32, lr 1e-4 -- section III-C verbatim.
REM
REM  TWO runs, because "the paper's configuration" is ambiguous in one place:
REM    literal  absolute coordinates into the trunk + max normalisation.
REM             This is what the paper describes.
REM    fixed    our two corrections (cellsize coordinates, rms
REM             normalisation), which are what make dimension invariance
REM             actually work.
REM  Running both answers a real question: does L=4's 7x advantage over
REM  L=3 in Table I survive the corrections?  At 16^3 it did not -- at
REM  equal epochs L=4 degraded 16.7x at 48^3 against L=3's 1.42x.
REM
REM  Needs roughly 8-10 GB of VRAM.  A 6 GB card cannot run this.
REM ===================================================================
setlocal
set PY=py -3.11

echo === 0. hardware check ==========================================
%PY% -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available());print('device',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE');print('VRAM GB %.1f'%(torch.cuda.get_device_properties(0).total_memory/1e9) if torch.cuda.is_available() else '')"
if errorlevel 1 exit /b 1
echo.
echo   If cuda says False, STOP -- this run is pointless on CPU.
echo   If VRAM is under 10 GB, lower --batch to 8 and expect it to be slow.
echo.

if not exist data_32.npz (
  echo === generating the paper's dataset: 1000 samples at 32^^3 ^(~10 min^)
  %PY% gen_data.py --n 32 --samples 1000 --out data_32.npz --seed 5
  if errorlevel 1 exit /b 1
)

set BASE=--data data_32.npz --levels 4 --base 32 --epochs 1000 --batch 32 --lr 1e-4

echo. & echo === A. literal paper configuration =============================
%PY% train_dco.py %BASE% --coords abs --norm max --out dco_paper_literal.pt

echo. & echo === B. same, with our two corrections ==========================
%PY% train_dco.py %BASE% --coords cellsize --norm rms --out dco_paper_fixed.pt

echo. & echo === C. all three metrics + the gap decomposition ===============
for %%K in (dco_paper_literal dco_paper_fixed) do (
  if exist %%K.pt (
    echo. & echo ---- %%K ----
    %PY% gap_analysis.py --ckpt %%K.pt
    %PY% test_dco.py --ckpt %%K.pt --exp1-samples 20 --exp2-sizes 32 64 ^
        --steps 300 --warm 300 --src-mode diff
  )
)

%PY% make_figs.py
echo. & echo ALL DONE -- dco_paper_fixed.pt is the number to put next to Table I
endlocal

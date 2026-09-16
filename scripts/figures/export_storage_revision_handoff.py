"""Export exact goal handoff and document hashes; not a G0 verifier."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
from pathlib import Path
from pidon_recording import sha256_file

ROOT=PROJECT_ROOT
OUT=ROOT/'evidence/gpt6_plan_v4_review/storage_revision'
plan=ROOT/'docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md'
body=plan.read_text(encoding='utf-8')
section=body.split('## 七、给下一会话的 goal 执行指令',1)[1]
instruction=section.split('```text\n',1)[1].split('\n```',1)[0]+'\n'
dest=OUT/'GOAL_INSTRUCTION.txt'
if dest.exists():
    raise FileExistsError(dest)
dest.write_text(instruction,encoding='utf-8')
old=json.loads((ROOT/'evidence/gpt6_plan_v4_review/delivery_verification.json').read_text(encoding='utf-8'))
forecast=json.loads((OUT/'storage_forecast_refined.json').read_text(encoding='utf-8'))
snapshot=OUT/'plan_before_storage_revision.md'
assert sha256_file(snapshot)==old['plan_sha256']
assert forecast['estimated_new_artifact_bytes']<=forecast['normal_artifact_budget_bytes']
assert not (ROOT/'evidence/gpt6_plan_v4_night/night_manifest.json').exists()
manifest={'scope':'revised_plan_delivery_only_not_production_certification',
    'plan_path':str(plan), 'plan_sha256':sha256_file(plan),
    'original_plan_sha256':sha256_file(snapshot), 'goal_instruction_sha256':sha256_file(dest),
    'forecast_sha256':sha256_file(OUT/'storage_forecast_refined.json'),
    'cleanup_performed':False,'formal_training_started':False,
    'estimated_new_artifact_gib':forecast['estimated_new_artifact_gib'],
    'normal_artifact_budget_gib':forecast['normal_artifact_budget_gib'],
    'source_facts':'lab_log #177/#178; original audit delivery #176 preserved'}
(OUT/'revision_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))

"""Include both populated Adam states in the storage forecast."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
import math
import shutil
from pathlib import Path
import torch

from pidon_recording import sha256_file

ROOT = PROJECT_ROOT
OUT = ROOT / 'evidence/gpt6_plan_v4_review/storage_revision'
GIB = 1024 ** 3


def tensor_bytes(value):
    if torch.is_tensor(value):
        return value.numel() * value.element_size()
    if isinstance(value, dict):
        return sum(tensor_bytes(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(tensor_bytes(v) for v in value)
    return 0


initial = json.loads((OUT/'storage_audit.json').read_text(encoding='utf-8'))
model_path = ROOT / initial['checkpoints'][0]['path']
state = torch.load(model_path, map_location='cpu', weights_only=False)
adam_h = tensor_bytes(state['opt_H'])
adam_e = tensor_bytes(state['opt_E'])
# Same architecture for H/E. The old H-only file has an empty E optimizer.
full_state_estimate = model_path.stat().st_size + max(0, adam_h-adam_e)
conservative = math.ceil(full_state_estimate*1.25)
counts = initial['checkpoint_counts_budget']
estimate = sum(counts.values())*conservative+initial['other_artifact_allowance_bytes']
free = shutil.disk_usage(ROOT).free
budget = min(16*GIB, max(0, free-6*GIB))
result = {'classification':'refined_storage_forecast_not_training',
    'source_checkpoint': str(model_path.relative_to(ROOT)), 'source_sha256':sha256_file(model_path),
    'measured_adam_H_tensor_bytes':adam_h, 'measured_adam_E_tensor_bytes':adam_e,
    'full_two_optimizer_checkpoint_estimated_bytes':full_state_estimate,
    'conservative_full_checkpoint_bytes':conservative,
    'checkpoint_counts_budget':counts, 'estimated_new_artifact_bytes':estimate,
    'estimated_new_artifact_gib':estimate/GIB, 'disk_free_bytes':free, 'disk_free_gib':free/GIB,
    'normal_artifact_budget_bytes':budget,'normal_artifact_budget_gib':budget/GIB,
    'os_free_floor_bytes':5*GIB,'emergency_reserve_bytes':GIB,
    'cleanup_needed_now':estimate>budget, 'deleted_files':[], 'formal_dco_updates':0,
    'supersedes_forecast_only':'storage_audit.json; initial forecast did not add the second populated Adam state'}
path=OUT/'storage_forecast_refined.json'
if path.exists():
    raise FileExistsError(path)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

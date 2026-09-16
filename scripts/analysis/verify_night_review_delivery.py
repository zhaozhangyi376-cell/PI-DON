"""Verify this audit delivery; does not run production tests or training."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
from pathlib import Path
from night_review_evidence import ROOT, load_review, contract_checks
from pidon_recording import sha256_file
import verify_claims

data = load_review()
folder = ROOT / 'evidence/gpt6_plan_v4_review'
old = ROOT / 'evidence/gpt6_plan_v3/h_layout_candidate'
readback = json.loads((old / 'A3_readback.json').read_text(encoding='utf-8'))
old_hashes = {row['path']: row['sha256'] for row in readback['rows']}
weights = {row['path']: sha256_file(ROOT / row['path']) == row['sha256'] == old_hashes[Path(row['path']).name]
           for row in data['historical_fits']}
production = {name: sha256_file(ROOT / name) == data['source_hashes'][name]
              for name in ('pidon_solve.py', 'pidon_contract.py', 'pidon_recording.py',
                           'pidon_exact_control.py', 'g0_verifier.py', 'h_layout_candidate.py')}
required = ['REVIEW.md', 'PROTOCOL.md', 'PLAN_REVIEW.md', 'audit.json', 'review_evidence.png']
artifacts = {name: (folder/name).is_file() for name in required}
plan_path = ROOT / 'docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md'
plan = plan_path.read_text(encoding='utf-8')
checks = {
    'historical_weights_unchanged': all(weights.values()),
    'production_code_unchanged_this_audit': all(production.values()),
    'master_weight_hash_matches': sha256_file(ROOT/'dco_lr1e3_300.pt') == '3f259bc887a10fac77f6bdf77b43ba1ad6b45827a3f8b9bd685934acc47ca5d7',
    'audit_retains_six_failed_contract_assertions': all(not value for value in contract_checks(data).values()),
    'historical_G0_claim_withdrawn': verify_claims.v3_g0_complete(None)[0] == 'FAIL',
    'historical_candidate_still_FAIL': verify_claims.v3_h_layout_candidate(None)[0] == 'FAIL',
    'all_review_artifacts_exist': all(artifacts.values()),
    'plan_explicitly_not_executed': 'N0–N6 均 **NOT_RUN**' in plan,
    'plan_has_goal_handoff': '七、给下一会话的 goal 执行指令' in plan,
    'review_corrections_present': all(text in plan for text in ('G0_after_head_integration.json', '[896:1024]', '包括step、exp_avg、exp_avg_sq')),
    'no_formal_training_updates': data['formal_dco_updates_this_audit'] == 0,
}
out = {'scope': 'audit_delivery_integrity_only_not_production_G0', 'checks': checks,
       'weights': weights, 'production': production, 'artifacts': artifacts,
       'plan_sha256': sha256_file(plan_path), 'status': 'PASS' if all(checks.values()) else 'FAIL'}
(folder/'delivery_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
raise SystemExit(0 if all(checks.values()) else 1)

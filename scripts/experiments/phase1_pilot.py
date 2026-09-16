"""P5 phase-1 learnability pilot on fixed, declared 32^3 analytic samples."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

import dco as D


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def component_nmae(pred, target):
    return [float(D.nmae(pred[:, c:c + 1], target[:, c:c + 1])) for c in range(3)]


def update_segments(first_budget, maximum_budget):
    """Cumulative update targets for the pre-registered 200→500 escalation."""
    if first_budget <= 0 or maximum_budget < first_budget:
        raise ValueError("require 0 < first_budget <= maximum_budget")
    return (first_budget,) if first_budget == maximum_budget else (first_budget, maximum_budget)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data_32.npz")
    parser.add_argument("--indices", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--updates", type=int, default=200)
    parser.add_argument("--max-updates", type=int, default=500)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--device", default="", choices=["", "cpu", "cuda"])
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/phase1_pilot")
    args = parser.parse_args()
    if args.updates > args.max_updates:
        raise ValueError("--updates may not exceed --max-updates")
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    z = np.load(args.data)
    indices = list(args.indices)
    if not indices or min(indices) < 0 or max(indices) >= len(z["E"]):
        raise ValueError("indices must select existing samples")
    E = torch.from_numpy(z["E"][indices]).to(device)
    C = torch.from_numpy(z["C"][indices]).to(device)
    d = torch.from_numpy(z["D"][indices] * 1e3).to(device)
    n = int(z["n"])
    coords = torch.cat([D.make_coords(n, one, "cellsize") for one in d]).to(device)
    net = D.DCO(levels=4, base=32).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    eh, ch, scale, length = D.normalise(E, C, d, "rms")

    def measure():
        with torch.no_grad():
            out = net(eh, coords)
            loss = float(((out - ch).pow(2).flatten(1).mean(1) /
                          ch.pow(2).flatten(1).mean(1).clamp_min(1e-30)).mean())
            physical = D.denormalise(out, scale, length)
            per = component_nmae(physical, C)
        return loss, per, float(np.mean(per))

    initial_loss, initial_per, initial_macro = measure()
    history = [{"updates": 0, "relative_squared_loss": initial_loss,
                "component_nmae": initial_per, "macro_nmae": initial_macro}]
    started = time.perf_counter()
    targets = update_segments(args.updates, args.max_updates)
    target_updates = targets[0]
    completed_updates = 0
    while True:
        for _ in range(target_updates - completed_updates):
            out = net(eh, coords)
            loss = ((out - ch).pow(2).flatten(1).mean(1) /
                    ch.pow(2).flatten(1).mean(1).clamp_min(1e-30)).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
        final_loss, final_per, final_macro = measure()
        used = target_updates
        completed_updates = used
        history.append({"updates": used, "relative_squared_loss": final_loss,
                        "component_nmae": final_per, "macro_nmae": final_macro})
        passed = initial_loss / max(final_loss, 1e-300) >= 100.0 and final_macro <= 1e-3
        if passed or target_updates >= args.max_updates:
            break
        target_updates = targets[-1]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "learnability_checkpoint.pt"
    torch.save({"state": net.state_dict(), "optimizer": opt.state_dict(), "seed": args.seed,
                "indices": indices, "updates": used, "coords": "cellsize", "norm": "rms",
                "data_sha256": sha256(args.data)}, checkpoint)
    result = {
        "schema": "pidon-p5-learnability-v1", "classification": "phase-1 fixed-sample learnability pilot; not Fig.6 evaluation",
        "config": vars(args), "device": device, "data_sha256": sha256(args.data),
        "history": history, "actual_updates": used, "loss_reduction": initial_loss / max(final_loss, 1e-300),
        "passed": passed, "elapsed_s": time.perf_counter() - started,
        "gate": "relative squared loss reduction >=100 and macro nMAE <=1e-3",
    }
    (out / "learnability.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f'''# P5 固定样本可学习性检查

样本索引：{indices}；随机种子：{args.seed}；输入归一化：RMS；坐标：cellsize。

| 实际更新 | 相对平方损失 | 宏 nMAE |
|---:|---:|---:|
''' + "\n".join(f"| {row['updates']} | {row['relative_squared_loss']:.6e} | {row['macro_nmae']:.6e} |" for row in history) + f'''\n\n损失下降倍数：`{result['loss_reduction']:.3f}`。预登记门槛为下降至少 100 倍且宏 nMAE 不高于 `1e-3`；本次结果：**{'通过' if passed else '未通过'}**。

这只是四个固定训练样本的可学习性检查，不是论文 Table I、Fig.6 或阶段二闭环结果。
'''
    (out / "P5_LEARNABILITY_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"actual_updates": used, "loss_reduction": result["loss_reduction"],
                      "macro_nmae": final_macro, "passed": passed, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

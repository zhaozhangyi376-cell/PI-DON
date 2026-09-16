"""Read-only re-evaluation of saved P5 assets using the v2 metric contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch

import dco as D


ROOT = Path(__file__).resolve().parent
V1 = ROOT / "evidence" / "gpt6_plan_v1"
OUT = ROOT / "evidence" / "gpt6_plan_v2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def coords(d):
    return torch.cat([D.make_coords(32, row, "cellsize") for row in d])


def per_sample_metrics(pred, target):
    rows = []
    for sample in range(len(pred)):
        components = []
        for component in range(3):
            p, t = pred[sample, component], target[sample, component]
            maximum = float(t.abs().max())
            mae = float((p - t).abs().mean())
            components.append({"component": "xyz"[component], "mae": mae,
                               "target_max_abs": maximum,
                               "nmae": (mae / maximum if maximum else None),
                               "mre_eq5": float(D.mre_eq5(p, t)),
                               "strict_zero_count": int((t == 0).sum())})
        rows.append({"sample": sample, "components": components,
                     "macro_nmae": float(np.mean([x["nmae"] for x in components if x["nmae"] is not None]))})
    macro = float(np.mean([component["nmae"] for row in rows for component in row["components"]
                           if component["nmae"] is not None]))
    return rows, macro


def physical_prediction(net, E, C, d):
    with torch.no_grad():
        eh, _, scale, length = D.normalise(E, C, d, "rms")
        return D.denormalise(net(eh, coords(d)), scale, length)


def gradient_norm_for_scale(net, E, C, d, floor):
    net.zero_grad(set_to_none=True)
    eh, _, scale, length = D.normalise(E, C, d, "rms")
    physical = D.denormalise(net(eh, coords(d)), scale, length)
    local = C.abs().amax(dim=(2, 3, 4), keepdim=True).clamp_min(floor)
    loss = ((physical - C) / local).pow(2).mean()
    loss.backward()
    norm = float(torch.sqrt(sum((p.grad.pow(2).sum() for p in net.parameters() if p.grad is not None))).cpu())
    net.zero_grad(set_to_none=True)
    return float(loss.detach()), norm


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data_path = ROOT / "data_32.npz"
    pilot_path = V1 / "phase1_pilot_corrected" / "learnability_checkpoint.pt"
    pilot = torch.load(pilot_path, map_location="cpu", weights_only=False)
    z = np.load(data_path)
    indices = pilot["indices"]
    E = torch.from_numpy(z["E"][indices]).float()
    C = torch.from_numpy(z["C"][indices]).float()
    d = torch.from_numpy(z["D"][indices] * 1e3).float()
    net = D.DCO(levels=4, base=32); net.load_state_dict(pilot["state"]); net.eval()
    pred = physical_prediction(net, E, C, d)
    sample_rows, macro = per_sample_metrics(pred, C)

    ab = json.loads((V1 / "phase1_ab_pilot" / "ab_pilot.json").read_text(encoding="utf-8"))
    E128 = torch.from_numpy(z["E"][:128]).float()
    C128 = torch.from_numpy(z["C"][:128]).float()
    d128 = torch.from_numpy(z["D"][:128] * 1e3).float()
    maxima = C128.abs().amax(dim=(2, 3, 4))
    old_floor = 1e-6 * float(ab["curl_e0"])
    new_floor = 1e-6 * 20.0
    changed = (maxima < old_floor) & (maxima >= new_floor)
    below_new = maxima < new_floor
    b_state = torch.load(V1 / "phase1_ab_pilot" / "B_200.pt", map_location="cpu", weights_only=False)
    bnet = D.DCO(levels=4, base=32); bnet.load_state_dict(b_state["state"]); bnet.train()
    old_loss, old_grad = gradient_norm_for_scale(bnet, E128[:4], C128[:4], d128[:4], old_floor)
    new_loss, new_grad = gradient_norm_for_scale(bnet, E128[:4], C128[:4], d128[:4], new_floor)
    output = {
        "schema": "pidon-r3-v2-readonly-recompute", "classification": "read-only saved-asset audit; no optimizer.step",
        "data_sha256": sha256(data_path), "pilot_checkpoint_sha256": sha256(pilot_path),
        "indices": indices, "per_sample_component_metrics": sample_rows,
        "corrected_macro_nmae": macro,
        "legacy_macro_nmae": json.loads((V1 / "phase1_pilot_corrected" / "learnability.json").read_text(encoding="utf-8"))["history"][-1]["macro_nmae"],
        "ab_floor_audit": {"legacy_curlE0": ab["curl_e0"], "required_curlE0": 20.0,
                            "legacy_floor": old_floor, "required_floor": new_floor,
                            "components_affected_by_floor_change": int(changed.sum()),
                            "components_below_required_floor": int(below_new.sum()),
                            "total_components": int(maxima.numel()),
                            "final_B_first4_loss_old_floor": old_loss,
                            "final_B_first4_loss_required_floor": new_loss,
                            "final_B_first4_grad_norm_old_floor": old_grad,
                            "final_B_first4_grad_norm_required_floor": new_grad},
        "p3_asset_status": "INCOMPLETE: v1 fixed-state files contain inputs/targets and scalar reports, not final trained predictions/weights or fixed-amplitude denominators.",
    }
    (OUT / "R3_recompute.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f"""# R3：保存资产的只读复算

## 四样本固定可学习性

使用保存的 500-update checkpoint 对原索引 `{indices}` 做纯推理。v2 逐样本、逐分量 nMAE 宏平均为 `{macro:.6e}`；旧报告的跨样本全局最大值聚合为 `{output['legacy_macro_nmae']:.6e}`。两者并列保存，v2 数值才用于后续判断。

这一结果只说明保存模型在这四个训练样本上的误差；不构成 Fig.6、独立测试或阶段二证据。所有 4×3 MAE、局部最大值、nMAE、Eq.(5) MRE 和严格零点数在 `R3_recompute.json`。

## A/B 损失常数审计

旧 A/B 使用 `curlE0={ab['curl_e0']}`，对应 floor `{old_floor:.6e}`；登记定义应为 `curlE0=20`、floor `{new_floor:.6e}`。128×3 个训练样本分量中，{int(changed.sum())} 个会因两 floor 的差异改变权重，{int(below_new.sum())} 个甚至低于登记 floor。

在保存的 B-200 最终模型、前四训练样本上，不进行优化器更新而只反向计算：旧 floor loss/梯度范数为 `{old_loss:.6e}/{old_grad:.6e}`，登记 floor 为 `{new_loss:.6e}/{new_grad:.6e}`。这证明两种公式不是相同损失；它不能倒推出 200 次训练过程中哪个因素导致了 B 的退步。

## 固定状态资产

v1 P3 缺最终网络、预测场和固定幅值分母，无法从标量相对误差反造 G1 的 A_fixed。该项目保持 `INCOMPLETE`，待 R4 用修复接口重测。
"""
    (OUT / "R3_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"out": str(OUT / "R3_recompute.json"), "macro_nmae": macro,
                      "affected_floor_components": int(changed.sum()),
                      "legacy_floor": old_floor, "required_floor": new_floor}, ensure_ascii=False))


if __name__ == "__main__":
    main()

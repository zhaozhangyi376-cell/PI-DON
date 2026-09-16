"""P5 paired 128-sample A/B pilot for one declared loss reconstruction."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

import dco as D


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def batch_schedule(n_train, batch, updates, seed):
    gen = torch.Generator(device="cpu"); gen.manual_seed(seed)
    return [torch.randint(n_train, (batch,), generator=gen) for _ in range(updates)]


def make_coords(d):
    return torch.cat([D.make_coords(32, row, "cellsize") for row in d])


def per_component_macro(pred, target):
    per = []
    for c in range(3):
        vals = [D.nmae(pred[i:i + 1, c:c + 1], target[i:i + 1, c:c + 1]) for i in range(len(pred))]
        per.append(float(torch.stack(vals).mean()))
    return per, float(np.mean(per))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data_32.npz")
    parser.add_argument("--train-n", type=int, default=128)
    parser.add_argument("--dev-n", type=int, default=32)
    parser.add_argument("--updates", type=int, default=200)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--device", default="", choices=["", "cpu", "cuda"])
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/phase1_ab_pilot")
    args = parser.parse_args()
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    z = np.load(args.data)
    count = args.train_n + args.dev_n
    if count > len(z["E"]): raise ValueError("train/dev split exceeds available data")
    E = torch.from_numpy(z["E"][:count]).to(device)
    C = torch.from_numpy(z["C"][:count]).to(device)
    d = torch.from_numpy(z["D"][:count] * 1e3).to(device)
    Etr, Ctr, dtr = E[:args.train_n], C[:args.train_n], d[:args.train_n]
    Edev, Cdev, ddev = E[args.train_n:], C[args.train_n:], d[args.train_n:]
    schedule = batch_schedule(args.train_n, args.batch, args.updates, args.seed)
    initial = D.DCO(levels=4, base=32).state_dict()
    curl_e0 = float(Ctr.abs().amax())

    def evaluate(net):
        pred = []
        net.eval()
        with torch.no_grad():
            for start in range(0, len(Edev), args.batch):
                ee, cc, dd = Edev[start:start + args.batch], Cdev[start:start + args.batch], ddev[start:start + args.batch]
                eh, _, scale, length = D.normalise(ee, cc, dd, "rms")
                pred.append(D.denormalise(net(eh, make_coords(dd)), scale, length))
        net.train()
        return per_component_macro(torch.cat(pred), Cdev)

    def train(variant):
        net = D.DCO(levels=4, base=32).to(device); net.load_state_dict(copy.deepcopy(initial))
        opt = torch.optim.Adam(net.parameters(), lr=args.lr)
        before_per, before_macro = evaluate(net)
        started = time.perf_counter()
        for row in schedule:
            idx = row.to(device)
            ee, cc, dd = Etr[idx], Ctr[idx], dtr[idx]
            eh, ch, scale, length = D.normalise(ee, cc, dd, "rms")
            raw = net(eh, make_coords(dd))
            if variant == "A_relative":
                loss = ((raw - ch).pow(2).flatten(1).mean(1) /
                        ch.pow(2).flatten(1).mean(1).clamp_min(1e-30)).mean()
            else:
                physical = D.denormalise(raw, scale, length)
                component_scale = cc.abs().amax(dim=(2, 3, 4), keepdim=True).clamp_min(1e-6 * curl_e0)
                loss = ((physical - cc) / component_scale).pow(2).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
        after_per, after_macro = evaluate(net)
        return net, {"variant": variant, "actual_updates": args.updates,
                     "dev_component_nmae_before": before_per, "dev_macro_nmae_before": before_macro,
                     "dev_component_nmae_after": after_per, "dev_macro_nmae_after": after_macro,
                     "elapsed_s": time.perf_counter() - started}

    net_a, record_a = train("A_relative")
    net_b, record_b = train("B_component_localmax")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    torch.save({"state": net_a.state_dict(), "variant": "A_relative", "seed": args.seed}, out / "A_200.pt")
    torch.save({"state": net_b.state_dict(), "variant": "B_component_localmax", "seed": args.seed}, out / "B_200.pt")
    payload = {"schema": "pidon-p5-ab-v1", "classification": "paired development pilot; not Fig.6 or independent test",
               "config": vars(args), "data_sha256": sha256(args.data), "curl_e0": curl_e0,
               "batch_schedule_sha256": hashlib.sha256(torch.stack(schedule).numpy().tobytes()).hexdigest(),
               "records": [record_a, record_b], "same_initial_state": True,
               "selection_rule": "No promotion from this development result; full P5 noncubic and retention gates remain required."}
    (out / "ab_pilot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f'''# P5 配对 A/B 小试

两个方案从同一随机 L4/base32 初始状态开始，使用相同的 {args.updates} 个 batch（每 batch {args.batch} 个样本）、相同的 128 训练样本和 32 个未参与更新的开发样本。A 是现有相对损失；B 是按每个训练样本/分量真值局部最大值加权的物理量损失。B 的尺度只进入训练损失，不进入推理还原。

| 方案 | 开发宏 nMAE：训练前 | 开发宏 nMAE：{args.updates} 更新后 |
|---|---:|---:|
| A | {record_a['dev_macro_nmae_before']:.6e} | {record_a['dev_macro_nmae_after']:.6e} |
| B | {record_b['dev_macro_nmae_before']:.6e} | {record_b['dev_macro_nmae_after']:.6e} |

该表仅用于判断是否值得进入完整 P5 验收；不得以此选择结果宣称 Fig.6 改善或论文复现。
'''
    (out / "P5_AB_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"out": str(out), "A_dev_macro_nmae": record_a["dev_macro_nmae_after"],
                      "B_dev_macro_nmae": record_b["dev_macro_nmae_after"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

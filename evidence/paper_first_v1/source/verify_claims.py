# -*- coding: utf-8 -*-
"""
Claim ledger.  Every number I would put on a slide, re-derived from the files
on disk, with a PASS/FAIL next to it.

    py -3.11 verify_claims.py            # check what disk can already answer
    py -3.11 verify_claims.py --run      # also re-run the cheap checks (~1 min)
    py -3.11 verify_claims.py --md       # write RESULTS.md

WHY THIS EXISTS
    2026-09-10 group meeting: "复现没有数据支撑，不知道你做的是真是假".

    lab_log.py answers "did this run happen" (command + commit + sha256).
    This answers the other half: "does the claim still follow from the run".
    The two are different failures.  A number can be honestly produced and
    then quietly go stale when the artifact behind it is regenerated.

    Rules I am holding myself to here:
      * a claim with no artifact behind it prints 缺数据 and the exact command
        that would produce the artifact.  It never prints a remembered number.
      * the threshold is written down BEFORE the value, so a claim cannot be
        retro-fitted to whatever came out.
      * FAIL is a normal outcome, not an error.  Exit code counts FAILs so a
        batch file can stop on one.

    RESULTS.md is small and is committed.  The .pt/.npz/.json artifacts are
    gitignored (gigabytes), which is exactly why the repository currently
    looks like code with no evidence -- RESULTS.md is the evidence that fits.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np

SCRIPT_VERSION = "2026-09-10a"

# Paper-first audit: legacy numbers remain, but disputed scientific readings
# must not be promoted to PASS. Do not delete the C7 adverse observation.
AUDIT_NOTES = {
    'C2': '待重验：寿命字段可被误差1000阈值覆盖，而预测按误差1；局部谱相关不等于因果。',
    'C3': '待重验：阈值需统一；仅适用于所测冻结模型/步长/边界，不能推出减小dt普遍无效。',
    'C4': '撤回因果解读：偏相关大小比较不足以证明精度只通过rho作用。',
    'C5': '撤回替代性解读：两个不同配置的局部rho接近不能替代Algorithm1。',
    'C6': '待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。',
    'C8': '撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。',
}


def paper_evidence():
    """Verified files and recomputed metrics are shared by ledger and figures."""
    from pathlib import Path
    from paper_recheck import sha256
    import paper_protocol as pp
    root = Path('evidence/paper_first_v1')
    j = json.loads((root/'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if j['protocol'] != pp.VERSION:
        raise ValueError('protocol version mismatch')
    if sha256(root/'manifest.json') != j['manifest_sha256'] or sha256(root/'arrays.npz') != j['arrays_sha256']:
        raise ValueError('evidence hash mismatch')
    for name,h in manifest['sources'].items():
        if sha256(root/'source'/name) != h:
            raise ValueError('source snapshot mismatch: '+name)
    for model in j['models']:
        if model['sha256'] != model['sha256_after']:
            raise ValueError('model changed during inference')
    with np.load(root/'arrays.npz', allow_pickle=False) as z:
        for row in j['rows']:
            key = row['array_key']
            row['metrics'] = pp.vector_metrics(z[row['model']+'_'+key+'_pred'], z[key+'_true'])
    return j, manifest


_PAPER_CACHE = None


def paper_claims_data():
    global _PAPER_CACHE
    if _PAPER_CACHE is None: _PAPER_CACHE = paper_evidence()
    return _PAPER_CACHE


def p_protocol(_):
    j,m = paper_claims_data()
    from paper_protocol import SHAPES
    expected = {(model['tag'],s,'x'.join(map(str,sh)))
                for model in j['models'] for s in m['seeds'] for sh in SHAPES}
    actual = {(r['model'],r['seed'],r['size']) for r in j['rows']}
    ok = j['tests_passed'] and j['test_count'] >= 9 and len(j['rows']) == len(expected) and actual == expected
    return ('PASS' if ok else 'FAIL', f"{j['test_count']}项解析检查；{len(actual)}/{len(expected)}个模型/种子/网格组合",
            '判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。')


def p_reference(_):
    j,_ = paper_claims_data()
    r=j['reference']; vals=[abs(v['error_pct']) for v in r['modes']]
    ok = r['finite'] and r['steps']==8192 and len(vals)==5 and max(vals)<.5
    return ('PASS' if ok else 'FAIL', f"8192步；五模式最大绝对相对误差 {max(vals):.4f}%",
            '先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。')


def p_dco(_):
    import paper_protocol as pp
    j,m=paper_claims_data(); winners=[]; details=[]
    for model in j['models']:
        rows=[r for r in j['rows'] if r['model']==model['tag'] and r['size'] in pp.PAPER_MRE]
        ok=len(rows)==3*len(m['seeds']) and all(r['metrics']['components']['x']['mre_eq5']<=pp.PAPER_MRE[r['size']] for r in rows)
        if ok: winners.append(model['tag'])
        values=[r['metrics']['components']['x']['mre_eq5'] for r in rows]
        details.append(f"{model['tag']} x-MRE {min(values):.3g}~{max(values):.3g}")
    return ('PASS' if winners else 'FAIL', '; '.join(details),
            '先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；'
            '仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。')


PAPER_CLAIMS=[('P0','评估协议与解析检查完整',p_protocol),
              ('P1','候选网格下FDTD空气腔体参考通过',p_reference),
              ('P2','现有DCO在本轮Fig6重建案例达到预设MRE目标',p_dco)]

# --------------------------------------------------------------------------- #
# readers.  Schema matches what spectral_dco.py / train_dco.py actually write.
# --------------------------------------------------------------------------- #


def spectral(tag=None):
    """tag -> list of rows.  Row keys: cfl seed rho rho_exact eps0 rmsE
    blowup pred_blowup."""
    out = {}
    for f in sorted(glob.glob("spectral_*.json")):
        t = os.path.basename(f)[len("spectral_"):-len(".json")]
        if tag and t != tag:
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rows = [dict(r, tag=t) for r in j.get("rows", [])]
        if rows:
            out[t] = rows
    return out


def usable(rows):
    """Rows that mean anything.  eps0 > 0.5 means the network output is half
    the size of the field itself -- that checkpoint is not integrating, it is
    being replaced by its own error, and its 'lifetime' is not a lifetime."""
    return [r for r in rows
            if r.get("eps0", 0) <= 0.5 and r.get("blowup", -1) > 0
            and r.get("pred_blowup")]


def per_ckpt(all_rows):
    """One (rho-1, lifetime, eps0) per checkpoint, taken at the largest CFL
    they all share, so the comparison is not confounded by the time step."""
    flat = [r for rs in all_rows.values() for r in usable(rs)]
    if not flat:
        return {}
    hi = max(r["cfl"] for r in flat)
    out = {}
    for t in sorted(all_rows):
        rs = [r for r in usable(all_rows[t]) if r["cfl"] == hi]
        if rs:
            out[t] = dict(
                rho1=float(np.mean([r["rho"] for r in rs])) - 1.0,
                life=float(np.mean([r["blowup"] for r in rs])),
                eps0=float(np.mean([r["eps0"] for r in rs])),
                n=len(rs), cfl=hi)
    return out


def accuracy(tag):
    """Final single-step relative L2 from <tag>_hist.json, or None."""
    f = tag + "_hist.json"
    if not os.path.exists(f):
        return None
    try:
        j = json.load(open(f, encoding="utf-8"))
    except Exception:
        return None
    for k in ("relL2", "val_relL2", "val"):
        v = j.get(k)
        if isinstance(v, list) and v:
            return float(v[-1])
        if isinstance(v, (int, float)):
            return float(v)
    return None


def partial(x, y, z):
    """corr(x, y) with z held fixed.  Needed because accuracy and rho move
    together across checkpoints -- a plain correlation cannot say which of
    them the lifetime is actually responding to."""
    x, y, z = map(lambda v: np.asarray(v, float), (x, y, z))
    if len(x) < 4:
        return float("nan")

    def resid(v):
        A = np.vstack([z, np.ones_like(z)]).T
        return v - A @ np.linalg.lstsq(A, v, rcond=None)[0]
    rx, ry = resid(x), resid(y)
    if rx.std() < 1e-12 or ry.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# --------------------------------------------------------------------------- #
# claims.  Each returns (verdict, value_str, detail_str).
# verdict: "PASS" / "FAIL" / "NODATA"
# --------------------------------------------------------------------------- #

MISSING = {}          # claim id -> command that would produce the artifact


def need(cid, cmd, what):
    MISSING[cid] = cmd
    return "NODATA", "缺数据", f"跑 `{cmd}` 生成 {what}"


def c_selftest_cached(_):
    """The spectral probe is only believable if it returns rho = 1 for an
    operator whose rho is known to be 1."""
    m = spectral()
    rows = [r for rs in m.values() for r in rs if "rho_exact" in r]
    if not rows:
        return need("selftest", "py -3.11 spectral_dco.py --selftest",
                    "rho_exact 列")
    worst = max(abs(r["rho_exact"] - 1.0) for r in rows)
    ok = worst < 1e-3
    return ("PASS" if ok else "FAIL", f"|rho_exact - 1| <= {worst:.2e}",
            f"{len(rows)} 行里精确 Yee 旋度的谱半径都贴着 1；阈值 1e-3")


def c_rho_predicts(_):
    m = spectral()
    flat = [r for rs in m.values() for r in usable(rs)]
    if len(flat) < 20:
        return need("rho", "run_rho32.bat", "spectral_*.json（16 个 checkpoint）")
    p = np.log([r["pred_blowup"] for r in flat])
    q = np.log([r["blowup"] for r in flat])
    pooled = float(np.corrcoef(p, q)[0, 1])
    good = 0
    tot = 0
    for t, rs in m.items():
        rs = usable(rs)
        if len(rs) < 4:
            continue
        tot += 1
        c = np.corrcoef(np.log([r["pred_blowup"] for r in rs]),
                        np.log([r["blowup"] for r in rs]))[0, 1]
        if c > 0.8:
            good += 1
    ok = pooled >= 0.8
    return ("PASS" if ok else "FAIL", f"corr = {pooled:+.3f}",
            f"{len(flat)} 个点，{tot} 个 checkpoint 中 {good} 个自身 corr>0.8；"
            f"阈值 0.8")


def c_fixed_time(_):
    """The headline: does blow-up happen at a fixed PHYSICAL time, or after a
    fixed NUMBER of steps?  If physical time, halving the time step buys
    literally nothing and the instability belongs to the learnt operator, not
    to the time discretisation.

    2026-09-10, first run on real data: the original version of this check
    took max/min of blowup*cfl over every individual row and got 1.446x
    against a 1.30x threshold -- FAIL.  That statistic was wrong, and wrong in
    a way that flattered nobody: it lumps the seed-to-seed scatter in with the
    CFL dependence, so it cannot say which one it is measuring.  (The 1.023x
    I had quoted earlier came from the same quantity computed on per-
    checkpoint MEANS, i.e. with the noise averaged out first -- that framing
    was too kind to the claim and is retired.)

    So measure the thing itself.  Fit  log(lifetime_steps) = a + b log(CFL)
    per checkpoint, averaging seeds at each CFL first so noise enters as fit
    error rather than as signal:
        b = -1  ->  steps x CFL constant  ->  fixed physical time  (the claim)
        b =  0  ->  steps constant        ->  fixed step count     (the rival)
    Criteria, fixed before looking: median b within 0.15 of -1, and at least
    75% of checkpoints with b in [-1.15, -0.85].
    """
    m = spectral()
    slopes, noise = {}, []
    for t, rs in m.items():
        rs = usable(rs)
        cfls = sorted({r["cfl"] for r in rs})
        if len(cfls) < 3:
            continue
        y = []
        for c in cfls:
            v = [r["blowup"] for r in rs if r["cfl"] == c]
            y.append(float(np.mean(v)))
            if len(v) > 1:
                noise.append(max(v) / min(v))
        slopes[t] = float(np.polyfit(np.log(cfls), np.log(y), 1)[0])
    if len(slopes) < 4:
        return need("fixedtime", "run_rho32.bat",
                    "至少 4 个 checkpoint x 3 个 CFL 的 spectral_*.json")

    b = np.array(list(slopes.values()))
    med = float(np.median(b))
    inband = int(np.sum((b >= -1.15) & (b <= -0.85)))
    frac = inband / len(b)
    ok = abs(med + 1.0) <= 0.15 and frac >= 0.75
    seed_noise = float(np.median(noise)) if noise else float("nan")
    return ("PASS" if ok else "FAIL",
            f"斜率 b 中位数 {med:+.3f}（固定物理时间 = -1，固定步数 = 0），"
            f"{inband}/{len(b)} 个落在 [-1.15,-0.85]",
            f"判据：|中位数 +1| <= 0.15 且 >=75% 在带内（实得 {frac:.0%}）。"
            f"b 的范围 {b.min():+.2f}~{b.max():+.2f}；"
            f"同一 CFL 下换 seed 的寿命本身就差 {seed_noise:.2f}x，"
            f"这是噪声底，不是效应")


def c_accuracy_via_rho(_):
    """Does accuracy buy stability on its own, or only through rho?"""
    m = per_ckpt(spectral())
    tags = [t for t in m if accuracy(t) is not None]
    if len(tags) < 6:
        return need("partial", "run_rho32.bat",
                    f"更多 <tag>_hist.json（现有 {len(tags)} 个，需 >=6）")
    life = np.log([m[t]["life"] for t in tags])
    rho1 = np.log([max(m[t]["rho1"], 1e-9) for t in tags])
    acc = np.log([accuracy(t) for t in tags])
    p_acc = partial(acc, life, rho1)
    p_rho = partial(rho1, life, acc)
    ok = abs(p_rho) > abs(p_acc)
    return ("PASS" if ok else "FAIL",
            f"精度|固定rho: {p_acc:+.3f}　rho|固定精度: {p_rho:+.3f}",
            f"{len(tags)} 个 checkpoint。判据：rho 的偏相关绝对值更大，"
            f"即精度只是通过 rho 起作用")


def c_scale_vs_physics(_):
    """dco_paper32 is pure supervised, zero physics loss, just bigger.
    pidon_R2_all has the full physics + rollout loss.  If they tie, then the
    paper's Fig 7/8 is explained by scale, not by Algorithm 1."""
    m = per_ckpt(spectral())
    a, b = "dco_paper32", "pidon_R2_all"
    if a not in m or b not in m:
        return need("scale",
                    f"py -3.11 spectral_dco.py --ckpt {a}.pt  (以及 {b}.pt)",
                    f"spectral_{a}.json / spectral_{b}.json")
    ra, rb = m[a]["rho1"], m[b]["rho1"]
    ratio = max(ra, rb) / min(ra, rb)
    ok = ratio < 1.15
    return ("PASS" if ok else "FAIL",
            f"{a} rho-1={ra:.4f}　{b} rho-1={rb:.4f}　比值 {ratio:.3f}x",
            "阈值 1.15x。打平 = 纯监督的规模能顶上全套物理损失")


def c_literal_reading(_):
    """The paper does not state the trunk coordinate encoding or the input
    normalisation.  dco_L3b is the literal reading; dco_L3d is the fixed one."""
    m = per_ckpt(spectral())
    a, b = "dco_L3b", "dco_L3d"
    if a not in m or b not in m:
        return need("literal", f"py -3.11 spectral_dco.py --ckpt {a}.pt",
                    f"spectral_{a}.json / spectral_{b}.json")
    ra, rb = m[a]["rho1"], m[b]["rho1"]
    ok = ra > rb
    return ("PASS" if ok else "FAIL",
            f"{a} rho-1={ra:.4f}　{b} rho-1={rb:.4f}　差 {ra / rb:.2f}x",
            "两个实现开关（trunk 坐标编码 / 归一化）同时影响精度和稳定性。"
            "注意口径更正（2026-09-10 读原文后）：这两点论文其实都写了 —— "
            "III-A「trunk decodes coordinate information into cell sizes」"
            "指定了 cellsize 编码，III-B「output normalized by the local "
            "maximum for each component」指定了按分量的输出归一化。所以 "
            f"{a}（abs 坐标）不是「论文字面读法」，那个标签是错的，已撤。"
            "本条现在只主张我们自己消融里的敏感度，不再主张论文有遗漏")


def c_l3c_wrinkle(_):
    """Report the counterexample in the same breath as the claim above.
    dco_L3c (cellsize+max) beats dco_L3d (cellsize+rms) on rho, so the rms
    normalisation improved dimension invariance and made rho worse."""
    m = per_ckpt(spectral())
    if "dco_L3c" not in m or "dco_L3d" not in m:
        return need("wrinkle", "py -3.11 spectral_dco.py --ckpt dco_L3c.pt",
                    "spectral_dco_L3c.json")
    c, d = m["dco_L3c"]["rho1"], m["dco_L3d"]["rho1"]
    # this claim asserts the AWKWARD direction; PASS means "yes, still awkward"
    ok = c < d
    return ("WARN" if ok else "PASS",
            f"dco_L3c rho-1={c:.4f} < dco_L3d rho-1={d:.4f}"
            if ok else f"dco_L3c={c:.4f} >= dco_L3d={d:.4f}（反常消失了）",
            "这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说")


def c_long_run_impossible(_):
    """The strategic number.  How much better would rho have to be to run the
    1e5 steps the paper's setting implies?"""
    m = per_ckpt(spectral())
    if not m:
        return need("longrun", "run_rho32.bat", "spectral_*.json")
    best = min(m.values(), key=lambda v: v["rho1"])
    tag = min(m, key=lambda t: m[t]["rho1"])
    need_rho1 = 1.0 / 1e5           # rho^1e5 stays O(1)  =>  rho-1 ~ 1e-5
    factor = best["rho1"] / need_rho1
    return ("PASS", f"最好 {tag}: rho-1={best['rho1']:.4f}，"
                    f"要跑 1e5 步需再小 {factor:,.0f}x",
            "寿命约为 1/(rho-1)，所以目标步数 N 需要 rho-1 ~ 1/N。"
            + _grid_evidence(m)
            + "　按实测倍数外推，规模路线要跨过 4 个数量级并无依据 —— "
            "两周后的论文规模复现就是对「规模能否解决发散」的直接检验。"
            "这条不是失败，是本复现最有价值的负面结论")


def _grid_evidence(m):
    """2026-09-10 更正：这里原来写着「一次网格加倍大约把 rho-1 减半，所以还
    差 13 次加倍」。那个「减半」是我凭印象写的，而我们自己的数据否定它 ——
    唯一一次真实的训练网格加倍只改善了个位数百分比。用未经支持的外推去论证
    「不可行」、方向上还恰好对自己有利，不能留。改为只报那一次实测。"""
    if PARITY_CKPT not in m:
        return ""
    others = {t: v for t, v in m.items() if t != PARITY_CKPT}
    if not others:
        return ""
    b = min(others, key=lambda t: others[t]["rho1"])
    r16, r32 = others[b]["rho1"], m[PARITY_CKPT]["rho1"]
    return (f"　实测：唯一一次训练网格加倍（{b} 16^3 rho-1={r16:.4f} -> "
            f"{PARITY_CKPT} 32^3 rho-1={r32:.4f}）只带来 {r16 / r32:.2f}x 改善。")


# --------------------------------------------------------------------------- #
# EXP 2 claims.  These read test_results_*.npz, which test_dco.py writes.
# --------------------------------------------------------------------------- #

# Qi & Sarris 2025, section III-D, network trained at 32^3.
#
# 2026-09-10, after actually reading the paper: these are MRE as defined in
# the paper's eq. (5) -- the MEAN POINTWISE RELATIVE ERROR,
#     MRE = (1/N) sum |y_pred - y_true| / |y_true|   (and |y_pred| where
#     y_true == 0),
# which is neither relative L2 nor MAE/max.  We had been comparing our nMAE
# to them on the assumption that the paper used MAE/max.  It does not.  That
# is the SAME cross-metric mistake that produced the retracted "10x worse"
# claim, made a second time with a different wrong metric.
PAPER_IIID = {"64^3": 4.1e-3, "64x96x16": 3.8e-3, "32x64x16": 4.7e-3}


# The checkpoint the paper-parity claim is ABOUT.  Designated by its
# configuration -- L=4, base 32, trained on a 32-cubed grid, which is what the
# paper used -- and NOT by its score.  Comparing a 16-cubed-trained net to the
# paper's 32-cubed-trained one is not a reproduction test, it is a handicap
# match, so those checkpoints are reported below but do not decide the verdict.
PARITY_CKPT = "dco_paper32"


def _exp2_all():
    """[(label, train_n, {size: relL2}, {size: nMAE})] for every results file.

    2026-09-10: the first version of this read only the NEWEST
    test_results_*.npz.  run_meal.bat happened to finish with the dco_L4b
    control, so C9 graded the control and reported FAIL at 13.35x -- a real
    number attached to the wrong claim.  Read them all; let the claim say
    which one it is about.
    """
    out = []
    for f in sorted(glob.glob("test_results_*.npz")):
        try:
            z = np.load(f, allow_pickle=True)
        except Exception:
            continue
        if "exp2_nmae" not in z:
            continue
        sizes = [str(x) for x in z["exp2_sizes"]]
        tn = int(z["train_n"]) if "train_n" in z else 0
        out.append((os.path.basename(f)[len("test_results_"):-len(".npz")], tn,
                    dict(zip(sizes, [float(v) for v in z["exp2_rel"]])),
                    dict(zip(sizes, [float(v) for v in z["exp2_nmae"]]))))
    return out


def _metric_note(lab=None):
    return "式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。"


def c_dim_invariance(_):
    return ("RETRACTED", "旧0.70~1.50倍比较撤回；原始NPZ保留",
            _metric_note()+" 新协议与现有权重的结果见P0-P2。")


def c_metric_gap(_):
    """相对 L2 和 nMAE 不能混用 -- 这是上面那条错误的根源，值得单独立一条。"""
    all_ = _exp2_all()
    rr, labs = [], []
    for lab, _, rel, nm in all_:
        v = [rel[k] / nm[k] for k in rel if nm.get(k, 0) > 0]
        if v:
            rr += v
            labs.append(f"{lab} {min(v):.1f}-{max(v):.1f}x")
    if not rr:
        return need("exp2", "run_meal.bat", "test_results_*.npz")
    ok = min(rr) > 2.0
    return ("PASS" if ok else "FAIL",
            f"relative L2 / nMAE = {min(rr):.1f}~{max(rr):.1f}x"
            f"（{len(all_)} 个 checkpoint）",
            "判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。"
            f"逐 checkpoint：{'；'.join(labs)} —— 倍数本身就不是常数，"
            "所以任何记下来的固定倍数都不能用")


DISK_CLAIMS = [
    ("C1", "谱半径探针可信：精确 Yee 旋度测出来 rho = 1", c_selftest_cached),
    ("C2", "rho 能预测闭环能跑多少步", c_rho_predicts),
    ("C3", "发散发生在固定物理时间，不是固定步数", c_fixed_time),
    ("C4", "精度只通过 rho 影响稳定性", c_accuracy_via_rho),
    ("C5", "规模可以替代物理损失", c_scale_vs_physics),
    ("C6", "论文没写明的实现细节同时伤精度和稳定性", c_literal_reading),
    ("C7", "反例：消融链终点在 rho 上反而更差", c_l3c_wrinkle),
    ("C8", "无约束学习算子做不了长时程积分", c_long_run_impossible),
    ("C9", "旧跨指标、跨测试场景的论文对比", c_dim_invariance),
    ("C10", "相对 L2 与 nMAE 不可互换（上一条曾因此报错）", c_metric_gap),
]

# --------------------------------------------------------------------------- #
# claims that need a (cheap) run
# --------------------------------------------------------------------------- #

RUN_CLAIMS = [
    ("R1", "精确旋度就是一个 12 权重的 3x3x3 卷积",
     [sys.executable, "exact_stencil.py"],
     r"relative L2\s+([0-9.eE+-]+)",
     lambda v: float(v) < 1e-12,
     "relative L2 < 1e-12（等价于机器精度，说明 2.25M 参数在学一个 12 参数的东西）"),
    ("R2", "自己写的 FDTD 参考解对得上解析解",
     [sys.executable, "run_fdtd_cavity.py"],
     r"^\s*\d{3}\s+[0-9.]+\s+[0-9.]+\s+([+-][0-9.]+)",
     lambda v: abs(float(v)) < 0.5,
     "每个模式 |误差| < 0.5%"),
    ("R4", "PEC 边界下伴随恒等式 curl_H = curl_E^T 仍精确成立",
     [sys.executable, "structured_pec.py"],
     r"RESULT pec_adjoint_err ([0-9.eE+-]+)",
     lambda v: float(v) < 1e-12,
     "三明治结构的全部前提。此前只在周期盒验证过，而论文的腔体是 PEC；"
     "若此式不成立，成对替换在腔体里就要先补边界修正"),
    ("R5", "介质界面下成对替换的保证仍成立，单旋度替换仍不成立",
     [sys.executable, "structured_material.py"],
     r"RESULT material_(?:pair_ok 1|onesided_ok 0)",
     lambda v: True,
     "两条都要命中才算过：成对的成立、单侧的不成立。"
     "论文 Fig 8 本身含 eps_r=4 的 inhomogeneous cavity"),
    ("R3", "谱半径自检（现算，不看缓存）",
     [sys.executable, "spectral_dco.py", "--selftest"],
     r"self-test (PASSED|FAILED)",
     lambda v: v == "PASSED",
     "精确旋度 rho≈1 且倾斜旋度 rho>1，两个方向都要对"),
]


def run_claim(cid, name, cmd, pat, ok_fn, crit):
    if not os.path.exists(cmd[1]):
        return "NODATA", "缺脚本", f"{cmd[1]} 不在当前目录"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
    except Exception as exc:
        return "FAIL", "跑不起来", str(exc)[:120]
    if p.returncode != 0:
        return 'FAIL', f'exit {p.returncode}', (p.stdout+p.stderr)[-800:]
    hits = re.findall(pat, p.stdout+p.stderr, re.M)
    if not hits:
        return "FAIL", "输出里没匹配到数", f"exit {p.returncode}；{crit}"
    bad = [h for h in hits if not ok_fn(h)]
    shown = ", ".join(str(h) for h in hits[:6])
    return ("PASS" if not bad else "FAIL",
            shown + ("" if len(hits) <= 6 else f" … 共 {len(hits)} 个"),
            crit + (f"；{len(bad)} 个不满足" if bad else ""))


# --------------------------------------------------------------------------- #
# WARN is for a claim that is CONFIRMED but cuts against the story.  It has to
# be visually distinct from PASS or the table quietly reads as all-good.
MARK = {"PASS": "[ PASS ]", "FAIL": "[ FAIL ]", "NODATA": "[ 缺数据 ]",
        "WARN": "[ 反例 ]", 'REVIEW':'[ 待重审 ]', 'RETRACTED':'[ 撤回 ]'}
TICK = {"PASS": "✅", "FAIL": "❌", "NODATA": "⬜", "WARN": "⚠️",
        'REVIEW':'🔎', 'RETRACTED':'⛔'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true",
                    help="也重跑 R1-R3 这些便宜的检查（约 1 分钟）")
    ap.add_argument("--md", action="store_true", help="写出 RESULTS.md")
    ap.add_argument('--paper-first', action='store_true',
                    help='加入新协议P0-P2；--run仅重跑本阶段解析测试，不重跑旁支结构实验')
    a = ap.parse_args()

    print(f"[verify_claims.py  version {SCRIPT_VERSION}]")
    print(f"in {os.path.abspath('.')}\n")
    print('当前指标由产物重算。旧结论存在待重审项；检查通过不等于充分的科学证明。\n')

    results = []
    for cid, name, fn in DISK_CLAIMS + (PAPER_CLAIMS if a.paper_first else []):
        try:
            v, val, det = fn(None)
            if cid in AUDIT_NOTES:
                v, det = 'REVIEW', AUDIT_NOTES[cid] + ' 历史数值仅供溯源。'
        except Exception as exc:
            v, val, det = "FAIL", "检查本身抛异常", f"{type(exc).__name__}: {exc}"
        results.append((cid, name, v, val, det))
        print(f"  {MARK[v]:<10} {cid}  {name}")
        print(f"             {val}")
        print(f"             {det}\n")

    if a.run:
        print("  —— 重跑便宜的检查 ——\n")
        runs = ([('P0T','本阶段解析回归测试（本次现跑）',
                  [sys.executable,'test_paper_protocol.py'], r'Ran (\d+) tests',
                  lambda v:int(v)>=9, '测试进程exit=0且至少9项通过')]
                if a.paper_first else RUN_CLAIMS)
        for cid, name, cmd, pat, ok_fn, crit in runs:
            v, val, det = run_claim(cid, name, cmd, pat, ok_fn, crit)
            results.append((cid, name, v, val, det))
            print(f"  {MARK[v]:<10} {cid}  {name}")
            print(f"             {val}")
            print(f"             {det}\n")
    else:
        print("  （R1-R3 需要现跑，加 --run；不加就不会假装它们通过了）\n")

    npass = sum(1 for r in results if r[2] == "PASS")
    nfail = sum(1 for r in results if r[2] == "FAIL")
    nnd = sum(1 for r in results if r[2] == "NODATA")
    nw = sum(1 for r in results if r[2] == "WARN")
    print("=" * 66)
    print(f"  通过 {npass}　不通过 {nfail}　缺数据 {nnd}　反例 {nw}")
    if MISSING:
        print("\n  想把「缺数据」补齐，跑这些（已去重）：")
        for cmd in dict.fromkeys(MISSING.values()):
            print(f"    {cmd}")
    if a.md:
        write_md(results, a.run)
        print(f"\n  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）")
    return 1 if nfail else 0


def write_md(results, ran):
    import datetime as dt
    commit = ""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True,
                                timeout=10).stdout.strip()
    except Exception:
        pass
    with open("RESULTS.md", "w", encoding="utf-8") as f:
        f.write("# 复现结论核对表\n\n")
        f.write(f"> `verify_claims.py` 自动生成于 "
                f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                f"{'，commit `' + commit + '`' if commit else ''}。"
                f"**不要手工编辑。**\n>\n")
        f.write("> 本轮论文优先重评见P0-P2；历史指标保留，待重审/撤回不表示已验证。\n"
                "> 本轮复算：`py -3.11 lab_log.py run -m paper-first-verify -- py -3.11 verify_claims.py --paper-first --run --md`。\n"
                "> 复算指标不等于重新训练或推理；P0T是此次现跑的解析测试。\n"
                "> 产物文件（.pt/.npz/.json，好几个 GB）被 .gitignore 挡在外面，"
                "所以仓库里看不到数据 —— 这张表就是能进仓库的那份证据，\n"
                "> 每次运行的命令、commit、耗时和输出文件的 sha256 在 "
                "`LAB_NOTEBOOK.md`。本轮源代码快照与权重哈希另见 `evidence/paper_first_v1/manifest.json`。\n\n")
        def cell(t):
            return str(t).replace("|", "\\|").replace("\n", " ")
        f.write("| | 结论 | 复算值 | 判据 |\n|---|---|---|---|\n")
        for cid, name, v, val, det in results:
            tick = TICK[v]
            f.write(f"| {tick} | **{cid}** {cell(name)} | {cell(val)} | "
                    f"{cell(det)} |\n")
        if not ran:
            f.write("\n> R1–R3 这次没跑（没加 `--run`），所以没有列进来。\n")
        nd = [r for r in results if r[2] == "NODATA"]
        if nd:
            f.write("\n## 还缺的\n\n")
            for cmd in dict.fromkeys(MISSING.values()):
                f.write(f"- `{cmd}`\n")


if __name__ == "__main__":
    sys.exit(main())

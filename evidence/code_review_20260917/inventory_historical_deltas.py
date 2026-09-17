"""Group historical source snapshots and export full diffs for human review."""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def normalized(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    coverage = json.loads((OUT / "coverage_r4.json").read_text(encoding="utf-8"))
    reviewed = [r for r in coverage["files"] if r["coverage"] in {"FULL_SOURCE_READ", "FULL_TEMPLATE_DIFF"}]
    by_name = defaultdict(list)
    for row in reviewed:
        by_name[Path(row["path"]).name].append(row)
    groups = defaultdict(list)
    for row in coverage["files"]:
        if row["coverage"] == "PENDING_REVIEW":
            assert row["path"].startswith(("evidence/", "archive/")), row["path"]
            groups[hashlib.sha256(normalized(ROOT / row["path"])).hexdigest()].append(row)
    destination = OUT / args.output_dir
    destination.resolve().relative_to(OUT.resolve())
    destination.mkdir(exist_ok=False)
    entries = []
    core_names = {"dco.py", "fdtd.py", "pidon_solve.py", "pidon_contract.py", "pidon_recording.py", "paper_protocol.py", "head_lstsq.py"}
    for index, (sha, rows) in enumerate(sorted(groups.items()), 1):
        representative = rows[0]["path"]
        body = normalized(ROOT / representative).decode("utf-8-sig")
        candidates = by_name[Path(representative).name]
        candidates.sort(key=lambda r: r["path"])
        canonical = candidates[0] if len(candidates) == 1 else max(candidates, key=lambda r: difflib.SequenceMatcher(None, body.splitlines(), normalized(ROOT / r["path"]).decode("utf-8-sig").splitlines(), autojunk=False).ratio()) if candidates else None
        previous = normalized(ROOT / canonical["path"]).decode("utf-8-sig") if canonical else ""
        diff = list(difflib.unified_diff(previous.splitlines(True), body.splitlines(True), fromfile=canonical["path"] if canonical else "NO_CURRENT_COUNTERPART", tofile=representative, n=4))
        partition = "core" if Path(representative).name in core_names else "support"
        name = f"{index:03d}_{Path(representative).stem}.diff"
        (destination / name).write_text("".join(diff), encoding="utf-8")
        entries.append({"id": index, "partition": partition, "representative": representative,
                        "normalized_sha256": sha, "canonical": canonical["path"] if canonical else None,
                        "diff_file": name, "diff_lines": len(diff), "source_lines": len(body.splitlines()),
                        "members": [{"path": r["path"], "sha256": r["sha256"]} for r in rows]})
        if index % 25 == 0:
            print(f"Grouped {index}/{len(groups)} distinct historical sources", flush=True)
    payload = {"review_only": True, "updates": 0, "coverage_source": "coverage_r4.json", "groups": entries,
               "counts": dict(Counter(e["partition"] for e in entries)),
               "diff_lines": dict(Counter({p: sum(e["diff_lines"] for e in entries if e["partition"] == p) for p in ("core", "support")}))}
    (destination / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("counts", "diff_lines")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

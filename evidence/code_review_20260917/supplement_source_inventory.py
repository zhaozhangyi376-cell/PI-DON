"""Catch source omitted by the initial census or newly available on disk."""
from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EXTENSIONS = {".py", ".js", ".ps1", ".m", ".bas", ".vbs", ".bat", ".cmd", ".sh", ".ipynb"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    initial = json.loads((OUT / "source_inventory.json").read_text(encoding="utf-8"))
    old = {r["path"]: r for r in initial["files"]}
    known = {}
    for row in initial["files"]:
        if row["path"].startswith("evidence/code_review_20260917/"):
            continue
        path = ROOT / row["path"]
        if path.exists():
            known.setdefault(digest(path.read_bytes().replace(b"\r\n", b"\n")), row["path"])
    destination = OUT / "supplementary_sources"
    destination.mkdir(exist_ok=False)
    rows = []
    for directory, folders, names in os.walk(ROOT):
        folders[:] = [n for n in folders if n not in {".git", "__pycache__", "node_modules", ".venv", "venv"}]
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix.lower() not in EXTENSIONS:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in old or relative.startswith("evidence/code_review_20260917/"):
                continue
            raw = path.read_bytes()
            normalized = raw.replace(b"\r\n", b"\n")
            sha = digest(normalized)
            match = known.get(sha)
            row = {"path": relative, "sha256": digest(raw), "normalized_sha256": sha,
                   "lines": len(raw.splitlines()), "exact_lf_match": match}
            if not match and path.suffix.lower() != ".bat":
                candidates = [r for r in initial["files"] if Path(r["path"]).name == name]
                body = normalized.decode("utf-8-sig").splitlines(True)
                base = max(candidates, key=lambda r: difflib.SequenceMatcher(None, body, (ROOT / r["path"]).read_text(encoding="utf-8-sig").splitlines(True), autojunk=False).ratio()) if candidates else None
                base_lines = (ROOT / base["path"]).read_text(encoding="utf-8-sig").splitlines(True) if base else []
                diff = "".join(difflib.unified_diff(base_lines, body, fromfile=base["path"] if base else "NO_COUNTERPART", tofile=relative, n=4))
                filename = f"{len(rows):03d}_{path.stem}.diff"
                (destination / filename).write_text(diff, encoding="utf-8")
                row.update({"diff_file": filename, "canonical": base["path"] if base else None})
            rows.append(row)
            # Repeated newly available snapshots inherit the first one's
            # eventual review, not an automatic PASS from this inventory.
            known.setdefault(sha, relative)
    result = {"review_only": True, "production_updates": 0, "files": rows,
              "notes": "Exact content match inherits static review only once its canonical has been reviewed; no proof of historical execution identity."}
    with (destination / "index.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"additional_files": len(rows), "bat_files": sum(r["path"].endswith(".bat") for r in rows),
                      "exact_lf_matches": sum(bool(r["exact_lf_match"]) for r in rows),
                      "new_diffs": [r["diff_file"] for r in rows if "diff_file" in r]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

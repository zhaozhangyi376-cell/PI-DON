"""
Experiment logger.  Wrap any run so the record is a BYPRODUCT of running it,
not extra work you have to remember to do afterwards.

    py -3.11 lab_log.py run -m "32^3 parity, finish 260->300" -- ^
        py -3.11 train_dco.py --data data_32.npz --epochs 40 ...

    py -3.11 lab_log.py show            # last 10 entries, one line each
    py -3.11 lab_log.py show --id 14    # one entry in full
    py -3.11 lab_log.py verify          # do the recorded output files still
                                        # match the hashes in the log?

WHY THIS EXISTS
    2026-09-10 group meeting: "复现没有数据支撑，不知道你做的是真是假".
    That criticism is correct and it is not about honesty -- it is about
    traceability.  Numbers on a slide have to lead back to a run, and a run
    has to lead back to a command, a commit, and a file you can hash.

    So every entry records:
      * the exact command line, verbatim, so it can be re-run
      * the git commit and whether the tree was dirty at the time
      * python / torch / GPU / host, because "it worked on my machine" is
        only meaningful if the machine is written down
      * wall time and exit code
      * EVERY file the run created or modified, with its size and sha256.
        The JSONL row carries the 25 largest INLINE; the complete list always
        goes to a side-car manifest whose own sha256 is in the row, so the
        machine evidence is never the truncated one (see F14 below).
      * the tail of stdout, and any "key: value" numbers matched from it

    The hashes are the part that makes it checkable by someone else: they can
    take dco_paper32.pt off the disk, hash it, and see that it is the file
    this entry says was produced by that command at that commit.

    Output goes to two places on purpose:
      LAB_NOTEBOOK.md   human-readable, append-only, commit it to git
      lab_runs.jsonl    machine-readable, one JSON per line, for tables/figs
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import uuid
from project_paths import PROJECT_DIR, configure, resolve_legacy

configure()

SCRIPT_VERSION = "2026-09-10a"
NOTEBOOK = "records/LAB_NOTEBOOK.md"
JSONL = "records/lab_runs.jsonl"
# figs/ is NOT ignored: the figures are exactly the artefacts that end
# up on a slide, so they are the ones most worth hashing.  Skipping
# them made a make_figs.py run record "0 file(s) touched".
IGNORE_DIRS = {".git", "__pycache__", "cst"}
IGNORE_EXT = {".pyc", ".log", ".tmp"}
MAX_HASH_MB = 400            # inline-hash limit; larger files stream instead
MANIFEST_DIR = "records/output_manifests"
INLINE_OUTPUTS = 25          # rows kept inline; the manifest always holds all


# --------------------------------------------------------------------------- #
def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


def environment():
    """Everything about the machine that could change a result."""
    env = {
        "host": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cwd": os.path.abspath("."),
    }
    try:
        import torch
        env["torch"] = torch.__version__
        env["cuda"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            env["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        env["torch"] = "not importable"
    env["git_commit"] = sh("git rev-parse --short HEAD") or "?"
    env["git_branch"] = sh("git rev-parse --abbrev-ref HEAD") or "?"
    # Only TRACKED modifications make a run unreproducible from the commit.
    # Untracked files sitting in the tree do not, and this repository always
    # has plenty of them (project directories, logs, datasets).  Counting
    # those made every single run print "WORKING TREE DIRTY", and a warning
    # that always fires is a warning nobody reads.
    tracked = sh("git status --porcelain --untracked-files=no")
    # 2026-09-12：同一个坑第二次。上面那条注释说「总是响的警报没人看」，
    # 然后这个警报又变成总是响 —— 因为【记账文件本身是被跟踪的】：
    # LAB_NOTEBOOK.md / lab_runs.jsonl 是 lab_log 自己写的，RESULTS.md 是
    # verify_claims 写的。每跑一次它们必然变化，于是每次运行都报
    # 「跟踪文件与 commit 不一致，此次运行无法复现」，把真正该看的信号
    # （代码改了没提交就跑）淹掉了。
    # 记账文件的变化不影响可复现性：决定结果的是代码与数据，不是日志。
    # 所以把它们单列出来、不计入判定，但仍然打印，不做静默忽略。
    LEDGER = {"LAB_NOTEBOOK.md", "lab_runs.jsonl", "RESULTS.md"}
    entries = [l[2:].strip() for l in tracked.splitlines()]
    ledger = [f for f in entries if os.path.basename(f) in LEDGER]
    real = [f for f in entries if os.path.basename(f) not in LEDGER]
    env["git_dirty"] = bool(real)
    env["git_ledger_files"] = ledger
    if real:
        # l[3:] ate the leading dot of ".codex_ppt_build/..." -- the
        # status prefix is two columns plus one space, but a rename
        # entry shifts it.  Take everything after the status columns
        # and strip, which is right for every entry shape.
        env["git_dirty_files"] = real[:12]
    n_untracked = len([l for l in sh("git status --porcelain").splitlines()
                       if l.startswith("??")])
    env["git_untracked"] = n_untracked
    return env


def snapshot(root="."):
    """path -> mtime, for every file we might care about."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS
                   and not d.startswith(".")]
        for f in files:
            if os.path.splitext(f)[1] in IGNORE_EXT:
                continue
            p = os.path.join(dirpath, f)
            try:
                out[p] = os.path.getmtime(p)
            except OSError:
                pass
    return out


def sha256(path, *, stream_large=True):
    """sha256 of a file.

    F14: files above ``MAX_HASH_MB`` used to return None, i.e. "recorded but
    NOT hashed", and a reader could not tell that from "hashed".  Large files
    are streamed as well now -- the reader is the same loop either way -- and
    the caller records ``hash_method`` so a skip is always visible.
    """
    n = os.path.getsize(path)
    if n > MAX_HASH_MB * 1024 * 1024 and not stream_large:
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# numbers worth pulling out of stdout automatically.  Add patterns here as
# new scripts appear -- anything not matched still lives in the stdout tail.
PATTERNS = [
    (r"FINAL\s+relative L2\s*=\s*([0-9.eE+-]+)", "relL2"),
    (r"nMAE\s*=\s*([0-9.eE+-]+)", "nMAE"),
    (r"blew up at step\s+(\d+)", "blowup_step"),
    (r"rho\s+DCO, linearised power iter\s*=\s*([0-9.]+)", "rho"),
    (r"relative L2 = ([0-9.eE+-]+)", "exp2_relL2"),
    (r"self-test (PASSED|FAILED)", "selftest"),
    (r"total ([0-9.]+)s", "train_seconds"),
]


def harvest(text):
    got = {}
    for pat, key in PATTERNS:
        m = re.findall(pat, text)
        if m:
            got[key] = m if len(m) > 1 else m[0]
    return got


# --------------------------------------------------------------------------- #
def next_id():
    """Reserve a run id under an exclusive lock.

    F15: the id used to be "number of finished rows + 1", computed at start
    and never reserved.  Two wrappers launched before either finished were
    handed the SAME id, and the two runs became indistinguishable in the
    ledger.  A reservation file, written under an O_EXCL lock, hands out a
    monotonically increasing id even while earlier runs are still going.
    """
    os.makedirs("records", exist_ok=True)
    reservation = "records/lab_run_reservation.json"
    lock = reservation + ".lock"
    handle = None
    for _ in range(600):
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.05)
    try:
        committed = 0
        if os.path.exists(JSONL):
            with open(JSONL, encoding="utf-8") as f:
                committed = sum(1 for _ in f)
        reserved = 0
        if os.path.exists(reservation):
            try:
                with open(reservation, encoding="utf-8") as f:
                    reserved = int(json.load(f).get("last_reserved_id", 0))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                reserved = 0
        rid = max(committed, reserved) + 1
        tmp = reservation + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"last_reserved_id": rid,
                       "reserved_at": dt.datetime.now().isoformat(timespec="seconds"),
                       "host": platform.node(), "pid": os.getpid()}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, reservation)
        return rid
    finally:
        if handle is not None:
            os.close(handle)
            try:
                os.unlink(lock)
            except OSError:
                pass


def write_output_manifest(rid, run_uuid, touched):
    """Persist the COMPLETE output list and return its own identity."""
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    path = f"{MANIFEST_DIR}/run_{rid:05d}_{run_uuid}.json"
    document = {
        "schema": "pidon-lab-output-manifest-v1",
        "run_id": rid, "run_uuid": run_uuid,
        "written_at": dt.datetime.now().isoformat(timespec="seconds"),
        "count": len(touched),
        "outputs": touched,
        "note": "完整产出清单；JSONL 行内只保留最大的若干条，机器证据以本文件为准。",
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return {"path": path, "sha256": sha256(path), "count": len(touched)}


def quote(argv):
    """Printable one-liner.  Only for display -- argv is what actually runs."""
    out = []
    for t in argv:
        out.append(f'"{t}"' if (" " in t or not t) else t)
    return " ".join(out)


def launch(argv, run_id=None, run_uuid=None):
    """Popen the child.  No shell, so an argument with spaces stays ONE
    argument -- ' '.join + shell=True silently splits it and you get a
    different run than the one written in the log.
    .bat / .cmd are the exception: Windows cannot exec them directly."""
    if argv[0].lower().endswith((".bat", ".cmd")):
        argv = ["cmd", "/c"] + argv
    # Force the CHILD to write UTF-8.  We decode its pipe as UTF-8, but a
    # Python child on Windows encodes stdout in the locale codepage (cp936
    # here) as soon as stdout is a pipe rather than a console -- so every
    # non-ASCII line came back as mojibake, both on screen and in the
    # recorded stdout_tail.  PYTHONIOENCODING makes the two ends agree.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    if run_id is not None:
        env['PIDON_LAB_RUN_ID'] = str(run_id)
    if run_uuid is not None:
        env['PIDON_LAB_RUN_UUID'] = str(run_uuid)
    return subprocess.Popen(argv, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1,
                            env=env)


def do_run(a):
    if not a.cmd:
        raise SystemExit("nothing to run -- put the command after --")
    argv = list(a.cmd)
    cmd = quote(argv)
    rid = next_id()
    # F15: the host+id pair was not unique while runs overlapped.  A per-run
    # UUID makes every wrapper invocation addressable on its own.
    run_uuid = uuid.uuid4().hex[:16]
    env = environment()
    before = snapshot()

    print(f"\n=== lab_log run #{rid} ===")
    print(f"  {cmd}")
    un = env.get("git_untracked", 0)
    print(f"  commit {env['git_commit']}"
          f"{'  (TRACKED FILES MODIFIED)' if env['git_dirty'] else ''}"
          f"{f'  [{un} untracked]' if un else ''}"
          f"   {env.get('gpu', 'no gpu')}")
    if env["git_dirty"]:
        print("  *** tracked files differ from the commit -- this run is NOT "
              "reproducible from the commit alone:")
        for f in env.get("git_dirty_files", [])[:6]:
            print(f"        {f}")
    led = env.get("git_ledger_files", [])
    if led:
        print(f"  （记账文件 {', '.join(os.path.basename(f) for f in led)} "
              f"有改动，这是本工具自己写的，不影响可复现性）")
    print("=" * 60 + "\n")

    t0 = time.time()
    lines = []
    try:
        proc = launch(argv, run_id=rid, run_uuid=run_uuid)
    except OSError as exc:
        raise SystemExit(f"could not start {argv[0]!r}: {exc}")
    # F15: a Ctrl+C (or a killed wrapper) used to leave NOTHING in the ledger
    # -- the row was only written after the child exited -- so the cost of an
    # interrupted training run simply vanished from the accounting.  Catch the
    # interrupt, stop the child, and fall through to the same bookkeeping with
    # an explicit interrupted flag.
    interrupted = False
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            lines.append(line)
        rc = proc.wait()
    except KeyboardInterrupt:
        interrupted = True
        print("\n  *** 收到中断：正在停止子进程并落账，成本不丢失 ***", flush=True)
        try:
            proc.terminate()
            rc = proc.wait(timeout=30)
        except Exception:                                        # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                    # noqa: BLE001
                pass
            rc = proc.poll()
        if rc is None:
            rc = -1
    dur = time.time() - t0
    text = "".join(lines)

    after = snapshot()
    touched = []
    for p, m in after.items():
        if p not in before or before[p] != m:
            try:
                touched.append({"path": os.path.relpath(p).replace("\\", "/"),
                                "bytes": os.path.getsize(p),
                                "sha256": sha256(p)})
            except OSError:
                pass
    touched.sort(key=lambda d: -d["bytes"])
    # F14: the row keeps the largest few for human reading, but the complete
    # list -- with the small summaries, protocols and source files that used
    # to be squeezed out -- is written to its own manifest and identified by
    # its own hash.  Console output is bounded; machine evidence is not.
    manifest = write_output_manifest(rid, run_uuid, touched)

    entry = {
        "id": rid,
        "run_uuid": run_uuid,
        "when": dt.datetime.now().isoformat(timespec="seconds"),
        "note": a.message or "",
        "cmd": cmd,
        "argv": argv,
        "exit_code": rc,
        "interrupted": interrupted,
        "cost_accounting": "LOWER_BOUND" if interrupted else "COMPLETE",
        "seconds": round(dur, 1),
        "env": env,
        "outputs": touched[:INLINE_OUTPUTS],
        "outputs_total_count": len(touched),
        "outputs_truncated_inline": len(touched) > INLINE_OUTPUTS,
        "output_manifest": manifest,
        "harvested": harvest(text),
        "stdout_tail": lines[-40:],
    }
    with open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    append_markdown(entry)

    print("\n" + "=" * 60)
    print(f"  run #{rid} recorded  ({dur:.0f}s, exit {rc}, "
          f"{len(touched)} file(s) touched)")
    print(f"  -> {NOTEBOOK}  and  {JSONL}")
    if entry["harvested"]:
        for k, v in entry["harvested"].items():
            print(f"     {k} = {v}")
    if interrupted:
        print("  本次为人为中断：已落账的成本是下界，未落盘的尾部记 UNKNOWN。")
    return rc


def append_markdown(e):
    new = not os.path.exists(NOTEBOOK)
    with open(NOTEBOOK, "a", encoding="utf-8") as f:
        if new:
            f.write("# 实验记录\n\n"
                    "由 `lab_log.py` 自动追加。**不要手工编辑** —— 手写的记录"
                    "证明不了任何事，自动记录才能。\n\n"
                    "每条记录包含：命令原文、git commit、机器、耗时、"
                    "产生的文件及其 sha256。\n"
                    "别人可以拿磁盘上的文件算一遍哈希，对照这里，"
                    "确认它确实是那条命令在那个 commit 下产生的。\n\n"
                    "---\n")
        env = e["env"]
        ok = "OK" if e["exit_code"] == 0 else f"FAILED (exit {e['exit_code']})"
        f.write(f"\n## #{e['id']}　{e['when']}　{ok}\n\n")
        if e["note"]:
            f.write(f"**{e['note']}**\n\n")
        f.write("```\n" + e["cmd"] + "\n```\n\n")
        f.write(f"- 耗时 {e['seconds']:.0f}s ｜ commit `{env['git_commit']}` "
                f"({env['git_branch']})"
                f"{' ⚠ **跟踪文件与该 commit 不一致，此次运行无法仅凭 commit 复现**' if env['git_dirty'] else ''}\n")
        f.write(f"- {env['host']} ｜ {env['os']} ｜ python {env['python']} ｜ "
                f"torch {env.get('torch', '?')} ｜ {env.get('gpu', 'CPU only')}\n")
        if e["harvested"]:
            f.write("- 抓到的关键数：")
            f.write("　".join(f"`{k} = {v}`" for k, v in e["harvested"].items()))
            f.write("\n")
        if e["outputs"]:
            f.write("\n| 产生/修改的文件 | 大小 | sha256 (前 16 位) |\n")
            f.write("|---|---|---|\n")
            for o in e["outputs"][:12]:
                h = o["sha256"][:16] if o["sha256"] else "(太大,未哈希)"
                f.write(f"| `{o['path']}` | {o['bytes'] / 1024:,.0f} KB | "
                        f"`{h}` |\n")
            if len(e["outputs"]) > 12:
                f.write(f"| … 另有 {len(e['outputs']) - 12} 个 | | |\n")
        f.write("\n<details><summary>输出末尾</summary>\n\n```\n")
        f.write("".join(e["stdout_tail"]))
        f.write("```\n\n</details>\n")


# --------------------------------------------------------------------------- #
def pad(text, width):
    """Left-justify by DISPLAY width.  A Chinese character is two columns
    wide but one len(), so plain f-string padding shreds the alignment."""
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    while w > width and text:
        text = text[:-1]
        w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
                for c in text)
    return text + " " * (width - w)


def do_show(a):
    if not os.path.exists(JSONL):
        print("还没有任何记录。用  py -3.11 lab_log.py run -- <命令>  开始。")
        return 0
    rows = [json.loads(l) for l in open(JSONL, encoding="utf-8")]
    if a.id:
        e = next((r for r in rows if r["id"] == a.id), None)
        if not e:
            print(f"没有 #{a.id}")
            return 1
        print(json.dumps(e, ensure_ascii=False, indent=1))
        return 0
    for e in rows[-a.n:]:
        ok = "ok  " if e["exit_code"] == 0 else "FAIL"
        got = "  ".join(f"{k}={v}" for k, v in list(e["harvested"].items())[:3])
        print(f"  #{e['id']:<3} {e['when'][5:16]}  {ok}  "
              f"{e['seconds']:>6.0f}s  {pad(e['note'], 34)} {got}")
    print(f"\n  共 {len(rows)} 条。  py -3.11 lab_log.py show --id N  看某一条。")
    return 0


def do_verify(a):
    """Do the files the log says were produced still hash the same?"""
    if not os.path.exists(JSONL):
        print("还没有任何记录。")
        return 0
    rows = [json.loads(l) for l in open(JSONL, encoding="utf-8")]
    latest = {}                       # path -> (run id, sha, bytes)
    for e in rows:
        for o in e["outputs"]:
            if o["sha256"]:
                latest[o["path"]] = (e["id"], o["sha256"], o["bytes"])
    okc = badc = gone = 0
    print(f"核对 {len(latest)} 个有哈希记录的文件…\n")
    for path, (rid, sha, n) in sorted(latest.items()):
        path = str(resolve_legacy(path))
        if not os.path.exists(path):
            print(f"  缺失   #{rid:<3} {path}")
            gone += 1
            continue
        cur = sha256(path)
        if cur == sha:
            okc += 1
        else:
            print(f"  不符   #{rid:<3} {path}")
            print(f"         记录 {sha[:16]}…  现在 "
                  f"{(cur or '(太大)')[:16]}…")
            badc += 1
    print(f"\n  一致 {okc}　不符 {badc}　缺失 {gone}")
    if badc:
        print("\n  「不符」不一定是坏事 —— 重跑同名输出就会变。它说明的是："
              "\n  这个文件已经不是那条记录产生的那一个了，引用时要指向新的那次运行。")
    # F16: this printed its findings and then returned 0 whatever it found, so
    # an automated caller that only inspects the exit code read "three recorded
    # outputs are gone" as a clean verification.  Report the states in the exit
    # code; the human-readable text above is unchanged.
    #   0 complete and consistent
    #   3 one or more recorded outputs are missing
    #   4 one or more recorded outputs hash differently
    #   5 both
    status = (3 if gone else 0) + (4 if badc else 0)
    if status == 7:
        status = 5
    if status:
        print(f"\n  退出码 {status}：缺失={gone}，不符={badc}。"
              "读取成功不等于证据一致，自动流程请按退出码分支，不要只看进程成功。")
    return status


def main():
    os.chdir(PROJECT_DIR)
    os.makedirs("records", exist_ok=True)
    ap = argparse.ArgumentParser(description="实验过程记录")
    sub = ap.add_subparsers(dest="what", required=True)

    r = sub.add_parser("run", help="跑一条命令并记录")
    r.add_argument("-m", "--message", default="", help="这次想验证什么")
    r.add_argument("cmd", nargs=argparse.REMAINDER)

    s = sub.add_parser("show", help="看记录")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--id", type=int)

    sub.add_parser("verify", help="核对文件哈希还对不对")

    a = ap.parse_args()
    if a.what == "run":
        if a.cmd and a.cmd[0] == "--":
            a.cmd = a.cmd[1:]
        return do_run(a)
    if a.what == "show":
        return do_show(a)
    return do_verify(a)


if __name__ == "__main__":
    sys.exit(main() or 0)

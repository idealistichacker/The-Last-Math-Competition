"""Offline reproduction for the local TLMC 00000000118 package.

This script reads only the frozen local Git object, builds the pinned dependency-free
Lean project, audits advertised theorem axioms, and rebuilds the PDF using only cached
Tectonic bundles. It never invokes lake update or any network command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEAN_ROOT = ROOT / "lean4"
SOURCE_PATH = "conjectures/00000000118.md"
BLOB = "697131a7b8dc0a62c539018c7d22612df1e7909a"
RAW_BLOB_SHA256 = "91b64b4a671db1806c346247acbc2e0d849c5f73337bc807806c7cd00bbd580a"
TOOLCHAIN = "leanprover/lean4:v4.33.1"
FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|native_decide|unsafe|implemented_by|extern|run_tac|elab|macro)\b")


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
    print("[RUN] " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, check=True, text=True,
                            encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    return result.stdout or ""


def verify_frozen_source(repo: Path) -> None:
    print("[STEP 1/4] Verify frozen organizer Git object and raw blob SHA-256.", flush=True)
    tree = run(["git", "-C", str(repo), "rev-parse", f"HEAD:{SOURCE_PATH}"], ROOT, capture=True).strip()
    if tree != BLOB:
        raise SystemExit(f"frozen Git blob mismatch: expected {BLOB}, got {tree!r}")
    raw = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", BLOB], check=True, stdout=subprocess.PIPE).stdout
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != RAW_BLOB_SHA256:
        raise SystemExit(f"raw Git blob SHA-256 mismatch: expected {RAW_BLOB_SHA256}, got {actual_sha}")
    current_blob = run(["git", "-C", str(repo), "hash-object", "--", SOURCE_PATH], ROOT, capture=True).strip()
    if current_blob != BLOB:
        raise SystemExit(f"checkout source hashes to {current_blob}, not frozen blob {BLOB}")
    print(f"[PASS] frozen blob {BLOB} and raw SHA-256 {actual_sha}", flush=True)


def verify_package() -> dict:
    print("[STEP 2/4] Verify package layout, pin, and Lean-source guard.", flush=True)
    if (LEAN_ROOT / "lean-toolchain").read_text(encoding="utf-8").strip() != TOOLCHAIN:
        raise SystemExit("unexpected Lean toolchain")
    manifest = json.loads((LEAN_ROOT / "lake-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("packages") != []:
        raise SystemExit("this dependency-free package must have an empty packages array")
    if "from path" in (LEAN_ROOT / "lakefile.lean").read_text(encoding="utf-8"):
        raise SystemExit("lakefile.lean must not use a path dependency")
    for path in (LEAN_ROOT / "Main.lean", LEAN_ROOT / "Check.lean"):
        match = FORBIDDEN.search(path.read_text(encoding="utf-8"))
        if match:
            raise SystemExit(f"forbidden Lean token in {path.relative_to(ROOT)}: {match.group(0)!r}")
    metadata = json.loads((ROOT / "submission.json").read_text(encoding="utf-8"))
    if metadata.get("source_git_blob") != BLOB or metadata.get("source_sha256") != RAW_BLOB_SHA256:
        raise SystemExit("submission.json source fingerprint differs from this reproduction script")
    pdf = ROOT / "main.pdf"
    expected_pdf_sha = metadata.get("artifacts", {}).get("main.pdf", {}).get("sha256")
    if not isinstance(expected_pdf_sha, str) or len(expected_pdf_sha) != 64:
        raise SystemExit("submission.json lacks a final main.pdf SHA-256")
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != expected_pdf_sha:
        raise SystemExit("checked-in main.pdf does not match submission.json")
    print("[PASS] layout, toolchain, no-dependency manifest, Lean guard, and checked-in PDF hash.", flush=True)
    return metadata


def verify_lean(lake: str) -> None:
    print("[STEP 3/4] Build and replay the dependency-free Lean project.", flush=True)
    version = run([lake, "env", "lean", "--version"], LEAN_ROOT, capture=True)
    if "Lean (version 4.33.1" not in version:
        raise SystemExit(f"unexpected Lean version:\n{version}")
    run([lake, "build", "Main"], LEAN_ROOT)
    run([lake, "env", "lean", "-DwarningAsError=true", "Main.lean"], LEAN_ROOT)
    audit = run([lake, "env", "lean", "-DwarningAsError=true", "Check.lean"], LEAN_ROOT, capture=True)
    if "sorryAx" in audit:
        raise SystemExit("axiom audit reported sorryAx")
    print(audit, end="")
    print("[PASS] build, warning-as-error replay, and axiom audit completed.", flush=True)


def default_tectonic(repo: Path) -> str:
    explicit = os.environ.get("TECTONIC")
    if explicit:
        return explicit
    found = shutil.which("tectonic")
    if found:
        return found
    for parent in (repo, *repo.parents):
        candidate = parent / ".local" / "tools" / "tectonic.exe"
        if candidate.is_file():
            return str(candidate)
    return "tectonic"


def verify_pdf(tectonic: str, expected_sha: str) -> None:
    print("[STEP 4/4] Rebuild PDF with cached-only Tectonic and compare bytes.", flush=True)
    outdir = ROOT / ".repro-pdf"
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir()
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "0"
    try:
        command = [tectonic, "--only-cached", "--outdir", str(outdir), "main.tex"]
        print("[RUN] " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
        rebuilt = outdir / "main.pdf"
        actual_sha = hashlib.sha256(rebuilt.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise SystemExit(f"rebuilt PDF SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
    finally:
        if outdir.exists():
            shutil.rmtree(outdir)
    print("[PASS] cached-only PDF rebuild is byte-identical.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", default=os.environ.get("LAKE", "lake"), help="path to local lake executable")
    parser.add_argument("--tectonic", default=None, help="optional Tectonic path; otherwise find local cached tool")
    parser.add_argument("--repo", type=Path, required=True, help="local organizer checkout containing the frozen source object")
    args = parser.parse_args()
    verify_frozen_source(args.repo)
    metadata = verify_package()
    verify_lean(args.lake)
    verify_pdf(args.tectonic or default_tectonic(args.repo.resolve()), metadata["artifacts"]["main.pdf"]["sha256"])
    print("[PASS] all local #118 reproduction checks completed.", flush=True)


if __name__ == "__main__":
    main()

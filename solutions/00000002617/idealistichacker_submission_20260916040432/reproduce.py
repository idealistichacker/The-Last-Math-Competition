#!/usr/bin/env python3
"""Reproduce the fixed standard-Mathlib bridge for TLMC conjecture 00000002617."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEAN_ROOT = ROOT / "lean4"
SOURCE_PATH = "conjectures/00000002617.md"
BLOB = "e23e80d92bfbf3e0970c427716f7ce3c2f97a39e"
RAW_SHA256 = "03ba0f9febb435b53de0c4df73642bbb647b1a0b9eef3f297cedf5263564bc5b"
MATHLIB_URL = "https://github.com/leanprover-community/mathlib4.git"
MATHLIB_REV = "0df444a360eaa60ab8c11dca51a86af692955474"
FORBIDDEN = re.compile(r"(?m)^\s*(?:sorry|admit|axiom|unsafe)\b|\bnative_decide\b")


def run(command: list[str], *, cwd: Path = LEAN_ROOT, capture: bool = False) -> str:
    print("[RUN]", subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(
        command, cwd=cwd,
        env={**os.environ, "MATHLIB_NO_CACHE_ON_UPDATE": "1", "PYTHONUTF8": "1"},
        check=True, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else ""


def verify_frozen_source(repo: Path) -> None:
    print("[STEP 1/4] Verify frozen organizer blob and raw-content SHA-256.", flush=True)
    if not repo.is_dir():
        raise SystemExit(f"--repo is not a directory: {repo}")
    object_type = run(["git", "-C", str(repo), "cat-file", "-t", BLOB], cwd=ROOT, capture=True).strip()
    if object_type != "blob":
        raise SystemExit(f"expected {BLOB} to be a blob, got {object_type!r}")
    raw = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", BLOB], check=True, stdout=subprocess.PIPE).stdout
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != RAW_SHA256:
        raise SystemExit(f"raw Git-blob SHA-256 mismatch: expected {RAW_SHA256}, got {actual_sha}")
    current_blob = run(["git", "-C", str(repo), "hash-object", "--", SOURCE_PATH], cwd=ROOT, capture=True).strip()
    if current_blob != BLOB:
        raise SystemExit(f"{SOURCE_PATH} does not hash to the frozen blob: got {current_blob}")
    print(f"[PASS] frozen blob {BLOB} and raw SHA-256 {actual_sha}", flush=True)


def verify_manifest() -> dict:
    print("[STEP 2/4] Verify the portable Git-pinned Mathlib manifest.", flush=True)
    manifest = json.loads((LEAN_ROOT / "lake-manifest.json").read_text(encoding="utf-8"))
    mathlib = next((p for p in manifest.get("packages", []) if p.get("name") == "mathlib"), None)
    if mathlib is None:
        raise SystemExit("lake-manifest.json has no mathlib package")
    required = {"type": "git", "url": MATHLIB_URL, "rev": MATHLIB_REV, "inputRev": MATHLIB_REV}
    for field, expected in required.items():
        if mathlib.get(field) != expected:
            raise SystemExit(f"Mathlib manifest {field} must be {expected!r}, got {mathlib.get(field)!r}")
    if any(p.get("type") == "path" for p in manifest.get("packages", [])):
        raise SystemExit("lake-manifest.json must not contain a path dependency")
    lakefile = (LEAN_ROOT / "lakefile.lean").read_text(encoding="utf-8")
    if MATHLIB_URL not in lakefile or MATHLIB_REV not in lakefile or "from path" in lakefile:
        raise SystemExit("lakefile.lean lacks the required Git-pinned Mathlib dependency")
    if (LEAN_ROOT / "lean-toolchain").read_text(encoding="utf-8").strip() != "leanprover/lean4:v4.33.1":
        raise SystemExit("unexpected Lean toolchain")
    for source in (LEAN_ROOT / "Main.lean", LEAN_ROOT / "Check.lean"):
        match = FORBIDDEN.search(source.read_text(encoding="utf-8"))
        if match:
            raise SystemExit(f"forbidden Lean construct in {source.name}: {match.group(0)!r}")
    print("[PASS] fixed Git manifest, toolchain, and Lean-source guard verified.", flush=True)
    return manifest


def verify_materialized_packages(manifest: dict) -> None:
    """Offline mode is valid only when every manifest package is present at its exact Git revision."""
    print("[OFFLINE] Verify every materialized package checkout against lake-manifest.json.", flush=True)
    packages = LEAN_ROOT / ".lake" / "packages"
    for spec in manifest.get("packages", []):
        if spec.get("type") != "git":
            raise SystemExit(f"offline mode requires a Git package, got {spec.get('type')!r} for {spec.get('name')!r}")
        name, revision, url = spec["name"], spec["rev"], spec.get("url")
        checkout = packages / name
        actual = run(["git", "-C", str(checkout), "rev-parse", "HEAD"], cwd=ROOT, capture=True).strip()
        if actual != revision:
            raise SystemExit(f"materialized package {name} has {actual}, expected {revision}")
        if url:
            origin = run(["git", "-C", str(checkout), "remote", "get-url", "origin"], cwd=ROOT, capture=True).strip()
            if origin != url:
                raise SystemExit(f"materialized package {name} origin differs from manifest")
    print("[PASS] all materialized Git package checkouts match the manifest exactly.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", default=os.environ.get("LAKE", "lake"), help="Lake executable or command name")
    parser.add_argument("--repo", type=Path, required=True, help="checkout containing the frozen organizer Git blob")
    parser.add_argument("--skip-update", action="store_true", help="offline exact-dependency mode; verify every package checkout before building")
    args = parser.parse_args()
    verify_frozen_source(args.repo)
    manifest = verify_manifest()
    if args.skip_update:
        verify_materialized_packages(manifest)
        print("[STEP 3/4] Offline exact-dependency mode: skip lake update and build the pinned project.", flush=True)
    else:
        print("[STEP 3/4] Update the fixed Git dependency and source-build the Lean project.", flush=True)
        run([args.lake, "update"])
    run([args.lake, "build"])
    print("[STEP 4/4] Replay Main.lean and print advertised theorem axiom footprints.", flush=True)
    run([args.lake, "env", "lean", "-DwarningAsError=true", "Main.lean"])
    run([args.lake, "env", "lean", "-DwarningAsError=true", "Check.lean"])
    print("[PASS] source fingerprint, Git manifest, source build, replay, and axiom audit completed.", flush=True)


if __name__ == "__main__":
    main()

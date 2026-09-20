#!/usr/bin/env python3
"""Build the committed packages twice offline and record identical wheel hashes.

Run with a Python environment containing setuptools>=75 and wheel. No package
installation, publication, image tagging or secret access is performed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tarfile
import tomllib
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise SystemExit("Commit the reviewed changes before building; working tree must be clean")
    commit = git("rev-parse", "HEAD")
    epoch = git("show", "-s", "--format=%ct", "HEAD")
    work = REPO / "tmp" / "fiscal-020" / ("repro-" + commit[:12])
    output = REPO / "dist" / ("buyer-profile-" + commit[:12])
    work.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "SOURCE_DATE_EPOCH": epoch, "PYTHONHASHSEED": "0"}
    versions = {}
    source_hashes = {}
    for run in ("one", "two"):
        source = work / run
        source.mkdir()
        archived = subprocess.check_output(["git", "archive", commit, "packages"], cwd=REPO)
        with tarfile.open(fileobj=BytesIO(archived)) as archive:
            archive.extractall(source, filter="data")
        destination = output if run == "one" else source / "dist"
        destination.mkdir(exist_ok=True)
        for package in ("core", "server"):
            project = source / "packages" / package
            metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
            versions[package] = metadata["project"]["version"]
            for file in sorted((project / "src").rglob("*.py")):
                source_hashes[str(file.relative_to(source)).replace("\\", "/")] = sha256(file)
            result = subprocess.run(
                [sys.executable, "-c", "from setuptools.build_meta import build_wheel; "
                 "import sys; build_wheel(sys.argv[1])", str(destination)],
                cwd=project, env=env, capture_output=True, text=True,
            )
            (work / f"{run}-{package}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            result.check_returncode()
    wheels = {wheel.name: sha256(wheel) for wheel in sorted(output.glob("*.whl"))}
    repeated = {wheel.name: sha256(wheel) for wheel in sorted((work / "two" / "dist").glob("*.whl"))}
    if len(wheels) != 2 or wheels != repeated:
        raise SystemExit("Reproducibility check failed")
    manifest = {
        "commit": commit, "tree": git("rev-parse", "HEAD^{tree}"),
        "source_date_epoch": int(epoch), "versions": versions,
        "builder_python": sys.version, "setuptools": importlib.metadata.version("setuptools"),
        "wheel": importlib.metadata.version("wheel"), "sha256": wheels,
        "repeated_build_identical": True, "committed_source_sha256": source_hashes,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "requirements-wheels.txt").write_text(
        "# Install from this directory after installing the approved requirements.lock.\n" +
        "\n".join(f"./{name} --hash=sha256:{digest}" for name, digest in wheels.items()) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), **manifest}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build twice from Git bytes; reproduce the approved release unless --candidate.

Install requirements-build.lock first. Candidates require a clean committed tree;
copy their manifest to release/manifest.json only after reviewing the artifacts.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[1]
BUILD_TOOLS = {"setuptools": "80.9.0", "wheel": "0.48.0", "packaging": "25.0"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def git_bytes(spec: str) -> bytes:
    return subprocess.check_output(["git", "show", spec], cwd=REPO)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_wheel(path: Path, epoch: int) -> None:
    """Fix container metadata across operating systems; preserve all code bytes.

    Setuptools emits platform-specific METADATA line endings and ZIP permissions.
    Store uncompressed members to avoid zlib-version-dependent hashes as well.
    RECORD must describe the final metadata bytes, as required by the wheel format.
    """
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    record = next(name for name in files if name.endswith(".dist-info/RECORD"))
    del files[record]
    for name in files:
        if name.endswith(".dist-info/METADATA"):
            files[name] = files[name].replace(b"\r\n", b"\n")
    rows = StringIO(newline="")
    writer = csv.writer(rows, lineterminator="\n")
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(data)))
    writer.writerow((record, "", ""))
    files[record] = rows.getvalue().encode("utf-8")
    result = BytesIO()
    with ZipFile(result, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, date_time=time.gmtime(max(epoch, 315532800))[:6])
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    path.write_bytes(result.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=REPO / "dist" / "release")
    args = parser.parse_args()
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise SystemExit("Commit the reviewed changes before building; working tree must be clean")
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Release builds require Python 3.12")
    actual_tools = {name: importlib.metadata.version(name) for name in BUILD_TOOLS}
    if actual_tools != BUILD_TOOLS:
        raise SystemExit("Install the pinned requirements-build.lock before building")
    approved = None if args.candidate else json.loads(
        (REPO / "release" / "manifest.json").read_text(encoding="utf-8"),
    )
    commit = approved["commit"] if approved else git("rev-parse", "HEAD")
    # Compare Git tree content, not commit ancestry: squash merges retain the
    # same bytes even when the candidate commit is no longer reachable.
    package_tree = git("rev-parse", "HEAD:packages")
    lock = git_bytes("HEAD:requirements.lock")
    if approved and (
        package_tree != approved["package_tree"]
        or sha256(lock) != approved["requirements_lock_sha256"]
    ):
        raise SystemExit("Runtime changed since approval: build and review a new versioned candidate")
    epoch = str(approved["source_date_epoch"]) if approved else git("show", "-s", "--format=%ct", commit)
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite artifacts: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "SOURCE_DATE_EPOCH": epoch, "PYTHONHASHSEED": "0"}
    versions = {}
    source_hashes = {}
    with tempfile.TemporaryDirectory(prefix="dian-wheels-") as temporary:
        work = Path(temporary)
        for run in ("one", "two"):
            source = work / run
            source.mkdir()
            archived = subprocess.check_output(["git", "archive", "HEAD", "packages"], cwd=REPO)
            with tarfile.open(fileobj=BytesIO(archived)) as archive:
                archive.extractall(source, filter="data")
            destination = source / "dist"
            destination.mkdir()
            for package in ("core", "server"):
                project = source / "packages" / package
                metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
                versions[package] = metadata["project"]["version"]
                for file in sorted((project / "src").rglob("*.py")):
                    source_hashes[file.relative_to(source).as_posix()] = sha256(file.read_bytes())
                result = subprocess.run(
                    [sys.executable, "-c", "from setuptools.build_meta import build_wheel; "
                     "import sys; build_wheel(sys.argv[1])", str(destination)],
                    cwd=project, env=env, capture_output=True, text=True,
                )
                if result.returncode:
                    raise SystemExit(result.stdout + result.stderr)
            for wheel in destination.glob("*.whl"):
                canonicalize_wheel(wheel, int(epoch))
        wheels = {p.name: sha256(p.read_bytes()) for p in sorted((work / "one/dist").glob("*.whl"))}
        repeated = {p.name: sha256(p.read_bytes()) for p in sorted((work / "two/dist").glob("*.whl"))}
        if len(wheels) != 2 or wheels != repeated or len(set(versions.values())) != 1:
            raise SystemExit("Reproducibility/version check failed")
        manifest = {
            "commit": commit, "package_tree": package_tree, "source_date_epoch": int(epoch),
            "versions": versions, "build_tools": actual_tools, "python_minor": "3.12",
            "wheel_format": "canonical-zip-v1",
            "requirements_lock_sha256": sha256(lock), "sha256": wheels,
            "repeated_build_identical": True, "committed_source_sha256": source_hashes,
        }
        if approved and manifest != approved:
            raise SystemExit("Build differs from the approved release/manifest.json")
        output.mkdir()
        for name in wheels:
            (output / name).write_bytes((work / "one/dist" / name).read_bytes())
        (output / "requirements.lock").write_bytes(lock)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (output / "requirements-wheels.txt").write_text(
            "\n".join(f"./{name} --hash=sha256:{digest}" for name, digest in wheels.items()) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"output": str(output), "commit": commit, "sha256": wheels}, indent=2))


if __name__ == "__main__":
    main()

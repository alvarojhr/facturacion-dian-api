#!/usr/bin/env python3
"""Verify wheel hashes and the exact package bytes imported by the image."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
from pathlib import Path
from zipfile import ZipFile


def verify(artifact_dir: Path, *, runtime: bool = False, approved_manifest: Path | None = None) -> dict:
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    approved = approved_manifest or artifact_dir / "approved-manifest.json"
    if approved_manifest or approved.exists():
        if manifest != json.loads(approved.read_text(encoding="utf-8")):
            raise ValueError("Bundle differs from the approved release manifest")
    wheels = manifest["sha256"]
    expected_names = {
        f"facturacion_dian_api_{name}-{version}-py3-none-any.whl"
        for name, version in manifest["versions"].items()
    }
    if set(manifest["versions"]) != {"core", "server"} or set(wheels) != expected_names:
        raise ValueError("Release must contain exactly the core and server wheels")
    if set(p.name for p in artifact_dir.glob("*.whl")) != expected_names:
        raise ValueError("Unexpected or missing wheel in the release bundle")
    lock_hash = hashlib.sha256((artifact_dir / "requirements.lock").read_bytes()).hexdigest()
    if lock_hash != manifest["requirements_lock_sha256"]:
        raise ValueError("Runtime lock differs from the approved release")
    expected_requirements = "\n".join(
        f"./{name} --hash=sha256:{digest}" for name, digest in wheels.items()
    ) + "\n"
    if (artifact_dir / "requirements-wheels.txt").read_text(encoding="utf-8") != expected_requirements:
        raise ValueError("Wheel installation list differs from the approved manifest")
    checked = 0
    for name, version in manifest["versions"].items():
        filename = f"facturacion_dian_api_{name}-{version}-py3-none-any.whl"
        wheel = artifact_dir / filename
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != wheels[filename]:
            raise ValueError(f"Wheel hash mismatch: {filename}")
        if not runtime:
            continue
        dist = metadata.distribution("facturacion-dian-api-" + name)
        if dist.version != version:
            raise ValueError(f"Installed version mismatch: {name}")
        direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
        if direct_url.get("dir_info", {}).get("editable"):
            raise ValueError(f"Editable installation forbidden: {name}")
        prefix = f"facturacion_dian_api/{name}/"
        with ZipFile(wheel) as archive:
            package_files = {p for p in archive.namelist() if p.startswith(prefix) and not p.endswith("/")}
            for relative in package_files:
                installed = Path(dist.locate_file(relative)).resolve()
                if not installed.is_relative_to(Path(sys.prefix).resolve()):
                    raise ValueError(f"Package outside the runtime environment: {relative}")
                if not installed.is_file() or installed.read_bytes() != archive.read(relative):
                    raise ValueError(f"Installed bytes differ from the wheel: {relative}")
                if relative.endswith(".py"):
                    module_name = relative.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
                    module = importlib.import_module(module_name)
                    if Path(module.__file__).resolve() != installed:
                        raise ValueError(f"Import is shadowed by another source: {module_name}")
                checked += 1
            root = Path(dist.locate_file(prefix))
            actual = {prefix + p.relative_to(root).as_posix() for p in root.rglob("*.py")}
            expected = {p for p in package_files if p.endswith(".py")}
            if actual != expected:
                raise ValueError(f"Unexpected Python files in installed package: {name}")
    return {"versions": manifest["versions"], "commit": manifest["commit"],
            "runtime_files_verified": checked, "editable": False if runtime else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--approved-manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact_dir, runtime=args.runtime, approved_manifest=args.approved_manifest), indent=2))


if __name__ == "__main__":
    main()

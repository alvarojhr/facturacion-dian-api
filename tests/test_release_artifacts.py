"""Regressions for editable installs and the Windows checkout byte mismatch."""

from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

VERIFY = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/verify_release.py"))["verify"]


@pytest.fixture
def release_bundle(tmp_path, monkeypatch):
    installed = tmp_path / "installed"
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    versions = {"core": "0.2.0a2", "server": "0.2.0a2"}
    hashes = {}
    for name, version in versions.items():
        path = f"facturacion_dian_api/{name}/__init__.py"
        wheel = artifact / f"facturacion_dian_api_{name}-{version}-py3-none-any.whl"
        with ZipFile(wheel, "w") as archive:
            archive.writestr(path, b'"""LF bytes from git archive."""\n')
        target = installed / path
        target.parent.mkdir(parents=True)
        target.write_bytes(b'"""LF bytes from git archive."""\n')
        hashes[wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    manifest = {"commit": "test", "versions": versions, "sha256": hashes,
                "requirements_lock_sha256": hashlib.sha256(b"# locked\n").hexdigest()}
    (artifact / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (artifact / "requirements.lock").write_bytes(b"# locked\n")
    (artifact / "requirements-wheels.txt").write_text(
        "\n".join(f"./{name} --hash=sha256:{digest}" for name, digest in hashes.items()) + "\n",
        encoding="utf-8",
    )
    dist = SimpleNamespace(version="0.2.0a2", read_text=lambda _: "{}", locate_file=lambda p: installed / p)
    globals_ = VERIFY.__globals__
    monkeypatch.setattr(globals_["metadata"], "distribution", lambda _: dist)
    monkeypatch.setattr(globals_["sys"], "prefix", str(installed))
    monkeypatch.setattr(globals_["importlib"], "import_module", lambda name: SimpleNamespace(
        __file__=installed / name.replace(".", "/") / "__init__.py",
    ))
    return artifact, installed, dist


def test_exact_wheel_installation_passes(release_bundle):
    artifact, _, _ = release_bundle
    assert VERIFY(artifact, runtime=True)["runtime_files_verified"] == 2


def test_crlf_checkout_cannot_pass_as_the_approved_wheel(release_bundle):
    artifact, installed, _ = release_bundle
    path = installed / "facturacion_dian_api/core/__init__.py"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="Installed bytes differ"):
        VERIFY(artifact, runtime=True)


def test_editable_install_is_rejected_even_with_matching_bytes(release_bundle):
    artifact, _, dist = release_bundle
    dist.read_text = lambda _: '{"dir_info":{"editable":true}}'
    with pytest.raises(ValueError, match="Editable installation forbidden"):
        VERIFY(artifact, runtime=True)


def test_wheel_tampering_is_rejected(release_bundle):
    artifact, _, _ = release_bundle
    wheel = next(artifact.glob("*.whl"))
    wheel.write_bytes(wheel.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Wheel hash mismatch"):
        VERIFY(artifact, runtime=True)


def test_extra_installed_python_file_is_rejected(release_bundle):
    artifact, installed, _ = release_bundle
    (installed / "facturacion_dian_api/core/stale.py").write_text("# old file", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected Python files"):
        VERIFY(artifact, runtime=True)


def test_shadowed_import_is_rejected(release_bundle, monkeypatch):
    artifact, installed, _ = release_bundle
    monkeypatch.setattr(VERIFY.__globals__["importlib"], "import_module", lambda _: SimpleNamespace(
        __file__=installed / "checkout/core/__init__.py",
    ))
    with pytest.raises(ValueError, match="Import is shadowed"):
        VERIFY(artifact, runtime=True)


def test_dependency_lock_tampering_is_rejected(release_bundle):
    artifact, _, _ = release_bundle
    (artifact / "requirements.lock").write_bytes(b"# unapproved\n")
    with pytest.raises(ValueError, match="Runtime lock differs"):
        VERIFY(artifact, runtime=True)


def test_self_consistent_bundle_still_needs_the_approved_manifest(release_bundle):
    artifact, _, _ = release_bundle
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    manifest["commit"] = "different-candidate"
    approved = artifact / "approved-manifest.json"
    approved.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Bundle differs from the approved"):
        VERIFY(artifact, runtime=True)

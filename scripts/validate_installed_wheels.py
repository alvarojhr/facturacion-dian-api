#!/usr/bin/env python3
"""Run offline contract/signature/XSD QA using installed, non-editable wheels.

Invoke with the clean venv's Python -I, after installing runtime and dev test
dependencies. The two official XSD directories are mandatory for release QA.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import ipaddress
import json
import os
import runpy
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--fe-xsd-dir", type=Path, required=True)
    parser.add_argument("--dee-xsd-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((args.artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    verification = runpy.run_path(str(repo / "scripts" / "verify_release.py"))["verify"](
        args.artifact_dir, runtime=True,
    )
    for family in ("fe", "dee"):
        folder = getattr(args, family + "_xsd_dir")
        assert (folder / "UBL-Invoice-2.1.xsd").is_file(), folder
        os.environ[f"DIAN_{family.upper()}_XSD_DIR"] = str(folder.resolve())
    for wheel, expected in manifest["sha256"].items():
        assert hashlib.sha256((args.artifact_dir / wheel).read_bytes()).hexdigest() == expected

    # Windows asyncio needs loopback for its internal wakeup socket.
    def guard(original):
        def connect(sock, address):
            if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
                raise AssertionError(f"External network forbidden in wheel QA: {address!r}")
            return original(sock, address)
        return connect
    socket.socket.connect = guard(socket.socket.connect)
    socket.socket.connect_ex = guard(socket.socket.connect_ex)
    os.environ.update(
        DIAN_ENVIRONMENT="habilitacion", DIAN_SOFTWARE_ID="offline-software",
        DIAN_SOFTWARE_PIN="offline-pin", DIAN_TECHNICAL_KEY="offline-key",
        DIAN_TEST_SET_ID="offline-test-set", PYTHONDONTWRITEBYTECODE="1",
    )
    import facturacion_dian_api.core.models as core
    import facturacion_dian_api.server.contracts as server
    from facturacion_dian_api.server.app import app
    from fastapi.testclient import TestClient

    modules = {"core": str(Path(core.__file__).resolve()), "server": str(Path(server.__file__).resolve())}
    versions = {name: metadata.version("facturacion-dian-api-" + name) for name in modules}
    assert versions == manifest["versions"], versions
    assert all(Path(path).is_relative_to(Path(sys.prefix)) for path in modules.values()), modules
    for name in modules:
        dist = metadata.distribution("facturacion-dian-api-" + name)
        direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
        assert not direct_url.get("dir_info", {}).get("editable")
    client = TestClient(app)
    health = []
    for days in (365, 3):
        bundle = SimpleNamespace(is_valid=True, not_valid_after=datetime.now(UTC) + timedelta(days=days))
        with patch("facturacion_dian_api.server.api.health.get_certificate_bundle", return_value=bundle):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["version"] == versions["server"]
            health.append(response.json())
    with patch("facturacion_dian_api.server.api.health.get_certificate_bundle", side_effect=FileNotFoundError("offline")):
        response = client.get("/health")
        assert response.json()["certificate_loaded"] is False
        assert response.json()["version"] == versions["server"]
        health.append(response.json())

    import pytest
    result = pytest.main([
        "-c", str(repo / "pyproject.toml"), "-o", "pythonpath=", "-p", "no:cacheprovider",
        "-m", "not integration", "-q", str(repo / "tests"),
    ])
    assert all(Path(module.__file__).resolve().is_relative_to(Path(sys.prefix)) for module in (core, server))
    (args.artifact_dir / "installed-qa.json").write_text(json.dumps({
        "commit": manifest["commit"], "python": sys.executable, "modules": modules,
        "versions": versions, "health": health, "pytest_exit_code": int(result),
        "runtime_verification": verification,
        "fe_xsd_dir": str(args.fe_xsd_dir), "dee_xsd_dir": str(args.dee_xsd_dir),
        "external_network_blocked": True,
    }, indent=2) + "\n", encoding="utf-8")
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())

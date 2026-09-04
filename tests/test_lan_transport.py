"""Tests for the deliberately conservative LAN transport scaffold."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).parents[1] / "custom_components" / "kidde_homesafe"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Build a minimal package namespace without importing Home Assistant.
package = types.ModuleType("kidde_homesafe")
package.__path__ = [str(_ROOT)]
sys.modules["kidde_homesafe"] = package
transport_package = types.ModuleType("kidde_homesafe.transport")
transport_package.__path__ = [str(_ROOT / "transport")]
sys.modules["kidde_homesafe.transport"] = transport_package
_load("kidde_homesafe.models", _ROOT / "models.py")
_load("kidde_homesafe.transport.base", _ROOT / "transport" / "base.py")
lan = _load("kidde_homesafe.transport.lan", _ROOT / "transport" / "lan.py")


def test_discovery_reports_reachability_without_claiming_capabilities() -> None:
    async def fake_probe(endpoint, timeout):
        assert endpoint.host == "192.0.2.10"
        assert timeout == 1.0
        return True

    transport = lan.AylaLanTransport(
        {"device_test": lan.LanEndpoint("192.0.2.10")},
        timeout=1.0,
        probe=fake_probe,
    )
    capabilities = asyncio.run(transport.discover())["device_test"]
    assert capabilities.readable_fields == frozenset()
    assert capabilities.commands == frozenset()
    assert capabilities.metadata["tcp_reachable"] == "true"
    assert capabilities.metadata["protocol_verified"] == "false"


def test_read_refuses_unverified_protocol() -> None:
    transport = lan.AylaLanTransport(
        {"device_test": lan.LanEndpoint("192.0.2.10")}
    )
    try:
        asyncio.run(transport.read("device_test"))
    except lan.LanProtocolNotVerifiedError as err:
        assert "not verified" in str(err)
    else:
        raise AssertionError("unverified LAN read was allowed")

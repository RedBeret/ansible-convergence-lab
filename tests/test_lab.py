from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

WORKSPACE = Path(os.environ.get("LAB_WORKSPACE", Path(__file__).resolve().parents[1])).resolve()
SIMULATOR_URL = os.environ.get("LAB_SIMULATOR_URL", "http://simulator:8080").rstrip("/")
HOSTNAME = "edge-r1.lab.example"


def run_labctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "aclab.labctl", *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        env={**os.environ, "LAB_WORKSPACE": str(WORKSPACE), "LAB_SIMULATOR_URL": SIMULATOR_URL},
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        pytest.fail(f"labctl {' '.join(args)} failed with exit code {result.returncode}")
    return result


def read_json(path: str) -> dict:
    return json.loads((WORKSPACE / path).read_text(encoding="utf-8"))


def fetch_state() -> dict:
    with urllib.request.urlopen(f"{SIMULATOR_URL}/v1/device/config", timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))["state"]


@pytest.fixture(autouse=True)
def reset_simulator() -> None:
    run_labctl("reset")


def test_playbook_smoke() -> None:
    run_labctl("precheck")
    run_labctl("backup")
    run_labctl("deploy")
    run_labctl("verify")

    state = fetch_state()
    assert state["running_config"]["hostname"] == HOSTNAME
    assert state["startup_config"] == state["running_config"]
    assert state["last_saved_at"] is not None


def test_idempotency() -> None:
    run_labctl("precheck")
    run_labctl("deploy")
    run_labctl("verify")
    run_labctl("deploy")

    deploy_report = read_json("reports/20_deploy-latest.json")
    assert deploy_report["recap"]["changed"] == 0


def test_drift_detection() -> None:
    run_labctl("precheck")
    run_labctl("deploy")
    run_labctl("verify")
    run_labctl("inject-drift")

    drift_result = run_labctl("drift-check", check=False)
    drift_report = read_json(f"reports/drift-{HOSTNAME}.json")

    assert drift_result.returncode != 0
    assert drift_report["drift_detected"] is True

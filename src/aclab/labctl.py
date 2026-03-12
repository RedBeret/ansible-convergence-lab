from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, Field

from aclab.logging_utils import configure_json_logger

app = typer.Typer(help="Task runner for the synthetic Ansible convergence lab.", no_args_is_help=True)


class LabSettings(BaseModel):
    workspace: Path
    inventory_path: Path
    reports_dir: Path
    log_dir: Path
    backups_dir: Path
    rendered_dir: Path
    simulator_url: str = Field(pattern=r"^https?://")
    health_timeout_seconds: int = Field(default=60, ge=5, le=300)
    command_timeout_seconds: int = Field(default=240, ge=10, le=900)
    initial_backoff_seconds: float = Field(default=1.0, ge=0.5, le=10.0)
    max_backoff_seconds: float = Field(default=8.0, ge=1.0, le=30.0)

    @classmethod
    def from_env(cls) -> "LabSettings":
        workspace = Path(os.getenv("LAB_WORKSPACE", "/workspace")).resolve()
        return cls(
            workspace=workspace,
            inventory_path=workspace / "inventories" / "local.yml",
            reports_dir=workspace / "reports",
            log_dir=workspace / "reports" / "logs",
            backups_dir=workspace / "backups",
            rendered_dir=workspace / "rendered",
            simulator_url=os.getenv("LAB_SIMULATOR_URL", "http://simulator:8080").rstrip("/"),
        )

    def ensure_directories(self) -> None:
        for directory in (self.reports_dir, self.log_dir, self.backups_dir, self.rendered_dir, self.backups_dir / "last-known-good"):
            directory.mkdir(parents=True, exist_ok=True)


class PlaybookOutcome(BaseModel):
    playbook: str
    exit_code: int
    duration_seconds: float
    recap: dict[str, int] = Field(default_factory=dict)
    log_path: Path


def _logger(settings: LabSettings):
    return configure_json_logger("aclab.labctl", log_path=settings.log_dir / "labctl.jsonl")


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout_seconds: float = 5.0) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, method=method.upper(), data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _wait_for_health(settings: LabSettings, logger: Any) -> dict[str, Any]:
    attempt = 1
    backoff = settings.initial_backoff_seconds
    deadline = time.monotonic() + settings.health_timeout_seconds
    while time.monotonic() < deadline:
        try:
            payload = _request_json("GET", f"{settings.simulator_url}/healthz", timeout_seconds=3.0)
        except urllib.error.URLError as exc:
            logger.warning(
                "healthcheck attempt failed",
                extra={
                    "event": "lab.health.retry",
                    "attempt": attempt,
                    "extras": {"error": str(exc)},
                },
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, settings.max_backoff_seconds)
            attempt += 1
            continue
        if payload.get("status") == "ok":
            logger.info("simulator healthy", extra={"event": "lab.health.ok", "attempt": attempt, "extras": payload})
            return payload
        time.sleep(backoff)
        backoff = min(backoff * 2, settings.max_backoff_seconds)
        attempt += 1
    raise typer.Exit(code=1)


def _parse_recap(output: str) -> dict[str, int]:
    recap_pattern = re.compile(
        r"^\S+\s*:\s*ok=(?P<ok>\d+)\s+changed=(?P<changed>\d+)\s+unreachable=(?P<unreachable>\d+)\s+failed=(?P<failed>\d+)\s+skipped=(?P<skipped>\d+)\s+rescued=(?P<rescued>\d+)\s+ignored=(?P<ignored>\d+)",
        re.MULTILINE,
    )
    match = None
    for match in recap_pattern.finditer(output):
        pass
    if match is None:
        return {}
    return {key: int(value) for key, value in match.groupdict().items()}


def _run_command(command: list[str], settings: LabSettings, logger: Any, playbook: str, expect_failure: bool = False) -> PlaybookOutcome:
    settings.ensure_directories()
    logger.info("running command", extra={"event": "lab.command.start", "command": " ".join(command), "playbook": playbook})
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=settings.workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "ANSIBLE_CONFIG": str(settings.workspace / "ansible.cfg")},
    )
    assert process.stdout is not None
    lines: list[str] = []
    while True:
        line = process.stdout.readline()
        if line:
            sys.stdout.write(line)
            sys.stdout.flush()
            lines.append(line)
        if process.poll() is not None and not line:
            break
        if time.monotonic() - started > settings.command_timeout_seconds:
            process.kill()
            logger.error("command timed out", extra={"event": "lab.command.timeout", "command": " ".join(command), "playbook": playbook})
            raise typer.Exit(code=1)
    exit_code = process.wait()
    duration_seconds = round(time.monotonic() - started, 2)
    output = "".join(lines)
    stem = Path(playbook).stem
    log_path = settings.log_dir / f"{stem}.log"
    log_path.write_text(output, encoding="utf-8")
    outcome = PlaybookOutcome(
        playbook=playbook,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        recap=_parse_recap(output),
        log_path=log_path,
    )
    _write_json(
        settings.reports_dir / f"{stem}-latest.json",
        {
            "playbook": playbook,
            "exit_code": exit_code,
            "duration_seconds": duration_seconds,
            "recap": outcome.recap,
            "log_path": str(log_path),
        },
    )
    logger.info(
        "command finished",
        extra={
            "event": "lab.command.finish",
            "command": " ".join(command),
            "playbook": playbook,
            "elapsed_ms": round(duration_seconds * 1000, 2),
            "exit_code": exit_code,
        },
    )
    if exit_code != 0 and not expect_failure:
        raise typer.Exit(code=exit_code)
    return outcome


def _run_playbook(playbook: str, expect_failure: bool = False) -> PlaybookOutcome:
    settings = LabSettings.from_env()
    settings.ensure_directories()
    logger = _logger(settings)
    _wait_for_health(settings, logger)
    playbook_path = settings.workspace / "playbooks" / playbook
    return _run_command(
        ["ansible-playbook", "-i", str(settings.inventory_path), str(playbook_path)],
        settings=settings,
        logger=logger,
        playbook=playbook,
        expect_failure=expect_failure,
    )


def _post_admin(action: str) -> dict[str, Any]:
    settings = LabSettings.from_env()
    settings.ensure_directories()
    logger = _logger(settings)
    _wait_for_health(settings, logger)
    payload = _request_json("POST", f"{settings.simulator_url}/v1/admin/{action}")
    logger.info("admin action complete", extra={"event": f"lab.admin.{action}", "extras": payload})
    return payload


@app.command("reset")
def reset() -> None:
    payload = _post_admin("reset")
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("inject-drift")
def inject_drift() -> None:
    payload = _post_admin("drift")
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("precheck")
def precheck() -> None:
    _run_playbook("00_precheck.yml")


@app.command("backup")
def backup() -> None:
    _run_playbook("10_backup.yml")


@app.command("deploy")
def deploy() -> None:
    _run_playbook("20_deploy.yml")


@app.command("verify")
def verify() -> None:
    _run_playbook("30_verify.yml")


@app.command("drift-check")
def drift_check() -> None:
    _run_playbook("40_drift_check.yml")


@app.command("rollback")
def rollback() -> None:
    _run_playbook("50_rollback.yml")


@app.command("test")
def test() -> None:
    settings = LabSettings.from_env()
    settings.ensure_directories()
    logger = _logger(settings)
    _wait_for_health(settings, logger)
    _run_command([sys.executable, "-m", "pytest", "-q", "tests"], settings=settings, logger=logger, playbook="pytest")


@app.command("demo")
def demo() -> None:
    settings = LabSettings.from_env()
    settings.ensure_directories()
    _post_admin("reset")
    precheck_outcome = _run_playbook("00_precheck.yml")
    backup_outcome = _run_playbook("10_backup.yml")
    first_deploy = _run_playbook("20_deploy.yml")
    first_verify = _run_playbook("30_verify.yml")
    second_deploy = _run_playbook("20_deploy.yml")
    if second_deploy.recap.get("changed") not in (0, None):
        raise typer.Exit(code=1)
    _post_admin("drift")
    drift_outcome = _run_playbook("40_drift_check.yml", expect_failure=True)
    drift_reports = sorted(settings.reports_dir.glob("drift-*.json"))
    if not drift_reports:
        raise typer.Exit(code=1)
    drift_report_path = drift_reports[0]
    drift_report = json.loads(drift_report_path.read_text(encoding="utf-8"))
    if drift_outcome.exit_code == 0 or drift_report.get("drift_detected") is not True:
        raise typer.Exit(code=1)
    rollback_outcome = _run_playbook("50_rollback.yml")
    final_verify = _run_playbook("30_verify.yml")
    summary = {
        "demo_completed": True,
        "blank_state_converged": first_deploy.exit_code == 0 and first_verify.exit_code == 0,
        "idempotent_second_run": second_deploy.recap.get("changed", 0) == 0,
        "drift_detected": drift_report.get("drift_detected", False),
        "rollback_restored_last_known_good": rollback_outcome.exit_code == 0 and final_verify.exit_code == 0,
        "steps": {
            "precheck": precheck_outcome.model_dump(mode="json"),
            "backup": backup_outcome.model_dump(mode="json"),
            "first_deploy": first_deploy.model_dump(mode="json"),
            "first_verify": first_verify.model_dump(mode="json"),
            "second_deploy": second_deploy.model_dump(mode="json"),
            "drift_check": drift_outcome.model_dump(mode="json"),
            "rollback": rollback_outcome.model_dump(mode="json"),
            "final_verify": final_verify.model_dump(mode="json"),
        },
    }
    _write_json(settings.reports_dir / "demo-latest.json", summary)
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

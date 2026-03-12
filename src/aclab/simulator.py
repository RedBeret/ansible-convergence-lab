from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import typer
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aclab.logging_utils import configure_json_logger
from aclab.models import BaselineRequest, InterfacesRequest, LocalUsersRequest, RestoreRequest, SSHRequest, render_cli_config
from aclab.store import SQLiteStore

cli_app = typer.Typer(help="CLI helpers for the synthetic device simulator.", no_args_is_help=True)


def _default_base_url() -> str:
    return os.getenv("SIMULATOR_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def _db_path() -> Path:
    return Path(os.getenv("SIMULATOR_DB_PATH", "/var/lib/cli-device-sim/state.db"))


def _logger():
    log_path = Path(os.getenv("SIMULATOR_LOG_PATH", "/var/lib/cli-device-sim/simulator.jsonl"))
    return configure_json_logger("aclab.simulator", log_path=log_path)


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout_seconds: float = 5.0) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, method=method.upper(), data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def create_app() -> FastAPI:
    app = FastAPI(title="cli-device-sim", version="0.1.0")
    store = SQLiteStore(_db_path())
    logger = _logger()
    app.state.store = store
    app.state.logger = logger

    @app.middleware("http")
    async def structured_request_logging(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "event": "http.request.failed",
                    "path": request.url.path,
                    "extras": {"method": request.method},
                },
            )
            raise
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "event": "http.request.completed",
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "extras": {"method": request.method},
            },
        )
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        state = store.get_state()
        return {
            "status": "ok",
            "db_path": str(_db_path()),
            "revision": state.revision,
            "hostname": state.running_config.hostname,
        }

    @app.get("/v1/device/facts")
    def facts() -> dict[str, Any]:
        return store.get_state().facts.model_dump(mode="json")

    @app.get("/v1/device/config")
    def config() -> dict[str, Any]:
        state = store.get_state()
        return {"state": state.model_dump(mode="json")}

    @app.get("/v1/device/running-config")
    def running_config() -> dict[str, Any]:
        state = store.get_state()
        return {
            "running_config": render_cli_config(state.running_config, state),
            "startup_config": render_cli_config(state.startup_config, state),
            "last_saved_at": state.last_saved_at,
        }

    @app.put("/v1/device/baseline")
    def baseline(payload: BaselineRequest) -> dict[str, Any]:
        result = store.apply_baseline(payload)
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.put("/v1/device/local-users")
    def local_users(payload: LocalUsersRequest) -> dict[str, Any]:
        result = store.apply_local_users(payload)
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.put("/v1/device/interfaces")
    def interfaces(payload: InterfacesRequest) -> dict[str, Any]:
        result = store.apply_interfaces(payload)
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.put("/v1/device/ssh")
    def ssh(payload: SSHRequest) -> dict[str, Any]:
        result = store.apply_ssh(payload)
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.post("/v1/device/startup/save")
    def startup_save() -> dict[str, Any]:
        result = store.save_startup()
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.post("/v1/device/restore")
    def restore(payload: RestoreRequest) -> dict[str, Any]:
        result = store.restore_backup(payload)
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.get("/v1/admin/events")
    def events(limit: int = 20) -> dict[str, Any]:
        return {"events": store.list_events(limit=limit)}

    @app.post("/v1/admin/reset")
    def reset() -> dict[str, Any]:
        result = store.reset()
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.post("/v1/admin/drift")
    def inject_drift() -> dict[str, Any]:
        result = store.inject_drift()
        return {"changed": result["changed"], "state": result["state"].model_dump(mode="json")}

    @app.exception_handler(Exception)
    async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled application exception", extra={"event": "http.unhandled_exception"})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


@cli_app.command("healthcheck")
def healthcheck(url: str = typer.Option("http://127.0.0.1:8080/healthz"), timeout_seconds: float = typer.Option(3.0)) -> None:
    try:
        payload = _request_json("GET", url=url, timeout_seconds=timeout_seconds)
    except urllib.error.URLError as exc:
        raise typer.Exit(code=1) from exc
    if payload.get("status") != "ok":
        raise typer.Exit(code=1)
    typer.echo(json.dumps(payload, sort_keys=True))


@cli_app.command("reset")
def reset(base_url: str | None = typer.Option(None)) -> None:
    payload = _request_json("POST", f"{(base_url or _default_base_url())}/v1/admin/reset")
    typer.echo(json.dumps(payload, sort_keys=True))


@cli_app.command("inject-drift")
def inject_drift(base_url: str | None = typer.Option(None)) -> None:
    payload = _request_json("POST", f"{(base_url or _default_base_url())}/v1/admin/drift")
    typer.echo(json.dumps(payload, sort_keys=True))


@cli_app.command("show-running-config")
def show_running_config(base_url: str | None = typer.Option(None)) -> None:
    payload = _request_json("GET", f"{(base_url or _default_base_url())}/v1/device/running-config")
    typer.echo(payload["running_config"])


def cli_main() -> None:
    cli_app()


def server_main() -> None:
    uvicorn.run(
        "aclab.simulator:create_app",
        host=os.getenv("SIMULATOR_HOST", "0.0.0.0"),
        port=int(os.getenv("SIMULATOR_PORT", "8080")),
        factory=True,
    )


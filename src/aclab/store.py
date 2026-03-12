from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from aclab.models import BackupRecord, BaselineRequest, DeviceConfig, DeviceState, InterfacesRequest, LocalUsersRequest, RestoreRequest, SSHRequest


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_schema()
        self._ensure_seed_data()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS device_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _ensure_seed_data(self) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM device_state WHERE id = 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO device_state (id, payload) VALUES (1, ?)", (DeviceState.blank().model_dump_json(),))
                connection.commit()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _dump(data: Any) -> str:
        if hasattr(data, "model_dump"):
            return json.dumps(data.model_dump(mode="json"), sort_keys=True)
        return json.dumps(data, sort_keys=True, default=str)

    def _load_state(self, connection: sqlite3.Connection) -> DeviceState:
        row = connection.execute("SELECT payload FROM device_state WHERE id = 1").fetchone()
        if row is None:
            state = DeviceState.blank()
            connection.execute("INSERT INTO device_state (id, payload) VALUES (1, ?)", (state.model_dump_json(),))
            connection.commit()
            return state
        return DeviceState.model_validate_json(row["payload"])

    def _save_state(self, connection: sqlite3.Connection, state: DeviceState, event_type: str, payload: dict[str, Any]) -> None:
        connection.execute("UPDATE device_state SET payload = ? WHERE id = 1", (state.model_dump_json(),))
        connection.execute(
            "INSERT INTO audit_events (created_at, event_type, payload) VALUES (?, ?, ?)",
            (self._now().isoformat(), event_type, self._dump(payload)),
        )
        connection.commit()

    def get_state(self) -> DeviceState:
        with self._lock, self._connect() as connection:
            return self._load_state(connection)

    def list_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT created_at, event_type, payload FROM audit_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row["created_at"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]

    def _mutate(self, event_type: str, transform: Callable[[DeviceState], DeviceState], payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            current = self._load_state(connection)
            candidate = DeviceState.model_validate(current.model_dump(mode="python"))
            candidate = transform(candidate)
            candidate = DeviceState.model_validate(candidate.model_dump(mode="python"))
            changed = current.model_dump(mode="json") != candidate.model_dump(mode="json")
            if changed:
                candidate.updated_at = self._now()
                candidate.revision = current.revision + 1
                self._save_state(connection, candidate, event_type, payload)
            return {"changed": changed, "state": candidate}

    def reset(self) -> dict[str, Any]:
        def _reset(_: DeviceState) -> DeviceState:
            return DeviceState.blank()

        return self._mutate("device.reset", _reset, {"reason": "synthetic reset"})

    def apply_baseline(self, request: BaselineRequest) -> dict[str, Any]:
        def _apply(state: DeviceState) -> DeviceState:
            state.running_config.hostname = request.hostname
            state.running_config.banner = request.banner
            return state

        return self._mutate("device.apply_baseline", _apply, request.model_dump(mode="json"))

    def apply_local_users(self, request: LocalUsersRequest) -> dict[str, Any]:
        def _apply(state: DeviceState) -> DeviceState:
            state.running_config.local_users = request.local_users
            return state

        return self._mutate("device.apply_local_users", _apply, request.model_dump(mode="json"))

    def apply_interfaces(self, request: InterfacesRequest) -> dict[str, Any]:
        def _apply(state: DeviceState) -> DeviceState:
            state.running_config.interfaces = request.interfaces
            return state

        return self._mutate("device.apply_interfaces", _apply, request.model_dump(mode="json"))

    def apply_ssh(self, request: SSHRequest) -> dict[str, Any]:
        def _apply(state: DeviceState) -> DeviceState:
            state.running_config.ssh = request.ssh
            return state

        return self._mutate("device.apply_ssh", _apply, request.model_dump(mode="json"))

    def save_startup(self) -> dict[str, Any]:
        def _save(state: DeviceState) -> DeviceState:
            running = DeviceConfig.model_validate(state.running_config.model_dump(mode="python"))
            if state.startup_config.model_dump(mode="json") != running.model_dump(mode="json"):
                state.startup_config = running
                state.last_saved_at = self._now()
            return state

        return self._mutate("device.save_startup", _save, {"action": "save_startup"})

    def save_snapshot(self, name: str, kind: str = "named") -> BackupRecord:
        state = self.get_state()
        backup = BackupRecord(host=state.running_config.hostname, snapshot_name=name, captured_at=self._now(), state=state)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO snapshots (name, kind, created_at, payload) VALUES (?, ?, ?, ?)",
                (name, kind, self._now().isoformat(), backup.model_dump_json()),
            )
            connection.execute(
                "INSERT INTO audit_events (created_at, event_type, payload) VALUES (?, ?, ?)",
                (self._now().isoformat(), "device.save_snapshot", self._dump({"name": name, "kind": kind})),
            )
            connection.commit()
        return backup

    def restore_backup(self, request: RestoreRequest) -> dict[str, Any]:
        backup_state = request.backup.state

        def _restore(state: DeviceState) -> DeviceState:
            state.running_config = DeviceConfig.model_validate(backup_state.running_config.model_dump(mode="python"))
            state.startup_config = DeviceConfig.model_validate(backup_state.startup_config.model_dump(mode="python"))
            state.last_saved_at = self._now()
            return state

        return self._mutate("device.restore_backup", _restore, request.model_dump(mode="json"))

    def inject_drift(self) -> dict[str, Any]:
        def _drift(state: DeviceState) -> DeviceState:
            if state.running_config.interfaces:
                state.running_config.interfaces[0].description = "DRIFT: unmanaged synthetic change"
            else:
                state.running_config.banner = "Synthetic training only. Drift injected."
            if state.running_config.local_users:
                state.running_config.local_users = state.running_config.local_users[:-1]
            return state

        return self._mutate("device.inject_drift", _drift, {"mode": "default"})

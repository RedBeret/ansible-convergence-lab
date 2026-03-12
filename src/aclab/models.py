from __future__ import annotations

from datetime import datetime, timezone
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, IPvAnyInterface, IPvAnyNetwork, model_validator


class LocalUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(pattern=r"^[a-z][a-z0-9_]{2,31}$")
    role: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,31}$")
    ssh_key: str = Field(min_length=32, max_length=512)


class InterfaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^(Ethernet|Loopback)\d+$")
    description: str = Field(min_length=3, max_length=128)
    ipv4: IPvAnyInterface
    enabled: bool = True


class SSHAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    listen_port: int = Field(default=22, ge=1, le=65535)
    allowed_subnets: list[IPvAnyNetwork] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        self.allowed_subnets = sorted(self.allowed_subnets, key=str)
        return self


class DeviceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(pattern=r"^[a-z0-9-]+\.lab\.example$")
    banner: str = Field(min_length=8, max_length=256)
    local_users: list[LocalUser] = Field(default_factory=list)
    interfaces: list[InterfaceConfig] = Field(default_factory=list)
    ssh: SSHAccess = Field(default_factory=SSHAccess)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        self.local_users = sorted(self.local_users, key=lambda item: item.username)
        self.interfaces = sorted(self.interfaces, key=lambda item: item.name)
        return self

    @classmethod
    def blank(cls) -> "DeviceConfig":
        return cls(
            hostname="blank.lab.example",
            banner="Synthetic training only. Blank state.",
            local_users=[],
            interfaces=[],
            ssh=SSHAccess(enabled=False, listen_port=22, allowed_subnets=[]),
        )


class DeviceFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mgmt_ip: IPvAnyAddress
    serial: str = Field(pattern=r"^SIM-[A-Z0-9-]+$")
    platform: str = Field(default="cli-device-sim", pattern=r"^[a-z0-9-]+$")
    site: str = Field(pattern=r"^[a-z0-9-]+$")


class DeviceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: DeviceFacts
    running_config: DeviceConfig
    startup_config: DeviceConfig
    created_at: datetime
    updated_at: datetime
    last_saved_at: datetime | None = None
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        self.running_config = DeviceConfig.model_validate(self.running_config.model_dump(mode="python"))
        self.startup_config = DeviceConfig.model_validate(self.startup_config.model_dump(mode="python"))
        return self

    @classmethod
    def blank(cls) -> "DeviceState":
        now = datetime.now(timezone.utc)
        blank = DeviceConfig.blank()
        return cls(
            facts=DeviceFacts(
                mgmt_ip="198.51.100.10",
                serial="SIM-EDGE-0001",
                platform="cli-device-sim",
                site="lab-dc1",
            ),
            running_config=blank,
            startup_config=blank,
            created_at=now,
            updated_at=now,
            last_saved_at=None,
            revision=0,
        )


class BaselineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(pattern=r"^[a-z0-9-]+\.lab\.example$")
    banner: str = Field(min_length=8, max_length=256)


class LocalUsersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_users: list[LocalUser]


class InterfacesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interfaces: list[InterfaceConfig]


class SSHRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ssh: SSHAccess


class BackupRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str
    snapshot_name: str
    captured_at: datetime
    state: DeviceState


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup: BackupRecord


def render_cli_config(config: DeviceConfig, state: DeviceState) -> str:
    lines = [
        f"hostname {config.hostname}",
        f"banner motd ^{config.banner}^",
        f"! synthetic serial {state.facts.serial}",
        f"! synthetic management-ip {state.facts.mgmt_ip}",
        "!",
    ]
    for user in config.local_users:
        lines.append(f"username {user.username} role {user.role} ssh-key {user.ssh_key}")
    if config.local_users:
        lines.append("!")
    for interface in config.interfaces:
        lines.append(f"interface {interface.name}")
        lines.append(f" description {interface.description}")
        lines.append(f" ip address {interface.ipv4}")
        lines.append(" no shutdown" if interface.enabled else " shutdown")
        lines.append("!")
    if config.ssh.enabled:
        lines.append(f"ip ssh port {config.ssh.listen_port}")
        for network in config.ssh.allowed_subnets:
            lines.append(f"ip ssh allow {network}")
    else:
        lines.append("no ip ssh server")
    lines.append("!")
    lines.append("end")
    return "\n".join(lines)


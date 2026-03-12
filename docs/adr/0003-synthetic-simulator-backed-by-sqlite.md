# ADR 0003: Use a synthetic device simulator backed by SQLite

## Status

Accepted

## Context

The lab must be safe, local-only, deterministic, and fast to reset while still teaching backup, drift, idempotency, and rollback.

## Decision

Build a small Python simulator with a SQLite state store and an HTTP API that Ansible can manage through local actions.

## Consequences

- The repo avoids real devices and credentials.
- State transitions are easy to inspect and test.
- The simulator is intentionally simpler than a real network operating system.

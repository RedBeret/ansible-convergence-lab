# ADR 0002: Make Docker Compose the default demo runtime

## Status

Accepted

## Context

The repo needs a one-command demo path from Windows that works locally and finishes quickly.

## Decision

Use Docker Compose as the default runtime for the simulator and the Ansible execution environment, with WSL as an alternate path.

## Consequences

- The demo path is easier to reset and repeat.
- Image builds are required the first time.
- WSL support remains available for users who want a native Linux shell workflow.


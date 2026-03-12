# ADR 0001: Keep Windows as the entrypoint and Linux as the Ansible runtime

## Status

Accepted

## Context

The target audience operates from Windows desktops, but the training should not teach an unsupported or misleading control-node pattern.

## Decision

Use Windows PowerShell as the human entrypoint and run Ansible inside Docker or WSL2 Ubuntu.

## Consequences

- The operator workflow stays Windows-friendly.
- The automation runtime stays aligned with Linux-based Ansible execution.
- Wrapper scripts become part of the teaching material.


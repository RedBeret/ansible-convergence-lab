# Contributing

Thanks for taking an interest in `ansible-convergence-lab`.

This repo is meant to stay practical, safe, and easy to learn from. If you want to contribute, the best changes are the ones that improve clarity, repeatability, and teaching value.

## Ground rules

- Keep the repo local-only and synthetic-only
- Do not add real credentials, real hostnames, customer data, or proprietary images
- Keep Windows PowerShell as the primary user entrypoint
- Keep Linux-only tooling inside Docker or WSL
- Prefer small, reviewable pull requests

## Local development

Primary demo path:

```powershell
pwsh ./scripts/demo.ps1 -Runtime docker -Build
```

Test path:

```powershell
pwsh ./scripts/test.ps1 -Runtime docker
```

Cleanup:

```powershell
pwsh ./scripts/down.ps1
```

## Project expectations

When you touch automation or simulator behavior, keep these qualities intact:

- explicit validation
- structured logging
- retries with backoff
- timeouts
- idempotent operations
- health checks
- rollback notes for any mutating workflow

## Docs expectations

If you change behavior, update the docs that teach it:

- `README.md`
- `docs/runbook.md`
- `docs/study-guide.md`
- `docs/failure-modes.md`

If the change affects architecture or a key tradeoff, add or update an ADR in `docs/adr/`.

## Style notes

- Use ASCII unless the file already requires something else
- Keep language clear and direct
- Avoid em dashes
- Prefer synthetic examples using `.lab.example`, RFC5737 IP ranges, fake serials, and fake users

## Pull request checklist

Before opening a PR, make sure you have:

- explained the why, not just the what
- updated docs for any behavior change
- kept the demo path working
- preserved idempotency where expected
- preserved the safety guardrails


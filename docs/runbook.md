# Runbook

## Default demo path

From Windows PowerShell:

```powershell
pwsh ./scripts/demo.ps1 -Runtime docker -Build
```

This starts the simulator, runs the convergence loop, proves idempotency, injects drift, detects it, and rolls back.

## Deploy

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task deploy -Runtime docker
```

Expected result:

- Desired hostname, users, interfaces, and SSH policy are applied.
- Startup-config is saved.
- Rendered artifacts are updated in `rendered/`.

Rollback notes:

- If deploy completes but the state is wrong, run rollback.
- If deploy fails mid-way, run verify first to understand actual state, then rollback to the last-known-good file.

## Verify

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task verify -Runtime docker
```

Expected result:

- Assertions pass for hostname, users, interface descriptions, and saved startup-config.
- `backups/last-known-good/` and `backups/last-known-good/edge-r1.lab.example.json` are refreshed.

Rollback notes:

- Verify does not mutate the device config.
- It does update the last-known-good artifact, so only run it after you trust the deployed state.

## Inject drift

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task inject-drift -Runtime docker
```

Expected result:

- The running config changes in a synthetic way.
- Startup-config remains at the last saved value.

Rollback notes:

- Run `drift-check` to confirm drift, then `rollback` to restore the last-known-good state.

## Drift check

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task drift-check -Runtime docker
```

Expected result:

- Exit code is non-zero when drift exists.
- A drift report is written to `reports/drift-edge-r1.lab.example.json`.

Rollback notes:

- Drift check does not mutate device state.
- Use the report to confirm the delta before rollback.

## Rollback

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task rollback -Runtime docker
pwsh ./scripts/invoke-lab.ps1 -Task verify -Runtime docker
```

Expected result:

- The simulator restores the last-known-good JSON backup.
- Verify passes again.

Rollback notes:

- Rollback is itself idempotent when the running state already matches the last-known-good file.
- If rollback fails because no last-known-good file exists, run a clean deploy and verify first.

## Reset

Command:

```powershell
pwsh ./scripts/invoke-lab.ps1 -Task reset -Runtime docker
```

Expected result:

- The synthetic device returns to blank state.

Rollback notes:

- Reset is destructive to synthetic running state.
- Recover by re-running deploy or the full demo. If a last-known-good file exists, rollback can also restore from it after the reset.


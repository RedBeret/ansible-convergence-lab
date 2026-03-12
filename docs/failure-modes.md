# Failure Modes

## Simulator never becomes healthy

Symptoms:

- `docker compose up -d simulator` succeeds but the demo waits and then fails.

Likely causes:

- Docker image build failed.
- Port `18080` is already in use.
- The SQLite state path is not writable inside the container.

Recovery:

- Re-run with `-Build` to force image rebuild.
- Check `docker compose logs simulator`.
- Remove conflicting containers and retry.

## Deploy is not idempotent on the second run

Symptoms:

- `20_deploy.yml` reports `changed > 0` on the second deploy.

Likely causes:

- A rendered artifact includes unstable data.
- A simulator endpoint always reports change.
- The startup-config save path is mutating when it should not.

Recovery:

- Inspect `reports/20_deploy-latest.json`.
- Compare `rendered/edge-r1.lab.example.cfg` across runs.
- Review the simulator change detection logic in `src/aclab/store.py`.

## Drift check passes when it should fail

Symptoms:

- You inject drift, but `drift-check` exits successfully.

Likely causes:

- The drift mutation touched a field not compared by `40_drift_check.yml`.
- The expected state and actual state were normalized differently.

Recovery:

- Compare `reports/drift-edge-r1.lab.example.json`.
- Confirm drift changed running config and not startup-config only.

## Rollback fails

Symptoms:

- `50_rollback.yml` fails with a missing file or restore error.

Likely causes:

- `verify` never ran after the last successful deploy.
- The last-known-good JSON file is malformed.

Recovery:

- Run `verify` after a known-good deploy to recreate the file.
- Inspect `backups/last-known-good/edge-r1.lab.example.json`.
- If needed, reset and redeploy.

## WSL path fails

Symptoms:

- `-Runtime wsl` errors before `make` starts.

Likely causes:

- The `Ubuntu` distro is not installed or not named `Ubuntu`.
- WSL access is disabled on the host.

Recovery:

- Use the Docker runtime first.
- Update the wrapper if your distro name differs.


# Publishing Checklist

Use this before making the repository public.

## Repo settings

- Confirm the repository name is `ansible-convergence-lab`
- Confirm the repository lives under the intended GitHub account or org
- Update any `RedBeret` URLs if the final owner path differs
- Enable Actions if you want CI to run
- Enable private vulnerability reporting if available

## Legal and policy

- Choose a license intentionally
- Add a `LICENSE` file once you decide the terms
- Review `SECURITY.md` and confirm the reporting path matches how you want to handle reports

## README and discoverability

- Add GitHub topics such as `ansible`, `powershell`, `windows`, `docker`, `python`, `training-lab`
- Pin the most important docs in the repo sidebar or About section if desired
- Confirm the README renders Mermaid diagrams correctly

## Smoke test before publish

- Start Docker Desktop
- Run `pwsh ./scripts/demo.ps1 -Runtime docker -Build`
- Run `pwsh ./scripts/test.ps1 -Runtime docker`
- Run `pwsh ./scripts/down.ps1`

## Safety review

- Confirm no real hostnames, credentials, or private data were added
- Confirm only RFC5737 example IPs are present
- Confirm generated artifacts are still ignored where appropriate


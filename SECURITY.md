# Security Policy

## Scope

This repo is a local-only synthetic training lab. It should never contain:

- real credentials
- real customer data
- proprietary images
- real device hostnames or production IPs

## Reporting

If you find a security issue in the code or workflow:

- do not post real secrets in a public issue
- do not attach any sensitive local environment data
- use GitHub private reporting if it is enabled for the repository

If private reporting is not available, open a minimal public issue that describes the problem without exposing sensitive details.

## Safe reporting examples

Good:

- "The repo may log a token value if a user adds one by mistake"
- "The simulator accepts unsafe input that should be rejected"

Not good:

- posting an actual token
- posting host-specific local machine details that are not needed
- posting customer or employer data

## Repository safety rules

Please preserve these constraints in all contributions:

- synthetic-only identifiers
- RFC5737 example IP space
- fake usernames and fake SSH keys
- local-only runtime assumptions


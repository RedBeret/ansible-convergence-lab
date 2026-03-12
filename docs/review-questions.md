# Review Questions

1. Why does this repo keep PowerShell as the entrypoint but run Ansible in Linux?
2. What is the difference between a timestamped backup and the last-known-good backup?
3. Why is `verify` responsible for refreshing the rollback anchor?
4. What makes the second deploy idempotent in this lab?
5. Which repo files define desired state versus execution flow?
6. How does the lab prove drift detection without using real devices?
7. Why are the IP addresses limited to RFC5737 example ranges?
8. Where are retries, timeouts, and health checks implemented?
9. What would break if the simulator always returned `changed: true`?
10. Why is rollback safer after verification than immediately after backup?


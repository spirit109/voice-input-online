# Security Policy

## Secrets

Real Azure credentials must stay in `.env` or in your local environment
variables. The repository tracks `.env.example` only.

If you accidentally expose an Azure Speech key:

1. Rotate or regenerate the key in Azure immediately.
2. Remove the exposed value from any public issue, log, screenshot, or commit.
3. Assume the old key is compromised once it has been published.

## Reporting

Please open a GitHub issue for security-sensitive bugs that do not include
private credentials or personal information. If a report needs real secrets to
reproduce, replace them with placeholders before posting.

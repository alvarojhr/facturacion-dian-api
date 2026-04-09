# Security Policy

## Reporting a vulnerability

Do not open public issues for credential leaks, certificate handling flaws, signing bypasses, or DIAN submission vulnerabilities.

Report security-sensitive issues privately through a GitHub security advisory when available. If that is not possible, contact the repository owner privately before disclosure.

## Scope

Security issues include:

- certificate or key handling flaws
- signing bypasses or signature corruption
- credential leakage
- SSRF or unsafe outbound behavior against DIAN endpoints
- sensitive artifact exposure through API responses or logs

## Disclosure expectations

- Give maintainers time to reproduce and patch the issue
- Avoid publishing proof-of-concept exploits before a fix is available
- Include affected versions, conditions, and a minimal reproduction

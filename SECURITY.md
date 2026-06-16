# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security bugs.

Email: trivikramnarayanan@gmail.com

Include:
- A description of the issue
- Steps to reproduce
- Affected versions
- Any suggested fix if you have one

You'll get a response within 72 hours. If the issue is confirmed, a fix will be released as quickly as possible.

## Scope

Things we care about:

- Remote code execution
- SQL / NoSQL injection
- Authentication bypass (when `REQUIRE_AUTH=true`)
- Path traversal
- Sensitive data exposure

## Out of scope

- Issues that require physical access to the machine
- Denial of service via resource exhaustion
- Rate limit bypasses on self-hosted instances you control

## Default security posture

UMLGen runs without auth by default (`REQUIRE_AUTH=false`), designed for local / single-user use. If you expose it over a network, either set `REQUIRE_AUTH=true` or put it behind a reverse proxy with access controls.

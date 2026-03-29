# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in nCode, please report it responsibly by using GitHub's [private vulnerability reporting](https://github.com/opsingh861/nCode/security/advisories/new) feature.

Alternatively, you can email the maintainer directly. Include as much detail as possible:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue
- Any proof-of-concept code or workflow JSON (if applicable)

### What to expect

- **Acknowledgement** within 48 hours
- **Initial assessment** within 5 business days
- **Fix or mitigation plan** communicated before any public disclosure
- Credit in the release notes once the vulnerability is patched (if desired)

## Scope

### In scope

- Remote code execution in the transpiler pipeline
- Server-Side Request Forgery (SSRF) via generated workflow code
- Credential/secret leakage in generated Python or ZIP artifacts
- Path traversal via uploaded workflow JSON
- Injection vulnerabilities in the FastAPI backend

### Out of scope

- Vulnerabilities in third-party dependencies (report upstream; also tracked by Dependabot)
- Issues requiring physical access to the server
- Social engineering

## Security Design Notes

nCode is a **code generation tool**. The security model is:

1. **Credentials are never embedded** in generated code — all sensitive values are emitted as `os.getenv("CREDENTIAL_NAME")` and scaffolded in `.env.example`.
2. **Uploaded workflow JSON is parsed as data**, not executed. Pydantic validation rejects malformed input.
3. **Generated Python is not executed server-side** — the ZIP is returned to the user for local execution.
4. **Download IDs are UUID4** (256-bit entropy) and are served as deterministic file references with no directory traversal.

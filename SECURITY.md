# Security Policy

## Project profile

`pbi-docs` is a local command-line tool and read-only [MCP](https://modelcontextprotocol.io) server
that extracts and documents Power BI data models (`.pbit`, `.pbip`/TMDL). This shapes what kind of
report is relevant here:

- **Zero runtime dependencies** (`dependencies = []` in `pyproject.toml`) — there is no third-party
  supply chain to compromise at runtime. Development-only dependencies (`pytest`, `jsonschema`) are
  never installed for end users of the published package.
- **No network calls, no telemetry.** The CLI and MCP server only read local files you point them
  at and write local output files. The MCP server communicates over stdio, not a network socket, and
  is not exposed to the network by default.
- **Read-only.** `pbi-docs` never modifies your `.pbit`/`.pbip` source files — it only reads them and
  writes new files under an output directory you choose.

Given this, the most relevant report categories are things like: a malformed/malicious `.pbit`
(ZIP) or `.pbip`/TMDL file causing path traversal, zip-slip, unbounded resource consumption, or
similar during extraction/parsing — not "vulnerable dependency" reports, since there isn't one in
runtime.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

This is the first published release (PyPI, 2026-07-28), so there is no older line to maintain yet.
Security fixes are released as a new patch/minor version — there is no long-term-support branch.
Supported Python versions follow `pyproject.toml`'s classifiers (currently 3.10–3.13).

## Reporting a Vulnerability

**Preferred: GitHub Private Vulnerability Reporting.** Use the **"Report a vulnerability"** button
under the [Security tab](https://github.com/Osc2405/pbi-docs/security) of this repository
(Security → Advisories → "Report a vulnerability"). This opens a private draft advisory visible
only to you and the maintainer — please do **not** open a public GitHub issue for a suspected
security vulnerability.

**Alternative:** if you don't have a GitHub account or the option above isn't available, email
**orosero2405@gmail.com** with the same details.

When reporting, please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce it (ideally a minimal `.pbit`/`.pbip` sample or script that triggers it).
- The `pbi-docs` version (`pbi-docs --help` shows the version, or check `pip show pbi-docs`) and
  Python version you're running.

### What to expect

`pbi-docs` is maintained by a single person, so there's no formal SLA — but every report gets a
response. Expect an acknowledgment within a few days. If the report is confirmed, a fix will be
prioritized and released as a new version, with credit to the reporter (unless you prefer to stay
anonymous) once the fix ships, following [GitHub's coordinated disclosure
process](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability).

## Scope

In scope: the `pbi_extractor` package as published on PyPI — the `.pbit`/`.pbip` extractors, TMDL
parser, resolver, MCP server, and CLI.

Out of scope: the `scripts/`, `githooks/`, and `Pruebas/` directories, which are development-only
tooling not shipped in the published package (see `CLAUDE.md` for what's excluded from the
distributed package and why).

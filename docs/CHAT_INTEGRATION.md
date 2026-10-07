# Chat-first Website Production Engine

The Engine is the primary production authority. The Studio is an optional view and interactive approval surface. Chat intake, decisions, visual review, revisions, final review and resume can be performed through Codex without filling Studio forms.

## In this workspace

`AGENTS.md` directs Codex to `skills/website-production/SKILL.md` when asked to use the Website Production Engine. Say: **Use website-production to create a website project from this brief…** or **Resume website-production project PROJECT_ID.** Codex performs supported operations using connected tools or the independent CLI; the user need not run commands.

The workflow preserves three human gates. Codex presents actual prototype captures/artifacts before visual approval, then uses the same immutable lock and Engine production/independent QA/repair pipeline. Final approval requires an actual release candidate and explicit approval. Natural-language corrections remain surgical patches rather than redesign authorization.

## MCP interface implemented

`engine/mcp.py` uses the official Python MCP SDK and serves local stdio. Install the `chat` optional dependencies. Entry point: `website-engine-mcp`; equivalent module invocation: `python -m engine.mcp --data-dir /absolute/project/data --asset-root /authorized/input/root`.

Fourteen actual tools:

- `website_projects`, `website_create`, `website_status`
- `website_run`, `website_job`
- `website_review`, `website_approve_final`
- `website_ingest_asset`, `website_assign_asset`, `website_regenerate`
- `website_resolve`, `website_recover`
- `website_artifacts`, `website_read_artifact`

The `website_production` MCP prompt explains the same execution contract. Tool schemas are typed; operations delegate to Engine rather than mutating production state independently. Background operations return persistent job IDs. Tool errors preserve failures rather than converting them into completion.

## Codex client configuration

For a client with this repository available, configure its MCP server named `website-production` to run the Python environment that has this package and its `chat` extra installed. Example configuration (absolute paths must reflect the actual installation):

```toml
[mcp_servers.website-production]
command = "/absolute/python"
args = ["-m", "engine.mcp", "--data-dir", "/absolute/data", "--asset-root", "/authorized/assets"]

[mcp_servers.website-production.env]
PYTHONPATH = "/absolute/source"
```

The skill folder is distributable to clients' supported skill installation directories. This repository's AGENTS instructions work without MCP registration. A selectable `@` app/connector entry is an account/client registration surface, not created by writing a skill or starting a local process. The current managed session exposes no API to register a new connector or alter its read-only client configuration, so no selectable `@WebsiteProduction` entry is claimed installed. The stdio server is real and protocol-tested, not a placeholder for that registration.

## Shared state and security

Configure MCP and Studio to the SAME physical data directory to share projects, exact assets, approvals, locks, jobs and release evidence. A local directory and a separately hosted Replit directory are different stores even if their names match. This integration currently operates locally; it does not silently synchronize or duplicate hosted projects. A remote connector for the hosted passcode-authenticated application requires a supported authenticated transport and deployment/configuration in that host. Do not pretend it is already connected.

Stdio inherits local client trust and is not a publicly exposed HTTP endpoint. Uploads are bounded to configured authorized roots and exclude hidden credential files/symlinks to those files. Artifact reads reject traversal, hidden/server files and oversized text. Reference evidence remains untrusted data. The server has no tool for live deployment, purchase, live-store deletion or automatic approval.

Normal stdio shutdown waits for its own jobs. Do not automatically interrupt jobs belonging to a separately running Studio worker. Recovery verifies project hashes/checkpoints; worker recovery needs verified process ownership if a process was abruptly terminated.

## Verification

`tests/test_chat.py` checks authority delegation, shared persistence/recovery, human gates, production preconditions, exact assets, input-root/symlink exclusions and artifact traversal. `tests/mcp_smoke.py` runs an actual MCP subprocess/client handshake, invokes typed tools, drives an explicitly fictional project through real discovery/browser QA/production/release, refuses unapproved operations and restarts a new MCP process to verify persistent approval/locks. No customer project receives automated approvals.

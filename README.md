# Website Production Studio + Engine

A runnable, persistent local production workspace. The Studio is a FastAPI application with a responsive browser interface. The Engine is an independently invocable Python package. SQLite owns project state, jobs and events; versioned project folders hold original assets, evidence, design locks, builds, QA and release packages.

## Run

```bash
python -m pip install -e .
npm ci --prefix tools/shopify --cache /tmp/studio-npm-cache
# Use installed Chromium, or: python -m playwright install chromium
python run.py --port 8000
```

Open **http://127.0.0.1:8000**. Python 3.12+ and Node 20+ are required. System Chromium is discovered automatically; set `STUDIO_CHROMIUM` for another executable. The bundled Shopify skill validator uses the pinned npm dependency lockfile and its offline documentation/schema fallback.

The workspace is single-user and loopback-only by default. Configure `STUDIO_TOKEN` before exposing it to a network, use HTTPS, and run one application worker. Never put credentials in a brief. See [security](docs/SECURITY.md).

## Create a website

Choose **New website**, supply the brand, website type (or let the Engine infer it), platform, natural-language instructions, reference roles, exact assets, requirements and approved copy. Discovery begins after intake. Review the coherent desktop/mobile direction, use **Keep / Revise / Reject**, and approve it when ready. Approval creates an immutable versioned Design Lock and starts production. Final review becomes available only after all required independent QA gates pass. Final approval readies the package; live publishing is a separate explicitly authorized operation.

Custom Web currently produces semantic, responsive, source-controlled HTML/CSS/JS sites with a working bundled enquiry service when contact is required. Shopify produces native Liquid sections, JSON templates, snippets, locale/config files and native commerce bindings. These are real adapters, with their limitations exposed before approval. Webflow, complex web-app business logic and arbitrary integrations remain unavailable and create explicit blockers rather than mislabeled output.

## Fictional fixtures

```bash
python -m engine.cli seed --all-stages
```

This command creates two **explicitly fictional** projects and automates approval only for those fixtures. Customer projects are never automatically approved. Fieldwork exercises Custom Web, scoped revision, independent QA and release. Still Objects exercises native Shopify and honestly blocked live-store QA. Fixtures live separately in `data/fixtures/projects/`; customer projects live in `data/projects/`.

## Independent Engine

```bash
python -m engine.cli create fixtures/custom-web-brief.json
python -m engine.cli list
python -m engine.cli discover PROJECT_ID
python -m engine.cli review PROJECT_ID --action KEEP --version 1
python -m engine.cli produce PROJECT_ID
python -m engine.cli recover PROJECT_ID
python -m engine.cli resume PROJECT_ID
python -m engine.cli approve-final PROJECT_ID BUILD_ID
```

Use `--data-dir PATH` before the subcommand for isolated workspaces. `recover` verifies locks, source hashes and artifacts. `resume` invokes the next valid operation; it never discards approvals or restarts an approved project from intake. `/docs` exposes the authenticated API schema when the server runs.

## Verify

```bash
python -m unittest tests.test_engine -v
python -m tests.smoke
python tools/build_distribution.py
```

The real browser smoke test runs an isolated authenticated Studio, creates a project through the UI, revises and approves it, executes browser QA at six viewport sizes, injects unauthorized production content, verifies final approval is blocked, observes repair and retest, and restarts the application to verify persistence/recovery. It writes reports and screenshots to `test-results/`. Unit tests use explicitly labeled test stubs for slow integrations; they are never application results.

## Project memory and output

- Database: `data/studio.sqlite3` (project revisions, durable jobs, append-only events).
- Project authority: `data/projects/PROJECT_ID/project.json`, `brand/constitution.json`, `approvals/design-lock-vN.json` and `approvals/ledger.json`.
- Reference evidence: `evidence/`, `references/SITE_REFERENCE.json`, `references/SITE_REFERENCE.md`.
- Approved prototype and controlled captures: `design/vN/`.
- Native output: `production/build-N/site/`; Shopify handoff is beside `site/`.
- Independent QA: `qa/BUILD_ID/run-N/report.json`, screenshots and image diffs.
- Tested ZIP: `release/build-N-candidate.zip` or clearly labeled `build-N-diagnostic.zip`; diagnostic packages have not passed release gates.

Set `STUDIO_DATA_DIR` to relocate the entire persistent workspace. Back up the SQLite database with SQLite's backup API and copy project folders together; do not copy a live WAL database as a single file.

## Capability boundaries

The internal design/strategy implementation is a deterministic, bounded design system, not an unconfigured generative AI service. It supports scoped changes to image scale/position, heading scale, spacing and unlocked palette/font tokens. Other feedback is persisted as structured tasks and pending decisions, with no fabricated implementation. Arbitrary functional requirements become blockers when the selected adapter cannot provide them.

Reference crawling is bounded (up to five existing-site pages, 30 inventoried routes). It stores source HTML, semantic inventories and controlled screenshots/computed measurements when access permits. Static evidence does not establish untested motion. Public fetches validate every redirect and block private destinations. A configured trusted egress proxy is optional; its security contract is documented separately.

Research retrieves actual standards/platform sources and retains unavailable states honestly. Category research uses bounded public RSS search and up to two retrieved source candidates, alongside observed supplied references; candidates are not asserted to be direct competitors or market leaders. Original mode uses supplied authority, assets, audience, goal and platform-aware architecture; it does not invent market findings.

Automated accessibility audits use axe-core plus keyboard/name/label checks. They are release gates for the implemented scope, not a claim of exhaustive human accessibility certification. Performance checks use explicit byte budgets and controlled local navigation measurements, not fabricated field Core Web Vitals. Exact oversized assets cause a blocker rather than silent alteration.

Shopify local syntax/schema/package validation can run without store access. Live products, checkout, customer accounts, editor behavior, app compatibility and installation require an authenticated development store. No live Shopify store was modified. Claude is advisory and optional (`ANTHROPIC_API_KEY`); unavailable integrations never fabricate output.

See [architecture and protocols](docs/PROTOCOLS.md), [security](docs/SECURITY.md), [recovery and release](docs/OPERATIONS.md), [94-section self-audit](docs/SELF_AUDIT.md) and [completion evidence](docs/COMPLETION.md).

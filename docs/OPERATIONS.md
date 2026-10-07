# Recovery, deployment and release

## Local operation

Run `python run.py --port 8000`. Configure one worker; multi-process job ownership is intentionally unsupported. SQLite is the source of truth. JSON artifacts make project authority and evidence reviewable; chat history is never used to reconstruct state. Restart marks active jobs INTERRUPTED and verifies checkpoints. Use the Studio recovery control or `python -m engine.cli resume PROJECT_ID` to continue the next verified operation. Human approval gates remain pending across a restart.

Corrupt/missing original assets, approved prototype files or immutable approval artifacts cause blocked recovery. Restore the exact artifact from a known-good backup. If a built file changes after independent QA, the release candidate is invalidated and must be independently retested. Recovery never silently regenerates an approved authority document.

Retry policy: two fidelity-preserving repair operations with three independent QA runs per production cycle. First restore the approved adapter output; next reinitialize native output while retaining failed artifact evidence. Persistent failures create a blocking decision. A verified code revision permits a new independent retest; the same implementation cannot loop indefinitely. New user feedback creates a scoped version, never overwrites old locks. Superseded builds, QA evidence and release history remain available for rollback.

## Custom Web deployment preparation

Required environment: static HTTPS hosting; Python 3.12 service/reverse proxy when a contact page is present. Generated `DEPLOYMENT.md`, `serve.py` and route manifest are inside the candidate. Contact messages require a writable **private directory outside the public document root** (`CONTACT_DATA_DIR`). The server is loopback-bound by default. Email forwarding is not configured. Supply domain/canonical/sitemap configuration at deployment; no domain is invented. Hosting, TLS, retention and monitoring remain deployment responsibilities. Validate the actual destination with page requests, asset/link checks, form success/error/private-storage checks and captured visual comparisons. Retain the previous versioned directory/package, then switch a reversible alias or deployment pointer after release authorization. Rollback switches that pointer to the previous validated version.

## Shopify deployment preparation

The native theme is `production/build-N/site/` with layout/templates/sections/snippets/assets/config/locales. The sibling `shopify-handoff.json` maps exact original asset uploads/bindings, data ownership, audit scope and safe deployment steps. The archive contains only native theme files. Local validator output and ZIP/manifest checks are retained.

Next external action: authenticate Shopify CLI against an authorized **development store**; upload required original files and bind images; run theme-check; push to an **unpublished** theme; preview and test product/variant/selling-plan/cart/checkout/contact/search/account/localization behavior and editor settings against real data. For an existing store, audit products, collections, menus, apps, metafields, tracking, scripts, templates, subscriptions, reviews and URL requirements before merging. Do not replace the live theme. Local static PASS never becomes installation PASS. Once remote evidence is available, extend the adapter's independent platform/browser QA contract; never manually overwrite `project.qa` or database status to bypass the release gate.

Production publication remains a separate explicit action after final approval and rollback preparation. The V1 system prepares artifacts; it has no live-publish credential adapter. Retain the current published theme ID and backup before promotion. Rollback re-publishes the prior validated theme, where permitted.

## Optional Claude

Set `ANTHROPIC_API_KEY` and, optionally, `CLAUDE_MODEL` in the process environment. Configuration changes are applied on the next real consultation. States distinguish configuration from verified health. Two bounded attempts precede internal fallback. Feedback is stored as advisory evidence; it never changes locked authority. No key is shipped in a project export.

## Extensions

Production adapters implement the abstract build/validation/deployment-preparation contract and describe capabilities, constraints, content ownership, routing, assets, styling, interactions and failure behavior. Add an adapter to the registry without changing Studio approval authority. A monitoring adapter can consume release IDs/URLs/baseline hashes and append events/defects; it must not rewrite approvals. Schema changes require explicit migrations; V1 rejects unknown project schema versions instead of destructively resetting them.

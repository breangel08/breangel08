# Completion evidence

The locally testable Website Production Studio + Engine V1 is implemented and running. This is functioning software, not a dashboard mockup or an SOP-only deliverable. The controlling requirements were evaluated section by section in [SELF_AUDIT.md](SELF_AUDIT.md), with bounded intelligence and unavailable external operations identified explicitly.

## Architecture

- Python 3.12, FastAPI and Uvicorn serve the Studio and typed Engine API.
- SQLite owns persistent projects, optimistic revisions, durable jobs and role-tagged activity; project folders contain exact assets, evidence, versioned authority, builds, QA and release packages.
- `engine/service.py` owns orchestration, checkpoints, approvals, locks, repair/retry, recovery and release gates; Studio components have no production authority.
- `engine/models.py`, `authority.py`, `design.py`, `evidence.py`, `assets.py`, `qa.py`, `store.py` and `adapters/` separate validation/interpretation/intelligence/persistence/production boundaries.
- Native Shopify and Custom Web adapters produce real target-specific artifacts. Claude is an optional advisory adapter. Webflow and unsupported business logic stay explicitly blocked.
- `studio/static/` implements a responsive interactive application; `engine/cli.py` invokes the same Engine independently.

## Studio and Engine capabilities

Persistent projects; all specified business website types plus AUTO; separate platform and inferred scope; concise natural-language brief; multiple references and roles; drag/drop exact asset ingestion/inventory; classified Brand Constitution; supplied/approved content permissions; public-source/reference and existing-site inventories/captures; bounded standards/category research; sitemap/platform-aware strategy; coherent clickable visual directions; desktop/tablet/mobile review; Keep/Revise/Reject; persistent natural feedback/tasks; surgical supported patches; immutable hash-locked approved versions; automatic native production; eight independent QA gates; typed defects; real bounded repair/retest; batched pending decisions; checkpoint/restart recovery; gated release candidates; final approval; tested native packages and rollback/deployment preparation.

Unsupported absolutes are conservatively surfaced as decisions, not silently asserted implemented. The internal designer is a deterministic bounded design system, not a falsely configured generative AI agent. Exact original bytes remain exact. No reference copy/identity/photography is transferred into production. No invented business facts are inserted.

## Verification executed

| Verification | Result |
|---|---|
| Engine/workflow/API/security automated tests | **26 passed**, zero failures/errors/skips |
| Real browser + HTTP end-to-end smoke | **32 assertions passed** |
| Custom Web independent QA | All **8 gates PASS**, across six viewport classes |
| Studio automated accessibility | PASS; no recorded WCAG-tagged axe violations |
| Actual injected unauthorized content/visual tampering | Final approval denied; defects created; faithful repair/retest PASS |
| Persistence and real application restart | PASS; approvals/locks survive, interrupted job identified, next action verified |
| Live public reference access | example.com source OBSERVED and desktop/mobile browser captures CAPTURED |
| Live standards/platform retrieval | W3C, web.dev and Shopify source documents FETCHED and retained |
| Category research | Real bounded public RSS search/source candidates retained; relevance is classified and candidates are not asserted to be competitors/leaders |
| Official Shopify local skill validator | **32 native files passed** syntax/schema/contract checks |
| Python compile / JavaScript syntax | PASS |
| Python wheel build | PASS |
| Source/package archive | CRC and per-entry SHA-256 manifest match PASS |

Evidence: `test-results/unit-test-report.json`, `unit-test-output.log`, `smoke-report.json`, `studio-accessibility.json`, `verification-report.json`, fixture project QA/reference/research artifacts, and `shopify-validation-output.txt`. Screenshots include projects at desktop/mobile and final review. Earlier failures were repaired and retested; stale failed-attempt reports are not completion evidence.

## Shopify capabilities and exact external blocker

Real layout, JSON templates, editable Liquid sections, product-card snippet, assets, settings/config and locale files. Native bindings cover products/titles/prices/availability/media/variants/quantity/selling plans/collections/menus/cart state/updates/checkout handoff/search/contact/blog/article/account/localization. Packages are CRC/hash-tested and match their manifests. Exact asset upload/binding maps and preservation inventories are provided beside the theme.

**Authenticated development-store access is not configured.** Therefore native browser rendering, live products/cart/checkout/customer behavior, editor/app compatibility and actual installation remain BLOCKED. The Shopify fixture has a preserved diagnostic theme package and no release candidate; it cannot be incorrectly approved as live production-ready. Next step: authenticate Shopify CLI against an authorized development store, upload/bind original files, push to an unpublished theme, execute independent native QA and integrate its recorded evidence. No live store, customer data or published theme was modified.

## Run and use

The development instance is at **http://127.0.0.1:8000**. Restart with `python run.py --port 8000`. Install dependencies with `python -m pip install -e .` and `npm ci --prefix tools/shopify`; Chromium is required for rendered QA. On this managed environment the trusted egress proxy mode is configured for public-source research; default direct/pinned access remains safer elsewhere. See SECURITY.md for the proxy contract.

Choose **New website**, submit the brand brief/assets/copy, review the coherent direction, then Keep/Revise/Reject. Keep locks authority and starts production. Final approval is available only for QA-passing candidates and does not publish a live website.

Independent CLI: `python -m engine.cli --help`. Create with `create fixtures/custom-web-brief.json`; use `discover`, `review`, `produce`, `recover`, `resume`, `repair` and `approve-final` as applicable. Automated fixture approval is explicit and limited to fictional fixture data.

## State, resume and output locations

Database: `data/studio.sqlite3`. Customer memory: `data/projects/PROJECT_ID/`. Fictional fixtures: `data/fixtures/projects/PROJECT_ID/`. Each includes brief/constitution, asset inventory, source/reference/research evidence, design versions/captures, immutable `approvals/design-lock-vN.json`, ledger, versioned native output, QA/defects/repair evidence and release manifests.

Resume: `python -m engine.cli recover PROJECT_ID` verifies source hashes/lock artifact/prototype/build integrity; `resume PROJECT_ID` continues the next valid operation. Restart identifies interrupted durable jobs and resumes valid in-flight stages while preserving human gates. Recovery never reconstructs authority from chat memory.

Shopify output: `data/fixtures/projects/SHOPIFY_PROJECT_ID/production/build-1/site/` for the supplied demo; customer paths use `data/projects/`. Handoff: sibling `shopify-handoff.json`. Archive: project `release/build-1-diagnostic.zip` until native remote QA passes. Custom Web output includes the actual semantic site, `serve.py` enquiry service when applicable, route manifest and deployment instructions.

Source distribution: `dist/website-production-studio-1.0.0.zip`; integrity report: `dist/distribution-report.json`. It includes software, docs, fixtures, tests, validator helper and dependency lockfiles, plus concise verification evidence; it excludes customer/project databases, uploads, environment secrets and node_modules.

## Known limits and remaining external operations

- V1 is a local single-user workspace with one application worker, not a multi-tenant hosted SaaS. Network exposure requires a configured token, HTTPS and controlled egress.
- The bounded designer is reusable and brand-driven, but not an unconstrained art director. Unsupported complex functional or aesthetic transformations create explicit decisions; they are not completed by fake AI text.
- Public crawling is bounded and cannot inspect private integrations or reliably establish untested interaction/motion. Search sources carry relevance/confidence, not invented market conclusions.
- Automated accessibility and local performance QA are scoped measurements, not exhaustive manual certification or field Core Web Vitals.
- Domain/canonical/sitemap destination configuration, TLS, hosting, private contact-data retention and live deployment validation remain environment-specific release steps. Contact server persists actual messages privately; email/CRM forwarding is not configured. Review sandbox intentionally disables delivery.
- Claude remains NOT_CONFIGURED without `ANTHROPIC_API_KEY`; core operation continues. No consultation was fabricated.
- Webflow, live deployment/publishing and arbitrary business integrations require compatible credentialed adapters. Existing-site public audit does not authorize removal of business-critical integrations.
- No irreversible publication, domain change, purchase or production deletion was performed. Finished artifacts and rollback preparation are concrete and reviewable before any later external authorization.


## Chat integration addition

The independently invocable Engine now also has an official-SDK MCP stdio server, fourteen typed tools, a chat production prompt, Codex workspace instructions and a distributable website-production skill. Studio use is optional. The added chat bridge delegates to the same Engine and persistence; approval and release gates remain enforced. Five added bridge tests bring automated tests to **31 PASS**; a separate actual MCP protocol smoke reports **14 PASS** checks including real browser QA/production and process-restart recovery. See [CHAT_INTEGRATION.md](CHAT_INTEGRATION.md).

Client/account MCP registration and a remote authenticated connection to the separate Replit data store are not represented as completed. The local chat integration is functioning; a selectable account @ entry cannot be created from the managed client configuration available in this session.

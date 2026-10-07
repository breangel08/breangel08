# Engine authority and implemented protocols

This file documents the implemented V1 contracts. It does not replace code. Authoritative runtime behavior is in `engine/service.py`, validated intake in `engine/models.py`, design decisions in `engine/design.py`, artifact-reading QA in `engine/qa.py`, and target-specific implementation in `engine/adapters/`.

## Engine Constitution / Master SOP / Autonomy Doctrine

Project authority: current explicit user instruction, project requirements, Brand Constitution, approved Design Lock and approval ledger, platform safety, master workflow, supported evidence, then worker preferences. Level 5 is the default. Continue safe independent work; never fabricate unavailable evidence, connectivity, claims, QA or deployment. A bounded workflow creates a coherent direction, asks Gate 2 once, implements locked authority, independently checks/repairs it and presents Gate 3 only after required PASS. Only consequential external actions require separate final authorization.

## Intake / Classification / Brand Constitution

`Brief` validates website type separately from production target. AUTO infers the business type from instructions/goals/functionality; commerce defaults to Shopify, other informational sites to Custom Web. Scope distinguishes new, extension and redesign. Original user choices win. Submitted brief is Gate 1 authority. Palette/fonts become locked requirements; assets with `exact=true` become hash-locked rules. Requirements retain REQUIRED/LOCKED/ALLOWED/PREFERRED/AVOID/FORBIDDEN classification and participate in strategy evidence. Rules that need unsupported functionality create a production blocker rather than silently changing scope. Arbitrary aesthetic prose beyond the bounded renderer needs scoped feedback or an adapter extension; V1 does not claim an unconstrained AI art director.

## Content Permission / Asset Intelligence

SUPPLIED and APPROVED content fields may render; RESEARCH_SUPPORTED facts remain held until approval, and UNAUTHORIZED fields are excluded. Production text QA checks rendered text against supplied content/offerings and a conventional interface-label allowlist. No research-derived claim automatically becomes copy. Reference HTML stays evidence. Asset ingestion preserves original bytes, hashes, image metadata, roles, exact status and restrictions. Duplicate hashes are deduplicated. Text/PDF guides are extracted verbatim; structured JSON guides validate palette/fonts/requirements before applying them. Unknown metadata is recorded as unknown. Production asset QA recomputes original hashes and browser loading state.

## Reference Forensics / Existing Site Audit / Confidence

Public sources are bounded, timestamped, captured and stored. Evidence includes source HTML, headings, metadata, links, forms, image references, rendered screenshots and section geometry/computed styles where browser access succeeds. Every observation declares HIGH/MEDIUM/LOW/UNKNOWN; motion not exercised is UNKNOWN. Explicit reference roles persist; inferred composition roles are MEDIUM. Transfers retain observation → principle → target-brand interpretation → implementation, with protected copy/identity/assets expressly excluded. Existing-site crawling preserves available routes, metadata/content/form inventory and raises a release dependency for business-critical integrations that public access cannot establish. No destructive store/site modifications occur.

## Research / Sitemap / Platform Intelligence / Strategy

Research retrieves accessibility/performance and, for Shopify, platform architecture documents; unavailable requests retain status/errors. Category/competitor evidence comes from supplied references and a bounded public RSS search with up to two fetched source candidates. Candidates are never asserted to be market leaders or direct competitors without supporting evidence; unavailable searches retain their errors. The smallest sitemap follows supplied narrative, contact need and native commerce scope. Platform capabilities/constraints and content ownership inform the strategy before visual review. Strategy records business intent, audience, image plan, reference transfers, content policy and generic-design checks. The deterministic composition uses supported editorial/service/portfolio/commerce layouts, without fake stats/testimonials/gradients or arbitrary icon strips.

## Claude Collaboration

`ClaudeReviewer` declares capability/authentication/configuration/health/operations/retries/fallback/data policy. No key → NOT_CONFIGURED and null consultation. A successful request → CONNECTED with actual response and timestamp. Errors fall back internally after two attempts. Advisory feedback is persisted and reconciled as risks; it cannot override project authority or automatically recolor/rewrite an approved design.

## Visual Direction / Approval / Surgical Revision / Design Lock

Directions are clickable prototypes with a page selector and desktop/tablet/mobile view controls. Six controlled viewport baseline captures are recorded when browser capability is available. Keep creates a versioned immutable lock, spec hash, approved prototype manifest and capture hashes; production starts through an Engine job. Revise/Reject retain feedback/tasks/history and create a new version. Scoped changes support image size/position, heading scale, section spacing and unlocked visual tokens. Unrecognized multi-part feedback becomes explicit pending tasks rather than a false claim of completion. Previous locks survive on disk; the active authority is invalidated until the revised version is approved. Palette/fonts locked in the brief cannot be silently changed. New assets require refreshing visual review before approval.

## Production / Shopify Production / CMS Ownership

Adapters describe platform capabilities, constraints, native initialization/build, validation, preview strategy and deployment preparation. Custom Web uses semantic components, responsive CSS tokens and progressive JavaScript, plus an isolated contact service. Shopify uses native layout, sections, JSON templates, snippets, locale/config data and Shopify products/variants/prices/availability/media/selling plans/collections/cart/menu/search/contact/blog/localization/account bindings. Merchant editing controls exist for approved headings/body/images/links/menus/collection selection; hundreds of structural toggles are intentionally absent. Store-owned commerce facts remain dynamic. Existing-site output is a separate safe package, never a live overwrite. Webflow and unsupported business logic remain blocked.

## QA / Visual Diff / Functional / Responsive / Accessibility / Performance / SEO

Eight distinct gates: visual, functional, responsive, accessibility, performance, content integrity, asset integrity, platform compliance. States are PASS/FAIL/BLOCKED/NOT_APPLICABLE. The report is independently derived by artifact-reading QA; incomplete/unknown gate states are rejected by release authority. Failure creates a typed defect with severity/evidence/expected/actual/component/role/attempts/state/blocking.

Visual comparison reads hash-verified approved captures and newly rendered output at 1600, 1366, 1024, 768, 430 and 360-pixel widths. Image differences use a 24-level pixel threshold and 0.8% changed-area tolerance; page height rounding up to three pixels is padded, but changed width/material height is FAIL. Screenshots/diff/results are retained. Functional checks validate routes/fragments/assets, runtime errors, mobile menu/Escape and real isolated contact success/error/private storage. Responsive checks record overflow and control sizes at all six viewport classes. Accessibility uses axe-core WCAG tags, named controls/labels/headings/alternatives and keyboard focus. It is automated-scope evidence, not exhaustive manual certification. Performance records byte budgets and local timings, not invented field scores. SEO includes title/authorized description/Open Graph/semantic hierarchy/crawlable navigation/robots/route manifest; canonical/domain/sitemap configuration is part of deployment because no domain is invented. Shopify canonical/structured product data is native. Live native behavior that cannot be tested remains BLOCKED.

## Repair / Pending Decisions / Recovery

The Engine owns intermediate repair tasks. First restore approved adapter output, then reinitialize native output while retaining failed artifacts; independently retest each attempt, maximum three runs. A failed baseline never grants permission to change approved creative authority. Persistent defects/blockers remain visible. Pending decisions include id/question/reason/dependency/severity/blocking/attempted-resolution/options/recommendation/affected-stages/status. A selection cannot mark unavailable credentials configured. Recovery verifies schema, checkpoints, original hashes, approval artifacts, prototype manifests and release build integrity, then continues the next valid stage; locks are not reconstructed from conversation history.

## Release / Security / Future Monitoring

A release candidate needs every required QA gate and no unresolved blocking defects/decisions. Final approval verifies build integrity again. Packages are CRC-tested and every entry rehashed against the manifest. Blocked outputs receive diagnostic labels and cannot receive final approval. Candidate/deployment/rollback metadata and retained release history provide future monitoring interfaces. Credentials stay external; no adapter publishes, modifies DNS, deletes customer data or incurs charges automatically. See SECURITY.md and OPERATIONS.md for the executable boundaries and exact external next steps.

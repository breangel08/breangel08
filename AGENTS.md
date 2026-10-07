# Website Production Studio + Engine

When the user invokes the Website Production Engine, requests website production in this project, or says `website-production`, read `skills/website-production/SKILL.md` and execute its chat-first workflow. Studio use is optional. Do not ask the user to perform operations this workspace supports.

The same `engine/service.py` owns authority for CLI, MCP and Studio. Production rules must never be copied into chat-only code. Persist projects and resume verified state. Use actual artifacts for human review; general build autonomy does not authorize visual or final approval.

Prefer connected `website_*` MCP tools. If not connected, operate `python -m engine.cli` directly. Never claim this local store is the hosted Replit store unless a shared/configured backend is verified.

Validation: critical Engine tests, chat bridge tests and actual MCP protocol smoke. Browser QA remains required for website builds. No fabricated integration status, approvals or QA.

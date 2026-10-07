import json
import os
import httpx
from ..store import now


class ClaudeReviewer:
    """Optional external critic. The engine remains the approval authority."""
    def state(self):
        configured = bool(os.getenv("ANTHROPIC_API_KEY"))
        return {"configuration": "CONFIGURED" if configured else "NOT_CONFIGURED", "health": "NOT_CHECKED" if configured else "NOT_CONFIGURED", "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"), "capabilities": ["strategy critique", "adversarial review"], "authentication": "ANTHROPIC_API_KEY environment variable", "retry_limit": 2, "fallback": "Internal design and independent QA", "authority": "Advisory only", "data_policy": "Only project strategy and public design evidence sent; no keys, raw private assets, contact submissions or credentials"}

    def review(self, project):
        state = self.state()
        if state["configuration"] == "NOT_CONFIGURED":
            return {**state, "consultation": None, "timestamp": now()}
        payload = {"brand": project["brief"]["brand_name"], "strategy": project["strategy"], "rules": project["constitution"]["rules"], "sitemap": project["sitemap"]["pages"]}
        for attempt in range(2):
            try:
                response = httpx.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}, json={"model": state["model"], "max_tokens": 1500, "system": "Review the supplied strategy against its locked rules. Return concrete risks and suggestions. Never invent source facts. You are advisory; do not override user authority.", "messages": [{"role": "user", "content": json.dumps(payload)}]}, timeout=30)
                response.raise_for_status()
                answer = response.json()
                return {**state, "health": "CONNECTED", "timestamp": now(), "consultation": [block["text"] for block in answer.get("content", []) if block.get("type") == "text"], "reconciliation": "Recorded as advisory feedback; immutable user rules retain priority. No automatic design changes from unverified critique.", "attempts": attempt + 1}
            except (httpx.HTTPError, ValueError):
                if attempt == 1:
                    return {**state, "health": "ERROR", "timestamp": now(), "consultation": None, "error": "Claude consultation unavailable. Internal workflow continued.", "attempts": 2}

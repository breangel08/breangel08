import copy
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import assets, design, evidence, qa, authority
from .adapters import get_adapter
from .adapters.claude import ClaudeReviewer
from .models import Brief, Decision, Review, ROLES
from .render import render_custom
from .store import Store, Conflict, digest, now, uid

ENGINE_VERSION = "1.0.0"
SCHEMA_VERSION = 1


def implementation_fingerprint():
    root = Path(__file__).parent
    return digest({str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob("*.py"))})


class Engine:
    def __init__(self, store=None):
        self.store = store or Store()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="production")

    def create(self, brief: Brief):
        timestamp = now()
        raw = brief.model_dump(mode="json")
        project = {"id": uid("p_"), "name": raw["brand_name"], "engine_version": ENGINE_VERSION, "schema_version": SCHEMA_VERSION, "created_at": timestamp, "updated_at": timestamp, "revision": 0, "autonomy_level": 5, "stage": "BRIEF", "stage_status": "READY", "brief": raw, "classification": design.classify(raw), "assets": [], "evidence": [], "research": [], "constitution": {}, "sitemap": {}, "strategy": {}, "strategy_version": 0, "design_versions": [], "active_design": None, "design_lock": None, "approval_ledger": [{"gate": "BRIEF", "version": 1, "action": "APPROVED", "timestamp": timestamp, "authority": "Submitted project-specific user brief"}], "builds": [], "qa": None, "defects": [], "pending_decisions": [], "checkpoints": [], "release_candidate": None, "release_history": [], "deployment": {"state": "NOT_DEPLOYED", "published": False}, "integrations": {"claude": ClaudeReviewer().state(), "shopify": {"configuration": "NOT_CONFIGURED", "health": "NOT_CONFIGURED", "supported_operations": ["local theme generation", "local validation", "package"], "authentication": "Shopify CLI authenticated development store for remote testing", "fallback": "Preserve local theme with blocked remote QA"}, "webflow": {"configuration": "NOT_CONFIGURED", "health": "NOT_CONFIGURED"}}, "adapter_status": "SELECTED", "fixture": raw["demo"], "visual_dirty": False, "blockers": [], "last_error": None}
        project["constitution"] = design.constitution(project)
        self.checkpoint(project, "INTAKE_COMPLETE", "Orchestrator")
        self.store.artifact(project["id"], "intake/brief.json", raw)
        self.store.artifact(project["id"], "brand/constitution.json", project["constitution"])
        return project

    def checkpoint(self, project, name, role, data=None):
        project["checkpoints"].append({"name": name, "timestamp": now(), "stage": project["stage"], "data": data or {}})
        self.store.save(project, (name, data or {}), role)

    def decision(self, project, question, reason, dependency, options, recommended, blocking=True, severity="warning", identifier=None):
        key = identifier or uid("decision_")
        existing = next((d for d in project["pending_decisions"] if d["id"] == key and d["status"] == "OPEN"), None)
        if existing:
            return existing
        decision = Decision(id=key, question=question, reason=reason, dependency=dependency, severity=severity, blocking=blocking, attempted_resolution=["Inspected brief, assets, platform capabilities and available evidence", "Continued all independent work"], options=options, recommended_option=recommended, affected_stages=[dependency]).model_dump()
        project["pending_decisions"].append(decision)
        return decision

    def blocking(self, project, stage):
        return [d for d in project["pending_decisions"] if d["status"] == "OPEN" and d["blocking"] and (stage in d["affected_stages"] or d["dependency"] == stage)]

    def status(self, project):
        active_jobs = [j for j in self.store.jobs(project["id"]) if j["status"] in {"QUEUED", "RUNNING"}]
        action = not active_jobs and (project["stage"] in {"BRIEF", "VISUAL_REVIEW", "FINAL_REVIEW"} or bool(self.blocking(project, "VISUAL_REVIEW")) or bool(self.blocking(project, "PRODUCTION")))
        stages = ["INTAKE_COMPLETE", "REFERENCE_ANALYSIS_COMPLETE", "RESEARCH_COMPLETE", "ARCHITECTURE_COMPLETE", "STRATEGY_COMPLETE", "VISUAL_READY", "DESIGN_LOCKED", "BUILD_COMPLETE", "QA_PASS", "RELEASE_CANDIDATE_READY", "FINAL_APPROVED", "PACKAGED"]
        done = {c["name"] for c in project["checkpoints"]}
        return {"action_required": action, "working": bool(active_jobs), "completed_checkpoints": sum(s in done for s in stages), "total_checkpoints": len(stages), "progress_basis": "Completed named workflow checkpoints; no elapsed-time estimates", "next_action": self.next_action(project), "active_jobs": active_jobs}

    def next_action(self, project):
        stage = project["stage"]
        return {"BRIEF": "Begin discovery", "DISCOVERY": "Engine is preparing the direction", "VISUAL_REVIEW": "Review the coherent direction", "DESIGN_LOCKED": "Begin production", "PRODUCTION": "Engine is building", "QA": "Engine is checking the build", "FINAL_REVIEW": "Review the finished website", "READY": "Download approved release", "BLOCKED": "Review batched blockers; independent work has been preserved"}[stage]

    def contextual(self, project):
        return {**project, "status": self.status(project), "jobs": self.store.jobs(project["id"]), "events": self.store.events(project["id"])[:100]}

    def queue(self, project_id, kind):
        allowed = {"discover", "produce", "repair", "resume"}
        if kind not in allowed:
            raise ValueError("Unsupported engine operation")
        project = self.store.get(project_id)
        if kind == "discover" and project["stage"] not in {"BRIEF", "DISCOVERY"}:
            raise Conflict("Discovery cannot overwrite an existing visual direction")
        if kind == "produce" and not project["design_lock"]:
            raise Conflict("Gate 2 visual approval is required before production")
        if kind == "repair" and (not project["design_lock"] or not project["builds"]):
            raise Conflict("No approved build is available for repair")
        job = self.store.create_job(project_id, kind)
        self.pool.submit(self.execute_job, job["id"])
        return job

    def execute_job(self, job_id):
        if not self.store.claim_job(job_id):
            return
        job = self.store.job(job_id)
        try:
            getattr(self, job["kind"])(job["project_id"])
            self.store.update_job(job_id, "SUCCEEDED")
        except Exception as error:
            # Raw provider exceptions can contain credentials/URLs: preserve safe type
            # and an engine-generated message, not a stack trace or provider request.
            safe = str(error)[:500] if isinstance(error, (ValueError, Conflict, KeyError)) else f"{type(error).__name__}: operation failed; recover from verified project artifacts"
            self.store.update_job(job_id, "FAILED", safe)
            with self.store.lock(job["project_id"]):
                p = self.store.get(job["project_id"])
                p["last_error"] = safe
                p["stage_status"] = "FAILED"
                self.store.save(p, ("OPERATION_FAILED", {"operation": job["kind"], "error": safe}))

    def recover_jobs(self):
        # One Studio worker owns jobs. SQLite claims prevent duplicate submission;
        # deployment contract intentionally forbids concurrent Studio workers.
        for job in self.store.jobs():
            if job["status"] in {"RUNNING", "QUEUED"}:
                self.store.update_job(job["id"], "INTERRUPTED", "Application restart; persisted checkpoints retained")
        results = []
        for p in self.store.list():
            recovery = self.recover(p["id"])
            results.append(recovery)
            if recovery["status"] == "VERIFIED" and p["stage"] in {"DISCOVERY", "PRODUCTION", "QA"}:
                self.queue(p["id"], "resume")
        return results

    def discover(self, project_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            if p["stage"] not in {"BRIEF", "DISCOVERY"}:
                raise Conflict("Discovery cannot overwrite design or production history")
            p.update(stage="DISCOVERY", stage_status="RUNNING", last_error=None)
            self.store.save(p, ("DISCOVERY_STARTED", {}))
            p["constitution"] = design.constitution(p)
            self.store.artifact(project_id, "brand/constitution.json", p["constitution"])
            observed_urls = {e["source_url"] for e in p["evidence"]}
            sources = [(r["url"], r["role"], False) for r in p["brief"]["references"]]
            if p["brief"].get("current_url"):
                sources.insert(0, (p["brief"]["current_url"], "navigation", True))
            for url, role, existing in sources:
                if url in observed_urls:
                    continue
                record = evidence.ingest_source(self.store, project_id, url, role, existing)
                p["evidence"].append(record)
                self.store.save(p, ("EXISTING_SITE_AUDITED" if existing else "REFERENCE_ANALYZED", {"source": url, "status": record["status"], "capture": record["capture"]["status"]}), "Reference Analyst")
                if record["status"] != "OBSERVED":
                    self.decision(p, f"Reference evidence unavailable: {url}", record.get("error", "Source could not be captured"), "VISUAL_REVIEW", ["Continue with available evidence", "Provide authorized screenshots"], "Continue with available evidence", blocking=False, identifier="reference_" + record["id"])
            self.store.artifact(project_id, "references/SITE_REFERENCE.json", {"references": p["evidence"], "authority": "Evidence informs principles, never transfers reference content/assets"})
            self.store.artifact(project_id, "references/SITE_REFERENCE.md", "# Site reference authority\n\n" + "\n\n".join(f"## {e['source_url']}\nRole: {e['role']} ({e['role_confidence']})\nStatus: {e['status']}\n" + "\n".join(f"- [{o['confidence']}] {o['observation']}" for o in e["observations"]) for e in p["evidence"]) + "\n\nReference text, identity and imagery are excluded from production.\n")
            self.checkpoint(p, "REFERENCE_ANALYSIS_COMPLETE", "Reference Analyst")
            if not p["research"]:
                p["research"] = evidence.research(self.store, p)
            self.checkpoint(p, "RESEARCH_COMPLETE", "Researcher", {"retrieved_sources": sum(r["status"] == "FETCHED" for r in p["research"])})
            p["sitemap"] = design.sitemap(p)
            self.store.artifact(project_id, "architecture/sitemap.json", p["sitemap"])
            self.checkpoint(p, "ARCHITECTURE_COMPLETE", "Project Architect")
            self.platform_decisions(p)
            p["strategy"] = design.strategy(p)
            p["strategy_version"] += 1
            self.store.artifact(project_id, f"design/strategy-v{p['strategy_version']}.json", p["strategy"])
            p["integrations"]["claude"] = ClaudeReviewer().review(p)
            self.store.artifact(project_id, "research/claude-review.json", p["integrations"]["claude"])
            self.checkpoint(p, "STRATEGY_COMPLETE", "Design Strategist")
            self.make_visual(p, design.design_spec(p), feedback="Initial direction", patches={})
            return p

    def platform_decisions(self, p):
        interpretations = authority.interpret(p)
        self.store.artifact(p["id"], "brand/requirement-interpretations.json", interpretations)
        for record in interpretations:
            if record["status"] == "NEEDS_STRUCTURED_AUTHORITY":
                text = record["rule"]["text"]
                self.decision(p, "A nonnegotiable requirement needs structured authority: " + text, "The engine cannot safely assert that arbitrary prose is implemented. Supply a validated brand guide, a supported scoped directive or explicitly waive this requirement.", "VISUAL_REVIEW", ["Provide supported structured authority", "Explicitly waive this requirement"], "Provide supported structured authority", identifier="rule_" + digest(text)[:12])
        if p["classification"]["target"] == "WEBFLOW":
            self.decision(p, "Webflow native integration is unavailable", "No configured Webflow production adapter; cannot mislabel HTML as a native build", "PRODUCTION", ["Configure Webflow adapter", "Change target explicitly before approval"], "Configure Webflow adapter", identifier="webflow_integration")
        supported = {"contact", "contact form", "navigation", "responsive", "seo", "portfolio", "blog", "search", "products", "cart", "checkout", "variants", "ecommerce", "accessibility"}
        for function in p["brief"]["functionality"]:
            lower = function.lower().strip()
            if lower not in supported or (p["classification"]["target"] == "CUSTOM_WEB" and lower in {"search", "cart", "checkout", "variants", "ecommerce", "blog"}):
                self.decision(p, f"Required functionality needs a specialized implementation: {function}", "The selected adapter cannot truthfully deliver this capability using its current implementation", "PRODUCTION", ["Provide a compatible integration", "Explicitly remove this requirement"], "Provide a compatible integration", identifier="function_" + digest(function)[:12])
        if p["brief"]["website_type"] == "WEB_APP":
            self.decision(p, "Web app behavior requires a project-specific application adapter", "Authentication/business logic cannot be inferred as a static brand website", "PRODUCTION", ["Configure application extension", "Explicitly narrow to a public informational site"], "Configure application extension", identifier="webapp_scope")
        if p["brief"].get("current_url"):
            self.decision(p, "Verify existing business-critical integrations before release", "Public crawling cannot establish private app/configuration/template behavior; URLs and available forms were preserved as an audit inventory", "RELEASE", ["Provide verified platform audit and preservation plan"], "Provide verified platform audit and preservation plan", identifier="existing_preservation")

    def make_visual(self, p, spec, feedback, patches, tasks=None):
        critique = design.critique(p, spec)
        self.store.artifact(p["id"], f"design/critique-v{len(p['design_versions']) + 1}.json", critique)
        if critique["status"] != "PASS":
            raise ValueError("Pre-review design authority critique failed; visual direction was not presented")
        version = len(p["design_versions"]) + 1
        root = self.store.path(p["id"])
        relative = f"design/v{version}/prototype"
        project = {**p, "_root": str(root)}
        render_custom(project, spec, root / relative, prototype=True)
        captures = qa.capture_approved(root / relative, spec, root / f"design/v{version}/captures")
        old = p["active_design"]
        if old:
            previous = p["design_versions"][old - 1]
            if previous["approval_state"] != "APPROVED":
                previous["approval_state"] = "SUPERSEDED"
        entry = {"version": version, "timestamp": now(), "spec": spec, "sha256": digest(spec), "changes": patches, "originating_feedback": feedback, "tasks": tasks or [], "locked_elements": ["brand", "content", "assets", "layout", "pages", "section_order", *[field for field in design.PATCH_FIELDS if field not in patches]], "changed_elements": list(patches), "approval_state": "PENDING", "supersedes": old, "prototype_path": relative, "capture_path": f"design/v{version}/captures", "prototype_manifest": qa.manifest(root / relative), "captures": captures}
        p["design_versions"].append(entry)
        p.update(active_design=version, stage="VISUAL_REVIEW", stage_status="AWAITING_APPROVAL", visual_dirty=False, release_candidate=None, last_error=None)
        self.store.artifact(p["id"], f"design/v{version}/design.json", entry)
        self.checkpoint(p, "VISUAL_READY", "Visual Designer", {"version": version, "captures": captures["status"]})

    def review(self, project_id, review: Review):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            if p["stage"] not in {"VISUAL_REVIEW", "DESIGN_LOCKED", "FINAL_REVIEW", "READY", "BLOCKED"} or not p["active_design"]:
                raise Conflict("No visual direction is available for review")
            if review.version != p["active_design"]:
                raise Conflict("Review refers to a superseded design version")
            if any(j["status"] in {"RUNNING", "QUEUED"} for j in self.store.jobs(project_id)):
                raise Conflict("Wait for the current engine operation to finish")
            entry = p["design_versions"][review.version - 1]
            if review.action == "KEEP":
                if p["design_lock"] and p["design_lock"]["version"] == review.version:
                    return p
                if p["visual_dirty"]:
                    raise Conflict("New assets need a regenerated visual before approval")
                if self.blocking(p, "VISUAL_REVIEW"):
                    raise Conflict("Resolve the batched visual decisions before approval")
                if digest(entry["spec"]) != entry["sha256"] or qa.manifest(self.store.path(project_id) / entry["prototype_path"]) != entry["prototype_manifest"]:
                    raise Conflict("Visual artifact integrity failed; approval cannot lock modified files")
                entry["approval_state"] = "APPROVED"
                lock = {"version": entry["version"], "timestamp": now(), "sha256": entry["sha256"], "spec": copy.deepcopy(entry["spec"]), "prototype_path": entry["prototype_path"], "prototype_manifest": entry["prototype_manifest"], "capture_path": entry["capture_path"], "captures": entry["captures"], "locked": True, "authority": "Gate 2 user visual approval"}
                p.update(design_lock=lock, stage="DESIGN_LOCKED", stage_status="READY", qa=None, release_candidate=None)
                p["approval_ledger"].append({"gate": "VISUAL", "version": entry["version"], "action": "APPROVED", "sha256": entry["sha256"], "timestamp": now(), "feedback": review.feedback})
                self.store.artifact(project_id, f"approvals/design-lock-v{entry['version']}.json", lock)
                self.checkpoint(p, "DESIGN_LOCKED", "Orchestrator", {"version": entry["version"], "sha256": entry["sha256"]})
            else:
                inferred, tasks = design.feedback_patches(review.feedback, entry["spec"])
                patches = {**inferred, **review.patches}
                updated = design.apply_patches(entry["spec"], patches, p)
                if p["visual_dirty"]:
                    assets_spec = design.design_spec(p)
                    updated["hero_asset"] = assets_spec["hero_asset"]
                    updated["logo_asset"] = assets_spec["logo_asset"]
                unresolved = [t for t in tasks if t["status"] == "NEEDS_INTERPRETATION"]
                for task in unresolved:
                    if review.patches:
                        task["status"] = "SCOPED_BY_EXPLICIT_PATCH"
                        continue
                    self.decision(p, f"Revision needs a scoped design instruction: {task['target']}", "Natural-language feedback was recorded, but no supported precise patch could be safely inferred", "VISUAL_REVIEW", ["Supply a supported scoped patch", "Withdraw this revision request"], "Supply a supported scoped patch", identifier="revision_" + digest(task)[:12])
                p["approval_ledger"].append({"gate": "VISUAL", "version": review.version, "action": review.action, "timestamp": now(), "feedback": review.feedback, "patches": patches, "tasks": tasks})
                # Preserve previous immutable lock on disk; active production authority
                # is invalidated until the new bounded version is explicitly approved.
                p["design_lock"] = None
                entry["approval_state"] = "REJECTED" if review.action == "REJECT" else entry["approval_state"]
                self.make_visual(p, updated, review.feedback, patches, tasks)
            self.store.artifact(project_id, "approvals/ledger.json", p["approval_ledger"])
            return p

    def regenerate(self, project_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            if p["stage"] != "VISUAL_REVIEW" or p["design_lock"]:
                raise Conflict("Regeneration is only available before design approval")
            spec = copy.deepcopy(p["design_versions"][p["active_design"] - 1]["spec"])
            fresh = design.design_spec(p)
            spec.update(hero_asset=fresh["hero_asset"], logo_asset=fresh["logo_asset"])
            if p["brief"]["palette"]:
                for field in ["background", "ink", "accent"]:
                    spec["tokens"][field] = fresh["tokens"][field]
            if p["brief"]["fonts"]:
                for field in ["font", "body_font"]:
                    spec["tokens"][field] = fresh["tokens"][field]
            self.make_visual(p, spec, "New supplied assets integrated", {"assets": "Updated explicit supplied assets"})
            return p

    def produce(self, project_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            if not p["design_lock"] or not p["design_lock"]["locked"]:
                raise Conflict("Gate 2 approval and immutable Design Lock are required before production")
            if p["stage"] not in {"DESIGN_LOCKED", "PRODUCTION", "QA", "BLOCKED", "FINAL_REVIEW", "READY"}:
                raise Conflict("Invalid production stage")
            if self.blocking(p, "PRODUCTION"):
                p.update(stage="BLOCKED", stage_status="BLOCKED")
                self.store.save(p, ("PRODUCTION_BLOCKED", {"decisions": [d["id"] for d in self.blocking(p, "PRODUCTION")]}))
                return p
            if digest(p["design_lock"]["spec"]) != p["design_lock"]["sha256"]:
                raise Conflict("Design lock integrity failed")
            adapter = get_adapter(p["classification"]["target"])
            p.update(stage="PRODUCTION", stage_status="RUNNING", release_candidate=None, last_error=None)
            version = len(p["builds"]) + 1
            build_id = uid("build_")
            path = f"production/build-{version}/site"
            build = {"id": build_id, "version": version, "timestamp": now(), "engine_version": ENGINE_VERSION, "implementation_fingerprint": implementation_fingerprint(), "adapter": adapter.contract(), "design_version": p["design_lock"]["version"], "design_sha256": p["design_lock"]["sha256"], "path": path, "status": "BUILDING", "qa_history": [], "repairs": []}
            p["builds"].append(build)
            self.store.artifact(project_id, f"production/build-{version}/build-plan.json", {"authority": p["design_lock"]["sha256"], "adapter": adapter.contract(), "pages": p["sitemap"]["pages"], "content_ownership": adapter.capabilities.get("cms"), "tasks": ["Initialize native structure", "Bind approved assets and authorized copy", "Implement platform-native behavior", "Independent artifact QA", "Bounded fidelity-preserving repair", "Prepare release candidate only after PASS"]})
            self.store.save(p, ("PRODUCTION_STARTED", {"build": build_id}), "Developer")
            enriched = {**p, "_root": str(self.store.path(project_id))}
            adapter.build(enriched, p["design_lock"]["spec"], self.store.path(project_id) / path)
            build.update(status="BUILT", manifest=qa.manifest(self.store.path(project_id) / path))
            p.update(stage="QA", stage_status="RUNNING")
            self.checkpoint(p, "BUILD_COMPLETE", "Developer", {"build": build_id})
            self.qa_and_repair(p, build, adapter)
            return p

    def qa_and_repair(self, p, build, adapter):
        report = None
        for attempt in range(3):
            report = qa.run(self.store, p, build, adapter)
            if set(report["results"]) != set(qa.GATES):
                raise ValueError("Incomplete independent QA report; release authority rejected")
            if any(r["status"] not in {"PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"} for r in report["results"].values()):
                raise ValueError("Unknown QA gate state; release authority rejected")
            report["status"] = "FAIL" if any(r["status"] == "FAIL" for r in report["results"].values()) else "BLOCKED" if any(r["status"] == "BLOCKED" for r in report["results"].values()) else "PASS"
            build["qa_history"].append({"id": report["id"], "status": report["status"], "path": report["path"], "timestamp": report["timestamp"]})
            p["qa"] = report
            fresh_keys = {(d["category"], d["affected_component"], d["expected_result"]) for d in report["defects"]}
            for old in p["defects"]:
                if old["status"] in {"OPEN", "REPAIRING"} and (old["category"], old["affected_component"], old["expected_result"]) not in fresh_keys:
                    old["status"] = "RESOLVED"
                    old["resolved_by"] = report["id"]
            for new in report["defects"]:
                existing = next((d for d in p["defects"] if d["status"] in {"OPEN", "REPAIRING"} and (d["category"], d["affected_component"], d["expected_result"]) == (new["category"], new["affected_component"], new["expected_result"])), None)
                if existing:
                    existing.update(actual_result=new["actual_result"], evidence=new["evidence"], status="OPEN")
                else:
                    p["defects"].append(new)
            self.store.save(p, ("QA_COMPLETED", {"build": build["id"], "status": report["status"], "defects": len(report["defects"]), "attempt": attempt + 1}), "Visual QA")
            if report["status"] != "FAIL":
                break
            if attempt < 2:
                diagnosis = "Compare output with immutable design and asset hashes; restore faithful adapter output. Persistent baseline/unsupported platform defects must never change approved design."
                method = "RESTORE_APPROVED_BUILD" if attempt == 0 else "REINITIALIZE_NATIVE_OUTPUT"
                repair = {"attempt": attempt + 1, "method": method, "diagnosis": diagnosis, "timestamp": now(), "state": "REPAIRING", "defects": [d["id"] for d in p["defects"] if d["status"] == "OPEN"]}
                build["repairs"].append(repair)
                for d in p["defects"]:
                    if d["status"] == "OPEN":
                        d["status"] = "REPAIRING"
                        d["repair_attempts"].append(copy.deepcopy(repair))
                self.store.save(p, ("AUTONOMOUS_REPAIR_STARTED", repair), "Developer")
                output = self.store.path(p["id"]) / build["path"]
                if attempt == 1:
                    backup = output.parent / "failed-artifacts"
                    if not backup.exists():
                        shutil.copytree(output, backup)
                    shutil.rmtree(output)
                adapter.build({**p, "_root": str(self.store.path(p["id"]))}, p["design_lock"]["spec"], output)
                repair["state"] = "RETESTING"
        build["manifest"] = qa.manifest(self.store.path(p["id"]) / build["path"])
        build["status"] = "QA_PASS" if report["status"] == "PASS" else report["status"]
        if report["status"] == "PASS":
            for d in p["pending_decisions"]:
                if d["id"] == "qa_retry_exhausted" and d["status"] == "OPEN":
                    d.update(status="RESOLVED", resolution="Independent retest verified the repaired implementation", resolved_at=now())
            p["blockers"] = []
        if report["status"] == "PASS" and not self.blocking(p, "RELEASE") and not any(d["blocking"] and d["status"] != "RESOLVED" for d in p["defects"]):
            self.checkpoint(p, "QA_PASS", "Release Manager", {"qa": report["id"]})
            for gate, result in report["results"].items():
                self.checkpoint(p, gate.upper() + "_QA_PASS", "Release Manager", {"qa": report["id"]})
            p["release_candidate"] = {"id": uid("rc_"), "version": len(p["release_history"]) + 1, "build_id": build["id"], "design_sha256": build["design_sha256"], "manifest_sha256": digest(build["manifest"]), "qa_id": report["id"], "timestamp": now(), "status": "AWAITING_FINAL_APPROVAL", "target": adapter.name, "deployment": adapter.prepare_deployment(p), "rollback": {"previous_release": p["release_history"][-1]["id"] if p["release_history"] else None, "strategy": "Retain all prior builds; promote a versioned artifact only after explicit external release authorization"}, "monitoring": {"state": "NOT_CONFIGURED", "extension_contract": "Monitor receives release id, URL and baseline hashes; results append events/defects without changing authority"}}
            p.update(stage="FINAL_REVIEW", stage_status="AWAITING_APPROVAL")
            self.checkpoint(p, "RELEASE_CANDIDATE_READY", "Release Manager", {"build": build["id"]})
        else:
            p.update(stage="BLOCKED", stage_status="BLOCKED", release_candidate=None)
            p["blockers"] = [{"gate": name, "status": result["status"], "reason": result.get("reason", "Unresolved QA defects after bounded repair")} for name, result in report["results"].items() if result["status"] not in {"PASS", "NOT_APPLICABLE"}]
            if report["status"] == "FAIL":
                self.decision(p, "Required QA remains failed after bounded repair", "Faithful rebuild and native-output reinitialization did not resolve the defect; altering approved creative authority is not permitted", "RELEASE", ["Resolve underlying implementation defect", "Approve a scoped visual revision if the baseline itself is invalid"], "Resolve underlying implementation defect", identifier="qa_retry_exhausted")
            self.store.save(p, ("RELEASE_BLOCKED", {"blockers": p["blockers"]}), "Release Manager")
        self.store.artifact(p["id"], f"production/build-{build['version']}/build.json", build)
        self.prepare_package(p, build, diagnostic=p["release_candidate"] is None)

    def repair(self, project_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            if not p["design_lock"] or not p["builds"]:
                raise Conflict("No approved build to repair")
            # Retries never bypass approvals or invent missing external credentials.
            if any(d["id"] == "qa_retry_exhausted" and d["status"] == "OPEN" for d in p["pending_decisions"]) and p["builds"][-1].get("implementation_fingerprint") == implementation_fingerprint():
                raise Conflict("Repair threshold exhausted; resolve the underlying defect or approve a scoped revision first")
            p["builds"][-1]["implementation_fingerprint"] = implementation_fingerprint()
            p.update(stage="QA", stage_status="RUNNING", release_candidate=None)
            self.store.save(p, ("QA_RETEST_STARTED", {}), "Functional QA")
            self.qa_and_repair(p, p["builds"][-1], get_adapter(p["classification"]["target"]))
            return p

    def prepare_package(self, p, build, diagnostic=False):
        root = self.store.path(p["id"])
        output = root / build["path"]
        package = root / "release" / f"build-{build['version']}{'-diagnostic' if diagnostic else '-candidate'}.zip"
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.rglob("*")):
                if path.is_file():
                    archive.write(path, str(path.relative_to(output)))
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:
                raise ValueError("Package integrity test failed")
            if set(archive.namelist()) != set(build["manifest"]):
                raise ValueError("Package does not match the validated build manifest")
            for name, checksum in build["manifest"].items():
                if digest(archive.read(name)) != checksum:
                    raise ValueError("Package file differs from the validated build")
        build["package"] = {"path": str(package.relative_to(root)), "sha256": digest(package.read_bytes()), "status": "DIAGNOSTIC_NOT_RELEASE_READY" if diagnostic else "CANDIDATE", "zip_integrity": "PASS", "manifest_match": "PASS", "target": p["classification"]["target"]}
        self.store.artifact(p["id"], f"release/build-{build['version']}-manifest.json", {"build": build["id"], "manifest": build["manifest"], "package": build["package"], "credentials_included": False})
        self.store.save(p, ("PACKAGE_PREPARED", build["package"]), "Release Manager")

    def final_approve(self, project_id, build_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            candidate = p["release_candidate"]
            if p["stage"] != "FINAL_REVIEW" or not candidate or candidate["build_id"] != build_id:
                raise Conflict("Only the current QA-passing release candidate can receive final approval")
            if not p["qa"] or p["qa"]["status"] != "PASS" or set(p["qa"]["results"]) != set(qa.GATES) or any(r["status"] not in {"PASS", "NOT_APPLICABLE"} for r in p["qa"]["results"].values()):
                raise Conflict("Required independent QA gates have not passed")
            if self.blocking(p, "RELEASE") or self.blocking(p, "PRODUCTION"):
                raise Conflict("Unresolved release decisions")
            build = next(b for b in p["builds"] if b["id"] == build_id)
            if qa.manifest(self.store.path(project_id) / build["path"]) != build["manifest"]:
                raise Conflict("Build changed after QA; retest is required")
            package_path = self.store.path(project_id) / build["package"]["path"]
            if not package_path.is_file() or digest(package_path.read_bytes()) != build["package"]["sha256"]:
                raise Conflict("Package changed after manifest validation; regenerate and retest before approval")
            if candidate["manifest_sha256"] != digest(build["manifest"]) or candidate["design_sha256"] != p["design_lock"]["sha256"]:
                raise Conflict("Release candidate authority no longer matches the approved design/build")
            candidate.update(status="APPROVED", approved_at=now())
            p["release_history"].append(copy.deepcopy(candidate))
            p["approval_ledger"].append({"gate": "FINAL", "build_id": build_id, "version": candidate["version"], "action": "APPROVED", "timestamp": now(), "qa_id": p["qa"]["id"]})
            p.update(stage="READY", stage_status="COMPLETE")
            self.checkpoint(p, "FINAL_APPROVED", "Release Manager", {"build": build_id})
            self.checkpoint(p, "PACKAGED", "Release Manager", {"package": build["package"]["path"]})
            self.store.artifact(project_id, "release/release-history.json", p["release_history"])
            self.store.artifact(project_id, "approvals/ledger.json", p["approval_ledger"])
            return p

    def resolve(self, project_id, decision_id, resolution, patches=None):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            d = next((d for d in p["pending_decisions"] if d["id"] == decision_id), None)
            if not d or d["status"] != "OPEN":
                raise KeyError("Open decision not found")
            if resolution not in d["options"]:
                raise ValueError("Choose one of the declared resolution options")
            if resolution.startswith(("Configure", "Provide a compatible", "Provide verified", "Resolve underlying")):
                raise Conflict("Evidence of the required integration or fix is needed; a text selection cannot mark an unavailable capability configured")
            if resolution == "Supply a supported scoped patch":
                if not patches:
                    raise ValueError("A concrete supported patch is required")
                # Record explicit current user authority; generate a new bounded version.
                entry = p["design_versions"][p["active_design"] - 1]
                updated = design.apply_patches(entry["spec"], patches, p)
                d.update(status="RESOLVED", resolution=resolution)
                p["design_lock"] = None
                self.make_visual(p, updated, "Scoped resolution: " + d["question"], patches)
            elif resolution == "Explicitly remove this requirement":
                if p["design_lock"]:
                    raise Conflict("Required functionality is design-locked; reopen visual review with a scoped revision first")
                function = d["question"].split(": ", 1)[-1]
                p["brief"]["functionality"] = [f for f in p["brief"]["functionality"] if f != function]
            elif resolution == "Explicitly waive this requirement":
                if p["design_lock"]:
                    raise Conflict("Reopen visual review before changing a locked requirement")
                text = d["question"].split(": ", 1)[-1]
                p["brief"]["requirements"] = [r for r in p["brief"]["requirements"] if r["text"] != text]
                p["constitution"] = design.constitution(p)
                self.store.artifact(project_id, "brand/constitution.json", p["constitution"])
            elif resolution == "Explicitly narrow to a public informational site":
                if p["design_lock"]:
                    raise Conflict("Reopen visual review before changing project scope")
                p["brief"]["website_type"] = "BRAND_WEBSITE"
                p["classification"] = design.classify(p["brief"])
            elif resolution in {"Provide authorized screenshots", "Change target explicitly before approval", "Approve a scoped visual revision if the baseline itself is invalid"}:
                raise Conflict("Use asset ingestion or a scoped visual revision; recording a selection alone does not complete it")
            d.update(status="RESOLVED", resolution=resolution, resolved_at=now())
            self.store.save(p, ("DECISION_RESOLVED", {"id": decision_id, "resolution": resolution}))
            return p

    def recover(self, project_id):
        with self.store.lock(project_id):
            p = self.store.get(project_id)
            issues = []
            if p["schema_version"] != SCHEMA_VERSION:
                issues.append("Project schema requires an explicit migration")
            lock = p["design_lock"]
            if lock:
                if digest(lock["spec"]) != lock["sha256"]:
                    issues.append("Design lock hash failed")
                lock_path = self.store.path(project_id) / f"approvals/design-lock-v{lock['version']}.json"
                if not lock_path.exists():
                    issues.append("Immutable approval artifact missing")
                else:
                    try:
                        if json.loads(lock_path.read_text()) != lock:
                            issues.append("Database lock differs from its immutable approval artifact")
                    except (ValueError, OSError):
                        issues.append("Immutable approval artifact is unreadable")
                if qa.manifest(self.store.path(project_id) / lock["prototype_path"]) != lock["prototype_manifest"]:
                    issues.append("Approved prototype missing or changed")
            for asset in p["assets"]:
                path = self.store.path(project_id) / asset["path"]
                if not path.exists() or digest(path.read_bytes()) != asset["sha256"]:
                    issues.append("Source asset missing or changed: " + asset["id"])
            if p["release_candidate"] and p["builds"]:
                build = p["builds"][-1]
                if qa.manifest(self.store.path(project_id) / build["path"]) != build["manifest"]:
                    issues.append("QA-certified build changed; release invalidated")
                    p["release_candidate"] = None
                    p["stage"] = "BLOCKED"
            recovery = {"timestamp": now(), "status": "BLOCKED" if issues else "VERIFIED", "issues": issues, "last_checkpoint": p["checkpoints"][-1]["name"] if p["checkpoints"] else None, "approved_design": lock["version"] if lock else None, "unresolved_defects": [d["id"] for d in p["defects"] if d["status"] != "RESOLVED"], "pending_decisions": [d["id"] for d in p["pending_decisions"] if d["status"] == "OPEN"], "next_operation": "discover" if p["stage"] in {"BRIEF", "DISCOVERY"} else "produce" if p["stage"] in {"DESIGN_LOCKED", "PRODUCTION"} else "repair" if p["stage"] == "QA" else "human_review" if p["stage"] in {"VISUAL_REVIEW", "FINAL_REVIEW"} else "resolve_blockers" if p["stage"] == "BLOCKED" else "download"}
            p["recovery"] = recovery
            if issues:
                p["stage_status"] = "BLOCKED"
            self.store.save(p, ("RECOVERY_VERIFIED" if not issues else "RECOVERY_BLOCKED", recovery))
            self.store.artifact(project_id, "recovery/latest.json", recovery)
            return recovery

    def resume(self, project_id):
        recovery = self.recover(project_id)
        if recovery["status"] != "VERIFIED":
            raise Conflict("Recovery detected artifact inconsistencies; unsafe continuation blocked")
        operation = recovery["next_operation"]
        if operation in {"discover", "produce", "repair"}:
            return getattr(self, operation)(project_id)
        return self.store.get(project_id)

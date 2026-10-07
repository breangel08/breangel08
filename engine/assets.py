import io
import json
import mimetypes
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from .store import digest, now, uid, Conflict


ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".txt", ".md", ".csv", ".json", ".woff", ".woff2", ".ttf", ".otf"}
ROLES = {"unassigned", "logo", "hero", "photography", "product", "font", "guide", "content"}


def ingest(store, project_id, filename, raw, role="unassigned", exact=True, restrictions=""):
    if role not in ROLES:
        raise ValueError("Unsupported asset role")
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError("Unsupported asset type. Active SVG, HTML and executable files are excluded.")
    if not raw:
        raise ValueError("Empty asset")
    import os
    if len(raw) > int(os.getenv("STUDIO_MAX_UPLOAD_MB", "25")) * 1024 * 1024:
        raise ValueError("Asset exceeds upload size limit")
    with store.lock(project_id):
        project = store.get(project_id)
        if project["stage"] not in {"BRIEF", "VISUAL_REVIEW"}:
            raise Conflict("Assets cannot change during discovery or after the design has been locked")
        checksum = digest(raw)
        duplicate = next((a for a in project["assets"] if a["sha256"] == checksum), None)
        if duplicate:
            return {**duplicate, "duplicate": True}
        asset_id = uid("a_")
        asset = {"id": asset_id, "filename": name, "path": f"assets/{asset_id}{ext}", "mime": mimetypes.guess_type(name)[0] or "application/octet-stream", "bytes": len(raw), "sha256": checksum, "role": role, "approved_role": role if role != "unassigned" else None, "exact": exact, "restrictions": restrictions, "permission": "SUPPLIED", "timestamp": now(), "readiness": "NEEDS_ROLE" if role == "unassigned" else "READY"}
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    image.verify()
                with Image.open(io.BytesIO(raw)) as image:
                    width, height = image.size
                    if width * height > 40_000_000:
                        raise ValueError("Image exceeds safe pixel limit")
                    asset.update(width=width, height=height, ratio=round(width / height, 3), transparency=image.mode in {"RGBA", "LA"} or "transparency" in image.info, format=image.format, readiness="LOW_RESOLUTION" if width < 400 and role in {"hero", "photography", "product"} else asset["readiness"])
                    if asset["mime"] != Image.MIME.get(image.format):
                        raise ValueError("Image extension and file format disagree")
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
                raise ValueError("Invalid or unsafe image") from error
        path = store.path(project_id) / asset["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        if role in {"guide", "content"}:
            analysis = {"status": "UNAVAILABLE", "confidence": "UNKNOWN", "extracted_text": None, "production_copy": "Not automatically approved as a page content field"}
            try:
                if ext in {".txt", ".md", ".csv", ".json"}:
                    extracted = raw.decode("utf-8")[:20000]
                elif ext == ".pdf":
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(raw))
                    extracted = "\n".join(page.extract_text() or "" for page in reader.pages[:20])[:20000]
                else:
                    extracted = ""
                if extracted.strip():
                    analysis.update(status="EXTRACTED", confidence="HIGH", extracted_text=extracted, method="Verbatim supplied-document text extraction")
            except Exception:
                analysis["reason"] = "Document text extraction unavailable; original retained"
            asset["analysis"] = analysis
            if ext == ".json" and role == "guide":
                try:
                    from .models import Requirement, Brief
                    guide = json.loads(raw)
                    proposed = Brief.model_validate({**project["brief"], **{key: guide[key] for key in ["palette", "fonts"] if key in guide and not project["brief"].get(key)}})
                    rules = [Requirement.model_validate(rule).model_dump() for rule in guide.get("requirements", [])]
                    project["brief"]["palette"] = proposed.palette
                    project["brief"]["fonts"] = proposed.fonts
                    project["brief"]["requirements"].extend(rules)
                    asset["analysis"]["applied_rules"] = len(rules)
                except (ValueError, TypeError, KeyError):
                    asset["analysis"]["structured_rules"] = "INVALID_OR_UNSUPPORTED; no unvalidated rules applied"
        from .design import constitution
        project["assets"].append(asset)
        project["constitution"] = constitution(project)
        if project["stage"] == "VISUAL_REVIEW":
            project["visual_dirty"] = True
        store.save(project, ("ASSET_INGESTED", {"asset": asset_id, "sha256": checksum, "exact": exact}), "Asset Analyst")
        store.artifact(project_id, "assets/inventory.json", project["assets"])
        store.artifact(project_id, "brand/constitution.json", project["constitution"])
        return asset


def assign(store, project_id, asset_id, role):
    if role not in ROLES:
        raise ValueError("Unsupported asset role")
    with store.lock(project_id):
        project = store.get(project_id)
        if project["stage"] not in {"BRIEF", "VISUAL_REVIEW"}:
            raise Conflict("Asset roles are locked with the design")
        asset = next((a for a in project["assets"] if a["id"] == asset_id), None)
        if not asset:
            raise KeyError("Asset not found")
        asset.update(role=role, approved_role=role if role != "unassigned" else None)
        project["visual_dirty"] = project["stage"] == "VISUAL_REVIEW"
        store.save(project, ("ASSET_ROLE_ASSIGNED", {"asset": asset_id, "role": role}), "Asset Analyst")
        return asset

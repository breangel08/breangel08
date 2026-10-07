"""Explicitly fictional fixtures; automated approvals are exclusive to demo data."""
import io
from pathlib import Path
from PIL import Image, ImageDraw
from .assets import ingest
from .models import Brief, Review
from .store import now, uid


CUSTOM_BRIEF = {
    "brand_name": "Fieldwork — demo",
    "website_type": "SERVICE_WEBSITE",
    "target": "CUSTOM_WEB",
    "demo": True,
    "goals": "Present the fictional studio's work and accept project enquiries",
    "audience": "People interested in considered spaces and objects",
    "instructions": "A restrained editorial direction. Warm ivory, deep olive, generous typography. Let the supplied image anchor the composition. Preserve exact imagery and approved copy. This is a fictional test project; no real-company claims.",
    "references": [{"url": "https://reference.example.invalid/", "role": "composition"}],
    "offerings": ["Objects for living", "Spaces with intention", "Creative direction"],
    "functionality": ["contact form", "navigation", "responsive", "seo"],
    "palette": ["#f4f1e9", "#303b2d", "#465d3d"],
    "fonts": ["Georgia", "Arial"],
    "requirements": [{"classification": "LOCKED", "area": "content", "text": "Use only the supplied fictional copy"}, {"classification": "FORBIDDEN", "area": "design", "text": "No gradients, invented testimonials or decorative icon strips"}],
    "content": [{"id": key, "text": text, "permission": "SUPPLIED", "source": "Explicit fictional fixture"} for key, text in {
        "hero_heading": "A quieter kind\nof everyday.",
        "hero_body": "Objects, spaces and ideas, considered together. An exploration of how we live with less, and live with intention.",
        "cta_label": "Start a conversation",
        "offerings_heading": "Our practice",
        "about_heading": "Room for what matters.",
        "about_body": "Fieldwork is a fictional creative studio built for this production-engine demonstration. The sample explores a warm, editorial website system with a concise offering narrative and a working enquiry flow.",
        "hero_alt": "Illustrated terracotta vessels on a warm ivory plinth — fictional sample artwork",
        "meta_description": "Fieldwork is a fictional studio demonstration: objects, spaces and creative direction.",
    }.items()],
}

SHOPIFY_BRIEF = {
    "brand_name": "Still Objects — Shopify demo", "website_type": "FULL_ECOMMERCE_STORE", "target": "SHOPIFY", "demo": True,
    "instructions": "Fictional Shopify adapter test. Do not invent products, prices, reviews or availability. Bind commerce to native Shopify data.",
    "goals": "Exercise a real native Liquid theme, validation and honest remote QA blockers", "offerings": [],
    "palette": ["#f5f2ec", "#312c27", "#704b36"], "functionality": ["products", "variants", "cart", "checkout", "search", "contact form"],
    "content": [{"id": "hero_heading", "text": "Objects, thoughtfully placed.", "permission": "SUPPLIED"}, {"id": "hero_body", "text": "A fictional storefront direction. Real product data belongs to the connected Shopify store.", "permission": "SUPPLIED"}, {"id": "cta_label", "text": "Explore the collection", "permission": "SUPPLIED"}],
}


def sample_art():
    image = Image.new("RGB", (1200, 1400), "#dcd6c9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 960, 1200, 1400), fill="#b5b4a4")
    draw.polygon([(170, 1030), (1040, 1030), (1160, 1170), (50, 1170)], fill="#e5dfd1")
    draw.rectangle((50, 1170, 1160, 1400), fill="#c9c1af")
    draw.ellipse((205, 1020, 615, 1120), fill="#b1a18d")
    draw.ellipse((690, 1040, 1060, 1130), fill="#b1a18d")
    draw.rounded_rectangle((255, 610, 580, 1060), radius=95, fill="#a66c4c")
    draw.polygon([(255, 730), (580, 730), (548, 515), (286, 515)], fill="#a66c4c")
    draw.ellipse((286, 487, 548, 550), fill="#875038")
    draw.ellipse((301, 504, 533, 538), fill="#473b2d")
    draw.rounded_rectangle((717, 790, 1020, 1080), radius=100, fill="#7e8b66")
    draw.ellipse((725, 755, 1012, 830), fill="#63764e")
    draw.ellipse((748, 777, 990, 810), fill="#363f2a")
    draw.line((865, 770, 831, 310), fill="#485842", width=10)
    draw.line((830, 350, 734, 280), fill="#485842", width=6)
    draw.ellipse((685, 223, 780, 292), fill="#657751")
    draw.ellipse((807, 231, 861, 363), fill="#526a43")
    raw = io.BytesIO(); image.save(raw, "WEBP", quality=90)
    return raw.getvalue()


def add_reference_fixture(engine, project_id):
    p = engine.store.get(project_id)
    ref_id = uid("fixture_ref_")
    source = '<!doctype html><html lang="en"><head><title>Fictional composition evidence</title><style>body{margin:60px;background:#eee9df;color:#233020}h1{font:90px Georgia;max-width:700px}section{padding:70px 0;border-top:1px solid}</style></head><body><header>Reference fixture</header><main><h1>Editorial composition</h1><section><h2>Clear hierarchy</h2><p>Reference copy is evidence only; it must never enter the generated target website.</p></section></main></body></html>'
    engine.store.artifact(project_id, f"evidence/{ref_id}/source.html", source)
    ref = {"id": ref_id, "source_url": "https://reference.example.invalid/", "timestamp": now(), "kind": "REFERENCE", "fixture": True, "role": "composition", "requested_role": "composition", "role_confidence": "HIGH", "status": "OBSERVED", "title": "Fictional local reference fixture", "observations": [{"observation": "A local fixture HTML document uses one primary heading and a distinct narrative section", "confidence": "HIGH", "method": "Direct local HTML fixture parsing", "source": f"evidence/{ref_id}/source.html"}], "pages": [], "capture": {"status": "NOT_APPLICABLE", "reason": "Local deterministic HTML evidence fixture, not a fetched live website", "captures": []}, "principles": [{"reference_observation": "A leading heading establishes a clear narrative opening", "principle": "Use an editorial typographic entry", "brand_interpretation": "Target brand's authorized copy leads the composition", "implementation": "Approved heading tokens and supplied hero image", "confidence": "HIGH", "source": "Explicit local fixture"}]}
    p["evidence"].append(ref)
    engine.store.artifact(project_id, f"evidence/{ref_id}/reference.json", ref)
    engine.store.save(p, ("REFERENCE_FIXTURE_INGESTED", {"id": ref_id, "fixture": True}), "Reference Analyst")


def seed(engine, all_stages=False):
    ids = []
    for brief in [CUSTOM_BRIEF, SHOPIFY_BRIEF]:
        existing = next((p for p in engine.store.list() if p["fixture"] and p["name"] == brief["brand_name"]), None)
        if existing:
            ids.append(existing["id"]); continue
        p = engine.create(Brief.model_validate(brief))
        ids.append(p["id"])
        ingest(engine.store, p["id"], "fictional-vessels-hero.webp", sample_art(), "hero", exact=True, restrictions="Generated fictional test artwork; not a real product photograph")
        if brief["target"] == "CUSTOM_WEB":
            add_reference_fixture(engine, p["id"])
        engine.discover(p["id"])
        if all_stages:
            p = engine.store.get(p["id"])
            engine.review(p["id"], Review(action="REVISE", version=p["active_design"], feedback="The hero image is too large. Keep all other decisions."))
            p = engine.store.get(p["id"])
            engine.review(p["id"], Review(action="KEEP", version=p["active_design"], feedback="Automated fixture-only Gate 2 approval; no customer project authority"))
            p = engine.produce(p["id"])
            if p["stage"] == "FINAL_REVIEW":
                engine.final_approve(p["id"], p["release_candidate"]["build_id"])
    return {"fixture_project_ids": ids, "automated_approvals": "Only when --all-stages is explicitly requested; only fictional fixture projects", "projects": [{"id": i, "stage": engine.store.get(i)["stage"]} for i in ids]}

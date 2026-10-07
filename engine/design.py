import re
from .store import now, digest


def classify(brief):
    text = " ".join([brief["instructions"], brief["goals"], *brief["functionality"]]).lower()
    kind = brief["website_type"]
    if kind == "AUTO":
        if any(w in text for w in ["ecommerce", "e-commerce", "online store", "checkout", "sell products"]):
            kind = "FULL_ECOMMERCE_STORE"
        elif any(w in text for w in ["portfolio", "showcase work"]):
            kind = "PORTFOLIO"
        elif any(w in text for w in ["landing page", "campaign"]):
            kind = "LANDING_PAGE"
        elif any(w in text for w in ["service", "consulting", "booking"]):
            kind = "SERVICE_WEBSITE"
        else:
            kind = "BRAND_WEBSITE"
    target = brief["target"]
    commerce = kind in {"FULL_ECOMMERCE_STORE", "PRODUCT_PAGE", "COLLECTION_PAGE"}
    if target == "AUTO":
        target = "SHOPIFY" if commerce or "shopify" in text else "CUSTOM_WEB"
    scope = "FULL_REDESIGN" if kind == "EXISTING_WEBSITE_REDESIGN" else "EXTEND_EXISTING_STORE" if target == "SHOPIFY" and brief.get("current_url") and kind in {"PRODUCT_PAGE", "COLLECTION_PAGE"} else "NEW_STORE_BUILD" if target == "SHOPIFY" else "NEW_WEBSITE"
    return {"website_type": kind, "target": target, "scope": scope, "confidence": "HIGH" if brief["website_type"] != "AUTO" and brief["target"] != "AUTO" else "MEDIUM", "rationale": "Explicit brief choices take precedence; commerce uses native Shopify and other scopes use deployable Custom Web by default."}


def constitution(project):
    brief = project["brief"]
    rules = list(brief["requirements"])
    if brief["palette"]:
        rules.append({"classification": "LOCKED", "area": "palette", "text": ", ".join(brief["palette"])})
    if brief["fonts"]:
        rules.append({"classification": "LOCKED", "area": "typography", "text": ", ".join(brief["fonts"])})
    for asset in project["assets"]:
        if asset["exact"]:
            rules.append({"classification": "LOCKED", "area": "asset", "text": f"Preserve exact asset {asset['id']} ({asset['sha256']})"})
    rules.extend([
        {"classification": "FORBIDDEN", "area": "content", "text": "No invented facts, prices, reviews, testimonials or social proof"},
        {"classification": "FORBIDDEN", "area": "reference", "text": "No transfer of reference copy, logos, identity or protected imagery"},
        {"classification": "REQUIRED", "area": "accessibility", "text": "Semantic landmarks, keyboard operation, visible focus, text contrast and responsive reflow"},
    ])
    return {"version": 1, "brand": brief["brand_name"], "audience": brief["audience"], "goals": brief["goals"], "rules": rules, "instructions": brief["instructions"], "content_permissions": brief["content"], "brand_document_evidence": [{"asset": a["id"], "analysis": a.get("analysis")} for a in project["assets"] if a["role"] in {"guide", "content"}], "authority": "User requirements override engine defaults. Unknown facts are omitted.", "created_at": now()}


def sitemap(project):
    kind = project["classification"]["website_type"]
    target = project["classification"]["target"]
    brief = project["brief"]
    if target == "SHOPIFY":
        pages = [{"id": "home", "path": "/", "title": "Home", "template": "index"}]
        if kind in {"FULL_ECOMMERCE_STORE", "PRODUCT_PAGE", "EXISTING_WEBSITE_REDESIGN"}:
            pages.append({"id": "product", "path": "/products/:handle", "title": "Product", "template": "product"})
        if kind != "PRODUCT_PAGE":
            pages.append({"id": "collection", "path": "/collections/:handle", "title": "Collection", "template": "collection"})
        pages.extend([{"id": "cart", "path": "/cart", "title": "Cart", "template": "cart"}, {"id": "contact", "path": "/pages/contact", "title": "Contact", "template": "page.contact"}])
    elif kind in {"LANDING_PAGE", "PRODUCT_PAGE", "SALES_PAGE", "COLLECTION_PAGE"}:
        pages = [{"id": "home", "path": "/", "title": brief["brand_name"], "template": "primary"}]
    elif kind == "BLOG_EDITORIAL":
        pages = [{"id": "home", "path": "/", "title": "Journal", "template": "editorial"}]
    else:
        pages = [{"id": "home", "path": "/", "title": "Home", "template": "primary"}]
        if any(c["id"] == "about_body" and c["permission"] in {"SUPPLIED", "APPROVED"} for c in brief["content"]):
            pages.append({"id": "about", "path": "/about.html", "title": "About", "template": "narrative"})
        if "contact" in " ".join(brief["functionality"]).lower() or kind == "SERVICE_WEBSITE":
            pages.append({"id": "contact", "path": "/contact.html", "title": "Contact", "template": "form"})
    return {"pages": pages, "rationale": "Pages follow supplied content and scope; no filler pages added.", "preservation_inventory": [{"url": p.get("url"), "title": p.get("title"), "forms": p.get("forms", []), "metadata": p.get("metadata", [])} for e in project["evidence"] if e["kind"] == "EXISTING_SITE" for p in e.get("pages", [])], "redirects": [], "unverified_routes": [link for e in project["evidence"] if e["kind"] == "EXISTING_SITE" for link in e.get("links", [])]}


def strategy(project):
    kind = project["classification"]["website_type"]
    personality = " ".join([project["brief"]["instructions"], project["brief"]["audience"]]).lower()
    layout = "service" if kind == "SERVICE_WEBSITE" else "portfolio" if kind == "PORTFOLIO" else "commerce" if project["classification"]["target"] == "SHOPIFY" else "editorial"
    if "minimal" in personality:
        rhythm = "Restrained composition, generous negative space, functional imagery"
    else:
        rhythm = "A clear typographic opening, one structural image, and a concise narrative"
    return {"layout": layout, "narrative": rhythm, "business_goal": project["brief"]["goals"], "audience": project["brief"]["audience"], "platform_constraints": {"SHOPIFY": ["Native product forms, collections and cart; editable Liquid sections; checkout remains Shopify-owned"], "CUSTOM_WEB": ["Semantic HTML and progressively enhanced JavaScript; bundled contact service where required"], "WEBFLOW": ["Export handoff only until a Webflow publishing integration is configured"]}[project["classification"]["target"]], "reference_transfers": [principle for source in project["evidence"] for principle in source.get("principles", [])], "asset_plan": [{"id": a["id"], "role": a["role"], "exact": a["exact"]} for a in project["assets"]], "research_basis": [{"topic": r["topic"], "status": r["status"], "principle": r.get("principle"), "evidence": r.get("evidence"), "source_candidates": r.get("retrieved_sources", [])} for r in project["research"]], "content_plan": "Only supplied or approved content enters a production render. Unverified research facts are held for approval.", "anti_generic": {"status": "PASS", "checks": ["No statistics, testimonials or decorative gradients", "No repeated alternating sections", "Page scope justified by actual content", "Image composition uses supplied assets only", "Headings are supplied copy or literal brand/offer names"]}, "mode": "REFERENCE" if project["brief"]["references"] else "ORIGINAL", "designer": "Internal deterministic design system; no simulated AI reviewer output"}


def design_spec(project):
    brief = project["brief"]
    palette = brief["palette"]
    content = {c["id"]: c["text"] for c in brief["content"] if c["permission"] in {"SUPPLIED", "APPROVED"}}
    assets = project["assets"]
    hero = next((a for a in assets if a["role"] == "hero"), next((a for a in assets if a["role"] in {"photography", "product"}), None))
    logo = next((a for a in assets if a["role"] == "logo"), None)
    return {"brand": brief["brand_name"], "layout": project["strategy"]["layout"], "tokens": {"background": palette[0] if palette else "#f4f2ed", "ink": palette[1] if len(palette) > 1 else "#242922", "accent": palette[2] if len(palette) > 2 else "#4a5f42", "font": brief["fonts"][0] if brief["fonts"] else "Georgia", "body_font": brief["fonts"][1] if len(brief["fonts"]) > 1 else "Arial", "hero_scale": 1.0, "image_scale": 1.0, "section_space": 96, "image_position": "center"}, "content": content, "offerings": brief["offerings"], "pages": project["sitemap"]["pages"], "hero_asset": hero["id"] if hero else None, "logo_asset": logo["id"] if logo else None, "section_order": ["hero", "offerings", "narrative"], "target": project["classification"]["target"], "functionality": brief["functionality"], "rationale": {"hero": "Establish brand and intent using authorized headline and one clear action", "image": "Supplied structural image provides brand-specific composition" if hero else "Typography leads because no approved hero imagery was supplied", "offerings": "Literal supplied offerings clarify the business", "narrative": "Shown only if authorized narrative content exists"}}


PATCH_FIELDS = {
    "tokens.hero_scale": (float, 0.6, 1.4),
    "tokens.image_scale": (float, 0.5, 1.2),
    "tokens.section_space": (int, 40, 160),
    "tokens.image_position": (str, ["center", "top", "bottom", "left", "right"], None),
    "tokens.background": (str, "color", None),
    "tokens.ink": (str, "color", None),
    "tokens.accent": (str, "color", None),
    "tokens.font": (str, "font", None),
    "tokens.body_font": (str, "font", None),
}


def critique(project, spec):
    content = spec["content"]
    permitted = {c["id"]: c["text"] for c in project["brief"]["content"] if c["permission"] in {"SUPPLIED", "APPROVED"}}
    checks = [
        {"check": "Authorized content", "pass": content == permitted, "evidence": list(content)},
        {"check": "Justified composition", "pass": spec["layout"] in {"editorial", "service", "portfolio", "commerce"} and bool(spec["rationale"]["hero"]), "evidence": spec["rationale"]},
        {"check": "No unapproved imagery", "pass": all(asset is None or any(a["id"] == asset and a["approved_role"] for a in project["assets"]) for asset in [spec["hero_asset"], spec["logo_asset"]]), "evidence": [spec["hero_asset"], spec["logo_asset"]]},
        {"check": "No repetitive section/card rhythm", "pass": len(spec["section_order"]) == len(set(spec["section_order"])), "evidence": spec["section_order"]},
        {"check": "Brand palette respected", "pass": not project["brief"]["palette"] or spec["tokens"]["background"] == project["brief"]["palette"][0], "evidence": spec["tokens"]["background"]},
        {"check": "No generated social proof fields", "pass": not any(key.startswith(("generated_testimonial", "generated_stat", "generated_award")) for key in content), "evidence": "Renderer has no synthetic social-proof content path"},
    ]
    return {"status": "PASS" if all(c["pass"] for c in checks) else "FAIL", "checks": checks, "method": "Deterministic pre-review design/authority critique; external artistic critique is optional"}


def feedback_patches(feedback, current):
    text = feedback.lower()
    patches = {}
    tasks = []
    if "hero" in text and any(w in text for w in ["image", "photo"]):
        if any(w in text for w in ["too large", "too big", "smaller", "reduce"]):
            patches["tokens.image_scale"] = max(0.5, round(current["tokens"]["image_scale"] - .12, 2))
        elif any(w in text for w in ["too small", "larger", "bigger"]):
            patches["tokens.image_scale"] = min(1.2, round(current["tokens"]["image_scale"] + .12, 2))
        tasks.append({"target": "hero.image", "request": feedback, "status": "PATCHED" if patches else "NEEDS_INTERPRETATION"})
    if any(w in text for w in ["headline", "heading", "hero text"]):
        if any(w in text for w in ["smaller", "too big", "too large"]):
            patches["tokens.hero_scale"] = max(.6, round(current["tokens"]["hero_scale"] - .1, 2))
        elif any(w in text for w in ["bigger", "larger", "more impact"]):
            patches["tokens.hero_scale"] = min(1.4, round(current["tokens"]["hero_scale"] + .1, 2))
        tasks.append({"target": "hero.typography", "request": feedback, "status": "PATCHED" if "tokens.hero_scale" in patches else "NEEDS_INTERPRETATION"})
    if any(w in text for w in ["spacing", "space"]):
        if any(w in text for w in ["less", "reduce", "tighter"]):
            patches["tokens.section_space"] = max(40, current["tokens"]["section_space"] - 16)
        elif any(w in text for w in ["more", "increase"]):
            patches["tokens.section_space"] = min(160, current["tokens"]["section_space"] + 16)
        tasks.append({"target": "section.spacing", "request": feedback, "status": "PATCHED" if "tokens.section_space" in patches else "NEEDS_INTERPRETATION"})
    # Split free-form multi-section feedback into explicit responsibilities; unsupported
    # transformations remain pending rather than falsely claiming they were applied.
    for target in ["product", "faq", "header", "navigation", "footer", "palette", "motion"]:
        if target in text:
            tasks.append({"target": target, "request": feedback, "status": "NEEDS_INTERPRETATION"})
    if not tasks and feedback.strip():
        tasks.append({"target": "direction", "request": feedback, "status": "NEEDS_INTERPRETATION"})
    return patches, tasks


def apply_patches(spec, patches, project):
    import copy
    result = copy.deepcopy(spec)
    palette_locked = bool(project["brief"]["palette"]) or any(r["classification"] == "LOCKED" and r["area"] == "palette" for r in project["constitution"]["rules"])
    fonts_locked = bool(project["brief"]["fonts"])
    for field, value in patches.items():
        if field not in PATCH_FIELDS:
            raise ValueError(f"Unsupported patch field: {field}. Use a scoped revision rather than rewriting the approved design.")
        expected, lower, upper = PATCH_FIELDS[field]
        if expected in {int, float}:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lower <= value <= upper:
                raise ValueError(f"{field} must be between {lower} and {upper}")
            if expected is int and not isinstance(value, int):
                raise ValueError(f"{field} must be an integer")
        elif lower == "color":
            if palette_locked:
                raise ValueError("The brand palette is locked by the brief")
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError("Color must be a six-digit hex value")
        elif lower == "font":
            if fonts_locked:
                raise ValueError("Brand fonts are locked by the brief")
            if not isinstance(value, str) or not re.fullmatch(r"[\w ,.-]{1,100}", value):
                raise ValueError("Invalid font family")
        elif value not in lower:
            raise ValueError("Unsupported patch value")
        group, key = field.split(".")
        result[group][key] = value
    return result

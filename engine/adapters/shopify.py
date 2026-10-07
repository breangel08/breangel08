"""Native Shopify implementation; local validation never implies live installability."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from .base import ProductionAdapter
from ..render import asset_copy, css, SITE_JS


LAYOUT = '''<!doctype html>
<html lang="{{ request.locale.iso_code }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title | escape }}{% unless page_title contains shop.name %} · {{ shop.name | escape }}{% endunless %}</title>
<link rel="canonical" href="{{ canonical_url }}">
{% if page_description %}<meta name="description" content="{{ page_description | escape }}">{% endif %}
<meta property="og:title" content="{{ page_title | escape }}">
<meta property="og:url" content="{{ canonical_url }}">
{{ 'site.css' | asset_url | stylesheet_tag }}
<script src="{{ 'site.js' | asset_url }}" defer="defer"></script>
{{ content_for_header }}
</head>
<body>
<a class="skip" href="#main">{{ 'general.skip' | t }}</a>
<div class="wrap">{% section 'header' %}<main id="main">{{ content_for_layout }}</main>{% section 'footer' %}</div>
</body></html>
'''


def schema(code, name, settings=None, blocks=None, preset=False):
    value = {"name": name, "settings": settings or []}
    if blocks:
        value["blocks"] = blocks
    if preset:
        value["presets"] = [{"name": name}]
    return code + "\n{% schema %}\n" + json.dumps(value, indent=2) + "\n{% endschema %}\n"


HEADER = schema('''<header class="site-header">
<a class="wordmark" href="{{ routes.root_url }}">{% if section.settings.logo %}{{ section.settings.logo | image_url: width: 280 | image_tag: width: 140, alt: shop.name }}{% else %}{{ shop.name | escape }}{% endif %}</a>
<button class="menu-toggle" type="button" aria-controls="site-nav" aria-expanded="false">{{ 'general.menu' | t }}</button>
<nav class="site-nav" id="site-nav" aria-label="{{ 'general.navigation' | t }}">
{% for link in section.settings.menu.links %}<a href="{{ link.url }}"{% if link.current %} aria-current="page"{% endif %}>{{ link.title | escape }}</a>{% endfor %}
<a href="{{ routes.search_url }}">{{ 'general.search' | t }}</a>
<a href="{{ routes.cart_url }}">{{ 'cart.title' | t }} ({{ cart.item_count }})</a>
{% if shop.customer_accounts_enabled %}<a href="{{ routes.account_url }}">{{ 'general.account' | t }}</a>{% endif %}
</nav></header>''', "Header", [{"type": "image_picker", "id": "logo", "label": "Logo"}, {"type": "link_list", "id": "menu", "label": "Navigation", "default": "main-menu"}])

FOOTER = schema('''<footer class="site-footer"><span>{{ shop.name | escape }}</span><nav aria-label="{{ 'general.footer' | t }}">{% for link in section.settings.menu.links %}<a href="{{ link.url }}">{{ link.title | escape }}</a> {% endfor %}</nav>
{% if localization.available_languages.size > 1 %}{% form 'localization' %}<label for="FooterLanguage">{{ 'general.language' | t }}</label><select id="FooterLanguage" name="locale_code">{% for language in localization.available_languages %}<option value="{{ language.iso_code }}"{% if language.iso_code == localization.language.iso_code %} selected{% endif %}>{{ language.endonym_name | escape }}</option>{% endfor %}</select><button type="submit">{{ 'general.apply' | t }}</button>{% endform %}{% endif %}
</footer>''', "Footer", [{"type": "link_list", "id": "menu", "label": "Footer menu", "default": "footer"}])

HERO = schema('''<section class="hero{% unless section.settings.image %} no-image{% endunless %}"><div><h1>{{ section.settings.heading | escape }}</h1>{% if section.settings.body != blank %}<p>{{ section.settings.body | escape }}</p>{% endif %}{% if section.settings.link != blank and section.settings.label != blank %}<a class="button" href="{{ section.settings.link }}">{{ section.settings.label | escape }}</a>{% endif %}</div>{% if section.settings.image %}{{ section.settings.image | image_url: width: 1800 | image_tag: class: 'hero-image', loading: 'eager', fetchpriority: 'high', widths: '400,800,1200,1800', sizes: '(max-width: 700px) 88vw, 44vw' }}{% endif %}</section>''', "Approved hero", [{"type": "text", "id": "heading", "label": "Approved heading"}, {"type": "textarea", "id": "body", "label": "Approved supporting copy"}, {"type": "image_picker", "id": "image", "label": "Approved image"}, {"type": "text", "id": "label", "label": "Button label"}, {"type": "url", "id": "link", "label": "Button destination"}], preset=True)

NARRATIVE = schema('''{% if section.settings.body != blank %}<section class="narrative"><h2>{{ section.settings.heading | escape }}</h2><p>{{ section.settings.body | escape }}</p></section>{% endif %}''', "Approved narrative", [{"type": "text", "id": "heading", "label": "Heading"}, {"type": "textarea", "id": "body", "label": "Approved copy"}], preset=True)

CARD = '''{% doc %}
Renders a native product card.
@param {product} product - Product object
{% enddoc %}
<article class="product-card"><a href="{{ product.url }}">{% if product.featured_image %}{{ product.featured_image | image_url: width: 900 | image_tag: loading: 'lazy', widths: '300,600,900', sizes: '(max-width: 700px) 44vw, 28vw' }}{% endif %}<h3>{{ product.title | escape }}</h3><p>{{ product.price | money }}{% if product.compare_at_price > product.price %} <s>{{ product.compare_at_price | money }}</s>{% endif %}</p>{% unless product.available %}<span>{{ 'products.sold_out' | t }}</span>{% endunless %}</a></article>
'''

COLLECTION = schema('''<section class="form-page"><h1>{{ collection.title | escape }}</h1>{{ collection.description }}</section>{% paginate collection.products by 12 %}<div class="collection-grid">{% for product in collection.products %}{% render 'product-card', product: product %}{% else %}<p>{{ 'products.empty' | t }}</p>{% endfor %}</div>{{ paginate | default_pagination }}{% endpaginate %}''', "Collection")

FEATURED = schema('''{% if section.settings.collection != blank %}<section><h2>{{ section.settings.heading | escape }}</h2><div class="collection-grid">{% for product in section.settings.collection.products limit: 6 %}{% render 'product-card', product: product %}{% endfor %}</div></section>{% endif %}''', "Featured collection", [{"type": "text", "id": "heading", "label": "Heading"}, {"type": "collection", "id": "collection", "label": "Collection"}], preset=True)

PRODUCT = schema('''<section class="product-layout"><div>{% for media in product.media %}{% case media.media_type %}{% when 'image' %}{{ media | image_url: width: 1600 | image_tag: loading: 'lazy', widths: '400,800,1200,1600', sizes: '(max-width: 700px) 88vw, 44vw' }}{% when 'video' %}{{ media | video_tag: controls: true }}{% when 'external_video' %}{{ media | external_video_tag }}{% when 'model' %}{{ media | model_viewer_tag }}{% endcase %}{% endfor %}</div><div><h1>{{ product.title | escape }}</h1><p data-product-price>{{ product.selected_or_first_available_variant.price | money }}</p>
{% form 'product', product, class: 'product-form' %}{{ form.errors | default_errors }}<label for="Variant-{{ section.id }}">{{ 'products.variant' | t }}</label><select id="Variant-{{ section.id }}" name="id" data-variant-select>{% for variant in product.variants %}<option value="{{ variant.id }}" data-price="{{ variant.price | money | escape }}" data-available="{{ variant.available }}"{% if variant == product.selected_or_first_available_variant %} selected{% endif %}{% unless variant.available %} disabled{% endunless %}>{{ variant.title | escape }}{% unless variant.available %} — {{ 'products.sold_out' | t }}{% endunless %}</option>{% endfor %}</select>
{% if product.selling_plan_groups.size > 0 %}<label for="Plan-{{ section.id }}">{{ 'products.purchase_option' | t }}</label><select id="Plan-{{ section.id }}" name="selling_plan">{% unless product.requires_selling_plan %}<option value="">{{ 'products.one_time' | t }}</option>{% endunless %}{% for group in product.selling_plan_groups %}{% for plan in group.selling_plans %}<option value="{{ plan.id }}">{{ plan.name | escape }}</option>{% endfor %}{% endfor %}</select>{% endif %}
<label for="Quantity-{{ section.id }}">{{ 'products.quantity' | t }}</label><input id="Quantity-{{ section.id }}" type="number" name="quantity" value="1" min="1"><button type="submit" name="add" class="button" data-add-button{% unless product.available %} disabled{% endunless %}>{{ 'products.add_to_cart' | t }}</button>{% endform %}<div>{{ product.description }}</div></div></section><script type="application/ld+json">{{ product | structured_data }}</script>''', "Product")

CART = schema('''<section class="form-page"><h1>{{ 'cart.title' | t }}</h1>{% if cart.item_count > 0 %}<form action="{{ routes.cart_url }}" method="post"><table class="cart-items"><thead><tr><th scope="col">{{ 'cart.product' | t }}</th><th scope="col">{{ 'products.quantity' | t }}</th><th scope="col">{{ 'cart.total' | t }}</th></tr></thead><tbody>{% for item in cart.items %}<tr><td><a href="{{ item.url }}">{{ item.product.title | escape }}</a><div>{{ item.variant.title | escape }}</div>{% if item.selling_plan_allocation %}<div>{{ item.selling_plan_allocation.selling_plan.name | escape }}</div>{% endif %}<a href="{{ item.url_to_remove }}">{{ 'cart.remove' | t }}</a></td><td><label class="visually-hidden" for="Update-{{ forloop.index }}">{{ 'products.quantity' | t }}: {{ item.title | escape }}</label><input id="Update-{{ forloop.index }}" name="updates[]" type="number" min="0" value="{{ item.quantity }}"></td><td>{{ item.final_line_price | money }}</td></tr>{% endfor %}</tbody></table><p>{{ 'cart.total' | t }}: {{ cart.total_price | money }}</p><div class="cart-actions"><button class="button" type="submit" name="update">{{ 'cart.update' | t }}</button><button class="button" type="submit" name="checkout">{{ 'cart.checkout' | t }}</button></div></form>{% else %}<p class="empty">{{ 'cart.empty' | t }}</p><a class="button" href="{{ routes.all_products_collection_url }}">{{ 'cart.continue' | t }}</a>{% endif %}</section>''', "Cart")

CONTACT = schema('''<section class="form-page"><h1>{{ page.title | escape }}</h1>{{ page.content }}{% form 'contact', class: 'contact-form' %}{% if form.posted_successfully? %}<p role="status">{{ 'contact.success' | t }}</p>{% endif %}{{ form.errors | default_errors }}<label for="ContactName">{{ 'contact.name' | t }}</label><input id="ContactName" name="contact[name]" autocomplete="name" required><label for="ContactEmail">{{ 'contact.email' | t }}</label><input id="ContactEmail" type="email" name="contact[email]" autocomplete="email" required><label for="ContactMessage">{{ 'contact.message' | t }}</label><textarea id="ContactMessage" name="contact[body]" required></textarea><button type="submit" class="button">{{ 'contact.send' | t }}</button>{% endform %}</section>''', "Contact")

PAGE = schema('''<section class="form-page"><h1>{{ page.title | escape }}</h1>{{ page.content }}</section>''', "Page")
SEARCH = schema('''<section class="form-page"><h1>{{ 'general.search' | t }}</h1><form action="{{ routes.search_url }}" method="get"><label for="SearchQuery">{{ 'general.search' | t }}</label><input id="SearchQuery" type="search" name="q" value="{{ search.terms | escape }}"><button class="button" type="submit">{{ 'general.search' | t }}</button></form></section>{% if search.performed %}{% paginate search.results by 12 %}<div class="collection-grid">{% for item in search.results %}{% if item.object_type == 'product' %}{% render 'product-card', product: item %}{% else %}<a href="{{ item.url }}">{{ item.title | escape }}</a>{% endif %}{% endfor %}</div>{{ paginate | default_pagination }}{% endpaginate %}{% endif %}''', "Search")
BLOG = schema('''<section class="form-page"><h1>{{ blog.title | escape }}</h1>{% paginate blog.articles by 12 %}{% for article in blog.articles %}<article><h2><a href="{{ article.url }}">{{ article.title | escape }}</a></h2>{{ article.excerpt }}</article>{% endfor %}{{ paginate | default_pagination }}{% endpaginate %}</section>''', "Blog")
ARTICLE = schema('''<article class="form-page"><h1>{{ article.title | escape }}</h1><time datetime="{{ article.published_at | date: '%Y-%m-%d' }}">{{ article.published_at | date: format: 'date' }}</time>{{ article.content }}</article>''', "Article")
NOT_FOUND = schema('''<section class="form-page"><h1>{{ 'general.not_found' | t }}</h1><a class="button" href="{{ routes.root_url }}">{{ 'general.home' | t }}</a></section>''', "Not found")

SHOPIFY_JS = '''
document.querySelectorAll('[data-variant-select]').forEach(select=>{const update=()=>{const option=select.selectedOptions[0];const root=select.closest('.product-layout');root.querySelector('[data-product-price]').textContent=option.dataset.price;root.querySelector('[data-add-button]').disabled=option.dataset.available!=='true';const url=new URL(location.href);url.searchParams.set('variant',option.value);history.replaceState({},'',url)};select.addEventListener('change',update);update()});
'''

LOCALES = {"general": {"skip": "Skip to content", "menu": "Menu", "navigation": "Main navigation", "footer": "Footer", "search": "Search", "account": "Account", "language": "Language", "apply": "Apply", "not_found": "Page not found", "home": "Home"}, "products": {"sold_out": "Sold out", "empty": "No products in this collection", "variant": "Choose an option", "quantity": "Quantity", "add_to_cart": "Add to cart", "purchase_option": "Purchase option", "one_time": "One-time purchase"}, "cart": {"title": "Cart", "product": "Product", "total": "Total", "remove": "Remove", "update": "Update cart", "checkout": "Checkout", "empty": "Your cart is empty", "continue": "Continue shopping"}, "contact": {"name": "Name", "email": "Email", "message": "Message", "send": "Send message", "success": "Your message has been received"}}


class ShopifyAdapter(ProductionAdapter):
    name = "SHOPIFY"
    capabilities = {"native_liquid": True, "json_templates": True, "dynamic_commerce": True, "merchant_editability": True, "local_validation": True, "remote_installation": False, "cms": "Shopify products, collections, pages, blogs and section settings", "routing": "Shopify routes", "assets": "original user files and native image bindings", "styling": "approved design-token CSS", "preview": "local prototype plus credentialed native preview required"}
    constraints = ["Live Shopify data, app compatibility, checkout, customer accounts and installation require an authenticated development store", "Prototype is not a live Shopify storefront", "Existing themes are never overwritten; extension packages require audit/merge", "Approved exact assets must be uploaded to Shopify Files and bound using the included map"]

    def build(self, project, spec, output):
        self.initialize(output)
        for folder in ["layout", "templates", "sections", "snippets", "assets", "config", "locales"]:
            (output / folder).mkdir(exist_ok=True)
        asset_map = asset_copy(project, output)
        (output / "assets/site.css").write_text(css(spec) + '\n.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}')
        (output / "assets/site.js").write_text(SITE_JS + SHOPIFY_JS)
        (output / "layout/theme.liquid").write_text(LAYOUT)
        sections = {"header": HEADER, "footer": FOOTER, "approved-hero": HERO, "approved-narrative": NARRATIVE, "featured-collection": FEATURED, "main-product": PRODUCT, "main-collection": COLLECTION, "main-cart": CART, "main-contact": CONTACT, "main-page": PAGE, "main-search": SEARCH, "main-blog": BLOG, "main-article": ARTICLE, "main-404": NOT_FOUND}
        for name, code in sections.items():
            (output / "sections" / (name + ".liquid")).write_text(code)
        (output / "snippets/product-card.liquid").write_text(CARD)
        content = spec["content"]
        home = {"hero": {"type": "approved-hero", "settings": {"heading": content.get("hero_heading", spec["brand"]), "body": content.get("hero_body", ""), "label": content.get("cta_label", ""), "link": "/collections/all" if content.get("cta_label") else ""}}}
        if spec["hero_asset"]:
            path = asset_map[spec["hero_asset"]]
            home["hero"]["settings"]["image"] = "shopify://shop_images/" + Path(path).name
        if content.get("about_body"):
            home["narrative"] = {"type": "approved-narrative", "settings": {"heading": content.get("about_heading", "About " + spec["brand"]), "body": content["about_body"]}}
        (output / "templates/index.json").write_text(json.dumps({"sections": home, "order": list(home)}, indent=2))
        for template, section in {"product": "main-product", "collection": "main-collection", "cart": "main-cart", "page": "main-page", "page.contact": "main-contact", "search": "main-search", "blog": "main-blog", "article": "main-article", "404": "main-404"}.items():
            (output / "templates" / (template + ".json")).write_text(json.dumps({"sections": {"main": {"type": section, "settings": {}}}, "order": ["main"]}, indent=2))
        (output / "locales/en.default.json").write_text(json.dumps(LOCALES, indent=2))
        (output / "config/settings_schema.json").write_text(json.dumps([{"name": "theme_info", "theme_name": "Production Studio", "theme_version": self.version, "theme_author": "Website Production Studio", "theme_documentation_url": "https://shopify.dev/docs/storefronts/themes", "theme_support_url": "https://shopify.dev/docs/storefronts/themes"}], indent=2))
        settings = {"current": {"sections": {"header": {"type": "header", "settings": {"menu": "main-menu"}}, "footer": {"type": "footer", "settings": {"menu": "footer"}}}}}
        if spec["logo_asset"]:
            settings["current"]["sections"]["header"]["settings"]["logo"] = "shopify://shop_images/" + Path(asset_map[spec["logo_asset"]]).name
        (output / "config/settings_data.json").write_text(json.dumps(settings, indent=2))
        # Keep integration notes outside the theme ZIP to avoid non-native files.
        manifest = {"adapter": self.name, "version": self.version, "scope": project["classification"]["scope"], "remote_installation": "NOT_CONFIGURED", "asset_bindings": [{"asset_id": aid, "file": path, "shopify_file": "shopify://shop_images/" + Path(path).name, "required_action": "Upload original to Shopify Files; verify assigned binding"} for aid, path in asset_map.items()], "preserve_existing": project["sitemap"]["preservation_inventory"], "data_bindings": ["product", "collection", "cart", "shop", "routes", "localization", "blog", "article", "section.settings"], "deploy": "Push to an unpublished development theme with Shopify CLI. Upload/bind originals, test products/variants/cart/forms/customer accounts/editor and app integrations, then request final release approval. Never publish automatically."}
        (output.parent / "shopify-handoff.json").write_text(json.dumps(manifest, indent=2))
        return output

    def validate(self, output):
        issues = []
        for name in ["layout/theme.liquid", "templates/index.json", "templates/product.json", "templates/cart.json", "config/settings_schema.json", "locales/en.default.json"]:
            if not (output / name).is_file():
                issues.append({"file": name, "message": "Required native theme file missing"})
        for path in output.rglob("*.json"):
            try:
                value = json.loads(path.read_text())
                if path.parent.name == "templates":
                    if not isinstance(value.get("sections"), dict) or set(value.get("order", [])) != set(value["sections"]):
                        raise ValueError("Template sections/order do not match")
                    for section in value["sections"].values():
                        if not (output / "sections" / (section["type"] + ".liquid")).exists():
                            raise ValueError("Template references missing section")
            except (ValueError, KeyError, TypeError) as error:
                issues.append({"file": str(path.relative_to(output)), "message": str(error)})
        for path in (output / "sections").glob("*.liquid"):
            try:
                match = re.search(r"{%\s*schema\s*%}(.*?){%\s*endschema\s*%}", path.read_text(), re.S)
                if not match:
                    raise ValueError("Section schema missing")
                value = json.loads(match.group(1))
                ids = [s["id"] for s in value.get("settings", [])]
                if len(ids) != len(set(ids)):
                    raise ValueError("Duplicate section setting ID")
            except (ValueError, KeyError) as error:
                issues.append({"file": str(path.relative_to(output)), "message": str(error)})
        for path in output.rglob("*.liquid"):
            for asset in re.findall(r"'([^']+)'\s*\|\s*asset_url", path.read_text()):
                if not (output / "assets" / asset).exists():
                    issues.append({"file": path.name, "message": f"Missing asset: {asset}"})
            for key in re.findall(r"'([^']+)'\s*\|\s*t\b", path.read_text()):
                node = LOCALES
                try:
                    for part in key.split("."):
                        node = node[part]
                except KeyError:
                    issues.append({"file": path.name, "message": f"Missing locale key: {key}"})
        root = Path(__file__).resolve().parents[2]
        validator = root / "tools/shopify/validate.mjs"
        validation = {"status": "BLOCKED", "reason": "Official Shopify theme validator dependencies are not installed"}
        if (root / "tools/shopify/node_modules/@shopify/theme-check-common").exists():
            files = ",".join(str(p.relative_to(output)) for p in sorted(output.rglob("*")) if p.is_file())
            try:
                proc = subprocess.run(["node", str(validator), "--theme-path", str(output.resolve()), "--files", files], capture_output=True, text=True, timeout=60)
                validation = {"status": "PASS" if proc.returncode == 0 else "FAIL", "output": (proc.stdout + proc.stderr)[-15000:], "method": "Official Shopify theme-check skill validator"}
            except subprocess.TimeoutExpired:
                validation = {"status": "BLOCKED", "reason": "Official validator timed out; cannot assert syntax/schema PASS"}
        status = "FAIL" if issues or validation["status"] == "FAIL" else validation["status"]
        return {"status": status, "method": "Native file/schema/binding checks plus official theme-check", "issues": issues, "theme_check": validation, "remote_installation": {"status": "BLOCKED", "reason": "Authenticated Shopify development store is not configured"}}

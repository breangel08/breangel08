"""A shared design renderer provides review prototypes; adapters own production."""
import html
import json
import re
import shutil
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True)


def filename(page):
    return "index.html" if page["id"] == "home" else page["id"] + ".html"


def css(spec):
    t = spec["tokens"]
    return f""":root{{--paper:{t['background']};--ink:{t['ink']};--accent:{t['accent']};--space:{t['section_space']}px;--heading:'{t['font']}',Georgia,serif;--body:'{t['body_font']}',Arial,sans-serif;--scale:{t['hero_scale']};--image-scale:{t['image_scale']}}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;color:var(--ink);background:var(--paper);font-family:var(--body);line-height:1.6}}a{{color:inherit;text-underline-offset:5px}}button,input,textarea,select{{font:inherit}}button,a,input,textarea,select{{outline-offset:5px}}:focus-visible{{outline:3px solid var(--accent)}}img{{display:block;max-width:100%;height:auto}}.skip{{position:absolute;top:-100px;left:15px;background:var(--ink);color:var(--paper);padding:14px;z-index:99}}.skip:focus{{top:10px}}.wrap{{max-width:1440px;margin:auto;padding:0 6vw}}.site-header{{min-height:104px;display:flex;align-items:center;justify-content:space-between;gap:30px;border-bottom:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}}.wordmark{{text-decoration:none;font-size:24px;font-weight:700;letter-spacing:-1px}}.wordmark img{{width:140px;max-height:70px;object-fit:contain}}.site-nav{{display:flex;align-items:center;gap:30px}}.site-nav a{{font-size:14px;text-decoration:none;min-height:44px;display:flex;align-items:center}}.menu-toggle{{display:none;min-height:44px;background:none;border:1px solid var(--ink);padding:8px 14px}}main{{min-height:65vh}}.hero{{display:grid;grid-template-columns:1.05fr 1fr;gap:6vw;align-items:center;padding:var(--space) 0}}.hero.no-image{{grid-template-columns:1fr;max-width:1100px}}.hero h1{{font-family:var(--heading);font-size:calc(clamp(46px,6.5vw,100px) * var(--scale));font-weight:400;line-height:1.04;letter-spacing:-.045em;margin:0 0 30px}}.hero p{{max-width:440px;font-size:17px;line-height:1.75;margin:0 0 32px}}.hero-image{{width:calc(100% * var(--image-scale));max-width:100%;justify-self:end;aspect-ratio:4/5;object-fit:cover;object-position:{t['image_position']}}}.hero-image-contain{{object-fit:contain}}.button{{display:inline-flex;align-items:center;justify-content:center;gap:20px;min-height:48px;padding:13px 25px;background:var(--ink);color:var(--paper);border:1px solid var(--ink);text-decoration:none;cursor:pointer;font-size:14px}}.button:hover{{background:var(--accent);border-color:var(--accent)}}.eyebrow{{text-transform:uppercase;font-size:11px;letter-spacing:.15em;margin-bottom:24px}}.offerings{{display:grid;grid-template-columns:1fr 2fr;border-top:1px solid color-mix(in srgb,var(--ink) 22%,transparent);padding:50px 0;gap:40px}}h2{{font-family:var(--heading);font-size:clamp(30px,4vw,52px);line-height:1.15;font-weight:400;margin:0 0 24px;letter-spacing:-.025em}}.offering-list{{list-style:none;margin:0;padding:0}}.offering-list li{{padding:20px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 15%,transparent);font-size:22px;display:flex;justify-content:space-between}}.narrative{{max-width:900px;padding:var(--space) 0;margin-left:auto}}.narrative p{{font-size:19px;max-width:650px;white-space:pre-line}}.site-footer{{padding:38px 0;border-top:1px solid color-mix(in srgb,var(--ink) 22%,transparent);display:flex;justify-content:space-between;gap:24px;font-size:13px}}.contact-form{{max-width:650px;display:grid;gap:16px}}.contact-form label{{display:grid;gap:7px;font-size:14px}}input,textarea,select{{border:1px solid color-mix(in srgb,var(--ink) 45%,transparent);border-radius:0;background:var(--paper);color:var(--ink);padding:12px;min-height:46px;width:100%}}.contact-form textarea{{min-height:150px}}.form-status{{min-height:24px}}.form-page{{padding:var(--space) 0;max-width:850px}}.gallery{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:35px;padding:30px 0 var(--space)}}.gallery img{{width:100%;aspect-ratio:4/3;object-fit:cover}}.product-layout{{display:grid;grid-template-columns:1fr 1fr;gap:6vw;padding:var(--space) 0}}.product-layout h1{{font-family:var(--heading);font-size:52px;line-height:1.1}}.product-form{{display:grid;gap:16px;max-width:440px}}.collection-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:32px;padding:36px 0 var(--space)}}.product-card img{{aspect-ratio:4/5;object-fit:cover;width:100%}}.product-card a{{text-decoration:none}}.cart-items{{width:100%;border-collapse:collapse}}.cart-items th,.cart-items td{{text-align:left;padding:15px;border-bottom:1px solid color-mix(in srgb,var(--ink) 22%,transparent)}}.cart-items input{{max-width:90px}}.cart-actions{{display:flex;gap:16px;justify-content:flex-end;margin:28px 0}}.empty{{padding:60px 0}}.service .hero{{grid-template-columns:1.25fr .8fr}}.service .hero-image{{aspect-ratio:1/1}}.portfolio .hero{{align-items:end}}.portfolio .hero-image{{aspect-ratio:3/4}}.prototype-note{{padding:10px 6vw;background:var(--ink);color:var(--paper);font-size:12px}}
@media(min-width:1600px){{.wrap{{padding:0 70px}}}}@media(max-width:1000px){{.site-nav{{gap:18px}}.hero{{gap:4vw}}.hero h1{{font-size:calc(clamp(46px,7vw,75px) * var(--scale))}}.collection-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:700px){{.wrap{{padding:0 6vw}}.site-header{{min-height:80px;position:relative}}.menu-toggle{{display:block}}.site-nav{{display:none;position:absolute;z-index:5;top:79px;left:-6vw;right:-6vw;padding:22px 6vw;background:var(--paper);border-bottom:1px solid var(--ink);flex-direction:column;align-items:flex-start}}.site-nav.open{{display:flex}}.hero,.service .hero,.product-layout{{grid-template-columns:1fr;gap:40px;padding:54px 0}}.hero h1{{font-size:calc(clamp(42px,11vw,65px) * var(--scale));margin-bottom:24px}}.hero-image{{width:calc(100% * var(--image-scale));aspect-ratio:5/4}}.hero p{{font-size:16px}}.offerings{{grid-template-columns:1fr;gap:10px;padding:36px 0}}.offering-list li{{font-size:19px}}.narrative{{padding:54px 0}}.narrative p{{font-size:17px}}.site-footer{{flex-direction:column;padding:28px 0}}.gallery{{gap:14px}}.collection-grid{{gap:18px}}.product-layout h1{{font-size:38px}}.cart-items th,.cart-items td{{padding:8px;font-size:13px}}.cart-actions{{flex-direction:column}}.form-page{{padding:54px 0}}}}@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}*{{animation:none!important;transition:none!important}}}}
"""


SITE_JS = """const toggle=document.querySelector('.menu-toggle');
toggle?.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));document.querySelector('.site-nav')?.classList.toggle('open',open)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&toggle?.getAttribute('aria-expanded')==='true'){toggle.click();toggle.focus()}});
document.querySelectorAll('.contact-form[data-endpoint]').forEach(form=>form.addEventListener('submit',async event=>{event.preventDefault();const status=form.querySelector('[role=status]');const button=form.querySelector('button');button.disabled=true;status.textContent='Sending…';try{const response=await fetch(form.dataset.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(!response.ok)throw Error('Message could not be sent. Please try again.');status.textContent='Your message has been received.';form.reset()}catch(error){status.textContent=error.message}finally{button.disabled=false}}));
"""


def asset_copy(project, output):
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for asset in project["assets"]:
        if asset["role"] not in {"hero", "logo", "photography", "product", "font"}:
            continue
        source = Path(project["_root"]) / asset["path"]
        shutil.copy2(source, assets / source.name)
        mapping[asset["id"]] = "assets/" + source.name
    return mapping


def custom_page(project, spec, page, assets, prototype=False):
    content, brand = spec["content"], esc(spec["brand"])
    links = [(filename(p), p["title"]) for p in spec["pages"] if p["id"] != "home"]
    nav = "".join(f'<a href="{esc(path)}">{esc(title)}</a>' for path, title in links)
    if not nav and spec["offerings"]:
        nav = '<a href="index.html#offerings">' + esc(content.get("offerings_heading", "Explore")) + '</a>'
    logo = f'<img src="{esc(assets[spec["logo_asset"]])}" alt="{brand}" width="140">' if spec["logo_asset"] in assets else brand
    hero_image = ""
    if spec["hero_asset"] in assets:
        a = next(a for a in project["assets"] if a["id"] == spec["hero_asset"])
        hero_image = f'<img class="hero-image" src="{esc(assets[a["id"]])}" alt="{esc(content.get("hero_alt", a["filename"].rsplit(".",1)[0].replace("-", " ")))}" width="{a.get("width",800)}" height="{a.get("height",1000)}" fetchpriority="high">'
    footer_links = "".join(f'<a href="{esc(path)}">{esc(title)}</a> ' for path, title in links)
    if page["id"] == "contact":
        endpoint = "" if prototype else ' data-endpoint="/api/contact"'
        form_button = ' type="button" disabled' if prototype else ' type="submit"'
        body = f'''<section class="form-page"><h1>{esc(content.get('contact_heading', 'Contact'))}</h1><p>{esc(content.get('contact_body', ''))}</p><form class="contact-form"{endpoint}><label>Name<input name="name" autocomplete="name" maxlength="200" required></label><label>Email<input type="email" name="email" autocomplete="email" maxlength="254" required></label><label>Message<textarea name="message" maxlength="10000" required></textarea></label><div hidden aria-hidden="true"><label>Leave empty<input name="website" tabindex="-1" autocomplete="off"></label></div><button class="button"{form_button}>Send message</button><p class="form-status" role="status"></p></form></section>'''
    elif page["id"] == "about":
        body = f'<section class="form-page"><h1>{esc(content.get("about_heading", "About " + spec["brand"]))}</h1><div class="narrative"><p>{esc(content.get("about_body", ""))}</p></div></section>'
    elif page["id"] != "home":
        body = f'<section class="form-page"><h1>{esc(page["title"])}</h1><p>Commerce preview uses platform data after connection. No product facts or pricing have been invented.</p></section>'
    else:
        destination = "contact.html" if any(p["id"] == "contact" for p in spec["pages"]) else "#offerings" if spec["offerings"] else "#narrative" if content.get("about_body") else None
        cta = f'<a class="button" href="{destination}">{esc(content.get("cta_label", "Get in touch" if destination == "contact.html" else "Explore"))}<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M3 13L13 3M3 3h10v10" fill="none" stroke="currentColor" stroke-width="1.2"/></svg></a>' if destination else ""
        body = f'<section class="hero {"no-image" if not hero_image else ""}" id="hero"><div><h1>{esc(content.get("hero_heading",spec["brand"]))}</h1>{"<p>"+esc(content["hero_body"])+"</p>" if content.get("hero_body") else ""}{cta}</div>{hero_image}</section>'
        if spec["offerings"]:
            body += f'<section class="offerings" id="offerings"><h2>{esc(content.get("offerings_heading", "Explore"))}</h2><ul class="offering-list">' + "".join(f'<li>{esc(item)}</li>' for item in spec["offerings"]) + '</ul></section>'
        if content.get("about_body"):
            body += f'<section class="narrative" id="narrative"><h2>{esc(content.get("about_heading", "About " + spec["brand"]))}</h2><p>{esc(content["about_body"])}</p></section>'
        if spec["layout"] == "portfolio":
            others = [a for a in project["assets"] if a["role"] == "photography" and a["id"] != spec["hero_asset"]]
            if others:
                body += '<div class="gallery">' + "".join(f'<img src="{esc(assets[a["id"]])}" alt="{esc(a["filename"].rsplit(".",1)[0])}" width="{a.get("width",800)}" height="{a.get("height",600)}" loading="lazy">' for a in others if a["id"] in assets) + '</div>'
    description = content.get("meta_description", content.get("hero_body", ""))[:300]
    title = spec["brand"] if page["id"] == "home" else f"{page['title']} · {spec['brand']}"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(description)}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><link rel="stylesheet" href="assets/site.css"><script src="assets/site.js" defer></script></head><body class="{esc(spec['layout'])}"><a class="skip" href="#main">Skip to content</a><div class="wrap"><header class="site-header"><a class="wordmark" href="index.html">{logo}</a><button class="menu-toggle" aria-expanded="false" aria-controls="site-nav" type="button">Menu</button><nav class="site-nav" id="site-nav" aria-label="Main navigation">{nav}</nav></header><main id="main">{body}</main><footer class="site-footer"><span>{brand}</span><nav aria-label="Footer">{footer_links}</nav></footer></div></body></html>'''


def render_custom(project, spec, output, prototype=False):
    output.mkdir(parents=True, exist_ok=True)
    assets = asset_copy(project, output)
    (output / "assets/site.css").write_text(css(spec))
    font_css = []
    for asset in project["assets"]:
        if asset["role"] == "font" and asset["id"] in assets:
            # Font names bind explicitly to supplied filename stems, never guessed licensing.
            name = re.sub(r"[^\w .-]", "", Path(asset["filename"]).stem)
            font_css.append(f"@font-face{{font-family:'{name}';src:url('{Path(assets[asset['id']]).name}');font-display:swap}}")
    if font_css:
        with (output / "assets/site.css").open("a") as handle:
            handle.write("\n".join(font_css))
    (output / "assets/site.js").write_text(SITE_JS)
    for page in spec["pages"]:
        (output / filename(page)).write_text(custom_page(project, spec, page, assets, prototype))
    # Do not invent a domain: canonical URLs are added during deployment configuration.
    (output / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    (output / "route-manifest.json").write_text(json.dumps({"pages": [{"path": filename(p), "title": p["title"]} for p in spec["pages"]], "canonical_status": "REQUIRES_DEPLOYMENT_DOMAIN"}, indent=2))
    return output

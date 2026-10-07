"""Bounded public-source ingestion. Reference assets never become production assets."""
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from .store import now, uid


class UnsafeURL(ValueError):
    pass


def public_address(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURL("Only public HTTP(S) URLs without credentials are permitted")
    if parsed.port not in {None, 80, 443}:
        raise UnsafeURL("Only standard public web ports are permitted")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    ips = sorted({info[4][0] for info in addresses})
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise UnsafeURL("Private, loopback, link-local and reserved destinations are blocked")
    return parsed, ips[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, ip, port):
        super().__init__(hostname, port=port, timeout=12, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_public(url, limit=2_000_000, binary=False, timeout=12):
    """Validate and pin each redirect, including configured trusted egress proxies."""
    import httpx
    context=ssl.create_default_context()
    ca=os.getenv("CODEX_PROXY_CERT") or os.getenv("SSL_CERT_FILE")
    if ca and Path(ca).is_file(): context.load_verify_locations(ca)
    proxy=os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    for _ in range(5):
        parsed,ip=public_address(url)
        port=parsed.port or (443 if parsed.scheme=="https" else 80)
        if proxy:
            # The proxy tunnels to the validated public IP; original hostname remains
            # the Host header and TLS SNI identity. No proxy DNS re-resolution.
            host=f"[{ip}]" if ":" in ip else ip
            pinned=f"{parsed.scheme}://{host}:{port}{parsed.path or '/'}"+("?"+parsed.query if parsed.query else "")
            if os.getenv("STUDIO_TRUST_EGRESS_PROXY")=="1": pinned=url
            with httpx.Client(proxy=proxy,verify=context,timeout=timeout,follow_redirects=False,trust_env=False) as client:
                request=client.build_request("GET",pinned,headers={"Host":parsed.netloc,"User-Agent":"WebsiteProductionStudio/1.0","Accept":"text/html,text/plain,application/json"},extensions={"sni_hostname":parsed.hostname})
                with client.stream("GET",pinned,headers=dict(request.headers),extensions=request.extensions) as response:
                    status=response.status_code;location=response.headers.get("location");content_type=response.headers.get("content-type","")
                    raw=b""
                    if status not in {301,302,303,307,308}:
                        for chunk in response.iter_bytes():
                            raw+=chunk
                            if len(raw)>limit: raise ValueError("Source exceeds bounded crawl size")
        else:
            conn=PinnedHTTPS(parsed.hostname,ip,port) if parsed.scheme=="https" else http.client.HTTPConnection(ip,port,timeout=timeout)
            try:
                path=(parsed.path or "/")+("?"+parsed.query if parsed.query else "")
                conn.request("GET",path,headers={"Host":parsed.netloc,"User-Agent":"WebsiteProductionStudio/1.0","Accept":"text/html,text/plain,application/json"})
                response=conn.getresponse();status=response.status;location=response.getheader("Location");content_type=response.getheader("Content-Type","")
                raw=response.read(limit+1) if status not in {301,302,303,307,308} else b""
                if len(raw)>limit: raise ValueError("Source exceeds bounded crawl size")
            finally: conn.close()
        if status in {301,302,303,307,308}:
            if not location: raise ValueError("Redirect without a location")
            url=urljoin(url,location);continue
        if status>=400: raise ValueError(f"Source returned HTTP {status}")
        if not any(t in content_type.lower() for t in (["text/","application/json","application/xhtml"] + (["image/","font/","application/font","application/octet-stream"] if binary else []))): raise ValueError("Source is not an accessible supported document")
        return {"url":url,"status":status,"content_type":content_type,"body":raw.decode("utf-8",errors="replace"),"raw":raw,"bytes":len(raw)}
    raise ValueError("Redirect limit exceeded")


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.images, self.forms, self.headings, self.meta, self.text = [], [], [], [], [], []
        self.skip, self.heading, self.title = 0, None, ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "img":
            self.images.append({key: attrs.get(key) for key in ["src", "alt", "width", "height"]})
        if tag == "form":
            self.forms.append({key: attrs.get(key) for key in ["action", "method", "id"]})
        if tag == "meta":
            self.meta.append(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = {"level": tag, "text": ""}
        if tag == "link" and attrs.get("rel") == "canonical":
            self.meta.append({"canonical": attrs.get("href")})

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
        if self.heading and tag == self.heading["level"]:
            self.headings.append(self.heading)
            self.heading = None

    def handle_data(self, value):
        if self.skip:
            return
        if self.in_title:
            self.title += value
        if self.heading:
            self.heading["text"] += value
        clean = value.strip()
        if clean:
            self.text.append(clean)


MEASURE_JS = """() => {
 const rect = el => { const r=el.getBoundingClientRect(); const c=getComputedStyle(el); return {tag:el.tagName.toLowerCase(),x:Math.round(r.x),y:Math.round(r.y+scrollY),width:Math.round(r.width),height:Math.round(r.height),font:c.fontFamily,fontSize:c.fontSize,fontWeight:c.fontWeight,lineHeight:c.lineHeight,color:c.color,background:c.backgroundColor,gap:c.gap,padding:c.padding,position:c.position,borderRadius:c.borderRadius}; };
 return {viewport:{width:innerWidth,height:innerHeight},documentHeight:document.documentElement.scrollHeight,sections:Array.from(document.querySelectorAll('header,main,section,footer,h1,h2')).slice(0,35).map(rect),interactions:{details:document.querySelectorAll('details').length,buttons:document.querySelectorAll('button').length,dialogs:document.querySelectorAll('dialog,[role=dialog]').length},overflow:document.documentElement.scrollWidth>innerWidth};
}"""


def capture_reference(url, folder):
    result = {"status": "UNAVAILABLE", "captures": [], "measurements": [], "error": None}
    try:
        from playwright.sync_api import sync_playwright
        request_count=0
        deadline=time.monotonic()+35
        def guard(route):
            nonlocal request_count
            target=route.request.url
            if target.startswith("data:"):
                route.continue_();return
            request_count+=1
            if request_count>90 or time.monotonic()>deadline or route.request.resource_type in {"media","websocket"} or route.request.method!="GET":
                route.abort();return
            try:
                source=fetch_public(target,limit=4_000_000,binary=True,timeout=6)
                route.fulfill(status=source["status"],body=source["raw"],headers={"content-type":source["content_type"],"access-control-allow-origin":"*"})
            except Exception:
                route.abort()
        with sync_playwright() as pw:
            import shutil
            browser = pw.chromium.launch(headless=True, executable_path=os.getenv("STUDIO_CHROMIUM") or shutil.which("chromium"), args=["--disable-dev-shm-usage", "--disable-crash-reporter", "--disable-breakpad"])
            try:
                context = browser.new_context(service_workers="block", accept_downloads=False)
                context.route("**/*", guard)
                for name, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
                    page = context.new_page()
                    page.set_viewport_size({"width": width, "height": height})
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(800)
                    public_address(page.url)
                    dimensions = page.evaluate("({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})")
                    # Bound untrusted page image memory; tall sources get a viewport capture.
                    page.screenshot(path=str(folder / f"{name}.png"), full_page=dimensions["height"] < 14000 and dimensions["width"] < 2500)
                    result["captures"].append(f"{name}.png")
                    result["measurements"].append(page.evaluate(MEASURE_JS))
                    if name == "desktop":
                        for i, section in enumerate(page.locator("main section").all()[:4]):
                            box = section.bounding_box()
                            if box and 0 < box["height"] < 3000 and box["width"] < 2500:
                                section.screenshot(path=str(folder / f"section-{i + 1}.png"), timeout=3000)
                                result["captures"].append(f"section-{i + 1}.png")
                    page.close()
                context.close()
                result["status"] = "CAPTURED"
            finally:
                browser.close()
    except Exception as error:
        result["error"] = str(error)[:400]
    return result


def ingest_source(store, project_id, url, role="infer", existing=False, browser=True):
    evidence_id = uid("ref_")
    folder = store.path(project_id) / "evidence" / evidence_id
    folder.mkdir(parents=True)
    evidence = {"id": evidence_id, "source_url": str(url), "timestamp": now(), "kind": "EXISTING_SITE" if existing else "REFERENCE", "requested_role": role, "role": role if role != "infer" else "composition", "role_confidence": "HIGH" if role != "infer" else "MEDIUM", "status": "UNAVAILABLE", "observations": [], "pages": [], "capture": {"status": "UNAVAILABLE", "captures": []}, "principles": [], "nontransferable": ["copy", "branding", "logos", "photography", "products", "proprietary artwork"]}
    try:
        source = fetch_public(str(url))
        store.artifact(project_id, f"evidence/{evidence_id}/source.html", source["body"])
        doc = Document()
        doc.feed(source["body"])
        origin = urlparse(source["url"]).netloc
        links = sorted({urljoin(source["url"], link).split("#")[0] for link in doc.links if not link.startswith(("mailto:", "tel:", "javascript:")) and urlparse(urljoin(source["url"], link)).netloc == origin})[:30]
        evidence.update(status="OBSERVED", title=doc.title.strip(), headings=doc.headings, metadata=doc.meta, forms=doc.forms, images=doc.images, links=links, final_url=source["url"])
        evidence["observations"] = [
            {"observation": f"{len(doc.headings)} semantic headings and {len(doc.forms)} forms observed in the initial document", "confidence": "HIGH", "method": "HTML parsing", "source": f"evidence/{evidence_id}/source.html"},
            {"observation": "Motion, hover and sticky behavior require interaction evidence; static markup alone does not establish them", "confidence": "UNKNOWN", "method": "Unmeasured"},
        ]
        for page_url in ([source["url"]] + links[:4] if existing else [source["url"]]):
            try:
                page_source = source if page_url == source["url"] else fetch_public(page_url)
                page_doc = Document()
                page_doc.feed(page_source["body"])
                index = len(evidence["pages"])
                store.artifact(project_id, f"evidence/{evidence_id}/page-{index}.html", page_source["body"])
                evidence["pages"].append({"url": page_url, "title": page_doc.title, "metadata": page_doc.meta, "headings": page_doc.headings, "forms": page_doc.forms, "content": "\n".join(page_doc.text)[:20000] if existing else None, "permission": "UNAUTHORIZED", "evidence": f"page-{index}.html", "confidence": "HIGH"})
            except Exception as error:
                evidence["pages"].append({"url": page_url, "status": "UNAVAILABLE", "error": str(error)[:300]})
        if browser:
            evidence["capture"] = capture_reference(source["url"], folder)
        measurements = evidence["capture"].get("measurements", [])
        if measurements:
            desktop = measurements[0]
            evidence["observations"].append({"observation": "Rendered section geometry, typography, spacing and responsive viewport measurements captured", "confidence": "HIGH", "method": "Browser DOM and computed styles", "measurements": desktop})
            headings = [s for s in desktop["sections"] if s["tag"] in {"h1", "h2"}]
            if headings:
                evidence["principles"].append({"reference_observation": "Measured heading hierarchy establishes the page reading order", "principle": "Use a deliberate typographic hierarchy", "brand_interpretation": "Apply hierarchy to the target brand's approved copy and fonts", "implementation": "Design token heading scale; no reference content imported", "confidence": "HIGH", "source": source["url"]})
        if not evidence["principles"] and doc.headings:
            evidence["principles"].append({"reference_observation": "Semantic headings divide the source into distinct topics", "principle": "Organize the target site's narrative with semantic sections", "brand_interpretation": "Use only topics justified by the brief", "implementation": "Platform-native sections with supplied content", "confidence": "MEDIUM", "source": source["url"]})
    except Exception as error:
        evidence["error"] = str(error)[:400]
        evidence["observations"].append({"observation": "Source unavailable; no visual facts inferred", "confidence": "UNKNOWN", "method": "Failed bounded public fetch"})
    store.artifact(project_id, f"evidence/{evidence_id}/reference.json", evidence)
    return evidence


RESEARCH_SOURCES = [
    ("Accessibility", "https://www.w3.org/WAI/WCAG22/quickref/", "Use semantic landmarks, labeled controls, keyboard focus and responsive reflow."),
    ("Performance", "https://web.dev/articles/vitals", "Measure loading, interaction and layout stability; optimize supplied images without replacing originals."),
    ("Shopify architecture", "https://shopify.dev/docs/storefronts/themes/architecture", "Use Liquid sections and JSON templates with native commerce routes."),
]


def research(store, project):
    sources = RESEARCH_SOURCES if project["classification"]["target"] == "SHOPIFY" else RESEARCH_SOURCES[:2]
    records = []
    for topic, url, principle in sources:
        record = {"topic": topic, "url": url, "timestamp": now(), "status": "NOT_FETCHED", "confidence": "UNKNOWN", "principle": principle, "basis": "Internal standards baseline until source retrieval succeeds"}
        if os.getenv("STUDIO_ENABLE_RESEARCH", "1") == "1":
            try:
                source = fetch_public(url)
                name = f"research/{uid('source_')}.html"
                store.artifact(project["id"], name, source["body"])
                record.update(status="FETCHED", confidence="HIGH", evidence=name, basis="Retrieved public standards source")
            except Exception as error:
                record.update(status="UNAVAILABLE", error=str(error)[:250])
        records.append(record)
    # Category and competitor findings are only asserted when sources were observed.
    category={"topic": "Category and competitors", "status": "OBSERVED_REFERENCES" if any(e["status"] == "OBSERVED" for e in project["evidence"]) else "NO_VERIFIED_SOURCES", "confidence": "MEDIUM" if project["evidence"] else "UNKNOWN", "principle": "Use observed source architecture and supplied offerings to identify category expectations; never assert market leadership, customer counts or unverified business facts.", "source_ids": [e["id"] for e in project["evidence"] if e["status"] == "OBSERVED"],"retrieved_sources":[]}
    if os.getenv("STUDIO_ENABLE_RESEARCH","1")=="1":
        from urllib.parse import quote
        from xml.etree import ElementTree
        topic=project["brief"]["offerings"][-1] if project["brief"]["offerings"] else project["classification"]["website_type"].replace("_"," ").lower()
        query='"'+topic+'" business website design user experience'
        url="https://www.bing.com/search?format=rss&q="+quote(query)
        category.update(query=query,search_url=url)
        try:
            search=fetch_public(url,limit=1_000_000)
            artifact=f"research/{uid('category-search_')}.xml"
            store.artifact(project["id"],artifact,search["body"])
            category.update(status="SEARCHED",confidence="MEDIUM",evidence=artifact)
            parsed=ElementTree.fromstring(search["body"])
            for item in parsed.findall("./channel/item")[:2]:
                source_url=item.findtext("link","");title=item.findtext("title","")
                observed={"url":source_url,"title":title,"status":"UNAVAILABLE","confidence":"UNKNOWN","permission":"RESEARCH_SUPPORTED"}
                try:
                    source=fetch_public(source_url)
                    doc=Document();doc.feed(source["body"])
                    name=f"research/{uid('category-source_')}.html";store.artifact(project["id"],name,source["body"])
                    keywords={word.lower() for word in re.findall(r"[a-zA-Z]{4,}",topic)}
                    heading_text=(doc.title+" "+" ".join(h["text"] for h in doc.headings)).lower()
                    hits=sum(word in heading_text for word in keywords)
                    relevance="MEDIUM" if keywords and hits>=min(2,len(keywords)) else "LOW"
                    observed.update(status="FETCHED",confidence="HIGH",evidence=name,observed_title=doc.title,headings=doc.headings[:12],forms=len(doc.forms),links=len(doc.links),relevance=relevance,interpretation="Observed source candidate only; lexical relevance does not establish direct competitor status or market leadership")
                except Exception as error: observed["error"]=str(error)[:250]
                category["retrieved_sources"].append(observed)
        except Exception as error: category["search_error"]=str(error)[:250]
    records.append(category)
    store.artifact(project["id"], "research/research.json", records)
    return records

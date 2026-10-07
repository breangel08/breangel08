"""Independent artifact-reading QA; never certifies developer assertions."""
import functools
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlparse
import httpx
from PIL import Image, ImageChops, ImageStat
from .evidence import Document
from .render import filename
from .store import digest, now, uid

VIEWPORTS = [("large-desktop",1600,1000),("laptop",1366,900),("tablet-landscape",1024,768),("tablet-portrait",768,1024),("large-mobile",430,932),("small-mobile",360,800)]
GATES = ["visual","functional","responsive","accessibility","performance","content_integrity","asset_integrity","platform_compliance"]

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

@contextmanager
def local_site(root):
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(QuietHandler,directory=str(root)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield f"http://127.0.0.1:{server.server_port}"
    finally: server.shutdown();server.server_close();thread.join(timeout=2)

def launch(pw):
    return pw.chromium.launch(headless=True,executable_path=os.getenv("STUDIO_CHROMIUM") or shutil.which("chromium"),args=["--disable-dev-shm-usage","--disable-crash-reporter","--disable-breakpad"])

def manifest(root):
    return {str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}

def compare_images(approved,actual,output):
    a,b=Image.open(approved).convert("RGB"),Image.open(actual).convert("RGB")
    original_sizes={"approved":a.size,"actual":b.size}
    if a.size!=b.size:
        if a.width!=b.width or abs(a.height-b.height)>3: return {"status":"FAIL","changed_ratio":1,"expected_size":a.size,"actual_size":b.size,"reason":"Page dimensions materially changed"}
        # Subpixel text rounding can shift a full-page capture by <=3px.
        height=max(a.height,b.height)
        def pad(image):
            result=Image.new("RGB",(image.width,height),image.getpixel((0,image.height-1)));result.paste(image,(0,0));return result
        a,b=pad(a),pad(b)
    delta=ImageChops.difference(a,b)
    threshold=delta.convert("L").point(lambda v:255 if v>24 else 0)
    ratio=ImageStat.Stat(threshold).mean[0]/255;delta.save(output)
    return {"status":"PASS" if ratio<=.008 else "FAIL","changed_ratio":round(ratio,6),"tolerance":.008,"pixel_threshold":24,"diff":output.name,"dimensions":a.size,"source_dimensions":original_sizes}

def capture_approved(root,spec,folder):
    folder.mkdir(parents=True,exist_ok=True);records=[]
    try:
        from playwright.sync_api import sync_playwright
        with local_site(root) as url,sync_playwright() as pw:
            browser=launch(pw)
            try:
                for name,width,height in VIEWPORTS:
                    page=browser.new_page(viewport={"width":width,"height":height},reduced_motion="reduce")
                    for item in spec["pages"]:
                        page.goto(f"{url}/{filename(item)}",wait_until="networkidle")
                        page.evaluate("document.fonts.ready")
                        path=folder/f"{item['id']}-{name}.png"
                        page.screenshot(path=str(path),full_page=True,mask=[page.locator(".form-status")])
                        records.append({"page":item["id"],"viewport":name,"width":width,"height":height,"file":path.name,"sha256":digest(path.read_bytes())})
                    page.close()
            finally: browser.close()
        return {"status":"PASS","timestamp":now(),"captures":records}
    except Exception as error: return {"status":"BLOCKED","reason":f"Browser capture unavailable: {str(error)[:350]}","captures":records}

CHECK_JS="""() => {
const visible=e=>!!(e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden');
const name=e=>(e.getAttribute('aria-label')||e.getAttribute('alt')||e.innerText||e.getAttribute('title')||'').trim();
return {overflow:document.documentElement.scrollWidth>innerWidth+1,
missingImageAlt:[...document.images].filter(e=>!e.hasAttribute('alt')).length,
brokenImages:[...document.images].filter(e=>!e.complete||e.naturalWidth===0).map(e=>e.getAttribute('src')),
unnamedControls:[...document.querySelectorAll('button,a')].filter(visible).filter(e=>!name(e)).length,
unlabeledFields:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(visible).filter(e=>!e.labels?.length&&!e.getAttribute('aria-label')).length,
smallTargets:[...document.querySelectorAll('button,input,select')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();return r.height<40||r.width<24}).map(e=>e.tagName),
headings:[...document.querySelectorAll('h1,h2,h3,h4')].map(e=>({level:+e.tagName.slice(1),text:e.innerText})),timing:performance.getEntriesByType('navigation')[0]?.toJSON()}; }"""

def defect(category,expected,actual,evidence=None,page="site",severity="HIGH",role=None):
    roles={"visual":"Visual QA","responsive":"Visual QA","functional":"Functional QA","accessibility":"Accessibility QA","performance":"Performance QA","content_integrity":"Content Integrity QA","asset_integrity":"Content Integrity QA","platform_compliance":"Platform Specialist"}
    return {"id":uid("d_"),"category":category,"severity":severity,"evidence":evidence or [],"expected_result":expected,"actual_result":actual,"affected_component":page,"originating_role":role or roles[category],"repair_attempts":[],"status":"OPEN","blocking":severity in {"CRITICAL","HIGH","MEDIUM"},"created_at":now()}

def contact_check(output):
    if not (output/"serve.py").exists(): return {"status":"NOT_APPLICABLE"}
    with socket.socket() as sock: sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="qa-contact-") as private:
        proc=subprocess.Popen([sys.executable,str(output/"serve.py"),"--port",str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env={**os.environ,"CONTACT_DATA_DIR":private})
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}",timeout=3,trust_env=False) as client:
                for _ in range(40):
                    try:
                        if client.get("/contact.html").status_code==200: break
                    except httpx.ConnectError: time.sleep(.05)
                ok=client.post("/api/contact",json={"name":"QA fixture","email":"qa@example.invalid","message":"Isolated automated form test"})
                bad=client.post("/api/contact",json={"email":"bad"});private_file=client.get("/messages.sqlite3")
                result={"status":"PASS" if ok.status_code==200 and bad.status_code==422 and private_file.status_code==404 else "FAIL","success_status":ok.status_code,"validation_status":bad.status_code,"private_data_status":private_file.status_code,"test_data":"Discarded after isolated test"}
        except Exception as error: result={"status":"FAIL","reason":str(error)[:300]}
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()
        return result

def run(store,project,build,adapter):
    output=store.path(project["id"])/build["path"]
    folder=store.path(project["id"])/"qa"/build["id"]/f"run-{len(build.get('qa_history',[]))+1}"
    folder.mkdir(parents=True,exist_ok=True);spec=project["design_lock"]["spec"]
    results={key:{"status":"PASS","checks":[]} for key in GATES};defects=[]
    def fail(category,expected,actual,page="site",evidence=None):
        results[category]["status"]="FAIL";defects.append(defect(category,expected,actual,evidence,page))
    def block(category,reason):
        if results[category]["status"]!="FAIL": results[category]={"status":"BLOCKED","reason":reason,"checks":results[category].get("checks",[])}
    if digest(spec)!=project["design_lock"]["sha256"]: fail("content_integrity","Immutable design lock hash","Design authority modified")
    approved_root=store.path(project["id"])/project["design_lock"]["prototype_path"]
    if manifest(approved_root)!=project["design_lock"]["prototype_manifest"]: fail("visual","Approved prototype is immutable","Prototype files modified after approval")
    for asset in project["assets"]:
        if asset["role"] not in {"hero","logo","photography","product","font"}: continue
        copied=output/"assets"/Path(asset["path"]).name
        actual=digest(copied.read_bytes()) if copied.exists() else "MISSING"
        if actual!=asset["sha256"]: fail("asset_integrity",f"Exact asset {asset['id']} checksum {asset['sha256']}",actual)
        if asset.get("readiness")=="LOW_RESOLUTION": results["asset_integrity"]["checks"].append({"asset":asset["id"],"warning":"Low-resolution source preserved exactly"})
    results["asset_integrity"]["checks"].append({"method":"SHA-256 of every production asset against intake originals"})
    permitted={c["id"]:c["text"] for c in project["brief"]["content"] if c["permission"] in {"SUPPLIED","APPROVED"}}
    if spec["content"]!=permitted: fail("content_integrity","Every content field traces to supplied/approved text","Content authority mismatch")
    results["content_integrity"]["checks"].append({"authorized_content_ids":list(permitted),"unauthorized_ids_excluded":[c["id"] for c in project["brief"]["content"] if c["permission"] not in {"SUPPLIED","APPROVED"}],"reference_content_transferred":False})
    platform=adapter.validate(output);results["platform_compliance"]={"status":platform["status"],"checks":[platform]}
    if platform["status"]=="FAIL": fail("platform_compliance","Valid native package",json.dumps(platform)[:2500])
    if platform["status"]=="BLOCKED": results["platform_compliance"]["reason"]=platform.get("reason",platform.get("theme_check",{}).get("reason","Platform validation unavailable"))
    size=sum(p.stat().st_size for p in output.rglob("*") if p.is_file());js=sum(p.stat().st_size for p in output.rglob("*.js"));css=sum(p.stat().st_size for p in output.rglob("*.css"))
    budgets={"total_bytes":12000000,"javascript_bytes":100000,"css_bytes":100000,"individual_image_bytes":3000000}
    results["performance"]["checks"].append({"total_bytes":size,"javascript_bytes":js,"css_bytes":css,"budgets":budgets})
    if size>budgets["total_bytes"] or js>budgets["javascript_bytes"] or css>budgets["css_bytes"]: fail("performance","Delivery within explicit budgets",f"total={size}, js={js}, css={css}")
    for image in (output/"assets").glob("*"):
        if image.suffix.lower() in {".png",".jpg",".jpeg",".webp",".gif"} and image.stat().st_size>budgets["individual_image_bytes"]: fail("performance","Image <= 3 MB or approved budget exception",f"Exact image {image.name}: {image.stat().st_size} bytes")
    if adapter.name=="SHOPIFY":
        reason="Native Shopify render/live commerce tests require an authenticated development store; prototype is not commerce validation."
        for gate in ["visual","functional","responsive","accessibility"]: block(gate,reason)
        block("platform_compliance","Local validation recorded; remote installation/editor/app compatibility NOT_CONFIGURED")
        results["functional"]["checks"].append({"native_contracts":["variant","quantity","selling plans","product form","cart updates","checkout","search","contact","localization"],"live_test":"NOT_CONFIGURED"})
    else:
        for page_file in output.glob("*.html"):
            doc=Document();doc.feed(page_file.read_text())
            normalized=lambda text:" ".join(text.split())
            allowed={normalized(s) for s in [*permitted.values(),*spec["offerings"],spec["brand"],"About "+spec["brand"],"Explore","Get in touch","Home","About","Contact","Name","Email","Message","Leave empty","Send message","Menu","Skip to content","↗",*[p["title"] for p in spec["pages"]],*[p["title"]+" · "+spec["brand"] for p in spec["pages"]]]}
            unexpected=[text for text in doc.text if normalized(text) not in allowed]
            if unexpected: fail("content_integrity","Rendered text traces to authorized copy or conventional labels",str(unexpected)[:1500],page_file.name)
            if not doc.title.strip(): fail("accessibility","Document title","Missing title",page_file.name)
            for link in doc.links:
                target=urlparse(link)
                if target.scheme or link.startswith("#"): continue
                dest=output/unquote(target.path)
                if not dest.is_file(): fail("functional","Internal link resolves",link,page_file.name)
                elif target.fragment and f'id="{target.fragment}"' not in dest.read_text(): fail("functional","Fragment exists",link,page_file.name)
            for image in doc.images:
                if image["src"] and not (output/image["src"]).is_file(): fail("functional","Image file resolves",image["src"],page_file.name)
        forms=contact_check(output);results["functional"]["checks"].append({"contact":forms})
        if forms["status"]=="FAIL": fail("functional","Form success/validation/private storage",str(forms))
        capture=project["design_lock"]["captures"]
        if capture["status"]!="PASS": block("visual",capture.get("reason","Approved browser captures unavailable"))
        try:
            from playwright.sync_api import sync_playwright
            with local_site(output) as url,sync_playwright() as pw:
                browser=launch(pw);axe=Path(__file__).resolve().parents[1]/"tools/shopify/node_modules/axe-core/axe.min.js"
                try:
                    for name,width,height in VIEWPORTS:
                        page=browser.new_page(viewport={"width":width,"height":height},reduced_motion="reduce");errors=[]
                        page.on("pageerror",lambda e:errors.append(str(e)))
                        for item in spec["pages"]:
                            page_name=filename(item);page.goto(f"{url}/{page_name}",wait_until="networkidle");page.evaluate("document.fonts.ready")
                            actual=folder/f"{item['id']}-{name}.png";page.screenshot(path=str(actual),full_page=True,mask=[page.locator(".form-status")])
                            baseline=next((c for c in capture.get("captures",[]) if c["page"]==item["id"] and c["viewport"]==name),None)
                            if baseline:
                                approved=store.path(project["id"])/project["design_lock"]["capture_path"]/baseline["file"]
                                if not approved.exists() or digest(approved.read_bytes())!=baseline["sha256"]: fail("visual","Approved screenshot integrity","Baseline missing/modified",page_name)
                                else:
                                    diff=compare_images(approved,actual,folder/f"diff-{item['id']}-{name}.png")
                                    results["visual"]["checks"].append({"page":page_name,"viewport":name,**diff,"actual":str(actual.relative_to(store.path(project["id"]))),"approved":str(approved.relative_to(store.path(project["id"])))})
                                    if diff["status"]=="FAIL": fail("visual","Approved composition within tolerance",str(diff),page_name,[str(actual.relative_to(store.path(project["id"])))])
                            elif capture["status"]=="PASS": fail("visual","Baseline for every page/viewport","Missing baseline",page_name)
                            checks=page.evaluate(CHECK_JS)
                            results["responsive"]["checks"].append({"page":page_name,"viewport":name,"overflow":checks["overflow"],"small_targets":checks["smallTargets"]})
                            if checks["overflow"] or checks["smallTargets"]: fail("responsive","No overflow; usable controls",str(checks),page_name)
                            if checks["brokenImages"]: fail("asset_integrity","Images render",str(checks["brokenImages"]),page_name)
                            if checks["missingImageAlt"] or checks["unnamedControls"] or checks["unlabeledFields"] or len([h for h in checks["headings"] if h["level"]==1])!=1: fail("accessibility","Named controls, image alt and one h1",str(checks),page_name)
                            if axe.exists():
                                page.add_script_tag(path=str(axe))
                                audit=page.evaluate("async () => {const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>({id:v.id,description:v.description})),passes:r.passes.length}}");results["accessibility"]["checks"].append({"page":page_name,"viewport":name,"axe":audit})
                                if audit["violations"]: fail("accessibility","No automated WCAG violations",json.dumps(audit["violations"])[:3000],page_name)
                            else: block("accessibility","axe-core not installed; limited browser checks recorded")
                            page.keyboard.press("Tab");focus=page.evaluate("({tag:document.activeElement.tagName,outline:getComputedStyle(document.activeElement).outlineStyle})")
                            if focus["outline"]=="none": fail("accessibility","Visible keyboard focus",str(focus),page_name)
                            if width<=700:
                                page.locator(".menu-toggle").click()
                                if page.locator(".menu-toggle").get_attribute("aria-expanded")!="true" or not page.locator(".site-nav").is_visible(): fail("functional","Mobile menu opens","Menu did not open",page_name)
                                page.keyboard.press("Escape")
                                if page.locator(".menu-toggle").get_attribute("aria-expanded")!="false": fail("functional","Escape closes menu","Menu stayed open",page_name)
                            results["performance"]["checks"].append({"page":page_name,"viewport":name,"local_navigation_ms":round(checks["timing"]["domContentLoadedEventEnd"],2),"scope":"Controlled local measurement, not field Core Web Vitals"})
                        if errors: fail("functional","No browser exceptions",str(errors))
                        page.close()
                finally: browser.close()
        except Exception as error:
            for gate in ["visual","responsive","accessibility","functional"]: block(gate,f"Browser QA unavailable: {str(error)[:350]}")
    report={"id":uid("qa_"),"build_id":build["id"],"timestamp":now(),"role_authority":"Independent artifact-reading QA; Developer cannot declare PASS","results":results,"defects":defects,"status":"FAIL" if any(r["status"]=="FAIL" for r in results.values()) else "BLOCKED" if any(r["status"]=="BLOCKED" for r in results.values()) else "PASS","path":str(folder.relative_to(store.path(project["id"])))}
    store.artifact(project["id"],f"{report['path']}/report.json",report);return report

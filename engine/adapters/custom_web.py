import json
from .base import ProductionAdapter
from ..render import render_custom


CONTACT_SERVER = '''#!/usr/bin/env python3
"""Production handoff server. Put behind TLS/reverse proxy; messages stay private."""
import argparse, http.server, json, os, sqlite3, time
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
PRIVATE=Path(os.environ.get("CONTACT_DATA_DIR", str(ROOT.parent / "private-contact-data"))).resolve()
if PRIVATE.is_relative_to(ROOT):
    raise RuntimeError("CONTACT_DATA_DIR must be outside the public website directory")
PRIVATE.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(PRIVATE / "messages.sqlite3") as db:
    db.execute("CREATE TABLE IF NOT EXISTS messages (created REAL, name TEXT, email TEXT, message TEXT)")
class Handler(http.server.SimpleHTTPRequestHandler):
    rate={}
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith("/api/") or any(part.startswith(".") for part in path.split("/")) or path.endswith((".py",".sqlite3")):
            self.send_error(404); return
        super().do_GET()
    def list_directory(self,path): self.send_error(404); return None
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","strict-origin-when-cross-origin")
        super().end_headers()
    def do_POST(self):
        if self.path!="/api/contact": self.send_error(404); return
        origin=self.headers.get("Origin")
        if origin and urlparse(origin).netloc!=self.headers.get("Host"): self.send_error(403); return
        ip=self.client_address[0]; stamp=time.time()
        recent=[t for t in self.rate.get(ip,[]) if stamp-t<60]
        if len(recent)>=5: self.send_error(429); return
        self.rate[ip]=recent+[stamp]
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<16000: raise ValueError()
            data=json.loads(self.rfile.read(length))
            if data.get("website"): self.send_response(200); self.end_headers(); self.wfile.write(b'{}'); return
            name,email,message=[str(data.get(key,"")).strip() for key in ("name","email","message")]
            if not name or len(name)>200 or "@" not in email or len(email)>254 or not message or len(message)>10000: raise ValueError()
            with sqlite3.connect(PRIVATE / "messages.sqlite3") as db:
                db.execute("INSERT INTO messages VALUES(?,?,?,?)",(stamp,name,email,message))
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b'{"received":true}')
        except (ValueError,TypeError): self.send_error(422)
    def log_message(self,format,*args): pass
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,default=8080);parser.add_argument("--host",default="127.0.0.1");args=parser.parse_args()
    http.server.ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
'''


class CustomWebAdapter(ProductionAdapter):
    name = "CUSTOM_WEB"
    capabilities = {"semantic_pages": True, "responsive": True, "contact": True, "dynamic_commerce": False, "authentication": False, "cms": "source-controlled authorized content", "preview": "local HTTP", "assets": "exact originals", "routing": "file-based", "styling": "design tokens and component CSS", "interactions": "progressive enhancement"}
    constraints = ["Complex web app/authentication requirements require a specialized extension", "Canonical domain and external services configured at deployment", "Contact messages are stored locally, email delivery is not configured"]

    def build(self, project, spec, output):
        render_custom(project, spec, output, prototype=False)
        if any(p["id"] == "contact" for p in spec["pages"]):
            (output / "serve.py").write_text(CONTACT_SERVER)
        (output / "DEPLOYMENT.md").write_text("# Custom Web handoff\n\nServe this directory over HTTPS. For the contact page run `python serve.py --port 8080` behind a TLS reverse proxy. Contact data lives outside the public directory (CONTACT_DATA_DIR). Email forwarding, domain/canonical configuration and hosting credentials are external deployment steps. Do not serve the private message database.\n\nPreview: `python -m http.server 8080` for sites without contact; otherwise use the bundled server.\n")
        return output

    def validate(self, output):
        issues = []
        for page in output.glob("*.html"):
            content = page.read_text()
            if '<main id="main">' not in content or '<html lang="en">' not in content:
                issues.append({"file": page.name, "message": "Missing semantic or language markup"})
        if not (output / "index.html").exists():
            issues.append({"file": "index.html", "message": "Missing primary page"})
        return {"status": "FAIL" if issues else "PASS", "method": "Static adapter contract validation", "issues": issues}

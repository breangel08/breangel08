"""Network startup refuses to expose the Studio without authentication."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if len(os.getenv('STUDIO_TOKEN', '')) < 32:
    raise SystemExit('Set STUDIO_TOKEN in hosting Secrets to a random value of at least 32 characters before starting.')
import uvicorn
uvicorn.run('studio.app:app', host='0.0.0.0', port=int(os.getenv('PORT', '8000')), workers=1, proxy_headers=True)

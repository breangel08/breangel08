# Replit development preview

Import the existing source archive into a Python-capable Replit project. Do not regenerate the application from a prompt. Use Python 3.12 or newer and Node for local Shopify validation.

In the Replit Shell, install dependencies:

```
python -m pip install -e .
npm ci --prefix tools/shopify
python -m playwright install --with-deps chromium
```

Browser installation needs supported Linux system libraries; if the host prohibits this, rendered QA must remain BLOCKED rather than pass. Leave STUDIO_CHROMIUM unset to use Playwright's installed Chromium, unless the host provides its own browser executable.

Set STUDIO_TOKEN in Replit Secrets to a random value of at least 32 characters. Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`; never commit or share it in chat. Set STUDIO_DATA_DIR to an absolute writable project directory if overriding the default. Optional Claude configuration belongs only in Secrets.

Click Run. The .replit entry starts one authenticated application worker on port 8000, mapped to the preview web port. Open the actual preview URL shown by Replit and sign in with STUDIO_TOKEN. Check /api/health before reviewing projects. Seed fictional fixtures with `python -m engine.cli seed` if desired; demo project generation is separate from startup.

A development preview is not durable production hosting. This version stores SQLite and uploaded files on disk. Before deploying, confirm a persistent writable volume survives restarts/redeploys and back it up. An ephemeral or autoscaled deployment requires database/object-storage adaptation; selecting a deployment size alone does not solve persistence. Configure HTTPS and trusted proxy handling; never expose the backend without authentication. Do not purchase or publish until the deployment plan is reviewed.

GitHub stores the source and can feed Replit or another host. GitHub Pages cannot run the Python backend. No customer project data, credentials, node_modules, or database is included in the source archive.

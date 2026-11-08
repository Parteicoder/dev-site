# dev-site

Source of [dev.plakat-kompass.de](https://dev.plakat-kompass.de): one small page per open-source package.

`build.py` reads `packages.json`, fetches each package's metadata and score from pub.dev and its README and
CHANGELOG from GitHub, downloads the README images, and writes a static site to `dist/`. No JavaScript,
no cookies, no third-party requests at runtime.

## Add a package

Add `{ "name": "<pub.dev name>", "repo": "<owner>/<repo>" }` to `packages.json`. The repo needs a `main`
branch with a `README.md`.

## Build locally

```
pip install -r requirements.txt
python build.py
python -m http.server -d dist
```

## Hosting

Cloudflare Workers with static assets (`wrangler.jsonc`, assets from `dist`). Build command
`pip install -r requirements.txt && python build.py`, deploy command `npx wrangler deploy`.
The nightly workflow calls a Cloudflare deploy hook (secret `CF_PAGES_DEPLOY_HOOK`) to rebuild.

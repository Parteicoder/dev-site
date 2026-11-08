"""Builds the static developer site into dist/.

For every package in packages.json: pub.dev metadata + score, README and CHANGELOG from GitHub.
Images from the README are downloaded at build time, so the site makes no third-party requests.
README/CHANGELOG are our own repos (trusted HTML); the CSP in _headers blocks scripts anyway.
"""
import hashlib, html, json, re, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
SITE = "https://dev.plakat-kompass.de"
UA = {"User-Agent": "dev-site-builder (+https://dev.plakat-kompass.de)"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def get_text(url: str, optional: bool = False) -> str:
    try:
        return get(url).decode("utf-8")
    except Exception:
        if optional:
            return ""
        raise


def render(md: str) -> str:
    md = re.sub(r"\A\s*# [^\n]*\n", "", md)  # the page has its own title
    return markdown.markdown(md, extensions=["extra", "toc", "sane_lists"])


def localize(body: str, repo: str, out: Path) -> str:
    """Downloads images next to the page and points relative links to GitHub."""
    raw = f"https://raw.githubusercontent.com/{repo}/main/"
    blob = f"https://github.com/{repo}/blob/main/"

    def img(m: re.Match) -> str:
        src = urllib.parse.urljoin(raw, m.group(2))
        ext = Path(urllib.parse.urlparse(src).path).suffix or ".img"
        name = hashlib.sha1(src.encode()).hexdigest()[:12] + ext
        (out / "assets").mkdir(parents=True, exist_ok=True)
        (out / "assets" / name).write_bytes(get(src))
        return f'{m.group(1)}"assets/{name}"'

    body = re.sub(r'(<img[^>]*?\ssrc=)"([^"]+)"', img, body)

    def link(m: re.Match) -> str:
        href = m.group(2)
        if re.match(r"(https?:|mailto:|#)", href):
            return m.group(0)
        return f'{m.group(1)}"{urllib.parse.urljoin(blob, href)}"'

    return re.sub(r'(<a[^>]*?\shref=)"([^"]+)"', link, body)


def page(root: str, title: str, description: str, path: str, body: str) -> str:
    tpl = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    return tpl.format(
        title=html.escape(title), description=html.escape(description, quote=True),
        canonical=f"{SITE}/{path}", root=root, body=body,
    )


def build_package(entry: dict) -> dict:
    name, repo = entry["name"], entry["repo"]
    meta = json.loads(get(f"https://pub.dev/api/packages/{name}"))["latest"]
    score = json.loads(get(f"https://pub.dev/api/packages/{name}/score"))
    pub = meta["pubspec"]
    tags = score.get("tags", [])
    platforms = [t.split(":", 1)[1] for t in tags if t.startswith("platform:")]
    licence = next((t.split(":", 1)[1] for t in tags if t.startswith("license:") and t not in ("license:fsf-libre", "license:osi-approved")), "")
    out = DIST / name
    out.mkdir(parents=True, exist_ok=True)

    readme = localize(render(get_text(f"https://raw.githubusercontent.com/{repo}/main/README.md")), repo, out)
    changelog_md = get_text(f"https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md", optional=True)
    changelog = localize(render(changelog_md), repo, out) if changelog_md else ""

    e = html.escape
    chips = [f"v{e(meta['version'])}", f"{score['grantedPoints']}/{score['maxPoints']} pub points"]
    if licence:
        chips.append(e(licence.upper()))
    chips += [e(p) for p in platforms]
    links = [
        ("pub.dev", f"https://pub.dev/packages/{name}"),
        ("API documentation", f"https://pub.dev/documentation/{name}/latest/"),
        ("GitHub", f"https://github.com/{repo}"),
        ("Issues", pub.get("issue_tracker") or f"https://github.com/{repo}/issues"),
    ]
    body = f"""<nav class="crumbs"><a href="../">Packages</a> / {e(name)}</nav>
<h1>{e(name)}</h1>
<p class="lead">{e(pub.get('description', ''))}</p>
<ul class="meta">{''.join(f'<li>{c}</li>' for c in chips)}</ul>
<div class="install">flutter pub add {e(name)}</div>
<ul class="links">{''.join(f'<li><a href="{e(u, quote=True)}">{e(t)}</a></li>' for t, u in links)}</ul>
<section class="readme">{readme}</section>
""" + (f'<h2 id="changelog">Changelog</h2><section class="readme">{changelog}</section>' if changelog else "")
    (out / "index.html").write_text(
        page("../", f"{name} - Flutter package | Plakat Kompass Developers", pub.get("description", ""), f"{name}/", body),
        encoding="utf-8",
    )
    return {"name": name, "version": meta["version"], "description": pub.get("description", "")}


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    packages = [build_package(p) for p in json.loads((ROOT / "packages.json").read_text(encoding="utf-8"))]

    cards = "".join(
        f'<a class="card" href="{html.escape(p["name"])}/"><h3>{html.escape(p["name"])}</h3>'
        f'<p>{html.escape(p["description"])}</p><p>v{html.escape(p["version"])}</p></a>'
        for p in packages
    )
    intro = (
        "Plakat Kompass is an app for tracking election posters. Parts of it are useful on their own, "
        "so we publish them as separate open-source packages that anyone can use under their licenses."
    )
    body = f"""<h1>Packages from Plakat Kompass</h1>
<p class="lead">{intro}</p>
<div class="cards">{cards}</div>
<p>Every package page mirrors its GitHub README, changelog and pub.dev data. The site is rebuilt automatically, so it always shows the latest release.</p>"""
    (DIST / "index.html").write_text(page("./", "Plakat Kompass Developers - open-source Flutter packages", intro, "", body), encoding="utf-8")

    shutil.copy(ROOT / "static" / "style.css", DIST / "style.css")
    (DIST / "_headers").write_text(
        "/*\n  Strict-Transport-Security: max-age=86400\n  X-Frame-Options: DENY\n  Referrer-Policy: no-referrer\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n",
        encoding="utf-8",
    )
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    urls = [f"{SITE}/"] + [f"{SITE}/{p['name']}/" for p in packages]
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n",
        encoding="utf-8",
    )
    print("built", [p["name"] for p in packages])


if __name__ == "__main__":
    sys.exit(main())

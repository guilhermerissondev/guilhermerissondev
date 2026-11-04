"""Gera dist/languages.svg e dist/languages-dark.svg com as linguagens usadas ultimamente.

Cada repositório (não fork) com push nos últimos WINDOW_DAYS dias entra com a
proporção de linguagens dele, pesada pela recência do último push (meia-vida de
HALF_LIFE_DAYS). Assim um repositório gigante não engole os outros e o que foi
mexido semana passada pesa mais que o de cinco meses atrás.

Usa GITHUB_TOKEN. Com STATS_TOKEN (PAT com escopo repo) também conta os privados.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("GITHUB_USER", "guilhermerissondev")
WINDOW_DAYS = 180
HALF_LIFE_DAYS = 60
TOP = 6
IGNORE = {"Jupyter Notebook", "Dockerfile", "Makefile", "Mako", "Batchfile", "PowerShell"}

# Cores do linguist para as linguagens que aparecem nos meus repositórios
COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Rust": "#DEA584",
    "Go": "#00ADD8",
    "PLpgSQL": "#336790",
    "SQL": "#E38C00",
    "HTML": "#E34C26",
    "CSS": "#663399",
    "Shell": "#89E051",
    "C++": "#F34B7D",
}
OTHER_COLOR = "#8B949E"

THEMES = {
    "languages.svg": {"bg": "#FFFFFF", "ink": "#1F2328", "muted": "#59636E", "rule": "#D1D9E0"},
    "languages-dark.svg": {"bg": "#0D1117", "ink": "#F0F6FC", "muted": "#9198A1", "rule": "#3D444D"},
}


def get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER,
    })
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def list_repos(token, private):
    if private:
        url = "https://api.github.com/user/repos?affiliation=owner&per_page=100&page={}"
    else:
        url = f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={{}}"
    repos, page = [], 1
    while True:
        batch = get(url.format(page), token)
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def weights(token, private):
    now = datetime.now(timezone.utc)
    totals = {}
    for repo in list_repos(token, private):
        if repo["fork"] or repo["archived"]:
            continue
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        age = (now - pushed).days
        if age > WINDOW_DAYS:
            continue
        langs = {k: v for k, v in get(repo["languages_url"], token).items() if k not in IGNORE}
        size = sum(langs.values())
        if not size:
            continue
        recency = 0.5 ** (age / HALF_LIFE_DAYS)
        for lang, n in langs.items():
            totals[lang] = totals.get(lang, 0) + recency * n / size
    total = sum(totals.values())
    ranked = sorted(((k, v / total) for k, v in totals.items()), key=lambda kv: -kv[1])
    top, rest = ranked[:TOP], sum(v for _, v in ranked[TOP:])
    if rest > 0:
        top.append(("Outras", rest))
    return top


def svg(items, theme):
    width, bar_y, bar_h = 840, 46, 10
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="122" viewBox="0 0 {width} 122" '
        'role="img" aria-label="Linguagens mais usadas nos últimos meses">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="121" rx="6" fill="{theme["bg"]}" stroke="{theme["rule"]}"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">',
        f'<text x="20" y="30" font-size="14" font-weight="600" fill="{theme["ink"]}">Linguagens que mais uso ultimamente</text>',
        f'<text x="{width - 20}" y="30" font-size="12" text-anchor="end" fill="{theme["muted"]}">'
        f'repositórios com push nos últimos {WINDOW_DAYS // 30} meses, peso maior para os recentes</text>',
        f'<clipPath id="bar"><rect x="20" y="{bar_y}" width="{width - 40}" height="{bar_h}" rx="5"/></clipPath>',
        '<g clip-path="url(#bar)">',
    ]
    x, span = 20.0, width - 40
    for name, share in items:
        w = share * span
        color = COLORS.get(name, OTHER_COLOR)
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="{bar_h}" fill="{color}"/>')
        x += w
    parts.append("</g>")
    col_w = (width - 40) / 4
    for i, (name, share) in enumerate(items):
        cx = 20 + (i % 4) * col_w
        cy = 82 + (i // 4) * 24
        color = COLORS.get(name, OTHER_COLOR)
        parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>')
        parts.append(
            f'<text x="{cx + 16}" y="{cy}" font-size="12" fill="{theme["ink"]}">{escape(name)} '
            f'<tspan fill="{theme["muted"]}">{share * 100:.1f}%</tspan></text>'
        )
    parts.append("</g></svg>")
    return "\n".join(parts)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    private_token = os.environ.get("STATS_TOKEN")
    token = private_token or os.environ["GITHUB_TOKEN"]
    items = weights(token, private=bool(private_token))
    os.makedirs(out, exist_ok=True)
    for filename, theme in THEMES.items():
        with open(os.path.join(out, filename), "w", encoding="utf-8") as f:
            f.write(svg(items, theme))
    for name, share in items:
        print(f"{name:12} {share * 100:5.1f}%")


if __name__ == "__main__":
    main()

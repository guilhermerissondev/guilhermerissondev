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
TOP = 5
IGNORE = {"Jupyter Notebook", "Dockerfile", "Makefile", "Mako", "Batchfile", "PowerShell"}

# Cores por posição no ranking, para nunca repetir tom entre linguagens vizinhas
PALETTE = ["#2F6FEB", "#FF6A45", "#13A89E", "#A855F7", "#F2B705", "#E5488A"]
OTHER_COLOR = "#8B949E"

THEMES = {
    "languages.svg": {"bg": "#FFFFFF", "ink": "#1F2328", "muted": "#59636E", "rule": "#D1D9E0", "track": "#EEF1F4"},
    "languages-dark.svg": {"bg": "#0D1117", "ink": "#F0F6FC", "muted": "#9198A1", "rule": "#3D444D", "track": "#1C222B"},
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
    width, pad = 840, 28
    span = width - 2 * pad
    colors = [OTHER_COLOR if name == "Outras" else PALETTE[i % len(PALETTE)] for i, (name, _) in enumerate(items)]
    rows = (len(items) + 1) // 2
    height = 150 + rows * 46
    mono = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Linguagens que mais uso nos últimos meses">',
        "<style>",
        ".grow{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both}",
        ".fade{animation:fade .6s ease-out both}",
        "@keyframes grow{from{transform:scaleX(0)}}",
        "@keyframes fade{from{opacity:0}}",
        "@media (prefers-reduced-motion:reduce){.grow,.fade{animation:none}}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{theme["bg"]}" stroke="{theme["rule"]}"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">',
        f'<text x="{pad}" y="38" font-family="{mono}" font-size="11" letter-spacing="1.4" fill="{colors[0]}">LINGUAGENS</text>',
        f'<text x="{pad}" y="64" font-size="20" font-weight="600" fill="{theme["ink"]}">O que mais escrevo ultimamente</text>',
        f'<text x="{width - pad}" y="38" font-family="{mono}" font-size="11" text-anchor="end" fill="{theme["muted"]}">'
        f'ÚLTIMOS {WINDOW_DAYS // 30} MESES</text>',
        f'<text x="{width - pad}" y="64" font-size="12" text-anchor="end" fill="{theme["muted"]}">peso maior para os repositórios mexidos há pouco</text>',
    ]
    # Barra empilhada com a proporção de cada linguagem
    bar_y, bar_h = 86, 14
    parts.append(f'<clipPath id="bar"><rect x="{pad}" y="{bar_y}" width="{span}" height="{bar_h}" rx="7"/></clipPath>')
    parts.append(f'<rect x="{pad}" y="{bar_y}" width="{span}" height="{bar_h}" rx="7" fill="{theme["track"]}"/>')
    parts.append('<g clip-path="url(#bar)">')
    x = float(pad)
    for i, ((_, share), color) in enumerate(zip(items, colors)):
        w = share * span
        parts.append(
            f'<rect class="grow" style="animation-delay:{i * 0.12:.2f}s" x="{x:.2f}" y="{bar_y}" '
            f'width="{w + 1:.2f}" height="{bar_h}" fill="{color}"/>'
        )
        x += w
    parts.append("</g>")
    # Duas colunas: nome, percentual e uma barra própria relativa à linguagem mais usada
    gap = 40
    col_w = (span - gap) / 2
    top_share = items[0][1]
    for i, ((name, share), color) in enumerate(zip(items, colors)):
        col, row = i // rows, i % rows
        cx = pad + col * (col_w + gap)
        cy = 140 + row * 46
        delay = 0.3 + i * 0.1
        parts.append(f'<g class="fade" style="animation-delay:{delay:.2f}s">')
        parts.append(f'<rect x="{cx}" y="{cy - 11}" width="10" height="10" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{cx + 18}" y="{cy - 1}" font-size="14" font-weight="500" fill="{theme["ink"]}">{escape(name)}</text>')
        parts.append(
            f'<text x="{cx + col_w:.2f}" y="{cy - 1}" font-family="{mono}" font-size="13" font-weight="600" '
            f'text-anchor="end" fill="{theme["ink"]}">{share * 100:.1f}%</text>'
        )
        parts.append("</g>")
        parts.append(f'<rect x="{cx}" y="{cy + 9}" width="{col_w:.2f}" height="6" rx="3" fill="{theme["track"]}"/>')
        parts.append(
            f'<rect class="grow" style="animation-delay:{delay:.2f}s" x="{cx}" y="{cy + 9}" '
            f'width="{max(share / top_share * col_w, 6):.2f}" height="6" rx="3" fill="{color}"/>'
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

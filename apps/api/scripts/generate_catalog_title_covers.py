"""Create compact, original SVG title covers for imported catalog games."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps/api/alembic/data/awesome_astra_96b5360.json"
OUTPUT = ROOT / "static/web/catalog/2026-09-26-v1/covers"
WEB_MANIFEST = ROOT / "apps/web/src/features/catalog/coverManifest.ts"
VERSION = "2026-09-26-v1"

# 这些网址在 0074 已收录且有独立封面；0078 只给它们补作者，不重复建卡面。
EXISTING_COVER_URLS = {
    "https://melon-game.jack-514.chatgpt.site/",
    "https://dust-ii-map.yelin8130.chatgpt.site/",
    "https://infinite-garden.yelin8130.chatgpt.site/",
    "https://fruit-ninja-dojo-20260905.yongqixue666.chatgpt.site/",
}

CATEGORY_HUES = {
    "动作与街机": 333,
    "解谜与益智": 189,
    "策略与模拟": 242,
    "RPG 与冒险": 282,
    "平台跳跃与竞速": 213,
    "实验玩法与多人游戏": 158,
}


def _hsl(hue: int, saturation: int, lightness: int) -> str:
    """Return CSS HSL with an integer hue and fixed saturation/lightness."""

    return f"hsl({hue % 360} {saturation}% {lightness}%)"


def _width_units(character: str) -> int:
    """Estimate the SVG glyph width so mixed Chinese and Latin titles fit."""

    return 2 if unicodedata.east_asian_width(character) in ("F", "W") else 1


def _title_lines(value: str) -> list[str]:
    """Fit a game title into at most two cover lines without injecting markup."""

    normalized = " ".join(value.split())
    lines: list[str] = []
    current = ""
    truncated = False
    for character in normalized:
        if sum(_width_units(item) for item in current + character) > 16 and current:
            if " " in current:
                completed, carry = current.rsplit(" ", 1)
                lines.append(completed.rstrip())
                current = (carry + character).lstrip()
            else:
                lines.append(current.rstrip())
                current = character.lstrip()
            if len(lines) == 2:
                truncated = True
                break
        else:
            current += character
    if len(lines) < 2 and current:
        lines.append(current.rstrip())
    if truncated:
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines or ["AI Game"]


def _motif(category: str, seed: bytes, accent: str, secondary: str) -> str:
    """Draw one category motif with stable per-project positions and scale."""

    shift = seed[2] % 25 - 12
    x = 491 + shift
    y = 151 + seed[3] % 31 - 15
    if category == "动作与街机":
        return (
            f'<circle cx="{x}" cy="{y}" r="91" fill="none" stroke="{accent}" stroke-width="4" opacity=".55"/>'
            f'<circle cx="{x}" cy="{y}" r="56" fill="none" stroke="{secondary}" stroke-width="18" opacity=".82"/>'
            f'<path d="M{x-13} {y-82}L{x+28} {y-15}H{x+2}L{x+27} {y+74}L{x-48} {y-10}H{x-13}Z" fill="white" opacity=".92"/>'
        )
    if category == "解谜与益智":
        return (
            f'<g transform="translate({x-80} {y-81}) rotate({seed[4]%21-10} 80 80)">'
            f'<rect x="0" y="0" width="73" height="73" rx="17" fill="{accent}" opacity=".92"/>'
            f'<rect x="85" y="0" width="73" height="73" rx="17" fill="white" opacity=".79"/>'
            f'<rect x="0" y="85" width="73" height="73" rx="17" fill="white" opacity=".55"/>'
            f'<rect x="85" y="85" width="73" height="73" rx="17" fill="{secondary}" opacity=".84"/>'
            '<circle cx="79" cy="79" r="22" fill="white" opacity=".8"/></g>'
        )
    if category == "策略与模拟":
        return (
            f'<path d="M{x} {y-101}L{x+94} {y-50}V{y+51}L{x} {y+102}L{x-94} {y+51}V{y-50}Z" fill="{accent}" opacity=".8"/>'
            f'<path d="M{x} {y-65}L{x+61} {y-31}V{y+31}L{x} {y+66}L{x-61} {y+31}V{y-31}Z" fill="none" stroke="white" stroke-width="5" opacity=".84"/>'
            f'<path d="M{x} {y-64}V{y+66}M{x-60} {y-31}L{x} {y+2}L{x+60} {y-31}" stroke="{secondary}" stroke-width="5" fill="none" opacity=".9"/>'
        )
    if category == "RPG 与冒险":
        return (
            f'<circle cx="{x}" cy="{y}" r="96" fill="none" stroke="{accent}" stroke-width="3" opacity=".65"/>'
            f'<path d="M{x-93} {y+69}L{x-42} {y-35}L{x-2} {y+26}L{x+37} {y-67}L{x+97} {y+69}Z" fill="{accent}" opacity=".82"/>'
            f'<path d="M{x+37} {y-67}L{x+54} {y-27}L{x+23} {y-33}Z" fill="white" opacity=".9"/>'
            f'<circle cx="{x-42}" cy="{y-63}" r="8" fill="{secondary}"/>'
        )
    if category == "平台跳跃与竞速":
        return (
            f'<path d="M{x-94} {y+43}C{x-31} {y-51},{x+9} {y+20},{x+88} {y-76}" fill="none" stroke="{accent}" stroke-width="25" stroke-linecap="round"/>'
            f'<path d="M{x-107} {y+82}C{x-22} {y-28},{x+15} {y+55},{x+94} {y-41}" fill="none" stroke="white" stroke-width="10" stroke-linecap="round" opacity=".78"/>'
            f'<path d="M{x+64} {y-86}L{x+103} {y-83}L{x+94} {y-43}" fill="none" stroke="{secondary}" stroke-width="17" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return (
        f'<ellipse cx="{x}" cy="{y}" rx="111" ry="44" transform="rotate(-29 {x} {y})" fill="none" stroke="{accent}" stroke-width="10" opacity=".8"/>'
        f'<ellipse cx="{x}" cy="{y}" rx="111" ry="44" transform="rotate(35 {x} {y})" fill="none" stroke="white" stroke-width="5" opacity=".6"/>'
        f'<circle cx="{x}" cy="{y}" r="38" fill="{secondary}"/>'
        f'<circle cx="{x+80}" cy="{y-56}" r="14" fill="white"/>'
    )


def _svg(name: str, category: str, slug: str) -> str:
    """Build one minified SVG with escaped source text and a unique motif."""

    seed = hashlib.sha256(slug.encode("ascii")).digest()
    base_hue = CATEGORY_HUES[category] + seed[0] % 39 - 19
    accent = _hsl(base_hue + 38, 83, 71)
    secondary = _hsl(base_hue + 78, 86, 75)
    bg_start = _hsl(base_hue, 61, 35)
    bg_end = _hsl(base_hue + 41, 67, 19)
    lines = _title_lines(name)
    font_size = 40
    text_y = 173 if len(lines) == 1 else 150
    text_lines = "".join(
        f'<text x="38" y="{text_y + index * 53}" fill="white" font-size="{font_size}" font-weight="800" letter-spacing=".2">{escape(line, quote=True)}</text>'
        for index, line in enumerate(lines)
    )
    sparks = "".join(
        f'<circle cx="{397 + seed[index] % 223}" cy="{23 + seed[index+1] % 246}" r="{2 + seed[index+2] % 5}" fill="white" opacity=".35"/>'
        for index in (5, 8, 11, 14)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="300" viewBox="0 0 640 300" role="img">'
        f'<title>{escape(name, quote=True)}</title>'
        '<defs>'
        f'<linearGradient id="bg" x2="1" y2="1"><stop stop-color="{bg_start}"/><stop offset="1" stop-color="{bg_end}"/></linearGradient>'
        f'<radialGradient id="light"><stop stop-color="{accent}" stop-opacity=".42"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        '</defs>'
        '<rect width="640" height="300" fill="url(#bg)"/>'
        f'<circle cx="{468+seed[1]%57}" cy="{95+seed[2]%82}" r="228" fill="url(#light)"/>'
        '<path d="M0 262C124 204 186 318 349 247C463 197 552 233 640 205V300H0Z" fill="white" opacity=".06"/>'
        f'{sparks}{_motif(category,seed,accent,secondary)}'
        '<rect x="37" y="62" width="52" height="5" rx="3" fill="white" opacity=".69"/>'
        f'<g font-family="Inter,system-ui,-apple-system,BlinkMacSystemFont,Noto Sans SC,Microsoft YaHei,sans-serif">{text_lines}</g>'
        '</svg>\n'
    )


def main() -> None:
    """Regenerate only the pinned README game's 157 new covers and web manifest."""

    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if payload.get("source_commit") != "96b5360c69edf6f7ef59ac96072c6cdf9e93e5b1":
        raise RuntimeError("unexpected source snapshot")
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != 161:
        raise RuntimeError("expected the pinned 161-game snapshot")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("invalid snapshot entry")
        url, name, category = entry.get("url"), entry.get("name"), entry.get("source_category")
        if not isinstance(url, str) or not isinstance(name, str) or category not in CATEGORY_HUES:
            raise RuntimeError("invalid snapshot game")
        if url in EXISTING_COVER_URLS:
            continue
        slug = "astra-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        (OUTPUT / f"{slug}.svg").write_text(_svg(name, category, slug), encoding="utf-8")
        paths[slug] = f"/catalog/{VERSION}/covers/{slug}.svg"
    if len(paths) != 157:
        raise RuntimeError(f"expected 157 new covers, got {len(paths)}")
    manifest_entries = "\n".join(f'  "{slug}": "{path}",' for slug, path in sorted(paths.items()))
    WEB_MANIFEST.write_text(
        "// Pinned 0078 game covers: original artwork generated from the local snapshot.\n"
        "const CATALOG_COVER_PATHS: Readonly<Record<string, string>> = {\n"
        f"{manifest_entries}\n"
        "};\n\n"
        "export function getCatalogCoverPath(slug: string): string | null {\n"
        "  return CATALOG_COVER_PATHS[slug] ?? null;\n"
        "}\n",
        encoding="utf-8",
    )
    sizes = [path.stat().st_size for path in OUTPUT.glob("astra-*.svg")]
    print(f"generated {len(paths)} covers; total {sum(sizes)} bytes; largest {max(sizes)} bytes")


if __name__ == "__main__":
    main()

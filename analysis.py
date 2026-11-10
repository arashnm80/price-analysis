#!/usr/bin/env python3
"""Reprice Artificial Analysis Coding Agent Index runs at Cursor token rates.

Intelligence stays the published Coding Agent Index score. Cost is rebuilt
from the same per-task token counts using Cursor's list prices. A point is
on the Pareto line when no other point is both at least as capable and
strictly cheaper, or both strictly more capable and no more expensive.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "output"

# Coding-agent runs whose model is a row on the Cursor pricing page.
# Devin Fusion is a two-model harness, so it is not a Cursor model choice.
MODEL_KEYS = (
    ("sonnet 5.5", "claude-sonnet-5-5"),
    ("opus 5.5", "claude-opus-5-5"),
    ("fable 5.1", "claude-fable-5-1"),
    ("opus 5", "claude-opus-5"),
    ("grok 4.7", "grok-4-7"),
    ("grok 4.6", "grok-4-6"),
    ("muse spark", "muse-spark-1-3"),
    ("gemini 3.8", "gemini-3-8-flash"),
    ("glm-5.3", "glm-5-3"),
    ("glm 5.3", "glm-5-3"),
    ("kimi k3", "kimi-k3"),
    ("gpt-5.6 sol", "gpt-5-6-sol"),
    ("gpt-5.6 luna", "gpt-5-6-luna"),
)

PROVIDER_COLOR = {
    "Anthropic": "#b4532a",
    "Cursor": "#1f7a4d",
    "OpenAI": "#2c5f8a",
    "Meta": "#5b4b8a",
    "Google": "#8d6a2f",
    "Z.ai": "#7a4e62",
    "Moonshot": "#3d6b66",
    "DeepSeek": "#24566b",
    "Alibaba": "#6a5344",
    "Cognition": "#6e5a3a",
}

OUTSIDE_PROVIDER = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "alibaba_cloud": "Alibaba",
    "cognition": "Cognition",
    "anthropic": "Anthropic",
    "xai": "Cursor",
    "meta": "Meta",
    "google": "Google",
    "zai": "Z.ai",
    "moonshotai": "Moonshot",
}


def load() -> tuple[list[dict], dict, dict]:
    runs = json.loads((DATA / "coding_agent_runs.json").read_text())
    cursor = json.loads((DATA / "cursor_prices.json").read_text())
    aa = json.loads((DATA / "aa_prices.json").read_text())
    return runs, cursor, aa


def match_key(run: dict) -> str | None:
    if run["agent"].startswith("Devin"):
        return None
    model = run["model"].lower()
    for needle, key in MODEL_KEYS:
        if needle in model:
            return key
    return None


def _chart_label(label: str) -> str:
    short = (
        label.replace("Claude ", "")
        .replace("Muse Spark 1.3", "Muse")
        .replace("Gemini 3.8 Flash", "Gemini 3.8")
        .replace(", with fallback", "*")
    )
    return short


def outside_name(run: dict) -> str:
    name = run["model"]
    name = name.replace(" 0731", "").replace(" 0813", "")
    name = name.replace(" ({'reasoning_effort': 'max'})", "")
    return name


def short_name(run: dict, cursor_name: str) -> str:
    text = f"{run['model']} {run['label']}".lower()
    effort = ""
    for tag in ("xhigh", "max", "high", "medium", "low"):
        if f"({tag}" in text or f"'{tag}'" in text:
            effort = tag
            break
    if "fallback" in text:
        effort = f"{effort}, with fallback".strip(", ")
    return f"{cursor_name} ({effort})" if effort else cursor_name


def buckets(run: dict, aa_price: dict) -> dict:
    """Split the published mean into uncached input, cache read, cache write, output.

    AA's inputTokens already include cache reads. Cache-write tokens are not
    published; they are the residual that remains after pricing the published
    buckets at AA's list rates, divided by the cache-write price.
    """
    uncached = run["inputTokens"] - run["cacheTokens"]
    known = (
        uncached / 1e6 * aa_price["input"]
        + run["cacheTokens"] / 1e6 * aa_price["cacheRead"]
        + run["outputTokens"] / 1e6 * aa_price["output"]
    )
    write = 0.0
    write_price = aa_price["cacheWrite"]
    residual = run["costUsdAa"] - known
    if write_price and residual > 0.005:
        write = residual / write_price * 1e6
    return {
        "uncachedInput": uncached,
        "cacheRead": run["cacheTokens"],
        "cacheWrite": write,
        "output": run["outputTokens"],
        "aaResidualUsd": residual,
    }


def price_buckets(parts: dict, price: dict) -> float:
    cost = (
        parts["uncachedInput"] / 1e6 * price["input"]
        + parts["cacheRead"] / 1e6 * price["cacheRead"]
        + parts["output"] / 1e6 * price["output"]
    )
    write_price = price["cacheWrite"]
    if write_price is None:
        # No separate write fee: those tokens are ordinary input.
        cost += parts["cacheWrite"] / 1e6 * price["input"]
    else:
        cost += parts["cacheWrite"] / 1e6 * write_price
    return cost


def pareto(points: list[dict], cost_key: str) -> list[dict]:
    """Minimize cost, maximize index. Points sorted cheap to expensive."""
    frontier: list[dict] = []
    best = float("-inf")
    for point in sorted(points, key=lambda p: (p[cost_key], -p["index"])):
        if point["index"] > best:
            frontier.append(point)
            best = point["index"]
    return frontier


def build() -> dict:
    runs, cursor_doc, aa_doc = load()
    cursor_models = cursor_doc["models"]
    aa_models = aa_doc["models"]
    rate = cursor_doc["tokenRateUsdPerMillion"]
    included = []
    for run in runs:
        key = match_key(run)
        if key is None or key not in cursor_models:
            # Kept for the Pareto calculation. Drawn only if the point is on the line.
            # Cost stays the provider API price: Cursor does not sell the model.
            included.append(
                {
                    "id": run["slug"],
                    "label": outside_name(run),
                    "aaLabel": run["label"],
                    "agent": run["agent"],
                    "model": run["model"],
                    "cursorModel": None,
                    "provider": OUTSIDE_PROVIDER.get(run["provider"], run["provider"]),
                    "firstParty": False,
                    "inCursor": False,
                    "index": round(run["index"] * 100, 2),
                    "aaCostUsd": round(run["costUsdAa"], 4),
                    "individualUsd": round(run["costUsdAa"], 4),
                    "teamsUsd": round(run["costUsdAa"], 4),
                    "teamsFeeUsd": 0.0,
                    "priceDiffersFromAa": False,
                    "tokens": {
                        "uncachedInput": round(run["inputTokens"] - run["cacheTokens"]),
                        "cacheRead": round(run["cacheTokens"]),
                        "cacheWrite": 0,
                        "output": round(run["outputTokens"]),
                    },
                    "cursorPrice": None,
                }
            )
            continue
        cursor_price = cursor_models[key]
        aa_price = aa_models[key]
        parts = buckets(run, aa_price)
        prices_match = (
            cursor_price["input"] == aa_price["input"]
            and cursor_price["cacheRead"] == aa_price["cacheRead"]
            and cursor_price["output"] == aa_price["output"]
            and cursor_price["cacheWrite"] == aa_price["cacheWrite"]
        )
        if prices_match:
            individual = run["costUsdAa"]
        else:
            individual = price_buckets(parts, cursor_price)
        fee_tokens = run["inputTokens"] + run["outputTokens"] + parts["cacheWrite"]
        fee = 0.0 if cursor_price["firstParty"] else fee_tokens / 1e6 * rate
        included.append(
            {
                "id": run["slug"],
                "label": short_name(run, cursor_price["cursorName"]),
                "aaLabel": run["label"],
                "agent": run["agent"],
                "model": run["model"],
                "cursorModel": cursor_price["cursorName"],
                "provider": cursor_price["provider"],
                "firstParty": cursor_price["firstParty"],
                "inCursor": True,
                "index": round(run["index"] * 100, 2),
                "aaCostUsd": round(run["costUsdAa"], 4),
                "individualUsd": round(individual, 4),
                "teamsUsd": round(individual + fee, 4),
                "teamsFeeUsd": round(fee, 4),
                "priceDiffersFromAa": not prices_match,
                "tokens": {
                    "uncachedInput": round(parts["uncachedInput"]),
                    "cacheRead": round(parts["cacheRead"]),
                    "cacheWrite": round(parts["cacheWrite"]),
                    "output": round(parts["output"]),
                },
                "cursorPrice": {
                    "input": cursor_price["input"],
                    "cacheWrite": cursor_price["cacheWrite"],
                    "cacheRead": cursor_price["cacheRead"],
                    "output": cursor_price["output"],
                },
            }
        )
    included.sort(key=lambda p: -p["index"])
    individual_ids = {p["id"] for p in pareto(included, "individualUsd")}
    teams_ids = {p["id"] for p in pareto(included, "teamsUsd")}
    for point in included:
        point["paretoIndividual"] = point["id"] in individual_ids
        point["paretoTeams"] = point["id"] in teams_ids
        point["chartLabel"] = _chart_label(point["label"])
    return {
        "retrieved": "2026-09-29",
        "index": "Artificial Analysis Coding Agent Index v1.5",
        "indexComponents": ["DeepSWE v1.1", "Terminal-Bench 4.0", "SWE-Atlas-QnA"],
        "pricing": "https://cursor.com/docs/models-and-pricing",
        "intelligence": "https://artificialanalysis.ai/agents/coding-agents",
        "points": included,
        "excluded": [
            {
                "label": point["aaLabel"],
                "model": point["model"],
                "agent": point["agent"],
                "index": point["index"],
                "aaCostUsd": point["aaCostUsd"],
                "reason": "Not in Cursor, and not on the Pareto line in either price view",
            }
            for point in included
            if not point["inCursor"] and not point["paretoIndividual"] and not point["paretoTeams"]
        ],
        "frontierIndividual": [p["label"] for p in pareto(included, "individualUsd")],
        "frontierTeams": [p["label"] for p in pareto(included, "teamsUsd")],
    }


def shown_points(result: dict, pareto_key: str) -> list[dict]:
    """Cursor models, plus outside models that sit on this view's Pareto line."""
    return [p for p in result["points"] if p["inCursor"] or p[pareto_key]]


def svg_chart(result: dict, cost_key: str, pareto_key: str, title: str, subtitle: str) -> str:
    points = shown_points(result, pareto_key)
    width, height = 980, 640
    left, right, top, bottom = 72, 900, 78, 540
    costs = [p[cost_key] for p in points]
    xmin, xmax = min(costs) * 0.75, max(costs) * 1.22
    ymin, ymax = 34, 72

    def x_of(cost: float) -> float:
        t = (math.log10(cost) - math.log10(xmin)) / (math.log10(xmax) - math.log10(xmin))
        return left + t * (right - left)

    def y_of(score: float) -> float:
        t = (score - ymin) / (ymax - ymin)
        return bottom - t * (bottom - top)

    def tick(value: float) -> str:
        return f"{value:g}"

    x_ticks = [v for v in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20) if xmin <= v <= xmax]
    y_ticks = list(range(40, 75, 5))
    frontier = sorted(
        (p for p in points if p[pareto_key]),
        key=lambda p: p[cost_key],
    )
    line = " ".join(f"{x_of(p[cost_key]):.1f},{y_of(p['index']):.1f}" for p in frontier)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{title}</title>",
        '<rect width="100%" height="100%" fill="#f7f6f3"/>',
        f'<text x="{left}" y="34" font-family="ui-sans-serif, system-ui, sans-serif" font-size="20" font-weight="650" fill="#1c1917">{title}</text>',
        f'<text x="{left}" y="56" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#57534e">{subtitle}</text>',
    ]
    for value in y_ticks:
        y = y_of(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#e7e5e4" stroke-width="1"/>')
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#78716c">{value}</text>'
        )
    for value in x_ticks:
        x = x_of(value)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#e7e5e4" stroke-width="1"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 20}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#78716c">${tick(value)}</text>'
        )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#d6d3d1"/>')
    parts.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#d6d3d1"/>')
    parts.append(
        f'<text x="22" y="{(top + bottom) / 2:.0f}" transform="rotate(-90 22 {(top + bottom) / 2:.0f})" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#44403c">Coding Agent Index</text>'
    )
    parts.append(
        f'<text x="{(left + right) / 2:.0f}" y="{bottom + 42}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#44403c">Cost per task (USD, log scale)</text>'
    )
    parts.append(
        f'<polyline points="{line}" fill="none" stroke="#1c1917" stroke-width="1.75" stroke-linejoin="round"/>'
    )
    # Draw dominated points first so frontier rings sit on top.
    ordered = sorted(points, key=lambda p: p[pareto_key])
    boxes: list[tuple[float, float, float, float]] = []
    for point in ordered:
        x = x_of(point[cost_key])
        y = y_of(point["index"])
        color = PROVIDER_COLOR.get(point["provider"], "#44403c")
        radius = 6.5 if point[pareto_key] else 4.5
        outside = not point["inCursor"]
        fill = "#f7f6f3" if outside else color
        stroke = color if outside else ("#1c1917" if point[pareto_key] else "#ffffff")
        sw = 1.75 if outside else (1.6 if point[pareto_key] else 1)
        dash = ' stroke-dasharray="3 2"' if outside else ""
        availability = "" if point["inCursor"] else " · not in Cursor"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}>'
            f"<title>{point['label']} · index {point['index']:.2f} · ${point[cost_key]:.2f}{availability}</title></circle>"
        )
        label = point["chartLabel"]
        width_est = len(label) * 5.6 + 4
        placed = _place_label(x, y, width_est, 14, boxes, right + 48, top, bottom)
        if placed is None:
            continue
        lx, ly = placed
        boxes.append((lx, ly - 11, width_est, 14))
        weight = "650" if point[pareto_key] else "450"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" font-weight="{weight}" fill="#292524">{label}</text>'
        )
    legend_x = left
    legend_y = height - 28
    parts.append(
        f'<text x="{legend_x}" y="{legend_y}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#44403c">Pareto line</text>'
    )
    parts.append(
        f'<line x1="{legend_x + 72}" y1="{legend_y - 4}" x2="{legend_x + 98}" y2="{legend_y - 4}" stroke="#1c1917" stroke-width="1.75"/>'
    )
    parts.append(
        f'<circle cx="{legend_x + 118}" cy="{legend_y - 4}" r="5" fill="#f7f6f3" stroke="#1c1917" stroke-width="1.5" stroke-dasharray="3 2"/>'
    )
    parts.append(
        f'<text x="{legend_x + 128}" y="{legend_y}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#44403c">Not in Cursor</text>'
    )
    lx = legend_x + 230
    for name, color in PROVIDER_COLOR.items():
        if not any(p["provider"] == name for p in points):
            continue
        parts.append(f'<circle cx="{lx}" cy="{legend_y - 4}" r="4.5" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 8}" y="{legend_y}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#44403c">{name}</text>'
        )
        lx += 18 + len(name) * 6.2
    parts.append("</svg>")
    return "\n".join(parts)


def _overlaps(x: float, y: float, w: float, h: float, boxes: list[tuple[float, float, float, float]]) -> bool:
    for bx, by, bw, bh in boxes:
        if x < bx + bw and x + w > bx and y < by + bh and y + h > by:
            return True
    return False


def _place_label(
    x: float,
    y: float,
    w: float,
    h: float,
    boxes: list[tuple[float, float, float, float]],
    limit: float,
    top: float,
    bottom: float,
) -> tuple[float, float] | None:
    """Return a baseline (x, y) whose box misses other labels. Prefer the right side."""
    candidates = []
    for dx, dy in ((9, -8), (9, 14), (-w - 8, -8), (-w - 8, 14)):
        candidates.append((x + dx, y + dy))
    for step in range(1, 6):
        candidates.append((x + 9, y - 8 - step * 12))
        candidates.append((x + 9, y + 14 + step * 12))
        candidates.append((x - w - 8, y - 8 - step * 12))
        candidates.append((x - w - 8, y + 14 + step * 12))
    for lx, ly in candidates:
        box_y = ly - 11
        if lx < 76 or lx + w > limit or box_y < top or box_y + h > bottom:
            continue
        if _overlaps(lx, box_y, w, h, boxes):
            continue
        return lx, ly
    return None


def write_html(result: dict) -> None:
    payload = json.dumps(result)
    colors = json.dumps(PROVIDER_COLOR)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Coding Agent Index vs Cursor cost</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; background: #f7f6f3; color: #1c1917; font: 15px/1.45 ui-sans-serif, system-ui, sans-serif; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 64px; }}
  h1 {{ font-size: 22px; font-weight: 650; margin: 0 0 6px; }}
  .lede {{ color: #57534e; margin: 0 0 18px; max-width: 70ch; }}
  .row {{ display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }}
  button {{ border: 1px solid #d6d3d1; background: #fff; color: #1c1917; border-radius: 6px; padding: 6px 10px; font: inherit; cursor: pointer; }}
  button[aria-pressed="true"] {{ background: #1c1917; color: #fafaf9; border-color: #1c1917; }}
  .chart {{ background: #fff; border: 1px solid #e7e5e4; border-radius: 8px; }}
  .note {{ color: #57534e; font-size: 13px; margin: 10px 0 22px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border: 1px solid #e7e5e4; }}
  th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid #f5f5f4; vertical-align: top; }}
  th {{ font-weight: 650; color: #44403c; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.on td:first-child {{ box-shadow: inset 3px 0 0 #1c1917; }}
  h2 {{ font-size: 16px; margin: 28px 0 8px; }}
  .tip {{ position: fixed; pointer-events: none; background: #1c1917; color: #fafaf9; padding: 8px 10px; border-radius: 6px; font-size: 12px; display: none; max-width: 280px; }}
</style>
</head>
<body>
<main>
  <h1>Coding Agent Index vs Cursor cost per task</h1>
  <p class="lede">Each filled point is a model Cursor sells. Hollow points are on the Pareto line and are not sold in Cursor; their cost is the provider API price. The line joins the set where nothing else plotted is both smarter and cheaper.</p>
  <div class="row">
    <button id="individual" aria-pressed="true" type="button">Individual plans</button>
    <button id="teams" aria-pressed="false" type="button">Teams and Enterprise</button>
  </div>
  <div class="chart"><svg id="plot" viewBox="0 0 980 620" width="100%"></svg></div>
  <p class="note" id="caption"></p>
  <h2>On the chart</h2>
  <table id="table"></table>
  <h2>Left off the chart</h2>
  <table id="excluded"></table>
</main>
<div class="tip" id="tip"></div>
<script>
const RESULT = {payload};
const COLOR = {colors};
const svg = document.getElementById("plot");
const tip = document.getElementById("tip");
let mode = "individual";

function costOf(p) {{ return mode === "teams" ? p.teamsUsd : p.individualUsd; }}
function onFrontier(p) {{ return mode === "teams" ? p.paretoTeams : p.paretoIndividual; }}

function draw() {{
  const pts = RESULT.points.filter((p) => p.inCursor || onFrontier(p));
  const costs = pts.map(costOf);
  const xmin = Math.min(...costs) * 0.75;
  const xmax = Math.max(...costs) * 1.22;
  const ymin = 34, ymax = 72;
  const L = 72, R = 930, T = 28, B = 500;
  const W = 980, H = 620;
  const xOf = (c) => L + (Math.log10(c) - Math.log10(xmin)) / (Math.log10(xmax) - Math.log10(xmin)) * (R - L);
  const yOf = (s) => B - (s - ymin) / (ymax - ymin) * (B - T);
  const ns = "http://www.w3.org/2000/svg";
  svg.replaceChildren();
  const add = (name, attrs) => {{
    const el = document.createElementNS(ns, name);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.appendChild(el);
    return el;
  }};
  for (const v of [40, 45, 50, 55, 60, 65, 70]) {{
    const y = yOf(v);
    add("line", {{x1: L, y1: y, x2: R, y2: y, stroke: "#e7e5e4"}});
    const t = add("text", {{x: L - 10, y: y + 4, "text-anchor": "end", fill: "#78716c", "font-size": "11"}});
    t.textContent = v;
  }}
  for (const v of [0.1, 0.2, 0.5, 1, 2, 5, 10, 20].filter(v => v >= xmin && v <= xmax)) {{
    const x = xOf(v);
    add("line", {{x1: x, y1: T, x2: x, y2: B, stroke: "#e7e5e4"}});
    const t = add("text", {{x, y: B + 20, "text-anchor": "middle", fill: "#78716c", "font-size": "11"}});
    t.textContent = "$" + v;
  }}
  add("line", {{x1: L, y1: T, x2: L, y2: B, stroke: "#d6d3d1"}});
  add("line", {{x1: L, y1: B, x2: R, y2: B, stroke: "#d6d3d1"}});
  const ylab = add("text", {{x: 22, y: (T + B) / 2, "text-anchor": "middle", fill: "#44403c", "font-size": "12", transform: `rotate(-90 22 ${{(T + B) / 2}})`}});
  ylab.textContent = "Coding Agent Index";
  const xlab = add("text", {{x: (L + R) / 2, y: B + 44, "text-anchor": "middle", fill: "#44403c", "font-size": "12"}});
  xlab.textContent = "Cost per task (USD, log scale)";
  const frontier = pts.filter(onFrontier).sort((a, b) => costOf(a) - costOf(b));
  add("polyline", {{
    points: frontier.map(p => `${{xOf(costOf(p)).toFixed(1)}},${{yOf(p.index).toFixed(1)}}`).join(" "),
    fill: "none", stroke: "#1c1917", "stroke-width": "1.75"
  }});
  const boxes = [];
  const hits = (x, y, w, h) => boxes.some(b => x < b[0] + b[2] && x + w > b[0] && y < b[1] + b[3] && y + h > b[1]);
  function place(x, y, w, h) {{
    const spots = [[9, -8], [9, 14], [-w - 8, -8], [-w - 8, 14]];
    for (let step = 1; step < 6; step++) {{
      spots.push([9, -8 - step * 12], [9, 14 + step * 12], [-w - 8, -8 - step * 12], [-w - 8, 14 + step * 12]);
    }}
    for (const [dx, dy] of spots) {{
      const lx = x + dx, ly = y + dy, by = ly - 11;
      if (lx < 76 || lx + w > R + 40 || by < T || by + h > B) continue;
      if (hits(lx, by, w, h)) continue;
      return [lx, ly];
    }}
    return null;
  }}
  for (const p of [...pts].sort((a, b) => Number(onFrontier(a)) - Number(onFrontier(b)))) {{
    const x = xOf(costOf(p)), y = yOf(p.index);
    const outside = !p.inCursor;
    const c = add("circle", {{
      cx: x, cy: y, r: onFrontier(p) ? 6.5 : 4.5,
      fill: outside ? "#fff" : (COLOR[p.provider] || "#44403c"),
      stroke: outside ? (COLOR[p.provider] || "#1c1917") : (onFrontier(p) ? "#1c1917" : "#fff"),
      "stroke-width": outside ? 1.75 : (onFrontier(p) ? 1.6 : 1),
      "stroke-dasharray": outside ? "3 2" : ""
    }});
    c.addEventListener("mousemove", (ev) => {{
      tip.style.display = "block";
      tip.style.left = (ev.clientX + 12) + "px";
      tip.style.top = (ev.clientY + 12) + "px";
      tip.textContent = `${{p.label}} · index ${{p.index.toFixed(2)}} · $${{costOf(p).toFixed(2)}} · ${{p.agent}}${{outside ? " · not in Cursor" : ""}}`;
    }});
    c.addEventListener("mouseleave", () => {{ tip.style.display = "none"; }});
    const label = p.chartLabel;
    const w = label.length * 5.6 + 4;
    const placed = place(x, y, w, 14);
    if (!placed) continue;
    const [lx, ly] = placed;
    boxes.push([lx, ly - 11, w, 14]);
    const t = add("text", {{x: lx, y: ly, fill: "#292524", "font-size": "11", "font-weight": onFrontier(p) ? "650" : "450"}});
    t.textContent = label;
  }}
  let lx = L;
  const ly = H - 22;
  const key = add("text", {{x: lx, y: ly, fill: "#44403c", "font-size": "11"}});
  key.textContent = "Pareto line";
  add("line", {{x1: lx + 72, y1: ly - 4, x2: lx + 98, y2: ly - 4, stroke: "#1c1917", "stroke-width": "1.75"}});
  add("circle", {{cx: lx + 118, cy: ly - 4, r: 5, fill: "#fff", stroke: "#1c1917", "stroke-width": 1.5, "stroke-dasharray": "3 2"}});
  const outsideKey = add("text", {{x: lx + 128, y: ly, fill: "#44403c", "font-size": "11"}});
  outsideKey.textContent = "Not in Cursor";
  lx += 230;
  for (const [name, color] of Object.entries(COLOR)) {{
    if (!pts.some(p => p.provider === name)) continue;
    add("circle", {{cx: lx, cy: ly - 4, r: 4.5, fill: color}});
    const t = add("text", {{x: lx + 8, y: ly, fill: "#44403c", "font-size": "11"}});
    t.textContent = name;
    lx += 18 + name.length * 6.2;
  }}
  document.getElementById("caption").textContent = mode === "teams"
    ? "Filled points: Teams and Enterprise price, including the $0.25/M token rate on third-party models. Grok is exempt. Hollow points stay at the provider API price, because Cursor does not sell them."
    : "Filled points: Cursor list price on individual plans. Hollow points are provider API prices for models that sit on the Pareto line and are not in Cursor.";
  const headers = ["Model", "Agent on the benchmark", "Index", "Cost on this chart", "In Cursor", "On the line"];
  const table = document.getElementById("table");
  table.innerHTML = "<thead><tr>" + headers.map((h, i) => `<th class="${{i === 2 || i === 3 ? "num" : ""}}">${{h}}</th>`).join("") + "</tr></thead>";
  const body = document.createElement("tbody");
  for (const p of pts) {{
    const tr = document.createElement("tr");
    if (onFrontier(p)) tr.className = "on";
    const cells = [
      p.label, p.agent, p.index.toFixed(2),
      "$" + costOf(p).toFixed(2),
      p.inCursor ? "Yes" : "No",
      onFrontier(p) ? "Yes" : ""
    ];
    cells.forEach((value, i) => {{
      const td = document.createElement("td");
      if (i === 2 || i === 3) td.className = "num";
      td.textContent = value;
      tr.appendChild(td);
    }});
    body.appendChild(tr);
  }}
  table.appendChild(body);
}}

function setMode(next) {{
  mode = next;
  document.getElementById("individual").setAttribute("aria-pressed", String(next === "individual"));
  document.getElementById("teams").setAttribute("aria-pressed", String(next === "teams"));
  draw();
}}
document.getElementById("individual").onclick = () => setMode("individual");
document.getElementById("teams").onclick = () => setMode("teams");

const ex = document.getElementById("excluded");
ex.innerHTML = "<thead><tr><th>Run</th><th class='num'>Index</th><th class='num'>AA cost</th><th>Why it is off</th></tr></thead>";
const exBody = document.createElement("tbody");
for (const row of RESULT.excluded) {{
  const tr = document.createElement("tr");
  [row.label, row.index.toFixed(2), "$" + row.aaCostUsd.toFixed(2), row.reason].forEach((value, i) => {{
    const td = document.createElement("td");
    if (i === 1 || i === 2) td.className = "num";
    td.textContent = value;
    tr.appendChild(td);
  }});
  exBody.appendChild(tr);
}}
ex.appendChild(exBody);
setMode("individual");
</script>
</body>
</html>
"""
    (OUT / "chart.html").write_text(html)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    result = build()
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "individual.svg").write_text(
        svg_chart(
            result,
            "individualUsd",
            "paretoIndividual",
            "Coding Agent Index vs Cursor cost per task",
            "Filled points: Cursor list price · Hollow points: not sold in Cursor · 29 Sep 2026",
        )
    )
    (OUT / "teams.svg").write_text(
        svg_chart(
            result,
            "teamsUsd",
            "paretoTeams",
            "Coding Agent Index vs Cursor cost per task",
            "Filled points: Teams price · Hollow points: provider API price, not in Cursor · 29 Sep 2026",
        )
    )
    write_html(result)
    print("individual frontier:")
    for label in result["frontierIndividual"]:
        point = next(p for p in result["points"] if p["label"] == label)
        print(f"  {point['index']:6.2f}  ${point['individualUsd']:8.2f}  {label}")
    print("teams frontier:")
    for label in result["frontierTeams"]:
        point = next(p for p in result["points"] if p["label"] == label)
        print(f"  {point['index']:6.2f}  ${point['teamsUsd']:8.2f}  {label}")
    differ = [p for p in result["points"] if p["priceDiffersFromAa"]]
    print("price differs:", [(p["label"], p["aaCostUsd"], p["individualUsd"]) for p in differ])


if __name__ == "__main__":
    main()

# Cursor price vs Coding Agent Index

Scatter of coding quality against what that same task would cost in Cursor, with the Pareto line drawn through.

Intelligence is the [Artificial Analysis Coding Agent Index v1.5](https://artificialanalysis.ai/agents/coding-agents) (equal weight of DeepSWE v1.1, Terminal-Bench 4.0, and SWE-Atlas-QnA). Cost is recomputed from those runs' token counts using the [Cursor models and pricing](https://cursor.com/docs/models-and-pricing) table retrieved 29 Sep 2026.

The score belongs to the harness Artificial Analysis ran (Claude Code, Codex, Grok Build, and so on), not to Cursor's own agent. The dollar figure is what those measured tokens cost at Cursor's rates.

## Charts

- `output/chart.html` — both price views, hover for the exact point
- `output/individual.svg` — filled points are Pro, Pro Plus, Ultra, and Start list prices
- `output/teams.svg` — filled points add the $0.25 per million token rate on third-party models

Hollow points are on the Pareto line and are not sold in Cursor. Their cost is the provider API price from Artificial Analysis. Open the HTML file in a browser. The dark line is the Pareto set: no other plotted model is both smarter and cheaper.

## How the cost is rebuilt

Each run publishes average input, cache-read, and output tokens per task, plus the dollar cost Artificial Analysis computed from provider list prices.

Uncached input is input minus cache reads. Cache-write tokens are not published. Where the provider charges a separate write price, those tokens are the leftover dollars after pricing the published buckets, divided by that write price.

Cursor's list price is then applied to the same four buckets. When Cursor has no separate cache-write fee, write tokens are billed as ordinary input.

On the individual plans every plotted model except Gemini 3.8 Flash uses the same per-token rates Artificial Analysis used, so the task cost matches theirs. Gemini's output price is $3.50 per million tokens in Cursor and $3.75 on Artificial Analysis, which moves that one point from $2.47 to $2.44.

Teams and Enterprise add $0.25 per million tokens on input, output, and cache for third-party models. Grok is exempt. That fee is why Luna (max) leaves the frontier on the Teams chart: the run reads about 15 million tokens, and the fee is several dollars on a model whose own API cost is $0.44.

Fast mode, long-context multipliers, and regional uplifts are not applied. Per-task token totals are sums across many turns, not one context window, so a 2× long-context rate cannot be assigned from this data.

## Frontier, individual plans

Hollow rows are not sold in Cursor. Their cost is the provider API price.

| Model | In Cursor | Index | Cost per task |
| --- | --- | ---: | ---: |
| DeepSeek V4 Flash (max) | No | 38.74 | $0.09 |
| GPT-6 Luna (max) | No | 41.07 | $0.18 |
| DeepSeek V4 Pro (max) | No | 43.05 | $0.24 |
| GPT-5.6 Luna (max) | Yes | 43.22 | $0.44 |
| Claude Sonnet 5.5 (medium) | Yes | 45.88 | $0.62 |
| Claude Sonnet 5.5 (high) | Yes | 55.01 | $1.24 |
| GPT-6 Sol (max) | No | 56.66 | $2.99 |
| Claude Sonnet 5.5 (xhigh) | Yes | 62.87 | $3.33 |
| Claude Opus 5.5 (max) | Yes | 65.99 | $13.04 |
| Claude Sonnet 5.5 (max) | Yes | 68.36 | $14.19 |

GPT-6 Astra and Qwen3.8 Max are not on this line: a Cursor model is both smarter and cheaper. On the Teams chart the token rate pushes Sonnet xhigh to $5.13, so the Devin Fusion run of GPT-6 Astra plus SWE-2 (index 58.89, $4.54 API) joins the line. Composer 2.5 and Grok 4.5 have Cursor prices and no Coding Agent Index score, so they are not plotted.

Fable 5.1 (max*) is included. Artificial Analysis marks that run as falling back to another model on some safety refusals.

## Regenerate

```bash
python3 analysis.py
```

Inputs live in `data/`. `coding_agent_runs.json` is the 29 Sep 2026 snapshot of the public coding-agents page. `cursor_prices.json` and `aa_prices.json` are the list prices used to reprice it.

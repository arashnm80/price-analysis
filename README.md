# Cursor price vs Coding Agent Index

Scatter of coding quality against what that same task would cost in Cursor, with the Pareto line drawn through.

Intelligence is the [Artificial Analysis Coding Agent Index v1.5](https://artificialanalysis.ai/agents/coding-agents) (equal weight of DeepSWE v1.1, Terminal-Bench 4.0, and SWE-Atlas-QnA). Cost is recomputed from those runs' token counts using the [Cursor models and pricing](https://cursor.com/docs/models-and-pricing) table retrieved 29 Sep 2026.

The score belongs to the harness Artificial Analysis ran (Claude Code, Codex, Grok Build, and so on), not to Cursor's own agent. The dollar figure is what those measured tokens cost at Cursor's rates.

## Charts

- `output/chart.html` — both price views, hover for the exact point
- `output/individual.svg` — Pro, Pro Plus, Ultra, and Start: list price only
- `output/teams.svg` — Teams and Enterprise: list price plus the $0.25 per million token rate on third-party models

Open the HTML file in a browser. The dark line is the Pareto set: no other plotted model is both smarter and cheaper.

## How the cost is rebuilt

Each run publishes average input, cache-read, and output tokens per task, plus the dollar cost Artificial Analysis computed from provider list prices.

Uncached input is input minus cache reads. Cache-write tokens are not published. Where the provider charges a separate write price, those tokens are the leftover dollars after pricing the published buckets, divided by that write price.

Cursor's list price is then applied to the same four buckets. When Cursor has no separate cache-write fee, write tokens are billed as ordinary input.

On the individual plans every plotted model except Gemini 3.8 Flash uses the same per-token rates Artificial Analysis used, so the task cost matches theirs. Gemini's output price is $3.50 per million tokens in Cursor and $3.75 on Artificial Analysis, which moves that one point from $2.47 to $2.44.

Teams and Enterprise add $0.25 per million tokens on input, output, and cache for third-party models. Grok is exempt. That fee is why Luna (max) leaves the frontier on the Teams chart: the run reads about 15 million tokens, and the fee is several dollars on a model whose own API cost is $0.44.

Fast mode, long-context multipliers, and regional uplifts are not applied. Per-task token totals are sums across many turns, not one context window, so a 2× long-context rate cannot be assigned from this data.

## Frontier, individual plans

| Model | Index | Cost per task |
| --- | ---: | ---: |
| GPT-5.6 Luna (max) | 43.22 | $0.44 |
| Claude Sonnet 5.5 (medium) | 45.88 | $0.62 |
| Claude Sonnet 5.5 (high) | 55.01 | $1.24 |
| Claude Sonnet 5.5 (xhigh) | 62.87 | $3.33 |
| Claude Opus 5.5 (max) | 65.99 | $13.04 |
| Claude Sonnet 5.5 (max) | 68.36 | $14.19 |

On Teams and Enterprise, Luna drops off and Claude Sonnet 5.5 (low) at $0.73 becomes the cheap end. The rest of the line is the same models, at higher third-party cost. Grok 4.7 and Grok 4.6 stay at list price and are still inside the frontier, because a lower Sonnet effort setting scores higher for less money on this index.

## Left off on purpose

GPT-6 Sol, GPT-6 Luna, GPT-6 Astra, DeepSeek V4, and Qwen3.8 Max are on the Artificial Analysis chart and are not rows on Cursor's pricing page. Devin Fusion runs two models, so it is not a Cursor model choice either. Composer 2.5 and Grok 4.5 are on the Cursor price list and have no Coding Agent Index score, so they are not plotted.

Fable 5.1 (max*) is included. Artificial Analysis marks that run as falling back to another model on some safety refusals.

## Regenerate

```bash
python3 analysis.py
```

Inputs live in `data/`. `coding_agent_runs.json` is the 29 Sep 2026 snapshot of the public coding-agents page. `cursor_prices.json` and `aa_prices.json` are the list prices used to reprice it.

# sac — Search as Code Experiments

Testing whether code-generation beats tool-calling for complex search orchestration.
Runs on cloudfleet Spot VMs (Azure + Tailscale).

## Project purpose

Reproduce and extend the Perplexity "Search as Code" (SaC) pattern on commodity infra.
Combine with Vercel Eve's filesystem-first agent architecture.
Answer: should we adopt code-gen over MCP tools for search?

## Stack

- **Search backend:** Perplexity API (Sonar Pro) or Brave Search API
- **Sandbox:** Docker containers on Azure Spot VMs (D4as_v5 / D8as_v5)
- **Orchestration:** Claude API (Opus 4.8) or DeepSeek v4
- **Models (local):** Gemma 4B Q4 via llama.cpp (optional, for LLM judge)
- **Infra:** Azure Spot VMs in Central India, Tailscale mesh, cf-openclaw control plane
- **Provisioning:** Azure CLI wrapped by thin Python harness (<200 lines per file)

## File structure

```
skills/         ← FAT: experiment designs, SDK design, agent patterns (.md)
harness/        ← THIN: provision, sandbox runner, benchmark, teardown (.py)
infra/          ← Cloud-init configs, Dockerfiles
results/        ← Experiment outputs, one file per run
```

## Philosophy

Fat skills, thin harness. Intelligence lives in .md files. Python is plumbing.

Skills are under 2000 tokens each (Perplexity pattern: guard against context bloat).
Harness files are under 200 lines each.

## Key references

- `cloudfleet/docs/spot-vm-reference.md` — Spot VM pricing, eviction rates, provisioning
- `cloudfleet/docs/sac-experiments.md` — Full experiment designs
- `cloudfleet/PLAN-SAC-EXPERIMENTS.md` — Master experiment plan
- `brain/pages/references/agentic-engineering-hacks.md` — Matt Van Horn's workflow

## Search primitives (sac-sdk)

Not a monolithic search API. Composable primitives models can orchestrate via code:

- `search.web_many` — parallel search with configurable concurrency
- `search.page_fetch` — Playwright-based page content extraction
- `dedup.by_url` / `dedup.by` — deduplication
- `llm.extract_many` — structured extraction with schema
- `render.to_context` — render results for model consumption
- `filter.by_regex` — deterministic filtering

## Experiments (in order)

1. **SaC Reproduction** — CVE vendor advisory benchmark, prove the pattern works
2. **Code-gen vs Tool-calling** — Head-to-head on 5 tasks of increasing complexity
3. **Multi-agent Fan-out** — Scale to real wide-research tasks
4. **Filesystem-first Agent** — Eve pattern without Vercel
5. **Local LLM Judge** — Gemma 4B for extraction verification
6. **Persistent Sandbox** — Filesystem serde vs REPL for long trajectories

## Working style

- Follow shared conventions from `C:\Learn\CLAUDE.md`
- Write skills first, harness second, infra last
- Each experiment produces a results file
- Decisions captured to brain: `python -m brain page set experiments/sac/<slug>`

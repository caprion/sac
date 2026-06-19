# Search as Code — Experiments

Testing whether models that *write search code* outperform models that *call search tools*.

## What this is

Perplexity proved code-generation beats function-calling for complex search orchestration ([Rethinking Search as Code](https://research.perplexity.ai/articles/rethinking-search-as-code-generation)). Vercel open-sourced the filesystem-first agent pattern ([Eve](https://vercel.com/docs/eve)).

We're testing both patterns on commodity infra: Azure Spot VMs + Tailscale mesh.

## The question

Does a model that generates Python code orchestrating search primitives (fan-out, dedup, extraction, aggregation) produce better results than a model calling the same primitives as MCP tools?

And can we do it on a $15/month Spot VM instead of a managed platform?

## Experiments

| # | Experiment | Question | Time | Cost |
|---|-----------|----------|------|------|
| 1 | SaC reproduction | Does the pattern work on our infra? | 2-3h | ~$0.20 |
| 2 | Code-gen vs tool-calling | Is code-gen actually better? | 4-6h | ~$0.50 |
| 3 | Multi-agent fan-out | Does it scale to real research? | 4-6h | ~$0.50 |
| 4 | Filesystem-first agent | Eve pattern without Vercel | 3-4h | ~$0.20 |
| 5 | Local LLM judge | Gemma 4B for extraction verification | 2-3h | ~$0.50 |
| 6 | Persistent sandbox | State across long trajectories | 3-4h | ~$0.30 |

## Quick start

```bash
# Provision a spot sandbox
python harness/provision.py burst --name cf-spot-burst

# Run the benchmark
python harness/benchmark.py --agent code-gen --model claude-opus-4-8

# Tear down
python harness/teardown.py cf-spot-burst
```

## Infra

Runs on [cloudfleet](https://github.com/caprion/cloudfleet) Spot VMs. See `cloudfleet/docs/spot-vm-reference.md` for pricing and provisioning.

## Philosophy

Fat skills, thin harness. Intelligence in `skills/*.md`. Python in `harness/*.py` (<200 lines per file).

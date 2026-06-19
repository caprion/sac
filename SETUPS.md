# SETUPS: Experiment Configurations

Last updated: 2026-06-19
Philosophy: Fat skills, thin harness. Spot VMs are cattle. Results always go to git.

---

## Setup Map

```
Setup 0: Foundation ──────► Everything builds on this
│
├── Setup 1: Core ────────► Exp 1 (SaC Repro) + Exp 2 (Code-gen vs TC)
│   └── Infra: 1x D8as_v5 Spot, cf-openclaw orchestrator
│
├── Setup 2: Multi-agent ─► Exp 4 (Multi-agent fan-out)
│   └── Infra: 1x D8as_v5 Spot (parallel sandboxes), cf-openclaw
│
├── Setup 3: Filesystem ──► Exp 3 (Eve-style file-per-capability agent)
│   └── Infra: cf-openclaw agent + D4as_v5 Spot sandbox
│
├── Setup 4: Local LLM ────► Exp 5 (Gemma 4B as LLM judge)
│   └── Infra: E8as_v5 Spot (64GB) + persistent models disk
│
└── Setup 5: Persistence ─► Exp 6 (State across long trajectories)
    └── Infra: Same as Setup 1
```

---

## Fat Skills vs Thin Harness — The Split

```
skills/                         FAT — Intelligence lives here
├── sac-sdk.md                  SDK design: primitives, API, rationale
├── sandbox-pattern.md          Sandbox architecture, state, lifecycle
├── agent-pattern.md            Filesystem-first agent conventions
├── experiment-1-repro.md       CVE benchmark, metrics, expected results
├── experiment-2-codegen-vs-tc.md  5 arms, 5 tasks, hypotheses
├── experiment-3-filesystem.md    Agent built from files
├── experiment-4-multi-agent.md   Orchestrator + N sub-agents
├── experiment-5-local-judge.md   Model selection, API design, break-even
└── experiment-6-persistent.md    Serde vs REPL, state management

harness/                        THIN — Python plumbing, <200 lines each
├── provision.py                Spot VM provisioning (wraps az CLI)
├── sandbox_runner.py           HTTP API: POST /execute, runs code
├── sandbox_client.py           Client: send code to sandbox, get results
├── benchmark.py                Runs tasks, collects metrics
├── metrics.py                  Token counting, timing, accuracy scoring
├── eval_dsqa.py                DSQA auto-rater (calls Gemini 2.5 Flash)
├── eval_browsecomp.py          BrowseComp-Plus scoring (evidence match)
└── teardown.py                 Detach disks, delete VMs, verify cleanup

infra/                          INFRA — Cloud-init, Dockerfiles
├── cloud-init/
│   ├── spot-worker.yml         Base: swap, Tailscale, Docker, Python
│   └── spot-model-host.yml     + llama.cpp, model download
└── docker/
    ├── sandbox.Dockerfile      SaC sandbox container
    └── compose.yml             Local dev: sandbox + runner

results/                        OUTPUTS — Committed to git, survives teardown
├── exp1-cve/
├── exp2-codegen-vs-tc/
├── exp3-filesystem/
├── exp4-multi-agent/
├── exp5-local-judge/
└── exp6-persistent/
```

---

## Output Persistence Pattern

Every experiment run writes results to `results/<experiment>/`. Nothing valuable lives ONLY on a Spot VM.

```
                    ┌──────────────────────────┐
                    │   Spot VM (ephemeral)     │
                    │   ┌──────────────────┐   │
                    │   │ Docker: sandbox   │   │
                    │   │ /state/           │   │
                    │   │ /results/         │───┼──▶ sandbox_client.py
                    │   └──────────────────┘   │     pulls results back
                    └──────────────────────────┘     to yantra
                              │
                              ▼
                    ┌──────────────────────────┐
                    │   yantra (this machine)   │
                    │   C:\experiments\sac\     │
                    │   ├── results/            │
                    │   │   └── <experiment>/   │
                    │   │       ├── metrics.json│
                    │   │       ├── runs/       │
                    │   │       └── README.md   │
                    │   └── skills/             │
                    └──────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────────┐
                    │   GitHub                  │
                    │   github.com/caprion/sac  │
                    └──────────────────────────┘
```

Flow for each experiment run:
1. `provision.py` spins up spot VM (or reuses existing)
2. `benchmark.py` sends tasks to sandbox via Tailscale IP
3. Sandbox executes, writes intermediate state to /state/
4. `sandbox_client.py` pulls results back to yantra after each task
5. Results committed to `results/<experiment>/` in git
6. `teardown.py` tears down spot VM (or leaves it for next experiment)

---

## SSH Access

All spot VMs join Tailscale mesh during cloud-init. Same pattern as all cloudfleet nodes:

```bash
# From yantra — Tailscale SSH (no keys needed once mesh is joined)
ssh sumit@<tailscale-ip>

# Or traditional SSH if Tailscale isn't up yet
ssh -i ~/.ssh/id_ed25519 sumit@<public-ip>
```

Cloud-init includes Tailscale join with the fleet's reusable auth key.
After bootstrap, public IP can be removed — all access via Tailscale mesh.

---

## Setup 0: Foundation

**Goal:** sac-sdk package, sandbox Docker image, provisioning harness, dataset loaders.
**Infra:** None yet (local dev on yantra).
**Skills:** `sac-sdk.md`, `sandbox-pattern.md`, `agent-pattern.md`
**Harness:** `provision.py`, `sandbox_runner.py`, `sandbox_client.py`, `metrics.py`, `eval_dsqa.py`, `eval_browsecomp.py`, `teardown.py`
**Infra files:** `infra/cloud-init/spot-worker.yml`, `infra/docker/sandbox.Dockerfile`

### What gets built

```
sac-sdk/                         Python package
├── sac_sdk/
│   ├── __init__.py
│   ├── search.py               search.web_many, search.web_single, search.page_fetch
│   ├── dedup.py                dedup.by_url, dedup.by
│   ├── llm.py                  llm.extract_many, llm.extract_single
│   ├── render.py               render.to_context
│   └── filter.py               filter.by_regex, filter.by_predicate
├── pyproject.toml
└── README.md
```

### Verification

- [ ] `pip install -e .` works locally
- [ ] `search.web_many(["test query"])` returns structured results
- [ ] `llm.extract_many(items, schema)` returns typed objects
- [ ] Docker image builds: `docker build -t sac-sandbox infra/docker/`
- [ ] Sandbox runner starts: `docker run -p 8282:8282 sac-sandbox`
- [ ] DSQA dataset loads: `load_dataset("google/deepsearchqa")`
- [ ] BrowseComp-Plus dataset loads with decryption
- [ ] `provision.py --dry-run` validates CLI args

---

## Setup 1: Core Experiments

**Goal:** Exp 1 (SaC Repro) + Exp 2 (Code-gen vs Tool-calling)
**Skills:** `experiment-1-repro.md`, `experiment-2-codegen-vs-tc.md`
**Infra:** 1x D8as_v5 Spot VM (cf-spot-burst), cf-openclaw as orchestrator

### Infra diagram

```
yantra (this machine)
│
├── harness/benchmark.py ──► sends tasks, collects results
│
├── cf-openclaw (always-on, D2as_v4)
│   └── Optional: orchestrator for tool-calling arm
│       Model calls search tools, sandbox client
│
└── cf-spot-burst (Spot, D8as_v5, 8vCPU 32GB)
    └── Docker: sac-sandbox container
        ├── POST /execute  {"code": "...", "session_id": "..."}
        ├── GET  /state/{session_id}
        └── DELETE /session/{session_id}
```

### Experiment 1 flow

```
1. Load CVE task definition from skills/experiment-1-repro.md
2. Load BrowseComp-Plus 50q sample
3. For each task:
   a. Model (Claude API) generates Python code
   b. Code sent to sandbox via POST /execute
   c. Sandbox runs code (calls search primitives, extracts, filters)
   d. Results pulled back to yantra
   e. Metrics collected: tokens, latency, accuracy
4. Compare against naive search baseline (single query → answer)
5. Write results to results/exp1-cve/
```

### Experiment 2 flow

```
5 arms × 5 tasks = 25 runs (plus human arm on 2-3 tasks)

For each arm:
  A: Single search → model answers directly
  B: Tool-calling loop → model calls search tools in loop
  C: Code-gen single shot → model writes one program
  D: Code-gen multi-turn → model writes code, sees results, writes more
  E: Human → person does the task with web search

Tasks:
  1. Simple (DSQA easy)
  2. Fan-out (BrowseComp-Plus, 3 evidence sources)
  3. Conditional (custom CVE-style)
  4. Aggregation (BrowseComp-Plus, 6 evidence sources)
  5. Wide (DSQA hard + BrowseComp-Plus)

Metrics per run:
  - Accuracy (DSQA auto-rater / BrowseComp evidence match)
  - Total tokens (prompt + completion)
  - Number of model calls
  - Wall-clock time
  - Sandbox cost ($/hr × duration)
  - Distractor sensitivity: does accuracy drop as result count increases?
```

### Provisioning

```bash
python harness/provision.py burst --name cf-spot-burst --size D8as_v5
```

### Teardown

```bash
# After experiments complete, results safely in git
python harness/teardown.py cf-spot-burst
```

---

## Setup 2: Multi-agent Fan-out

**Goal:** Exp 4 — Orchestrator decomposes wide task, spawns N sub-agents, fans out across sandboxes.
**Skills:** `experiment-4-multi-agent.md`
**Infra:** 1x D8as_v5 Spot (or D16as_v5 for 8+ parallel sandboxes)

### Infra diagram

```
cf-openclaw (orchestrator)
│
├── Decomposes task into N sub-tasks
├── Spawns N sandbox sessions on cf-spot-burst
│
└── cf-spot-burst (D8as_v5, 8vCPU 32GB)
    ├── Sandbox 1 ──► Sub-agent 1 (Claude releases)
    ├── Sandbox 2 ──► Sub-agent 2 (OpenAI releases)
    ├── Sandbox 3 ──► Sub-agent 3 (Google releases)
    ├── Sandbox 4 ──► Sub-agent 4 (Open-source models)
    └── Sandbox 5 ──► Sub-agent 5 (Chinese models)
         │
         ▼
    Orchestrator aggregates, deduplicates, verifies
```

### Dataset

50 hard BrowseComp-Plus queries + 50 hard DSQA prompts.
Wide tasks requiring synthesis from 5+ sources each.

### Metrics

- Coverage: did we miss any source?
- Accuracy: are extracted facts correct?
- Time: parallel vs sequential baseline
- Cost: total tokens across orchestrator + all sub-agents
- Dedup quality: how many duplicates across sub-agents?

### Provisioning

```bash
# For 5 parallel sub-agents
python harness/provision.py burst --name cf-spot-burst --size D8as_v5

# For 8+ parallel sub-agents
python harness/provision.py burst --name cf-spot-burst --size D16as_v5
```

---

## Setup 3: Filesystem-first Agent

**Goal:** Exp 3 — Agent defined entirely by files. Same tasks as Exp 2, different agent architecture.
**Skills:** `experiment-3-filesystem.md`, `agent-pattern.md`
**Infra:** cf-openclaw runs the agent. D4as_v5 Spot runs sandbox.

### Agent structure (on cf-openclaw)

```
agent/
├── agent.py              # Model: Claude Opus 4.8
├── instructions.md        # Always-on system prompt
├── tools/                 # One typed tool per file
│   ├── web_search.py      # search.web_many
│   ├── browse_page.py     # Playwright page fetch
│   ├── extract_data.py    # llm.extract_many
│   └── run_python.py      # Execute code in sandbox
├── skills/                # Loaded on demand, <2000 tokens each
│   ├── cve-research.md    # How to research CVEs
│   ├── multi-source.md    # How to synthesize from many sources
│   └── verification.md    # How to verify extracted data
└── sandbox/
    └── config.py           # cf-spot-01:8282, Tailscale IP
```

### What we compare

Same 5 tasks from Exp 2. Same arm D (code-gen multi-turn).
Two agent implementations:
- **Monolithic**: single prompt, all tools inline, no skill files
- **Filesystem-first**: file-per-capability, skills loaded on demand

Metrics: same as Exp 2, plus skill-loading overhead (tokens consumed by skill files).

### Provisioning

```bash
python harness/provision.py worker --name cf-spot-01 --size D4as_v5
```

---

## Setup 4: Local LLM Judge

**Goal:** Exp 5 — Gemma 4B Q4 as extraction verification judge. Compare accuracy and cost vs API-based judge.
**Skills:** `experiment-5-local-judge.md`
**Infra:** E8as_v5 Spot (64GB) or D16as_v5 (64GB). Persistent 50GB models disk.

### Infra diagram

```
cf-spot-model (E8as_v5, 64GB RAM, Spot)
│
├── llama.cpp server
│   └── Gemma 3 4B Q4_K_M (~2.6 GB)
│   └── Listening on :8080
│
├── POST /judge
│   {
│     "passages": [...],
│     "schema": {"cve": str, "severity": str, ...},
│     "claim": "CVE-2024-1234 affects Chrome 120.0"
│   }
│   → {"verdict": "supported", "confidence": 0.92, "evidence": "..."}
│
└── Persistent models disk (cf-models, 50GB)
    └── /models/gemma-4b-q4_k_m.gguf
```

### What we compare

200 BrowseComp-Plus evidence verification tasks.
- **Arm A**: Claude Haiku as judge (API)
- **Arm B**: Gemma 4B Q4 as judge (local)

Metrics:
- Accuracy parity: does local match API on >90% of verdicts?
- Latency: API vs local
- Cost: API tokens vs spot VM + disk cost
- Break-even volume: at what QPS does local become cheaper?

### Provisioning

```bash
# Create persistent models disk (once)
az disk create --rg cloudfleet-rg --name cf-models --size-gb 50 --sku StandardSSD_LRS

# Provision model host
python harness/provision.py model --name cf-spot-model --size E8as_v5 --models-disk cf-models
```

---

## Setup 5: Persistent Sandbox

**Goal:** Exp 6 — Filesystem serde vs REPL for long multi-turn research trajectories.
**Skills:** `experiment-6-persistent.md`
**Infra:** Same as Setup 1 (D8as_v5).

### What we compare

20 DSQA causal-chain prompts (10-turn trajectories each).
- **Arm A (Filesystem serde)**: Each turn writes state to /state/*.json. Next turn reads it.
- **Arm B (REPL)**: Long-lived Python process. Appends code each turn. State in memory.

Metrics:
- Completion rate: do both finish 10 turns?
- State fidelity: does any state get lost or corrupted?
- Token efficiency: tokens spent managing state
- Failure modes: what breaks in each arm?

### Provisioning

Same as Setup 1 — reuse cf-spot-burst.

---

## Execution Order

```
Phase 0: Foundation (on yantra, no infra)
  ├── Build sac-sdk
  ├── Build sandbox Docker image
  ├── Write all harness scripts
  ├── Download and verify datasets
  └── Gate: docker run sandbox works locally

Phase 1: Core (Setup 1)
  ├── Provision cf-spot-burst (D8as_v5)
  ├── Run Exp 1 (SaC Repro — CVE + BrowseComp 50q)
  ├── Run Exp 2 (Code-gen vs TC — 5 arms × 5 tasks)
  ├── Push results to git
  ├── Tear down OR keep for Setup 2
  └── Gate: does code-gen beat tool-calling?

Phase 2: Scale (Setup 2)
  ├── Run Exp 4 (Multi-agent fan-out)
  ├── Push results to git
  └── Tear down

Phase 3: Agent Pattern (Setup 3)
  ├── Provision cf-spot-01 (D4as_v5) [if not already running]
  ├── Build filesystem-first agent on cf-openclaw
  ├── Run Exp 3 on same 5 tasks
  ├── Push results to git
  └── Gate: is file-per-capability better?

Phase 4: Local Compute (Setup 4)
  ├── Provision cf-spot-model (E8as_v5) + models disk
  ├── Download Gemma 4B
  ├── Run Exp 5 (Local judge vs API judge)
  ├── Push results to git
  └── Tear down or keep models disk

Phase 5: Reliability (Setup 5)
  ├── Reuse cf-spot-burst
  ├── Run Exp 6 (Serde vs REPL)
  ├── Push results to git
  └── Final teardown

Phase 6: Synthesize
  ├── Write findings to results/SUMMARY.md
  ├── Capture decisions to brain
  └── Publish: blog post / repo README
```

---

## Cost Summary

| Phase | Infra | Duration | Compute cost | API tokens (est.) |
|-------|-------|----------|-------------|-------------------|
| 0: Foundation | None (yantra) | N/A | $0 | $0 |
| 1: Core | D8as_v5 Spot | ~8-10h | ~$0.30-0.40 | ~$15-25 |
| 2: Scale | D8as_v5 Spot | ~4-6h | ~$0.15-0.25 | ~$10-15 |
| 3: Agent | D4as_v5 Spot | ~3-4h | ~$0.08-0.12 | ~$5-10 |
| 4: Local LLM | E8as_v5 Spot + models disk | ~2-3h | ~$0.12-0.18 | ~$2-5 |
| 5: Persistence | Same as Setup 1 | ~3-4h | ~$0.12-0.18 | ~$5-10 |
| 6: Synthesize | None | N/A | $0 | $0 |
| **Total** | | **~22-30h** | **~$1-2** | **~$37-65** |

Total experiment cost: roughly $40-70. Less than one month of cf-openclaw.

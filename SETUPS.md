# SETUPS: Experiment Configurations

Last updated: 2026-06-20
Philosophy: Fat skills, thin harness. Deallocate when idle. Results always go to git.

## Infra: Single VM, Deallocate-When-Idle

```
cf-sac (D16as_v5, 16 vCPU, 64 GB, 30 GB Premium SSD, regular)
│
├── Docker: sac-sandbox container
│   ├── POST /execute  {"code": "...", "session_id": "..."}
│   ├── GET  /state/{session_id}
│   └── DELETE /session/{session_id}
│
├── /opt/sac/              ← git repo (github.com/caprion/sac)
├── /opt/sac/datasets/     ← DSQA + BrowseComp-Plus (persist on disk)
├── /opt/sac/sac_sdk/      ← search primitives
└── /state/                ← sandbox state (ephemeral per session)

Lifecycle:
  az vm start cf-sac       → ~2 min to ready
  Run experiments          → $0.444/hr compute
  az vm deallocate cf-sac  → $0 compute, ~$5/mo disk
```

## Why One VM Works

- 16 vCPUs: Run 5-6 parallel sandbox containers for Exp 4 (multi-agent)
- 64 GB RAM: Host Gemma 4B (2.6 GB) + multiple sandboxes for Exp 5
- Docker handles isolation — no need for separate VMs per sandbox
- Deallocate-when-idle: compute cost only when actively experimenting
- 30 GB disk persists everything: datasets, code, Docker images

## Setup Map

```
Setup 0: Foundation (local, no VM needed)
│   Build sac-sdk, Docker image, harness scripts
│
├── Setup 1: Core
│   └── Exp 1 (SaC Repro) + Exp 2 (Code-gen vs TC)
│       VM: cf-sac, 5 arms × 5 tasks
│       ~10 hours compute, ~$4.44
│
├── Setup 2: Multi-agent
│   └── Exp 4 (Orchestrator + N sub-agents)
│       VM: cf-sac, parallel Docker sandboxes
│       ~5 hours compute, ~$2.22
│
├── Setup 3: Filesystem Agent
│   └── Exp 3 (Eve-style file-per-capability)
│       VM: cf-sac sandbox + cf-openclaw agent host
│       ~4 hours compute, ~$1.78
│
├── Setup 4: Local LLM
│   └── Exp 5 (Gemma 4B as LLM judge)
│       VM: cf-sac, 64 GB RAM for llama.cpp
│       ~3 hours compute, ~$1.33
│
└── Setup 5: Persistence
    └── Exp 6 (Serde vs REPL for long trajectories)
        VM: cf-sac
        ~4 hours compute, ~$1.78
```

## Fat Skills vs Thin Harness

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
├── vm.py                       VM lifecycle: start, deallocate, status, ssh
├── sandbox_runner.py           HTTP API: POST /execute, runs code (on VM)
├── sandbox_client.py           Client: send code to sandbox, get results (local)
├── benchmark.py                Runs tasks, collects metrics
├── metrics.py                  Token counting, timing, accuracy scoring
├── eval_dsqa.py                DSQA auto-rater (calls Gemini 2.5 Flash)
├── eval_browsecomp.py          BrowseComp-Plus scoring (evidence match)
└── sync.py                     Push results from VM to git

infra/                          INFRA — Dockerfile, cloud-init (reference only)
├── docker/
│   └── sandbox.Dockerfile      SaC sandbox container
└── cloud-init/
    └── spot-worker.yml         Reference: bootstrap config (not used for cf-sac)

results/                        OUTPUTS — Committed to git, survives teardown
├── exp1-cve/
├── exp2-codegen-vs-tc/
├── exp3-filesystem/
├── exp4-multi-agent/
├── exp5-local-judge/
└── exp6-persistent/
```

## VM Lifecycle Commands

```bash
# Start VM (takes ~2 min)
python harness/vm.py start

# Check status
python harness/vm.py status

# SSH into VM (fetches current IP)
python harness/vm.py ssh

# Deallocate when done
python harness/vm.py deallocate

# One-shot: start, run command, deallocate
python harness/vm.py run --script harness/benchmark.py --args "--exp exp1"
```

These wrap: `az vm start/stop/show` + Tailscale IP resolution.

## Output Persistence Pattern

```
1. cf-sac running → sandbox executes → writes to /opt/sac/results/
2. harness/sync.py pulls results from VM to local C:\experiments\sac\results\
3. git commit + push to github.com/caprion/sac
4. Results survive VM deallocation (they're on the persistent OS disk AND in git)
```

Even if the VM is deleted entirely, results are in git. The VM disk is a cache, not the source of truth.

## Execution Order

```
Phase 0: Foundation (on yantra, no VM)
  ├── Build sac-sdk
  ├── Build sandbox Docker image
  ├── Write all harness scripts
  ├── Download and verify datasets
  └── Gate: everything works locally

Phase 1: Core (Setup 1)
  ├── Start cf-sac
  ├── Run Exp 1 (SaC Repro — CVE + BrowseComp 50q)
  ├── Run Exp 2 (Code-gen vs TC — 5 arms × 5 tasks)
  ├── Sync results to git
  ├── Deallocate cf-sac
  └── Gate: does code-gen beat tool-calling?

Phase 2: Multi-agent (Setup 2)
  ├── Start cf-sac
  ├── Run Exp 4 (Multi-agent fan-out)
  ├── Sync results to git
  └── Deallocate cf-sac

Phase 3: Filesystem Agent (Setup 3)
  ├── Start cf-sac
  ├── Build filesystem-first agent on cf-openclaw
  ├── Run Exp 3 on same 5 tasks
  ├── Sync results to git
  └── Deallocate cf-sac

Phase 4: Local LLM (Setup 4)
  ├── Start cf-sac
  ├── Download Gemma 4B, start llama.cpp
  ├── Run Exp 5 (Local judge vs API judge)
  ├── Sync results to git
  └── Deallocate cf-sac

Phase 5: Persistence (Setup 5)
  ├── Start cf-sac
  ├── Run Exp 6 (Serde vs REPL)
  ├── Sync results to git
  └── Deallocate cf-sac

Phase 6: Synthesize
  ├── Write findings to results/SUMMARY.md
  ├── Capture decisions to brain
  └── Publish: blog post / repo README
```

## Cost Summary

| Phase | Compute | Duration | Cost |
|-------|---------|----------|------|
| 0: Foundation | $0 | N/A | $0 |
| 1: Core | $0.444/hr | ~10h | ~$4.44 |
| 2: Multi-agent | $0.444/hr | ~5h | ~$2.22 |
| 3: Filesystem | $0.444/hr | ~4h | ~$1.78 |
| 4: Local LLM | $0.444/hr | ~3h | ~$1.33 |
| 5: Persistence | $0.444/hr | ~4h | ~$1.78 |
| 6: Synthesize | $0 | N/A | $0 |
| **Compute total** | | **~26h** | **~$11.55** |
| OS disk (monthly) | | | ~$5 |
| API tokens (est.) | | | ~$37-65 |
| **Grand total** | | | **~$54-82** |

All-in cost: less than one month of cf-openclaw.

# STRATEGY: What We're Trying to Learn

Last updated: 2026-06-19

## The Convergence

Four independent teams. Same architecture. Same timing.

```
                    CODE GENERATION
                    (models write code, not just call tools)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Perplexity SaC        Vercel Eve           Hornet Code Mode
   "Code-gen beats        "A file becomes      "Retrieval has to
    tool-calling"          a capability"        return structure,
                                                 not chunks"
        │                     │                     │
        ▼                     ▼                     ▼
   Search primitives     Skills as .md files   Primitives > harness
   as SDK functions      loaded on demand      Weak primitives =
        │                     │                unrecoverable ceiling
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    THE SAME ARCHITECTURE
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    Models reason     Skills are files      Code executes in
    about tasks       (<2000 tokens,        sandboxes (Docker,
                      loaded on demand)     microVMs, Spot VMs)
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ALL THREE AGREE ON:
                              1. Code-gen > tool-calling
                              2. Skills should be files, not prompts
                              3. Sandboxes isolate execution
                              4. Primitives determine the ceiling
```

## The Counterpoint

Hornet's Berlin Buzzwords talk (June 9, 2026):

> "When better retrieval makes agents worse"

The failure mode: retrieval metrics improve, but agent behavior degrades. Why? Persuasive but wrong context gets promoted into multi-step loops. Better recall means more distractors. The agent can't tell the difference between relevant and persuasively-wrong.

**This is the risk in our architecture too.** Better search primitives → more results → more distractors → worse agent decisions. The code-gen pattern MUST include verification, not just retrieval. BrowseComp-Plus hard negatives are the tool to test this.

## Datasets

### Public benchmarks we use

| Dataset | Source | Size | License | Ground truth | Tests |
|---------|--------|------|---------|-------------|-------|
| **DeepSearchQA (DSQA)** | Google DeepMind | 900 prompts, 17 domains | Apache 2.0, [HuggingFace](https://huggingface.co/datasets/google/deepsearchqa) | Auto-rater (Gemini 2.5 Flash) | Live-web navigation, multi-step causal chains |
| **BrowseComp-Plus** | U Waterloo | 830 queries, 100K docs | MIT, [HuggingFace](https://huggingface.co/datasets/Tevatron/browsecomp-plus) | Human-verified evidence + hard negatives | Fixed-corpus retrieval precision amid distractors |

### What each dataset tests

```
                    DSQA                          BrowseComp-Plus
                    ════                          ═══════════════
               Live web search                   Fixed 100K-doc corpus
               900 multi-step prompts            830 queries
               17 domains                        ~6 evidence docs each
               Auto-ratable                      Hard negatives (distractors!)
               Causal chains                     Fully reproducible

                    │                                  │
                    ▼                                  ▼
          Tests: can the agent              Tests: can the agent find
          navigate the real web             the right evidence amid
          to answer complex,                intentionally planted
          multi-step questions?             distractors?

                    │                                  │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                    DSQA → web navigation + reasoning
                    BrowseComp-Plus → retrieval precision
                    amid noise (Hornet's concern!)
```

### Custom tasks we build

| Task | Type | Ground truth | What it tests |
|------|------|-------------|---------------|
| **CVE Vendor Advisory** | Reproduction of SaC's headline result | NVD/CVE database cross-reference | SDK primitives, structured extraction, dedup |
| **5-task complexity gradient** | Simple → Fan-out → Conditional → Aggregation → Wide | Auto-rater + human review | Code-gen vs tool-calling across increasing complexity |

### Dataset assignment per experiment

| Experiment | Primary dataset | Sample size | Why |
|-----------|----------------|-------------|-----|
| Exp 1: SaC Repro | Custom CVE task + BrowseComp-Plus | 200+ CVEs + 50 queries | CVE tests primitives. BrowseComp tests retrieval precision. |
| Exp 2: Code-gen vs TC | DSQA + BrowseComp-Plus + 5 custom tasks | 100 DSQA + 100 BrowseComp + 5 custom | Full complexity gradient. Both live web and fixed corpus. |
| Exp 3: Filesystem agent | Same as Exp 2 | Same sample | Same tasks, different agent architecture. Isolated variable. |
| Exp 4: Multi-agent | BrowseComp-Plus (hard queries) + DSQA (hard) | 50 hard queries each | Wide research benefits from parallel fan-out. |
| Exp 5: Local LLM judge | BrowseComp-Plus evidence verification | 200 evidence passages | Fixed ground truth = clean accuracy comparison. |
| Exp 6: Persistent sandbox | DSQA (causal chain subset) | 20 long-trajectory prompts | Multi-step chains that build on prior answers. |

## Baseline Arms (5 + human)

How we compare. Every experiment picks the relevant arms.

| Arm | What it does | Analogy |
|-----|-------------|---------|
| **A: Single search** | One `search(query)` → answer. No iteration. | The floor. |
| **B: Tool-calling loop** | Model calls search tools in a loop. Results in context. Model decides next step. | **Current default.** Claude Code, ChatGPT Browse, Perplexity consumer. |
| **C: Code-gen single shot** | Model writes ONE Python program. Fans out, filters, extracts. Returns. No second turn. | Perplexity's claim: one program beats many turns. |
| **D: Code-gen multi-turn** | Model writes code → sees output → writes more code. Filesystem state between turns. | Full SaC pattern. The new default we're testing. |
| **E: Human** | Person does the task with web search. Run on 2-3 tasks max. | The ceiling. |

```
E: Human ────────────────┐
                         │  "How far from human-level synthesis?"
D: Code-gen multi-turn ──┤
                         │  "Can one program beat many turns?"  (C vs B)
C: Code-gen single shot ─┤
                         │  "Does code-gen beat the default?"   (D vs B)
B: Tool-calling loop ────┤
                         │  "Does multi-step even help?"        (B vs A)
A: Single search ────────┘
```

**Primary fight: B vs D** — tool-calling (current default) vs code-gen multi-turn (proposed default).
**Secondary fight: B vs C** — context-compression claim. Can a single program beat a conversation?

---

## What We're Testing

```
EXPERIMENTS MAP

    Primitives              Orchestration           Reliability
    (Hornet lens)           (SaC lens)              (Eve lens)
    ═══════════             ════════════            ═══════════

    Exp 1: SaC Repro        Exp 2: Code-gen         Exp 6: Persistent
    ┌──────────────┐        vs Tool-calling          Sandbox
    │ CVE pipeline │        ┌──────────────┐        ┌──────────────┐
    │ + sensitivity│        │ 5-task bench │        │ Serde vs REPL│
    │ to result    │        │ + DSQA 100   │        │ over 10-turn │
    │ count        │        │ + BrowseComp │        │ DSQA causal  │
    │ (Hornet: more│        │ 100 queries  │        │ chains       │
    │ = worse?)    │        │ 5 arms (A→E) │        │              │
    └──────┬───────┘        └──────┬───────┘        └──────┬───────┘
           │                       │                      │
           ▼                       ▼                      ▼
    "Can we build          "Does code-gen         "Does persistence
     the primitives?"       actually win?"         survive long runs?"


    Agent Shape            Local Compute           Scale
    (Eve lens)             (Cost lens)             (Production lens)
    ═══════════            ═══════════             ═════════════

    Exp 3: File-per-       Exp 5: Gemma 4B         Exp 4: Multi-agent
    capability agent       as LLM judge            fan-out
    ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
    │ Agent built   │       │ Local model   │       │ Orchestrator │
    │ from files.   │       │ vs API judge  │       │ + N sub-agts │
    │ Skills load   │       │ for extraction│       │ Parallel fan │
    │ on demand     │       │ verification  │       │ -out, dedup, │
    │ Same Exp 2    │       │ BrowseComp    │       │ aggregation  │
    │ tasks         │       │ evidence set  │       │ BrowseComp + │
    │               │       │               │       │ DSQA hard    │
    └──────┬───────┘       └──────┬───────┘       └──────┬───────┘
           │                      │                      │
           ▼                      ▼                      ▼
    "Does file-per-        "Is local compute     "Does the pattern
     capability work?"      cheaper at scale?"    scale horizontally?"
```

## The Why

### 1. Architecture Convergence Is a Signal

Perplexity, Vercel, and Hornet all independently converged on the same architecture within weeks. Code-gen + file-based skills + sandboxed execution + structured primitives. Not coincidence — an emerging default. We need to know if it works without their platforms.

### 2. The Retrieval Bottleneck Is Underexplored

GPT-4.1 with oracle retrieval = 93.49%. Same model with BM25 = 14.58%. A 79-point gap. The model isn't the bottleneck — retrieval is. And Hornet's counterintuitive finding: better retrieval can make agents worse via distractors. BrowseComp-Plus hard negatives let us test this directly.

### 3. Commodity Infra Changes Who Can Build This

Perplexity runs on proprietary sandboxes. Eve runs on Vercel microVMs. If the pattern works on $15/month Azure Spot VMs, it's accessible to anyone — not just platform companies.

## The Hypothesis

```
Code-gen search pipelines, running in sandboxes on commodity Spot VMs,
with filesystem-first skills and structured retrieval primitives,
will outperform tool-calling agents on complex multi-step search tasks
— at lower cost, with better reliability, and without platform lock-in.
```

## The Null Hypothesis

```
Code-gen and tool-calling perform similarly. The gains reported by
Perplexity are from their proprietary search stack and model fine-tuning,
not from the code-gen pattern itself. The pattern doesn't survive
commodity infra.
```

We design experiments that can prove the null hypothesis.

## The Output

1. **sac-sdk**: A working Python SDK of search primitives. Installable. Tested.
2. **Benchmark data**: Head-to-head results. Code-gen vs tool-calling. Open data on GitHub.
3. **Reference architecture**: The pattern running on Spot VMs. Reproducible by anyone.
4. **A story**: "Here's what happened when we tested the convergence on commodity infra."

## Output Capture & Persistence

Spot VMs are cattle, not pets. Results must survive teardown.

```
                    ┌──────────────────────┐
                    │   Spot VM (ephemeral) │
                    │   ┌──────────────┐   │
                    │   │ sandbox/      │   │
                    │   │ /state/       │───┼──▶ rsync to cf-openclaw
                    │   │ results.json  │   │   or git push from sandbox
                    │   └──────────────┘   │
                    └──────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │   GitHub repo         │
                    │   C:\experiments\sac\ │
                    │   ├── results/        │
                    │   │   ├── exp1/       │
                    │   │   ├── exp2/       │
                    │   │   └── ...         │
                    │   └── skills/         │
                    └──────────────────────┘
```

Rule: nothing of value lives ONLY on a spot VM. After every experiment run:
1. Results JSON + logs → `results/<experiment>/` in git
2. Sandbox state → serialized and committed (if useful for debugging)
3. Metrics → `results/<experiment>/metrics.json`
4. Spot VM → torn down or deallocated

---

Sources:
- Perplexity: [Rethinking Search as Code](https://research.perplexity.ai/articles/rethinking-search-as-code-generation) (May 2026)
- Vercel: [Eve Agent Framework](https://vercel.com/docs/eve) (June 17, 2026)
- Hornet: [Code Mode for Agentic Retrieval](https://hornet.dev/blog/code-mode-for-agentic-retrieval)
- Hornet: [When Better Retrieval Makes Agents Worse](https://2026.berlinbuzzwords.de/speaker/lester-solbakken/) (Berlin Buzzwords, June 9, 2026)
- DSQA: [DeepSearchQA on HuggingFace](https://huggingface.co/datasets/google/deepsearchqa) (Google DeepMind, Dec 2025)
- BrowseComp-Plus: [arXiv 2508.06600](https://arxiv.org/abs/2508.06600), [HuggingFace](https://huggingface.co/datasets/Tevatron/browsecomp-plus) (U Waterloo)

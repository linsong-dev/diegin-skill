<p align="center">
  <img src="assets/logo.svg" width="200" alt="DGEN">
</p>

<h1 align="center">Diegin · DGEN</h1>

<p align="center">
  <b>An always-on, self-evolving cognitive layer for AI</b><br>
  AI that learns from its mistakes like a human — smarter with every use
</p>

<p align="center">
  [![中文](https://img.shields.io/badge/中文-README-red)](README.md) | [![EN](https://img.shields.io/badge/EN-README-blue)](README.en.md) |
  <a href="https://github.com/linsong-dev/diegin-skill/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/version-3.9.4-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/python-3.12+-orange" alt="Python">
  <img src="https://img.shields.io/badge/Codex-ready-purple" alt="Codex">
</p>

---

## What Diegin Is in 30 Seconds

Diegin is an **OS-level evolution layer for AI**. It calls no external APIs, needs no GPU, and runs in pure Python.

> Normal AI: the mistakes it made today may happen again tomorrow
>
> AI with Diegin: errors are auto-detected → fixed and hardened on the spot → generalized → never repeated

## Architecture

```
User action → [Constancy Gate · Persistence] entry resume check (user confirmation)
            → [Pre-strategy · Gather] collect outputs + task_id
            → [Truth Gate] verify information (P0 unconditional priority)
            → [Shou-san · lightweight] scan failure modes (anchor: success_patterns≥4.0)
            → [One-Two-No-Three] alerting → vigilance (no blocking)
            → [Pre-strategy · Weigh] P0–P6 unified arbitration (P3 constancy resume first)
            → Execute
               ├─ success → [Gong-qi · Xing-zhi] distill patterns → [Generalization] semantic threshold <0.7
               └─ failure → [One-Two-No-Three · Three-Strike Lock] fix → harden → escalate
            → [Closure · Wan-xing] seal this round (4 states + read-only snapshot)
            → [Shou-san · deep] offline review (≥2 blocks in 3 rounds → emergency)
            → [Self-Mirror · Direction] mirror report → courage signal ×0.6 → P6 silent influence
```

## Core Files

| File | Role |
|:-----|:-----|
| engine/evo/main.py | Unified entry + scheduled maintenance |
| engine/evo/rule_engine.py | Rule engine (235 rules, 42 active; CRUD + matching + RULE-GUARD) |
| engine/evo/tracker.py | Behavior tracking (One-Two-No-Three chain, Shou-san/Gong-qi loop) |
| engine/evo/arbiter.py | Pre-strategy arbiter (P0–P6; P6 weight ±0.3 / ±0.1 per round) |
| engine/evo/pacemaker.py | Pacemaker (removed from Nine Chapters; kept for downtime/cron) |
| engine/evo/closure.py | Closure · Wan-xing (4-state sealing + read-only snapshot) |
| engine/evo/evidence_vault.py | Truth-gate evidence vault + quarterly falsification |
| engine/evo/error_detector.py | Error detection + One-Two-No-Three blocking (vigilance −0.2) |
| engine/evo/constancy.py | Constancy Gate · Persistence (task_id lifecycle / nesting≤3 / 30-day snapshots) |
| engine/evo/self_mirror.py | Self-Mirror · Direction (courage signal ×0.6 / P6 silent influence) |
| engine/evo/dashboard.py | Health dashboard |
| engine/mindol/ | Mindol semantic memory engine |

## The Nine Chapters (Four Laws · Three Gates · One Lock · One Mirror)

| Ch. | Principle | Alias | Direction | Mechanism |
|:-:|:----|:----|:---:|:-----|
| 1 | Gong-qi 攻七 | Xing-zhi Law | Attack | Try by action → refine on success → solidify what works → verify generalization → discard what fails |
| 2 | Shou-san 守三 | Sheng-zhi Law | Defense | On failure break it down → trace the cause → refine → inscribe → fight again |
| 3 | One-Two-No-Three 一二不过三 | Three-Strike Lock | Safety valve | Fix & verify on first → lock the path on second → sword falls on third |
| 4 | Generalization 举一反三 | Tong-bian Gate | Expansion | One method → three derivations → hundred applications → return to verification |
| 5 | Truth Gate 去伪存真 | Zhen-wei Gate | Hard floor | Claims need evidence → evidence must be verifiable → verify as true |
| 6 | Pre-strategy 预策 | Verdict Law | Constitution | Gather → weigh → plan → decide → act → rebalance |
| 7 | Persistence 持存 | Constancy Gate | Continuity | Explore on start → record while doing → store on pause → resume on return |
| 8 | Closure 止观 | Wan-xing Law | Sealing | Seal when done → let go of merits and faults → mind like a mirror |
| 9 | Self-Mirror 自照镜 | Direction Mirror | Reflection | Look back → still the mind → see the path → advance with certainty |

> **Numbering is the cognitive order; runtime priority follows the Pre-strategy Law P0–P6, independent of numbering.**

**Runtime dominance mapping:**

| Verdict tier | Dominant principle at runtime |
|:---|:---|
| P0 truth | Truth Gate (false info never enters any pipeline) |
| P1 safety | One-Two-No-Three (blocking beats reinforcement/generalization; alerting → vigilance, no block) |
| P2 completion | Closure · Wan-xing (reset after sealing, no extra corrections) |
| P3 resume | Constancy Gate (resume signals unified in the weigh phase; user confirmation before resume) |
| P4 confidence | Gong-qi / Shou-san (higher confidence wins; vigilance −0.2 on related patterns) |
| P5 staging | Generalization (activate only after Truth Gate verification) |
| P6 memory | Mindol (weight ±0.3 / ±0.1 per round; includes Self-Mirror courage signal) |

> **Cognitive order is for learning and narrative; runtime control is decided by the Pre-strategy Law P0–P6. The two dimensions do not conflict.**
> **Pacemaker was removed from the Nine Chapters; it remains as a downtime/cron rhythm tool (no longer at P3).**

## Gong-qi Reinforcement (v3.8)

Verified good practices → **recommended in time → preferred → generalized fast → adoption feedback**:

- **Timely**: `pre_check` marks high-confidence patterns as priority and recommends them before tool calls
- **Preferred**: Arbiter P4 weights same-scenario reuse +0.5 (reusing a verified method beats negative correction)
- **Faster generalization**: reuse ≥2 times or conf ≥4.5 triggers cross-domain generalization
- **Feedback loop**: successful tool use auto-adopts (confidence +0.5); veto ×0.7
- **Quality guardrails**: `audit_patterns` / `audit_staging` / `audit_evidence` prevent hollow patterns and fake data

## Real-World Cases (verified 2026-08-10)

- **Generalization ×2 with 71/74 hits and zero false positives on day one**: two cross-domain rules shipped on 08-09 (`pat_rule_pat_manual_ps1_chinese_bom` / `pat_rule_pat_manual_backup_before_remove`) fired 71/74 times in production on 08-10; manual review confirmed clear boundaries and no false positives, so they were kept and officially released.
- **image_url Shou-san with 11 audit hits**: repeated `view_image` calls in one session triggered One-Two-No-Three; `self_error_image_url` was revived from archived to critical. All 11 hits that day went through audit (circuit-breaker behavior). Review scheduled ≈08-17; if no recurrence, strikes can be reset manually.
- **Mojibake root-cause fix**: Chinese garbled through the PS5.1 ↔ Python pipeline (`$OutputEncoding` defaults to US-ASCII, `[Console]::OutputEncoding` to GBK), corrupting stored prompts and breaking pre_reply JSON parsing → forced UTF-8 + lazy-quantifier fix in the quality gate; 7 rejected Gong-qi patterns were restored and the stuck experience-distillation pipeline was unblocked.
- **Same-day auto_adopt of Gong-qi rules**: Gong-qi rules shipped on 08-09 (`pat_manual_doc_writeback_verify` ×4, `pat_manual_new_tool_smoke` ×1) were auto-adopted in production on 08-10 (confidence +0.5) — the "ship → production → adopt" loop completed within 24 hours.

## Quick Start

### Requirements
- Python 3.12+
- Codex desktop (v3.0+; 26.x already ships Diegin hook support)
- PowerShell 5.1+ (Windows)

### Install
**Option 1: One-click deploy (recommended)**
```powershell
git clone https://github.com/linsong-dev/diegin-skill.git
cd Diegin
powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1
```
Deploys engine + hooks to `%USERPROFILE%/.codex/diegin/`, merges hook config into `%USERPROFILE%/.codex/hooks.json`, and registers the plugin.
Dependency (numpy) still needs a manual `pip install numpy`.

**Option 2: Manual install**
```powershell
git clone https://github.com/linsong-dev/diegin-skill.git
cd Diegin
pip install numpy
```

### Register hooks (manual)
Merge `deploy/hooks-template.json` into `%USERPROFILE%/.codex/hooks.json` (hook scripts auto-load from `%USERPROFILE%/.codex/diegin/hooks/`), then restart Codex.

### Activate
In a Codex conversation, enter `接入迭进` or `dgen on`.

### Verify
```powershell
cd engine
python test_all.py --verbose
```
Expected output: `结果: 32/32 通过 (0 失败)`

## Quick Usage

| Command | Effect |
|:-----|:------|
| `接入迭进` or `dgen on` | Activate the Diegin engine |
| `迭进状态` | View rule library / confidence / health |
| `守三攻七复盘` | Negative correction + positive reinforcement review |
| `@迭进` | Trigger pre-check, output raw JSON |
| `dgen feedback <ID> <agree/veto/silent>` | Give feedback on a rule to adjust confidence |

## Configuration

```toml
[pacemaker]
downtime_start = "23:00"
downtime_end   = "06:00"

[evidence_vault]
quarterly_falsification_enabled = true
```

## Project Structure

```
diegin/
├── engine/           Python engine
│   ├── call_diegin.py    CLI entry
│   ├── test_all.py       32 end-to-end tests
│   ├── evo/              nine-chapter engine (incl. constancy / self-mirror)-principle engine
│   └── mindol/           Mindol semantic memory engine
├── hooks/             PowerShell hooks (always-on)
├── config/            Routing config
├── assets/            Logo and assets
├── tests/             Test suite
├── sync.ps1           Sync script
├── deploy/            Deploy scripts + platform adapters
└── LICENSE            Apache 2.0
```

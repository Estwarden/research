---
status: evergreen
tags: [index, overview]
---

# EstWarden Research Vault

Research notebooks and findings for the [EstWarden](https://estwarden.eu) Baltic Security Monitor.

> **This is an [Obsidian](https://obsidian.md) vault.** Open the `vault/` directory in Obsidian for the best experience. See [[Using This Vault]] for setup.

> **Before deploying anything**, read [[Status Dashboard]] — several findings are marked DO NOT DEPLOY.

## Start Here

1. [[Research Mind Map]] — six core patterns that repeat across every track
2. [[Status Dashboard]] — what's deployed, blocked, and planned
3. [[Improvement Plan]] — what to do next, phased by urgency
4. [[Gaps Analysis]] — what's missing (cross-referenced with Education courses)

## Research Tracks

| Track | Status | Core Question |
|-------|--------|---------------|
| [[CTI Formula]] | Diagnostics complete, fixes partial | Why is the threat index stuck at YELLOW? |
| [[Campaign Detection]] | Architecture deployed, validation insufficient | How to detect hostile campaigns automatically? |
| [[Satellite Monitoring]] | Methods validated, pipeline broken | Can free satellite imagery detect military activity? |
| [[Data Quality]] | Primary blocker | Why is 76% of data degraded? |

## Navigation

| What | Where |
|------|-------|
| All 43 notebooks mapped by domain | [[Experiment Index]] |
| Datasets, freshness, regeneration | [[Data Catalog]] |
| Key terms (CTI, FIMI, Hawkes, etc.) | [[Glossary]] |

## Source Files

These files live outside the vault in the main repo:

| Document | Path | Purpose |
|----------|------|---------|
| Comprehensive findings | `../methodology/FINDINGS.md` | 742-line research summary |
| Validity audit | `../methodology/VALIDITY.md` | What's broken, what's safe |
| Topic findings | `../methodology/FINDINGS.*.md` | 11 deep-dive documents |
| Research specs | `../RESEARCH-SPECS.md` | Machine-readable status tracking |
| Roadmap | `../ROADMAP.md` | Phased plan for nb35+ |
| Algorithm spec | `../methodology/composite-threat-index.md` | CTI formula specification |

## Reading Paths

**"I want to understand the research"**
[[Research Mind Map]] → [[CTI Formula]] → [[Campaign Detection]] → [[Satellite Monitoring]]

**"I want to know what's real vs aspirational"**
[[Status Dashboard]] → `../methodology/VALIDITY.md`

**"I want to run experiments"**
[[Experiment Index]] → [[Data Catalog]] → pick a notebook

**"I want to improve the system"**
[[Improvement Plan]] → Phase 0 (deploy now) → Phase 1 (fix infra) → Phase 2+ (validate)

**"I want to do new research"**
[[Research Directions]] → pick an R-50+ experiment → [[Data Catalog]] for available data

**"I want to contribute"**
[[Gaps Analysis]] → [[Improvement Plan]] → `../ROADMAP.md`

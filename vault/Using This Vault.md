---
status: evergreen
tags: [guide, meta]
---

# Using This Vault

This research vault is built for **[Obsidian](https://obsidian.md)**, a free local-first knowledge base.

## Setup

1. [Download Obsidian](https://obsidian.md/download) (free — Linux, Mac, Windows)
2. Open Obsidian → **Open folder as vault**
3. Select the `vault/` directory inside this repository
4. Trust the vault when prompted

Obsidian will create a `.obsidian/` config directory on first open — this is gitignored.

## Navigation

| Action | Shortcut |
|--------|----------|
| Follow a wikilink | Click `[[Link Name]]` |
| Graph view (see connections) | `Ctrl+G` |
| Search all notes | `Ctrl+Shift+F` |
| Quick switcher | `Ctrl+O` |
| Backlinks (what links here) | Right sidebar |

Start at [[Home]] — it links to everything.

## Conventions

### Links

- `[[Page Name]]` — links between vault notes (clickable in Obsidian)
- `../methodology/FILE.md` — relative paths to methodology docs outside the vault
- `../notebooks/XX_name.py` — relative paths to experiment scripts

### Frontmatter

Every note has YAML frontmatter:

```yaml
---
status: seed | growing | evergreen
tags: [domain, topic]
---
```

| Status | Meaning |
|--------|---------|
| seed | Initial draft, needs work |
| growing | Substantial content, may have gaps |
| evergreen | Complete and current |

### Relationship to Existing Docs

The vault is a **readable navigation layer** on top of existing research files. It does not replace them:

- `methodology/` — deep findings, validity assessment, algorithm specs (the primary source of truth)
- `notebooks/` — all 43 experiment scripts (the actual research code)
- `data/` — CSV exports from production
- `output/` — computed results and visualizations
- `RESEARCH-SPECS.md` — machine-readable status tracking
- `ROADMAP.md` — phased research plan

The vault summarizes, organizes, and cross-links these files so you can navigate the research without reading 3,500 lines of methodology docs first.

## Structure

```
vault/
├── Home.md                  ← start here
├── Research Mind Map.md     ← core patterns
├── Status Dashboard.md      ← what works, what doesn't
├── CTI Formula.md           ← track 1
├── Campaign Detection.md    ← track 2
├── Satellite Monitoring.md  ← track 3
├── Data Quality.md          ← track 4 (blocker)
├── Experiment Index.md      ← all 43 notebooks
├── Data Catalog.md          ← all datasets
├── Gaps Analysis.md         ← missing methods
├── Glossary.md              ← terminology
└── Using This Vault.md      ← this file
```

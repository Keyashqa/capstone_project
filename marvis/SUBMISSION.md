# Marvis — Capstone Submission Checklist

Track what's done vs. left. This file is **not** the writeup or the video script —
it only lists the required deliverables and their status.

## Required deliverables

- [ ] **Kaggle writeup** (≤ 2500 words). Draw from `README.md` + `ARCHITECTURE.md`;
      lead with the three-sided marketplace and the self-growing loop. *(Not written here.)*
- [ ] **Cover image.** A hero image for the submission. *(A dedicated architecture
      diagram also goes at `docs/architecture.png`, referenced by the README.)*
- [ ] **YouTube video** (≤ 5 min, public/unlisted). Suggested arc: rent a hire →
      niche gap → build → the new skill appears → list-and-earn (owner + broker
      balances move). *(Script not written here.)*
- [ ] **Public project / repo link.** Push the cleaned `marvis/` folder (with
      `mcp-test/google_workspace_mcp` alongside) to a public repo.

## Rubric coverage (evidence lives in the repo)

- [x] **Documentation (README).** `README.md` — hook, problem, three sides,
      architecture, protocols, setup, demo, security, limitations.
- [x] **Course-concepts mapping.** Table in `README.md` → multi-agent/ADK, MCP,
      security, agent skills, deployability, each pointing at real files.
- [x] **Technical depth.** `ARCHITECTURE.md` — workflow state machine, money
      invariants, split math, two-store model, gap detection.
- [x] **Reproducible setup.** Exact prereqs, `.env.example`, run scripts, ports.
- [x] **Tests.** `tests/test_split.py` proves penny-exact zero-sum payouts.

## Pre-submission gate — secrets & cleanliness

- [x] `marvis/` tracks no secrets (only `.env.example`; no `.env`, `_keys/`, `*.db`).
- [x] `.gitignore` covers `.env`, `_keys/*.json` (anchored + nested), `*.db`,
      `__pycache__`, `node_modules`, OAuth token cache, `.adk/`.
- [x] Unused artifacts moved to `marvis/references/` (stub proxy, scratch files).
- [x] Untracked committed private keys + DBs in `adk_ucp_ap2_working_prototype/`
      (via `git rm --cached`).
- [ ] ⚠️ **Rewrite git history if the monorepo is ever published** — the removed
      private keys still exist in past commits. For a `marvis/`-only public repo
      (the chosen scope), publish `marvis/` as a fresh repo so that history never
      ships. Confirm before pushing.
- [ ] **Final secret sweep** before pushing:
      `git ls-files | grep -iE '\.env$|_keys/|\.db$|credential|token'` → should be empty.
- [ ] Add the real `docs/architecture.png` referenced by `README.md`.

## Notes / honest caveats to keep in the writeup

- Local `gemma2:2b` on CPU → tens-of-seconds latency per hire.
- "A2A" is a discovery/identity convention here; dispatch is in-process.
- The scoped MCP proxy is a stub; grant enforcement is in-process.
- Seller/buyer are demo-seeded; no live multi-user marketplace UX or cash-out rail.

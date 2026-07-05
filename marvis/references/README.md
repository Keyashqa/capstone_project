# references/ — parked, non-running artifacts

Nothing in this folder is imported or executed by the running Marvis app. It is
kept for provenance and to keep the top-level project directory clean.

| Item | What it is | Why it's here (not in the app) |
|---|---|---|
| `proxy_server/` | A FastAPI **stub** for the originally-planned out-of-process Scoped MCP Proxy (`:8003`). | Never implemented. Grant enforcement runs **in-process** (`app/capability/gdocs_session.py` + `InMemoryGrantRegistry`). The running system is 3 processes, not 4. |
| `run_proxy.sh` | Launcher for the stub above. | Not part of the real run instructions. |
| `dump.txt` | A scratch context dump from development. | Not used at runtime. |
| `stray-root-package-lock.json` | An empty `npm` lockfile that was accidentally created at the backend root. | The backend is Python/`uv`; only `frontend/` uses npm. |

**Planning docs** (`plan.md`, `plan2.md`, `plan3.md`, `audit.md`) live at the
outer repository root, one level above `marvis/`. They describe intended design;
where the shipped code diverges, **the code is authoritative** — see `README.md`
and `ARCHITECTURE.md` for what was actually built.

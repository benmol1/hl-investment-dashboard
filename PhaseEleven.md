# Phase 11 — User Accounts & Authentication: Design Notes

This document records the architectural decisions, trade-offs, and implementation
rationale for the remaining blocks of Phase 11. Blocks 1 and 2 (data model and demo
dataset) are already complete.

---

## Block 3 — Authentication

### Decision: FastAPI JWT vs. Authelia

| | **FastAPI JWT** ✓ | **Authelia** |
|---|---|---|
| Extra infrastructure | None — runs inside the existing FastAPI process | Requires a separate Docker container, a config file, a session store (Redis), and a database |
| Setup complexity | ~100 lines of Python | Significant — YAML config, proxy rules, Docker Compose wiring |
| Operational burden | Zero — no extra service to keep healthy | Must be kept updated; misconfiguration can lock you out |
| Features | Exactly what's needed: login, token, user isolation | Full SSO portal, TOTP, LDAP, forward-auth headers — vast overkill for 2–3 known users |
| Auditability | All auth logic lives in the same codebase | Behaviour is a black box from the app's perspective |
| User list management | `set_password.py` CLI script | Authelia's own user database or LDAP |

**Chosen: FastAPI JWT.** Authelia is the right tool when you need an SSO layer across multiple services or you want TOTP without building it yourself. For a personal dashboard with a handful of known users it adds weeks of operational complexity for no functional benefit.

**Library choice: PyJWT + passlib[bcrypt]**

`python-jose` (the other common option) has had long periods of inactivity and lags behind the JWT spec in places. PyJWT is actively maintained, has a clean API, and is the de facto standard in the Python ecosystem.

---

### Token design

| Property | Choice | Rationale |
|---|---|---|
| Algorithm | HS256 | Symmetric — suitable for a single-service app; no need for RS256 key pairs |
| Expiry | 24 hours | Long enough to not be annoying for a personal dashboard; short enough to limit exposure if a token is leaked |
| Payload | `sub` (user_id), `role`, `exp` | Minimal; role is embedded so the API can make access decisions without a DB round-trip |
| Refresh tokens | Not implemented | Adds significant complexity (storage, rotation, revocation). Re-logging in once a day is acceptable. Revisit if it becomes a pain point |
| Secret storage | `JWT_SECRET` env var | Never hard-coded; generate with `python -c "import secrets; print(secrets.token_hex(32))"` |

---

### User account filtering

The dbt mart layer is **user-agnostic** — all users' accounts are present in the same
materialized tables. Filtering happens at the API layer only:

1. Every protected endpoint depends on `get_user_accounts`, which queries
   `accounts WHERE user_id = <authenticated user>` and returns the permitted
   `account_name` set.
2. A `build_account_filter(user_accounts, account, column)` helper produces an
   `IN (?, ?, …)` SQL fragment that is injected into every mart query.
3. The existing `?account=ISA` query parameter continues to work — it is
   intersected with the user's permitted set.

This keeps the dbt models completely unchanged and concentrates all data-isolation
logic in one small helper function.

**Pros:**
- dbt models stay simple and user-agnostic
- Easy to reason about: auth logic lives in one file (`app/auth.py`)
- No dbt re-runs needed when users or accounts change

**Cons:**
- Every mart query gains an extra `IN (…)` clause (negligible performance impact
  for DuckDB on these data volumes)
- If the account list grows very large, the `IN` clause could become unwieldy
  (not a realistic concern for a personal portfolio tracker)

---

### Password bootstrap

Because `hashed_password` starts as `NULL` for all users (populated by `setup_db.py`),
a one-time CLI script is needed before first login:

```bash
uv run python backend/scripts/set_password.py owner
uv run python backend/scripts/set_password.py demo
```

This is preferable to a first-run web endpoint because it requires local filesystem
access, which means only someone who can access the server can set the initial password.

---

## Block 4 — Frontend Login

### Token storage: in-memory vs. localStorage vs. sessionStorage

| | **In-memory (React state)** ✓ | **sessionStorage** | **localStorage** |
|---|---|---|---|
| XSS risk | None — JS on other origins can't access React state | Low — accessible to JS in the same origin, cleared on tab close | Higher — persists across sessions, accessible to any JS on the same origin |
| Survives page refresh | No | Yes | Yes |
| Survives new tab | No | No | Yes |
| Implementation complexity | Trivial | Trivial | Trivial |

**Chosen: in-memory.** For a personal dashboard on a trusted device, the UX cost of
re-logging in after a page refresh is minimal. In-memory storage is unambiguously
the most secure option and requires no special handling.

If the forced re-login becomes annoying in practice, `sessionStorage` is a reasonable
upgrade — it survives refreshes without surviving across browser sessions, and the XSS
exposure is limited to the same origin (which you control entirely).

### 401 handling

When the API returns a 401 (token expired mid-session), the `client.ts` module:
1. Sets a `hl_session_expired=1` flag in `sessionStorage`
2. Calls a registered `onUnauthorized` callback (set by `AuthContext`)
3. The callback clears the token from React state
4. `ProtectedRoute` detects the cleared token and redirects to `/login`
5. `LoginPage` reads the `sessionStorage` flag and shows a "session expired" banner,
   then clears the flag

This avoids the need to pass `useNavigate()` into non-React modules and keeps the
navigation logic entirely within React Router.

### API client design

The existing `client.ts` is a thin `get()` wrapper. It is extended (not replaced) with:
- A module-level `_token` variable and a `setToken()` setter
- A module-level `_onUnauthorized` callback and a `setUnauthorizedHandler()` setter
- The `Authorization: Bearer {token}` header added to every request when a token is set
- A 401 check before the generic error handler

`AuthContext` synchronises React state to the module-level token via a `useEffect`,
so the two stay in lock-step without making the API module a React module.

---

## Block 5 — Deployment

### Decision: Tailscale vs. Public HTTPS (Caddy + Let's Encrypt)

| | **Tailscale** ✓ (for personal use) | **Caddy + Let's Encrypt** (for demo sharing) |
|---|---|---|
| Complexity | Zero extra infrastructure — Tailscale is already running | Requires a public domain, open ports 80/443, a Caddy service in Docker Compose |
| Security | Device-level auth on top of app-level JWT — two independent layers | App-level JWT only — requires the JWT layer to be correctly configured |
| Public exposure | None | Anyone on the internet can reach the login page |
| Sharing with family | Add them to the tailnet | They need a browser — no Tailscale required |
| Sharing for demo | Not suitable for people without Tailscale | Suitable — point at `hl_demo.duckdb` |
| HTTPS | Available via Tailscale's built-in cert authority (`tailscale cert`) | Automatic via Let's Encrypt |
| Maintenance | None | Cert renewal is automatic, but Caddy must be kept running |

**Recommended approach: both, serving different purposes.**

- **Tailscale** for day-to-day personal access and sharing with family. Use
  `tailscale cert` to get a valid HTTPS certificate for the tailnet hostname — zero
  Let's Encrypt config, not publicly routable.

- **Caddy profile** (opt-in Docker Compose profile) for demo sharing. When you want
  to show the dashboard to someone without Tailscale, bring up the Caddy profile
  pointing the backend at `hl_demo.duckdb`. The demo user can log in; your real data
  is never served.

This way neither use case forces a compromise on the other. The Caddy service is a
four-line `docker-compose.override.yml` and a one-page `Caddyfile` — low effort to
add when you actually need it.

**Implementation note:** Block 5 does not block Blocks 3 or 4. The JWT layer makes
the app safe to expose via either transport once it's implemented.

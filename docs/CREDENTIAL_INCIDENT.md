# Credential Incident — Robinhood session token in public Actions cache

Opened: 2026-09-13 · Status: **contained; revocation pending owner action** · No credential values appear in this document.

## 1. What was exposed

| Item | Exposed? | Detail |
|---|---|---|
| Robinhood OAuth **access token** | Yes (treat as compromised) | Inside a Python pickle at `~/.tokens/robinhood.pickle` on the runner, saved with `actions/cache` |
| Robinhood OAuth **refresh token** | Yes (treat as compromised) | Same pickle. Can mint new access tokens without a device approval — the most sensitive item |
| Robinhood **device token** | Yes | Same pickle. Identifies the "trusted device" used for refresh |
| Robinhood username / password | **No** | Stored only as GitHub Actions secrets (`RH_USERNAME`, `RH_PASSWORD`), masked in logs, never cached |
| GitHub token | No | Not present in cache, logs or history |

Capability of the exposed tokens: full API session on the Robinhood login (quotes, account data, order placement on accounts the login can access). Withdrawals typically require additional verification, but that must not be relied on.

## 2. Where it existed

| Location | Finding (verified 2026-09-13) | Now |
|---|---|---|
| GitHub Actions cache, repo `waziak/robinhood-bot` (**public**) | 29 entries `rh-session-<run_id>` (1.15 KiB each), created 2026-09-06 → 2026-09-13; caching began 2026-08-09 (older entries evicted by GitHub's 7-day policy) | **Deleted — 0 remain** |
| GitHub secret `RH_SESSION_SEED_B64` | Base64 of the 2026-08-09 bootstrap session (same token chain). Secrets are not publicly readable | **Deleted** |
| Local disk `~/.tokens/robinhood.pickle` | Plaintext, mode `-rw-r--r--` (readable by every local user), from 2026-08-09 | **Deleted** (not opened) |
| Git history (all refs, all blobs) | No token values. Pattern scan for JWTs, `Bearer …`, base64 pickles, `*_token=<value>`: 0 hits. `access_token`/`refresh_token` occur only as identifiers in `session_auth.py`, `scripts/bootstrap_session.py`, docs | Clean — **no history rewrite required** |
| GitHub Actions artifacts | `total_count = 0` | Clean |
| GitHub Actions logs | 297 of 299 runs scanned (2 expired). 4 matches, all the literal line `✓ Session refreshed via refresh_token — no approval needed`; no token values, no email, no account URLs | Clean |
| Other repo files / untracked files | Only `.env` (gitignored, never committed; not opened during this investigation) | Holds plaintext username/password — owner action below |

## 3. Likely exposure scope

- Cache **contents** are not downloadable through GitHub's public REST API; retrieval requires code running inside a workflow in this repository's context. On a public repo the realistic path is a pull-request workflow from a fork.
- Repository evidence: **0 forks, 0 pull requests ever, 0 stars/watchers**; all 299 workflow runs were `schedule` (296) or `workflow_dispatch` (3) by the owner on `waziak/robinhood-bot`.
- Conclusion: **no evidence of access by anyone else**. Because the window was ~5 weeks on a public repo and the refresh token is long-lived, the tokens are still treated as compromised and must be revoked — deletion alone does not invalidate them.

## 4. Remediation performed

1. Disabled the `Robinhood Trading Bot` workflow (`disabled_manually`) so no run can write a new plaintext session. Re-enable only after CI stops caching sessions in plaintext.
2. Force-cancelled in-progress run `34768963306` before its `if: always()` step could save a fresh session to cache (a normal cancel still runs `always()` steps).
3. Deleted all 29 `rh-session-*` caches; verified none remain.
4. Deleted secret `RH_SESSION_SEED_B64`.
5. Deleted the local plaintext session file and `~/.tokens/`.
6. Scanned git history, artifacts and all available logs (results above).
7. Added `trader/credentials.py`: credentials and session live only in the **macOS Keychain** (service `robinhood-bot`); password entry via `getpass`; login runs `robin_stocks` with `store_session=False`, captures the device token in memory, and passes library stdout through a redacting stream; refresh never logs response bodies; any plaintext `~/.tokens/*.pickle` makes resume/login refuse to run; there is **no automatic password-login fallback**.
8. Added `tests/test_credentials.py`, including a scan of every tracked/untracked repo file for token values that runs with the test suite.

Side effect: the legacy paper bot is stopped (it could not authenticate after revocation anyway).

## 5. Required owner actions (in order)

1. **Revoke the old session — change your Robinhood password now** (Robinhood app → Account → Settings → Security & privacy → Change password). While there, open **Devices** and remove any devices you don't recognise (the GitHub runners appear as unfamiliar Linux/Python devices). Changing the password is what actually invalidates the exposed refresh token.
2. **Store the new credentials in Keychain** (no echo, nothing written to disk):
   `cd ~/robinhood-bot && venv/bin/python -m trader.credentials setup`
3. **Fresh authentication**: `venv/bin/python -m trader.credentials login`
   → **Robinhood will send a device-approval request to your phone. Open the Robinhood app and approve the new login** (or type the SMS code if asked). This is the step automation must stop at.
4. Remove the plaintext `RH_USERNAME`/`RH_PASSWORD` lines from `~/robinhood-bot/.env` (they will also be stale after step 1).
5. GitHub secrets `RH_USERNAME`/`RH_PASSWORD`: delete them, or update them only if CI trading is ever re-enabled with encrypted session storage.
6. Keep the workflow disabled. Recommendation: do not run broker-connected automation from a public repository at all.

## 6. History cleanup procedure (not needed)

No credential exists in git history, so no rewrite is planned. If one were ever found: rotate the credential first; then `git filter-repo --replace-text` on a fresh mirror clone; force-push all refs; ask GitHub Support to purge cached views of the old commits; and treat any existing clones or forks as permanently exposed. Rewriting public history does not un-expose a secret — rotation does.

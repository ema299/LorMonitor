#!/usr/bin/env python3
"""Replay ownership round-trip — smoke test suite.

Companion to privacy_smoke_test.py. Covers the upload/list/delete owner-only
flow shipped 25/04 (B.2 Coach tier hardening + B.3 GDPR right-to-delete):

    T1  Endpoint registration — DELETE /api/v1/team/replay/:id wired
    T2  List shape — every row exposes is_owner boolean
    T3  DELETE auth — anonymous request rejected (401) when JWT mandatory
    T4  DELETE cross-user — user B gets 403 deleting user A's replay
    T5  DELETE owner success — owner gets 204; replay disappears from list
    T6  Upload rate limit — bucket fires after free-tier threshold

T4-T6 require real JWT tokens + a game_id; missing env vars => SKIP, not FAIL.
T3 only fails when TEAM_API_REQUIRE_JWT=true (otherwise transitional mode
returns 200 with no auth — that's expected today, hence skip-able).

Usage:
    venv/bin/python3 scripts/replay_ownership_smoke.py --base http://localhost:8100

Required env vars (optional):
    USER_A_TOKEN      JWT of non-admin user A (owns at least one replay)
    USER_B_TOKEN      JWT of non-admin user B
    USER_A_GAME_ID    a disposable game_id owned by A (T5 will DELETE it)
    UPLOAD_BURST_TOKEN JWT of a free-tier user, used for T6 burst test
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("FAIL: install 'requests' in the venv first — pip install requests")
    sys.exit(1)


RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"


class Result:
    def __init__(self, name: str):
        self.name = name
        self.status = "?"
        self.detail = ""

    def pass_(self, detail: str = "") -> None:
        self.status = "PASS"
        self.detail = detail

    def fail(self, detail: str) -> None:
        self.status = "FAIL"
        self.detail = detail

    def skip(self, detail: str) -> None:
        self.status = "SKIP"
        self.detail = detail

    def __str__(self) -> str:
        if self.status == "PASS":
            color = GREEN
        elif self.status == "FAIL":
            color = RED
        else:
            color = YELLOW
        return f"  {color}[{self.status:4}]{RESET} {self.name}" + (f" — {self.detail}" if self.detail else "")


class _NetErrResponse:
    def __init__(self, err: str):
        self.status_code = 0
        self.text = f"network error: {err}"
        self._err = err

    def json(self) -> Any:
        return {"error": self._err}


def _req(method: str, url: str, token: str | None = None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return requests.request(method, url, headers=headers, timeout=10, **kw)
    except requests.exceptions.RequestException as e:
        return _NetErrResponse(str(e))


# ═══ CHECKS ═════════════════════════════════════════════════════════════════


def t1_endpoint_registered() -> Result:
    r = Result("T1 endpoint — DELETE /api/v1/team/replay/{game_id} wired")
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from backend.api.team import router
        for route in router.routes:
            methods = getattr(route, "methods", set()) or set()
            if route.path == "/replay/{game_id}" and "DELETE" in methods:
                r.pass_("router carries DELETE /replay/{game_id}")
                return r
        r.fail("DELETE /replay/{game_id} not found in router")
    except Exception as e:
        r.fail(f"router import error: {e}")
    return r


def t2_list_is_owner_field(base: str, token: str | None) -> Result:
    r = Result("T2 list shape — rows expose is_owner boolean")
    if not token:
        r.skip("USER_A_TOKEN required (transitional mode would always send is_owner=false)")
        return r
    resp = _req("GET", f"{base}/api/v1/team/replay/list", token=token)
    if resp.status_code != 200:
        r.fail(f"status {resp.status_code}: {resp.text[:120]}")
        return r
    items = resp.json() if isinstance(resp.json(), list) else []
    if not items:
        r.skip("user has no replays — nothing to validate (upload one then re-run)")
        return r
    missing = [i for i in items if "is_owner" not in i]
    if missing:
        r.fail(f"{len(missing)}/{len(items)} rows missing is_owner")
        return r
    owned = sum(1 for i in items if i["is_owner"])
    r.pass_(f"is_owner present on all {len(items)} rows ({owned} owned)")
    return r


def t3_delete_anonymous_rejected(base: str) -> Result:
    r = Result("T3 DELETE auth — anonymous request rejected")
    # Use a sentinel game_id that almost certainly does not exist; we only
    # care about the auth gate firing before any DB lookup.
    resp = _req("DELETE", f"{base}/api/v1/team/replay/__smoke_nonexistent__")
    if resp.status_code == 0:
        r.skip(f"network error reaching API: {resp.text}")
        return r
    if resp.status_code == 401:
        r.pass_("401 Missing authorization (correct)")
    elif resp.status_code == 403:
        r.pass_("403 — auth-required short-circuit before lookup (correct)")
    elif resp.status_code == 404:
        r.fail("404 — auth not enforced; lookup ran for anonymous caller")
    elif resp.status_code == 405:
        r.fail("405 — DELETE route not served (live backend may need restart after deploy)")
    else:
        r.fail(f"unexpected status {resp.status_code}: {resp.text[:120]}")
    return r


def t4_delete_cross_user(base: str, token_a: str | None, token_b: str | None, game_id: str | None) -> Result:
    r = Result("T4 DELETE cross-user — user B forbidden on user A's replay")
    if not token_a or not token_b:
        r.skip("USER_A_TOKEN and USER_B_TOKEN required")
        return r
    if not game_id:
        # Pick the first replay owned by A
        lst = _req("GET", f"{base}/api/v1/team/replay/list", token=token_a)
        if lst.status_code != 200:
            r.skip(f"cannot fetch user A list (status {lst.status_code})")
            return r
        items = lst.json() if isinstance(lst.json(), list) else []
        owned = [i for i in items if i.get("is_owner")]
        if not owned:
            r.skip("user A owns no replays — nothing to cross-test")
            return r
        game_id = owned[0]["game_id"]

    resp = _req("DELETE", f"{base}/api/v1/team/replay/{game_id}", token=token_b)
    if resp.status_code == 403:
        r.pass_(f"403 returned to user B for replay {game_id} (correct)")
    elif resp.status_code == 204:
        r.fail(f"user B got 204 deleting user A's replay {game_id} — OWNERSHIP LEAK")
    elif resp.status_code == 404:
        r.fail(f"404 — endpoint resolved replay before owner check, or replay vanished")
    else:
        r.fail(f"unexpected status {resp.status_code}: {resp.text[:120]}")
    return r


def t5_delete_owner_success(base: str, token: str | None, game_id: str | None) -> Result:
    r = Result("T5 DELETE owner — 204 then replay gone from list")
    if not token or not game_id:
        r.skip("USER_A_TOKEN and USER_A_GAME_ID required (DESTRUCTIVE — replay is deleted)")
        return r
    # Confirm replay exists in user's list before delete
    pre = _req("GET", f"{base}/api/v1/team/replay/list", token=token)
    if pre.status_code != 200:
        r.fail(f"pre-list failed: {pre.status_code}")
        return r
    pre_items = pre.json() if isinstance(pre.json(), list) else []
    pre_match = next((i for i in pre_items if i.get("game_id") == game_id), None)
    if not pre_match:
        r.skip(f"game_id {game_id} not in user's list — nothing to delete")
        return r
    if not pre_match.get("is_owner"):
        r.skip(f"user is not owner of {game_id} (is_owner=false) — would 403 by design")
        return r

    resp = _req("DELETE", f"{base}/api/v1/team/replay/{game_id}", token=token)
    if resp.status_code != 204:
        r.fail(f"DELETE returned {resp.status_code}: {resp.text[:120]}")
        return r
    # Verify it disappeared
    post = _req("GET", f"{base}/api/v1/team/replay/list", token=token)
    if post.status_code != 200:
        r.fail(f"post-list failed: {post.status_code}")
        return r
    post_items = post.json() if isinstance(post.json(), list) else []
    if any(i.get("game_id") == game_id for i in post_items):
        r.fail(f"DELETE returned 204 but {game_id} still appears in list")
    else:
        r.pass_(f"204 + replay {game_id} no longer listed (was {len(pre_items)}, now {len(post_items)})")
    return r


def t6_upload_rate_limit(base: str, token: str | None) -> Result:
    r = Result("T6 rate limit — upload bucket fires after free-tier threshold")
    if not token:
        r.skip("UPLOAD_BURST_TOKEN required (free-tier JWT)")
        return r
    # Free tier limit = 5/min. Send 7 requests with a tiny invalid payload —
    # the rate-limit middleware rejects BEFORE the upload handler runs, so
    # invalid file content is fine here.
    statuses: list[int] = []
    for i in range(7):
        resp = _req(
            "POST",
            f"{base}/api/v1/team/replay/upload",
            token=token,
            files={"file": ("burst.replay.gz", b"\x00", "application/gzip")},
        )
        statuses.append(resp.status_code)
        time.sleep(0.05)
    rl_count = sum(1 for s in statuses if s == 429)
    if rl_count == 0:
        r.fail(f"no 429 in 7 attempts (statuses={statuses}) — bucket may not be wired")
    else:
        r.pass_(f"{rl_count}/7 attempts rate-limited (statuses={statuses})")
    return r


# ═══ MAIN ═══════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay ownership smoke test")
    parser.add_argument("--base", default="http://localhost:8100", help="API base URL")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    user_a_token = os.environ.get("USER_A_TOKEN")
    user_b_token = os.environ.get("USER_B_TOKEN")
    user_a_game_id = os.environ.get("USER_A_GAME_ID")
    burst_token = os.environ.get("UPLOAD_BURST_TOKEN") or user_a_token

    print(f"{BOLD}Replay ownership — smoke test{RESET}")
    print(f"Base URL: {base}")
    print(f"Tokens:   USER_A={'yes' if user_a_token else 'no'}  "
          f"USER_B={'yes' if user_b_token else 'no'}  "
          f"BURST={'yes' if burst_token else 'no'}  "
          f"GAME_ID={'yes' if user_a_game_id else 'no'}")
    print()

    results = [
        t1_endpoint_registered(),
        t2_list_is_owner_field(base, user_a_token),
        t3_delete_anonymous_rejected(base),
        t4_delete_cross_user(base, user_a_token, user_b_token, user_a_game_id),
        t5_delete_owner_success(base, user_a_token, user_a_game_id),
        t6_upload_rate_limit(base, burst_token),
    ]

    print(f"{BOLD}Results:{RESET}")
    for r in results:
        print(r)

    fails = [r for r in results if r.status == "FAIL"]
    skips = [r for r in results if r.status == "SKIP"]
    passes = [r for r in results if r.status == "PASS"]

    print()
    print(f"{BOLD}Summary: {GREEN}{len(passes)} pass{RESET}, "
          f"{RED}{len(fails)} fail{RESET}, "
          f"{YELLOW}{len(skips)} skip{RESET}")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

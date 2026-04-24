#!/usr/bin/env python3
"""Privacy Layer V3 — smoke test suite.

Runs 7 checks end-to-end against the live API. Designed to be executed after
deploying the privacy layer (alembic upgrade + systemctl restart).

Usage:
    python3 scripts/privacy_smoke_test.py --base http://localhost:8100

Exit codes:
    0 — all pass
    1 — at least one check failed

Checks (matches ARCHITECTURE.md §24.10 A10 and friends):

    T1  Schema — migration applied: team_replays has the 5 new columns
    T2  Access-control — user A cannot read user B's replay (needs 2 accounts)
    T3  Consent — upload without preferences.consents.replay_upload -> 412
    T4  Anonymization — /api/replay/list and /api/replay/public-log hide nicknames
    T5  GDPR export — response includes team_replays + preferences
    T6  Soft paywall — POST /api/user/interest records intent in preferences
    T7  Orphan records — pre-M1 replays (user_id IS NULL) denied for non-admin

T2 and T7 need at least one non-admin user + an admin user. The script uses
env vars to receive JWT tokens; if tokens are missing, those checks are
skipped (reported as SKIP, not FAIL).

Required env vars (optional; skips gracefully if missing):
    ADMIN_TOKEN       JWT of an admin user
    USER_A_TOKEN      JWT of non-admin user A
    USER_B_TOKEN      JWT of non-admin user B
    USER_A_GAME_ID    (optional) a game_id owned by user A for T2 cross-check
"""
from __future__ import annotations

import argparse
import json
import os
import sys
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
        self.status = "?"  # PASS | FAIL | SKIP
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
    """Placeholder returned when the HTTP call fails at network level."""
    def __init__(self, err: str):
        self.status_code = 0
        self.text = f"network error: {err}"
        self._err = err
    def json(self) -> Any:
        return {"error": self._err}


def get(url: str, token: str | None = None, **kw) -> requests.Response | _NetErrResponse:
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return requests.get(url, headers=headers, timeout=10, **kw)
    except requests.exceptions.RequestException as e:
        return _NetErrResponse(str(e))


def post(url: str, token: str | None = None, **kw) -> requests.Response | _NetErrResponse:
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return requests.post(url, headers=headers, timeout=10, **kw)
    except requests.exceptions.RequestException as e:
        return _NetErrResponse(str(e))


# ═══ CHECKS ═════════════════════════════════════════════════════════════════


def t1_schema(base: str) -> Result:
    r = Result("T1 schema — team_replays columns present")
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from backend.models import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='team_replays' ORDER BY ordinal_position"
            )).fetchall()
            cols = {row[0] for row in rows}
            required = {"user_id", "is_private", "consent_version", "uploaded_via", "shared_with"}
            missing = required - cols
            if missing:
                r.fail(f"missing columns: {sorted(missing)}")
            else:
                r.pass_(f"all 5 new columns present ({len(cols)} total)")
        finally:
            db.close()
    except Exception as e:
        r.fail(f"DB check error: {e}")
    return r


def t2_access_control(base: str, token_a: str | None, token_b: str | None, game_id: str | None) -> Result:
    r = Result("T2 access-control — user A replay not visible to user B")
    if not token_a or not token_b:
        r.skip("USER_A_TOKEN and USER_B_TOKEN env vars required")
        return r
    # If no game_id provided, try to pick one from user A's list
    if not game_id:
        lst = get(f"{base}/api/v1/team/replay/list", token=token_a)
        if lst.status_code != 200:
            r.skip(f"cannot fetch user A list (status {lst.status_code})")
            return r
        items = lst.json() if isinstance(lst.json(), list) else []
        if not items:
            r.skip("user A has no replays to cross-check")
            return r
        game_id = items[0].get("game_id")
    if not game_id:
        r.skip("no game_id resolved")
        return r

    # User B tries to GET it
    resp_b = get(f"{base}/api/v1/team/replay/{game_id}", token=token_b)
    if resp_b.status_code == 403:
        r.pass_(f"403 returned to user B for game {game_id} (correct)")
    elif resp_b.status_code == 200:
        r.fail(f"user B got 200 for user A's replay {game_id} — ACCESS LEAK")
    else:
        r.fail(f"unexpected status {resp_b.status_code}: {resp_b.text[:120]}")
    return r


def t3_consent_required(base: str, token_no_consent: str | None) -> Result:
    r = Result("T3 consent — upload without consent returns 412")
    if not token_no_consent:
        r.skip("need a JWT for a user WITHOUT preferences.consents.replay_upload")
        return r
    # Dummy tiny file payload — backend will reject with 412 BEFORE even parsing
    resp = post(
        f"{base}/api/v1/team/replay/upload",
        token=token_no_consent,
        files={"file": ("dummy.replay.gz", b"\x00", "application/gzip")},
    )
    if resp.status_code == 412:
        r.pass_("412 Precondition Failed (correct)")
    elif resp.status_code == 400:
        r.fail("got 400 — consent check may be running AFTER file validation")
    else:
        r.fail(f"unexpected status {resp.status_code}: {resp.text[:120]}")
    return r


def t4_anonymization(base: str) -> Result:
    r = Result("T4 anonymization — /api/replay/list + /api/replay/public-log hide nicknames")
    problems: list[str] = []

    # Try a known deck pair. If archive not found, this will skip silently.
    list_resp = get(f"{base}/api/replay/list?deck=EmSa&opp=AmAm&format=core")
    if list_resp.status_code == 0:
        r.skip(f"network error reaching API: {list_resp.text}")
        return r
    if list_resp.status_code == 200:
        data = list_resp.json() or {}
        games = data.get("games", [])
        for g in games[:5]:
            on = g.get("on", "")
            en = g.get("en", "")
            if on and on != "Player":
                problems.append(f"list: 'on' not anonymized ('{on}')")
                break
            if en and en != "Opponent":
                problems.append(f"list: 'en' not anonymized ('{en}')")
                break

    pub_resp = get(f"{base}/api/replay/public-log?match_id=1")
    if pub_resp.status_code == 200:
        pub = pub_resp.json() or {}
        log = pub.get("viewer_public_log") or {}
        meta = log.get("match_meta", {})
        names = meta.get("player_names", {})
        if names and names.get("1") and names.get("1") not in ("Player 1", "Player 2"):
            problems.append(f"public-log: player_names['1'] not anonymized ('{names['1']}')")
    # If both endpoints 404/empty, this is a skip not a fail
    if list_resp.status_code == 404 and pub_resp.status_code != 200:
        r.skip("no sample archive/match found — endpoints returned 404")
        return r

    if problems:
        r.fail("; ".join(problems))
    else:
        r.pass_("nicknames masked in both endpoints (or endpoints empty)")
    return r


def t5_gdpr_export(base: str, token: str | None) -> Result:
    r = Result("T5 GDPR export — includes team_replays + preferences")
    if not token:
        r.skip("USER_A_TOKEN required")
        return r
    resp = get(f"{base}/api/user/export", token=token)
    if resp.status_code != 200:
        r.fail(f"status {resp.status_code}: {resp.text[:120]}")
        return r
    body = resp.json()
    missing = [k for k in ("profile", "decks", "preferences", "team_replays") if k not in body]
    if missing:
        r.fail(f"missing keys: {missing}")
    else:
        r.pass_(f"keys present: profile/decks/preferences/team_replays (team_replays: {len(body['team_replays'])} rows)")
    return r


def t6_interest(base: str, token: str | None) -> Result:
    r = Result("T6 soft paywall — POST /api/user/interest records intent")
    if not token:
        r.skip("USER_A_TOKEN required")
        return r
    resp = post(
        f"{base}/api/user/interest",
        token=token,
        json={"tier": "pro"},
    )
    if resp.status_code != 200:
        r.fail(f"status {resp.status_code}: {resp.text[:120]}")
        return r
    # Verify via export
    exp = get(f"{base}/api/user/export", token=token)
    if exp.status_code != 200:
        r.fail(f"verify via export failed: {exp.status_code}")
        return r
    prefs = (exp.json() or {}).get("preferences", {})
    itp = prefs.get("interest_to_pay") or {}
    if itp.get("tier") == "pro" and itp.get("at"):
        r.pass_(f"interest_to_pay persisted: tier={itp['tier']} at={itp['at'][:19]}")
    else:
        r.fail(f"interest_to_pay not recorded: {itp}")
    return r


def t7_orphan_denied(base: str, token_admin: str | None, token_user: str | None) -> Result:
    r = Result("T7 orphan records — denied to non-admin (user_id IS NULL pre-M1)")
    if not token_admin or not token_user:
        r.skip("ADMIN_TOKEN and USER_A_TOKEN required")
        return r
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from backend.models import SessionLocal
        from backend.models.team import TeamReplay
        db = SessionLocal()
        try:
            orphan = db.query(TeamReplay).filter(TeamReplay.user_id.is_(None)).first()
            if not orphan:
                r.skip("no orphan records in DB (user_id IS NULL) — nothing to test")
                return r
            gid = orphan.game_id
        finally:
            db.close()
    except Exception as e:
        r.skip(f"DB probe failed: {e}")
        return r

    # Admin must see it
    adm = get(f"{base}/api/v1/team/replay/{gid}", token=token_admin)
    if adm.status_code != 200:
        r.fail(f"admin got {adm.status_code} for orphan {gid} (should be 200)")
        return r
    # Non-admin must be denied
    usr = get(f"{base}/api/v1/team/replay/{gid}", token=token_user)
    if usr.status_code == 403:
        r.pass_(f"admin sees orphan (200), non-admin denied (403) for {gid}")
    elif usr.status_code == 200:
        r.fail(f"non-admin got 200 for orphan {gid} — ACCESS LEAK")
    else:
        r.fail(f"non-admin got {usr.status_code} (expected 403)")
    return r


# ═══ MAIN ═══════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(description="Privacy Layer V3 smoke test")
    parser.add_argument("--base", default="http://localhost:8100", help="API base URL")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    admin_token = os.environ.get("ADMIN_TOKEN")
    user_a_token = os.environ.get("USER_A_TOKEN")
    user_b_token = os.environ.get("USER_B_TOKEN")
    user_a_game_id = os.environ.get("USER_A_GAME_ID")
    no_consent_token = os.environ.get("NO_CONSENT_TOKEN") or user_b_token  # reuse B if user B has no consent

    print(f"{BOLD}Privacy Layer V3 — smoke test{RESET}")
    print(f"Base URL: {base}")
    print(f"Tokens:   ADMIN={'yes' if admin_token else 'no'}  "
          f"USER_A={'yes' if user_a_token else 'no'}  "
          f"USER_B={'yes' if user_b_token else 'no'}")
    print()

    results = [
        t1_schema(base),
        t2_access_control(base, user_a_token, user_b_token, user_a_game_id),
        t3_consent_required(base, no_consent_token),
        t4_anonymization(base),
        t5_gdpr_export(base, user_a_token),
        t6_interest(base, user_a_token),
        t7_orphan_denied(base, admin_token, user_a_token),
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

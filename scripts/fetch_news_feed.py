#!/usr/bin/env python3
"""Fetch news from YouTube RSS + Twitch + Reddit for the Meta Ticker.

Usage:
    python scripts/fetch_news_feed.py
    python scripts/fetch_news_feed.py --dry-run
    python scripts/fetch_news_feed.py --resolve-channels   # one-time: print channel IDs

Crontab (every 3h):
    0 */3 * * * cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool && venv/bin/python scripts/fetch_news_feed.py

Twitch setup:
    1. Register app at https://dev.twitch.tv/console/apps
    2. Save credentials: echo 'CLIENT_ID:CLIENT_SECRET' > /tmp/.twitch_creds
"""
import argparse
import json
import logging
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── YouTube channels ──
# Map: handle → channel_id (UC... format)
# To find a channel ID: python scripts/fetch_news_feed.py --resolve-channels
YOUTUBE_CHANNELS = {
    # name → (channel_id, lang)   lang: "en" default, "it" for Italian, etc.
    # Tier 1
    "Lorcana Academy":       ("UCQErN2YGMuB385NlJoCRUkw", "en"),
    "Lorcana Goons":         ("UCqVv7rq9PGTJC5GbEbtgodA", "en"),
    "The Forbidden Mountain": ("UCzBbhYrk9quifEsIQbDj-xA", "en"),
    "The Illumiteers":       ("UChdIs1fGi3VYeVUBv_wdb-Q", "en"),
    "DMArmada":              ("UCLYtjHT4lwcN8-e5Fh9Rigg", "en"),
    "Team Covenant":         ("UCT0_zqao2b2kJBe-bmF_0og", "en"),
    # Tier 2
    "Ready Set Draw TCG":    ("UCOkGJOd98_ER6RsEqlglAZg", "en"),
    "The Inkwell":           ("UCxhyFyHmkevTXCBzCMmwGpA", "en"),
    "phonetiic":             ("UCJnExBLgj6nTts2sLsmQlOQ", "en"),
    "Mushu Report":          ("UCPiB2otsvIpnd0sdnX05uKA", "en"),
    "Inkborn Heroes":        ("UCXZ-zmr98-cZH9wouu3P-fA", "en"),
    # Affiliati IT
    "Tales of Lorcana":      ("UCffkK3cuuMOXs-eBkknxwww", "it"),
    "Inked Broom":           ("UC3ipghmUqKe3a1cBahdRbiQ", "it"),
}

YOUTUBE_API_KEY_FILE = Path("/tmp/.youtube_api_key")
YOUTUBE_API_URL = (
    "https://www.googleapis.com/youtube/v3/playlistItems"
    "?part=snippet&maxResults=5&playlistId={pid}&key={key}"
)

# Channels that are Lorcana-only don't need title filtering.
# Multi-TCG channels require the video title to match at least one keyword.
LORCANA_ONLY_CHANNELS = {
    "Lorcana Academy", "Lorcana Goons", "The Forbidden Mountain",
    "The Illumiteers", "The Inkwell", "phonetiic", "Mushu Report",
    "Inkborn Heroes", "Ready Set Draw TCG",
    "Tales of Lorcana", "Inked Broom",
}
LORCANA_KEYWORDS = re.compile(
    r"lorcana|illumineer|inklands|ink\s?deck|azurite|shimmering|floodborn|"
    r"rise of the floodborn|into the inklands|ursula.s return|"
    r"first chapter|set championship|dreamborn|wilds unknown",
    re.IGNORECASE,
)
# Reddit blocks datacenter IPs (403). Works with OAuth or residential IPs.
# For now YouTube + manual entry covers the ticker. Re-enable when OAuth is set up.
REDDIT_URL = "https://www.reddit.com/r/Lorcana/hot.json?limit=8"
REDDIT_USER_AGENT = "LorcanaMonitor/1.0 (by metamonitor.app)"

# ── Twitch channels ──
# name → (login, lang)
TWITCH_CHANNELS = {
    "Lorecast":         ("disneylorcana", "en"),
}
TWITCH_CREDS_FILE = Path("/tmp/.twitch_creds")  # format: CLIENT_ID:CLIENT_SECRET

MAX_AGE_HOURS = 24  # only import items from the last 24h
EXPIRE_HOURS = 24   # items expire after 24h


def _fetch_url(url: str, user_agent: str = "LorcanaMonitor/1.0") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


# ── YouTube ──

def fetch_youtube(dry_run: bool = False) -> list[dict]:
    """Fetch recent videos via YouTube Data API v3.

    Uses playlistItems.list on each channel's "uploads" playlist (1 quota unit/call).
    Uploads playlist id is derived from channel id: UC... → UU... (YouTube convention).
    Quota budget: ~13 channels × 8 runs/day = ~104 units/day (free tier = 10000).
    """
    if not YOUTUBE_API_KEY_FILE.exists():
        logger.warning("YouTube skipped: no API key at %s", YOUTUBE_API_KEY_FILE)
        return []
    api_key = YOUTUBE_API_KEY_FILE.read_text().strip()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    items = []

    for name, (cid, lang) in YOUTUBE_CHANNELS.items():
        if not cid.startswith("UC"):
            logger.warning("YouTube %s skipped: channel_id %r not in UC... format", name, cid)
            continue
        uploads_pid = "UU" + cid[2:]
        found = 0
        try:
            raw = _fetch_url(YOUTUBE_API_URL.format(pid=uploads_pid, key=api_key))
            data = json.loads(raw)

            for entry in data.get("items", []):
                sn = entry.get("snippet", {}) or {}
                pub_str = sn.get("publishedAt", "")
                if not pub_str:
                    continue
                pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                if pub < cutoff:
                    continue

                video_id = (sn.get("resourceId") or {}).get("videoId", "")
                title = sn.get("title", "")
                if not video_id:
                    continue

                if name not in LORCANA_ONLY_CHANNELS and not LORCANA_KEYWORDS.search(title or ""):
                    continue

                thumbs = sn.get("thumbnails") or {}
                thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url") \
                    or f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"

                items.append({
                    "label": "VIDEO",
                    "source": "youtube",
                    "title": title[:280],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": name,
                    "thumbnail_url": thumb,
                    "published_at": pub,
                    "expires_at": pub + timedelta(hours=EXPIRE_HOURS),
                    "meta": {"video_id": video_id, "lang": lang},
                })
                found += 1

            logger.info("YouTube %s: found %d recent videos", name, found)

        except Exception as e:
            logger.warning("YouTube %s fetch failed: %s", name, e)

    return items


# ── Reddit ──

def fetch_reddit(dry_run: bool = False) -> list[dict]:
    """Fetch hot posts from r/Lorcana."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    items = []

    try:
        raw = _fetch_url(REDDIT_URL, user_agent=REDDIT_USER_AGENT)
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post.get("data", {})
            score = p.get("score", 0)
            created = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc)

            if created < cutoff or score < 50:
                continue

            flair = (p.get("link_flair_text") or "").lower()
            label = "NEWS" if any(k in flair for k in ("news", "announcement", "official")) else "BUZZ"

            permalink = p.get("permalink", "")
            items.append({
                "label": label,
                "source": "reddit",
                "title": p.get("title", "")[:280],
                "url": f"https://reddit.com{permalink}" if permalink else None,
                "channel": "r/Lorcana",
                "thumbnail_url": None,
                "published_at": created,
                "expires_at": created + timedelta(hours=EXPIRE_HOURS),
                "meta": {"score": score, "flair": p.get("link_flair_text")},
            })

        logger.info("Reddit r/Lorcana: found %d qualifying posts", len(items))

    except Exception as e:
        logger.warning("Reddit fetch failed: %s", e)

    return items


# ── Twitch ──

def _twitch_get_token(client_id: str, client_secret: str) -> str | None:
    """Get Twitch app access token via client credentials flow."""
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }).encode()
    req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()).get("access_token")


def _twitch_api(endpoint: str, client_id: str, token: str) -> dict:
    """Call Twitch Helix API."""
    req = urllib.request.Request(
        f"https://api.twitch.tv/helix/{endpoint}",
        headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def fetch_twitch(dry_run: bool = False) -> list[dict]:
    """Fetch live streams + recent VODs from tracked Twitch channels."""
    if not TWITCH_CREDS_FILE.exists():
        logger.info("Twitch skipped: no credentials at %s", TWITCH_CREDS_FILE)
        return []

    try:
        creds = TWITCH_CREDS_FILE.read_text().strip()
        client_id, client_secret = creds.split(":", 1)
        token = _twitch_get_token(client_id, client_secret)
        if not token:
            logger.warning("Twitch: failed to get access token")
            return []
    except Exception as e:
        logger.warning("Twitch auth failed: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    items = []
    logins = [login for _, (login, _) in TWITCH_CHANNELS.items()]
    login_to_name = {login: name for name, (login, _) in TWITCH_CHANNELS.items()}
    login_to_lang = {login: lang for _, (login, lang) in TWITCH_CHANNELS.items()}

    # 1. Check live streams
    try:
        login_param = "&".join(f"user_login={l}" for l in logins)
        data = _twitch_api(f"streams?{login_param}", client_id, token)
        for s in data.get("data", []):
            login = s.get("user_login", "")
            name = login_to_name.get(login, login)
            lang = login_to_lang.get(login, "en")
            items.append({
                "label": "LIVE",
                "source": "twitch",
                "title": f"{name} is live: {s.get('title', '')}",
                "url": f"https://twitch.tv/{login}",
                "channel": name,
                "thumbnail_url": s.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180"),
                "published_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=3),  # re-check next cron
                "meta": {"lang": lang, "viewer_count": s.get("viewer_count", 0)},
            })
            logger.info("Twitch %s: LIVE with %d viewers", name, s.get("viewer_count", 0))
    except Exception as e:
        logger.warning("Twitch streams fetch failed: %s", e)

    # 2. Recent VODs (last 24h)
    try:
        # First get user IDs
        login_param = "&".join(f"login={l}" for l in logins)
        users_data = _twitch_api(f"users?{login_param}", client_id, token)
        for u in users_data.get("data", []):
            user_id = u["id"]
            login = u["login"]
            name = login_to_name.get(login, login)
            lang = login_to_lang.get(login, "en")

            vods = _twitch_api(f"videos?user_id={user_id}&type=archive&first=5", client_id, token)
            for v in vods.get("data", []):
                pub_str = v.get("created_at", "")
                if not pub_str:
                    continue
                pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                if pub < cutoff:
                    continue
                items.append({
                    "label": "VIDEO",
                    "source": "twitch",
                    "title": v.get("title", "")[:280],
                    "url": v.get("url", f"https://twitch.tv/{login}"),
                    "channel": name,
                    "thumbnail_url": v.get("thumbnail_url", "").replace("%{width}", "320").replace("%{height}", "180"),
                    "published_at": pub,
                    "expires_at": pub + timedelta(hours=EXPIRE_HOURS),
                    "meta": {"lang": lang, "view_count": v.get("view_count", 0), "duration": v.get("duration")},
                })

            logger.info("Twitch %s: found %d recent VODs", name, sum(1 for i in items if i["channel"] == name and i["label"] == "VIDEO"))
    except Exception as e:
        logger.warning("Twitch VODs fetch failed: %s", e)

    return items


# ── Resolve channel IDs helper ──

def resolve_channels():
    """One-time helper: try to resolve YouTube handles to channel IDs."""
    handles = [
        "LorcanaAcademy", "LorcanaGoons", "TheForbiddenMountain",
        "TheIllumiteers", "DMArmada", "TeamCovenant",
        "ReadySetDrawTCG", "TheInkwell", "phonetiic",
        "MushuReport", "InkbornHeroes",
    ]
    print("Visit each channel page, view source, and search for 'channel_id' or 'externalId':")
    for h in handles:
        print(f"  https://www.youtube.com/@{h}")
    print("\nOr use: curl -s 'https://www.youtube.com/@HANDLE' | grep -oP 'channel_id=\\K[^\"&]+'")


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Fetch news for Meta Ticker")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't write to DB")
    parser.add_argument("--resolve-channels", action="store_true", help="Print channel ID lookup instructions")
    args = parser.parse_args()

    if args.resolve_channels:
        resolve_channels()
        return

    # Fetch from all sources
    yt_items = fetch_youtube(dry_run=args.dry_run)
    twitch_items = fetch_twitch(dry_run=args.dry_run)
    reddit_items = fetch_reddit(dry_run=args.dry_run)
    all_items = yt_items + twitch_items + reddit_items

    logger.info("Total items fetched: %d (YouTube: %d, Twitch: %d, Reddit: %d)",
                len(all_items), len(yt_items), len(twitch_items), len(reddit_items))

    if args.dry_run:
        for it in all_items:
            print(f"  [{it['label']}] {it['channel']}: {it['title'][:80]}")
        return

    # Write to DB
    from backend.models import SessionLocal
    from backend.services import news_feed_service

    db = SessionLocal()
    try:
        upserted = 0
        for it in all_items:
            try:
                news_feed_service.upsert_from_source(
                    db,
                    source=it["source"],
                    url=it["url"],
                    label=it["label"],
                    title=it["title"],
                    channel=it.get("channel"),
                    thumbnail_url=it.get("thumbnail_url"),
                    published_at=it.get("published_at"),
                    expires_at=it.get("expires_at"),
                    meta=it.get("meta"),
                )
                upserted += 1
            except Exception as e:
                db.rollback()
                logger.warning("Failed to upsert item '%s': %s", it["title"][:50], e)

        cleaned = news_feed_service.cleanup_expired(db)
        logger.info("Done: %d items upserted, %d expired cleaned", upserted, cleaned)

    finally:
        db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Serve statico per il dashboard Lorcana — porta 8060. Gzip abilitato + API deck."""
import gzip
import http.server
import io
import json
import os
import uuid
from datetime import datetime

PORT = 8060
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
CARDS_DB_PATH = "/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json"
DECKS_FILE = os.path.join(DIRECTORY, "user_decks.json")
COACHING_DIR = os.path.join(DIRECTORY, "coaching")

# Coaching JS (served from App_tool frontend)
COACHING_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "..", "App_tool", "frontend", "assets", "js", "team_coaching.js")

# Dashboard deck codes → archive deck codes
DECK_ALIAS = {
    "AmSa": "AS", "EmSa": "ES",
    "AS": "AS", "ES": "ES",  # passthrough
}

os.chdir(DIRECTORY)

COMPRESSIBLE = {".html", ".json", ".js", ".css", ".md", ".txt", ".svg"}


def load_decks():
    try:
        with open(DECKS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_decks(data):
    with open(DECKS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class GzipHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with gzip for large text files + API endpoints."""

    def end_headers(self):
        """Add security + cache headers to all responses."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        path = self.translate_path(self.path)
        if path.endswith("chart.min.js"):
            self.send_header("Cache-Control", "public, max-age=3600")
        elif not path.endswith("chart.min.js"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _load_archive(self, deck, opp):
        """Load archive JSON for a matchup. Returns parsed dict or None."""
        # Translate dashboard deck codes to archive codes
        deck = DECK_ALIAS.get(deck, deck)
        opp = DECK_ALIAS.get(opp, opp)
        fname = f"archive_{deck}_vs_{opp}.json"
        path = os.path.join(ARCHIVE_DIR, fname)
        if not os.path.isfile(path):
            return None
        with open(path) as f:
            return json.load(f)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        # API: GET /api/replay/list?deck=AmAm&opp=ES
        if self.path.startswith("/api/replay/list"):
            qs = parse_qs(urlparse(self.path).query)
            deck = qs.get("deck", [""])[0]
            opp = qs.get("opp", [""])[0]
            if not deck or not opp:
                self._json_response({"error": "deck and opp required"}, 400)
                return
            archive = self._load_archive(deck, opp)
            if not archive:
                self._json_response({"error": "archive not found"}, 404)
                return
            games = archive.get("games", [])
            game_list = [{
                "i": i,
                "r": "W" if g.get("we_won") else "L",
                "otp": g.get("we_otp", False),
                "on": g.get("our_name", ""),
                "en": g.get("opp_name", ""),
                "om": g.get("our_mmr", 0),
                "em": g.get("opp_mmr", 0),
                "l": g.get("length", 0),
                "d": g.get("date", ""),
            } for i, g in enumerate(games)]
            self._json_response({"games": game_list, "total": len(games)})
            return

        # API: GET /api/replay/game?deck=AmAm&opp=ES&idx=0
        if self.path.startswith("/api/replay/game"):
            qs = parse_qs(urlparse(self.path).query)
            deck = qs.get("deck", [""])[0]
            opp = qs.get("opp", [""])[0]
            idx = int(qs.get("idx", ["0"])[0])
            if not deck or not opp:
                self._json_response({"error": "deck and opp required"}, 400)
                return
            archive = self._load_archive(deck, opp)
            if not archive:
                self._json_response({"error": "archive not found"}, 404)
                return
            games = archive.get("games", [])
            if idx < 0 or idx >= len(games):
                self._json_response({"error": "game index out of range"}, 400)
                return
            self._json_response({"game": games[idx]})
            return

        # API: GET /api/replay/cards_db (slim: only fields needed for replay)
        if self.path.startswith("/api/replay/cards_db"):
            if not os.path.isfile(CARDS_DB_PATH):
                self._json_response({"error": "cards_db not found"}, 404)
                return
            with open(CARDS_DB_PATH) as f:
                full_db = json.load(f)
            slim = {}
            for name, card in full_db.items():
                slim[name] = {
                    "cost": card.get("cost", ""),
                    "type": card.get("type", ""),
                    "ink": card.get("ink", ""),
                    "str": card.get("str", ""),
                    "will": card.get("will", ""),
                    "lore": card.get("lore", ""),
                    "ability": card.get("ability", ""),
                    "set": card.get("set", ""),
                    "number": card.get("number", ""),
                }
            self._json_response(slim)
            return

        # API: GET /api/decks?user=<nick>
        if self.path.startswith("/api/decks"):
            qs = parse_qs(urlparse(self.path).query)
            user = qs.get("user", [""])[0].lower()
            db = load_decks()
            user_decks = db.get(user, []) if user else []
            self._json_response({"decks": user_decks})
            return
        # Serve team_coaching.js
        if self.path == "/assets/js/team_coaching.js":
            if os.path.isfile(COACHING_JS):
                with open(COACHING_JS, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)
            return

        # API: GET /api/v1/team/replay/list
        if self.path.startswith("/api/v1/team/replay/list"):
            qs = parse_qs(urlparse(self.path).query)
            player = qs.get("player", [""])[0].lower()
            os.makedirs(COACHING_DIR, exist_ok=True)
            replays = []
            for fname in sorted(os.listdir(COACHING_DIR), reverse=True):
                if not fname.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(COACHING_DIR, fname)) as f:
                        data = json.load(f)
                    if player and data.get("player_name", "").lower() != player:
                        continue
                    pnames = data.get("player_names", {})
                    perspective = data.get("perspective", 1)
                    opp_name = [n for k, n in pnames.items() if k != str(perspective)]
                    replays.append({
                        "id": fname.replace(".json", ""),
                        "game_id": data.get("game_id", ""),
                        "player": data.get("player_name", ""),
                        "opponent": opp_name[0] if opp_name else "",
                        "winner": data.get("winner"),
                        "victory_reason": data.get("victory_reason", ""),
                        "turns": data.get("turn_count", 0),
                        "created_at": data.get("uploaded_at", ""),
                    })
                except Exception:
                    continue
            self._json_response(replays[:100])
            return

        # API: GET /api/v1/team/replay/{game_id}
        if self.path.startswith("/api/v1/team/replay/") and not self.path.startswith("/api/v1/team/replay/list"):
            game_id = self.path.split("/api/v1/team/replay/")[1].split("?")[0]
            fpath = os.path.join(COACHING_DIR, f"{game_id}.json")
            if os.path.isfile(fpath):
                with open(fpath) as f:
                    self._json_response(json.load(f))
            else:
                self._json_response({"error": "not found"}, 404)
            return

        super().do_GET()

    def do_POST(self):
        # API: POST /api/v1/team/replay/upload
        if self.path == "/api/v1/team/replay/upload":
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "App_tool"))
            try:
                from backend.services.replay_service import parse_replay_gz, auto_match_player
            except ImportError:
                self._json_response({"error": "replay_service not available"}, 500)
                return

            length = int(self.headers.get("Content-Length", 0))
            if not length or length > 500_000:
                self._json_response({"error": "File too large or empty"}, 400)
                return

            raw_body = self.rfile.read(length)
            # Extract file from multipart or raw body
            content_type = self.headers.get("Content-Type", "")
            if "multipart" in content_type:
                # Simple multipart parser: find gzip data between boundaries
                boundary = content_type.split("boundary=")[1].strip() if "boundary=" in content_type else ""
                if boundary:
                    parts = raw_body.split(b"--" + boundary.encode())
                    file_data = None
                    for part in parts:
                        if b"\r\n\r\n" in part:
                            file_data = part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n--")
                            break
                    if file_data:
                        raw_body = file_data
            try:
                parsed = parse_replay_gz(raw_body)
            except ValueError as e:
                self._json_response({"error": str(e)}, 400)
                return

            os.makedirs(COACHING_DIR, exist_ok=True)
            game_id = parsed["game_id"]
            fpath = os.path.join(COACHING_DIR, f"{game_id}.json")
            if os.path.isfile(fpath):
                self._json_response({"error": f"Game {game_id} already uploaded"}, 409)
                return

            # Auto-match player from team_roster.json
            roster_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_roster.json")
            roster = []
            try:
                with open(roster_path) as f:
                    roster = json.load(f).get("players", [])
            except Exception:
                pass
            matched = auto_match_player(parsed["player_names"], roster)
            parsed["player_name"] = matched or ""
            parsed["uploaded_at"] = datetime.now().isoformat()

            with open(fpath, "w") as f:
                json.dump(parsed, f, ensure_ascii=False)

            pnames = parsed["player_names"]
            perspective = parsed["perspective"]
            opp_name = [n for k, n in pnames.items() if k != str(perspective)]

            self._json_response({
                "status": "ok" if matched else "needs_assignment",
                "game_id": game_id,
                "player": matched or "",
                "player_names": pnames,
                "opponent": opp_name[0] if opp_name else "",
                "turns": parsed["turn_count"],
                "winner": parsed["winner"],
            })
            return

        # API: POST /api/decks
        if self.path == "/api/decks":
            body = self._read_body()
            user = (body.get("user") or "").lower().strip()
            if not user:
                self._json_response({"error": "user required"}, 400)
                return
            deck = {
                "id": str(uuid.uuid4())[:8],
                "name": body.get("name", "Unnamed"),
                "deckCode": body.get("deckCode", "?"),
                "cards": body.get("cards", {}),
                "total": sum((body.get("cards") or {}).values()),
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            db = load_decks()
            if user not in db:
                db[user] = []
            # Max 20 decks per user
            if len(db[user]) >= 20:
                db[user] = db[user][-19:]
            db[user].append(deck)
            save_decks(db)
            self._json_response({"ok": True, "deck": deck})
            return
        self._json_response({"error": "not found"}, 404)

    def do_PUT(self):
        # API: PUT /api/decks (update existing)
        if self.path == "/api/decks":
            body = self._read_body()
            user = (body.get("user") or "").lower().strip()
            deck_id = body.get("id", "")
            if not user or not deck_id:
                self._json_response({"error": "user and id required"}, 400)
                return
            db = load_decks()
            decks = db.get(user, [])
            found = next((d for d in decks if d["id"] == deck_id), None)
            if not found:
                self._json_response({"error": "deck not found"}, 404)
                return
            if "name" in body:
                found["name"] = body["name"]
            if "cards" in body:
                found["cards"] = body["cards"]
                found["total"] = sum(body["cards"].values())
            if "deckCode" in body:
                found["deckCode"] = body["deckCode"]
            found["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_decks(db)
            self._json_response({"ok": True, "deck": found})
            return
        self._json_response({"error": "not found"}, 404)

    def do_DELETE(self):
        # API: DELETE /api/decks?user=<nick>&id=<id>
        if self.path.startswith("/api/decks"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            user = qs.get("user", [""])[0].lower()
            deck_id = qs.get("id", [""])[0]
            if not user or not deck_id:
                self._json_response({"error": "user and id required"}, 400)
                return
            db = load_decks()
            decks = db.get(user, [])
            db[user] = [d for d in decks if d["id"] != deck_id]
            save_decks(db)
            self._json_response({"ok": True})
            return
        self._json_response({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_head(self):
        """Override send_head to add gzip encoding."""
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()

        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        accept = self.headers.get("Accept-Encoding", "")

        # Only gzip large compressible files
        if "gzip" not in accept or ext not in COMPRESSIBLE or size < 4096:
            return super().send_head()

        ctype = self.guess_type(path)
        try:
            with open(path, "rb") as f:
                raw = f.read()
            compressed = gzip.compress(raw, compresslevel=6)
        except Exception:
            return super().send_head()

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        # Cache static assets (chart.min.js) for 1h, data files no-cache
        if path.endswith("chart.min.js"):
            self.send_header("Cache-Control", "public, max-age=3600")
        else:
            self.send_header("Cache-Control", "no-cache")
        # Security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        return io.BytesIO(compressed)


http.server.SimpleHTTPRequestHandler.extensions_map.update({
    ".js": "application/javascript",
    ".json": "application/json",
})

with http.server.HTTPServer(("0.0.0.0", PORT), GzipHandler) as httpd:
    print(f"Dashboard Lorcana su http://0.0.0.0:{PORT}/dashboard.html (gzip)")
    httpd.serve_forever()

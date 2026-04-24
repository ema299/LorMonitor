# Set 12 Launch — Migration Plan

> Draft v3.1 — 2026-04-22 (S0 completo: codice + VPS actions applicate).
>
> **Stato attuale**: Fase S0 chiusa end-to-end. Codice in repo, migration `7dec24a98839` applicata, systemd drop-in con `APPTOOL_ADMIN_TOKEN`, crontab Dom 04:45 switched al wrapper, cron canary 07:05 UTC installata.
>
> La migration S0.5 (`7894044b7dd3_set12_launch_meta_epoch.py`) resta **in cassetto** e non deve essere applicata finché Ravensburger non annuncia data di release + rotation. Head alembic corrente = `7dec24a98839`.
>
> Changelog v3: S0 codice completato (commit sparsi 2026-04-22). Dry-run E2E confermato (folder fake `SETXX` → `perimeter=setXX`, `format=core`; env `APPTOOL_DEFAULT_CORE_PERIMETER=set12` → blob e `PERIMETER_CONFIG` si aggiornano automaticamente).
>
> Changelog v2: S0.3 riscritto (cross-process `reset_checkers` era concettualmente rotto, ora usa admin endpoint), S0.2 riscritto come canary filesystem-level, inventory §3 esteso con 5 miss (digest generator, partial index, import_from_archive, frontend_v3), aggiunta S0.6 (partial index migration), S1.3 estesa con "overlap aggregate policy", checklist §8 con E2E smoke-test esplicito.

Questo documento consolida le azioni necessarie per preparare App_tool al release di Set 12, con particolare attenzione alla **transition window** (pre-release + overlap S11/S12 + post-rotation) in cui dobbiamo catturare senza perdite tutti i match — anche quelli con naming queue/folder ancora ignoto.

Pattern operativo seguito: stesso approccio di `SPRINT_P1.5_VENDORED.md` (shadow mode dove possibile, rollback flag, zero breaking change).

---

## 1. Obiettivo

Rendere App_tool resiliente al release di Set 12 senza:
- perdere match durante la transition window,
- rompere il batch LLM (digest / KC / matchup reports) che già legge `meta_epochs.legal_sets`,
- forzare refactor lato frontend per il giorno-1.

---

## 2. Vincoli e fatti noti (al 2026-04-21)

- Data release ufficiale Set 12: **ignota** (fonte = sito Ravensburger, vedi `reference_lorcana_calendar.md`). Serve inserirla in `meta_epochs`.
- Rotation Core Set 12: **ignota** (quali set base ruotano fuori). Impatta `legal_sets`.
- Set code 3-letter ufficiale di Set 12: **ignoto**. Impatta `SET_MAP` in `static_importer.py`.
- Queue naming duels.ink atteso: `S12-BO1`, `S12-BO3`, possibile `S12-EA-*` per early access. Da confermare osservando il sito appena aperto.
- `backend/services/legality_service.py:43` — `FORMAT_QUEUE_PREFIXES` già pronto per `"S12-"`.
- `backend/services/legality_service.py:_legality_matches` già accetta tag `core_s12` / `core_s13` / ...
- `db/migrations/versions/b7c2e9d41058_add_meta_epochs_table.py` — seed corrente `Set11 settled` con `legal_sets=[1..11]`, `ended_at=NULL`. La migration ha già la nota "Adjust legal_sets / bounds here as Set 12 rotates in".

**Caveat emersi in review v2:**
- `meta_epochs.started_at` è `DATE`, non `TIMESTAMPTZ`. Se release Ravensburger avviene a metà giornata UTC, la transizione legalità è ambigua per ~24h. Accettabile se documentato; se servisse timezone-precise, servirebbe una migration separata (non blocker per S0).
- `reset_checkers()` è process-local: la `LegalityChecker` cache vive nel processo uvicorn, non nel processo `static_importer`. Cross-process invalidation richiede admin endpoint o restart (vedi S0.3 riscritto).
- Cache `dashboard-data` ha TTL 2h con stale-while-revalidate: post-cutover serve `?refresh=true` o force rebuild per vedere subito `set12` nel blob.

---

## 3. Inventario hardcodings da toccare

Ordinato per file. Ogni entry va validata e aggiornata in S0 o S1 a seconda del tipo (regex vs data puntuale).

| File | Riga | Hardcode attuale | Fix richiesto | Fase |
|---|---|---|---|---|
| `backend/workers/match_importer.py` | 19, 24 | `{"SET11": "core"/"set11"}` hardcoded | Regex `^SET(\d+)$` → `perimeter=f"set{n}"`, `format="core"` | S0.1 |
| `scripts/import_matches.py` | 59 | `CORE_QUEUES = {'S11-BO1','S11-BO3','SET11'}` | Prefix check `^S\d+-(BO1|BO3)$` + `^SET\d+$` | S0.1 |
| `scripts/import_matches.py` | 224 | `PERIM_PRIORITY = {'set11': 1, ...}` | Aggiungere default per `setNN: 1`, oppure lookup dinamico | S0.1 |
| `backend/workers/static_importer.py` | 16–20 | `SET_MAP` fino a `FLB="11"` | Aggiungere entry Set 12 al reveal del set code | S1.2 |
| `backend/workers/static_importer.py` | `import_cards_db` end | Nessun `reset_checkers()` | Aggiungere `from backend.services.legality_service import reset_checkers; reset_checkers()` a fine import | S0.3 |
| `backend/services/snapshot_assembler.py` | 27–34 (`PERIMETER_CONFIG`) | `'set11'` come key core High ELO | Aggiungere `'set12'` clone, introdurre `DEFAULT_CORE_PERIMETER` configurabile | S0.4 + S1.3 |
| `backend/services/snapshot_assembler.py` | 691, 702, 731 | Liste iterate hardcoded con `'set11'` | Sostituire con `CORE_PERIMETERS = [DEFAULT_CORE_PERIMETER, 'top', 'pro']` | S0.4 |
| `backend/services/snapshot_assembler.py` | top-level blob | Nessun campo `default_core_perimeter` | Aggiungere campo al blob per guidare frontend | S0.4 |
| `backend/services/rogue_scout_service.py` | 24, 27, 43, 203 | `'set11'` default perimeter | Parametrizzare via `meta_epoch_service.get_active_core_perimeter()` | S1.3 |
| `backend/services/tech_service.py` | 21, 63, 78 | `'set11'` default | Idem | S1.3 |
| `backend/services/history_service.py` | 10, 82 | `'set11'` default | Idem | S1.3 |
| `backend/api/monitor.py` | 137, 161 | `Query("set11")` default | Idem | S1.3 |
| `backend/api/dashboard.py` | 119 | docstring "set11" | Aggiornare docstring | S1.3 |
| `frontend/dashboard.html` | multi (search `'set11'`) | Hardcoded perimeter | Leggere `DATA.default_core_perimeter` con fallback `'set11'` | S0.4 + S1.4 |
| `db/migrations/versions/<new>_set12_launch.py` | nuovo | Non esiste | Migration che chiude Set11 + apre Set12 | S1.1 |
| **`pipelines/digest/generator.py`** | **93** | **`PERIMETERS = {"set11","top","pro","friends"}`** — perimeter set hardcoded nel digest nativo. Post-cutover **i match `set12` verrebbero silently ignorati** dal digest/KC anche se tutto il resto è aggiornato. **Fix più critico.** | Sostituire con `lambda p: p != "other" and not p.startswith("inf")` o lista estensibile | S0.1 |
| **`backend/models/match.py`** | **44** | **`postgresql_where=text("perimeter IN ('set11', 'top', 'pro', 'friends')")`** — partial index `idx_matches_lookup`. `set12` resta fuori dall'indice → query core su match `set12` fanno seq-scan, degradato di ~10-100x su tabella da 200K+ righe. | Migration Alembic che ricrea l'indice con perimeter generico | S0.6 |
| **`db/migrations/versions/274c18df8c4a_initial_schema_all_tables_and_indexes.py`** | **92, 193** | Stesso partial index nella migration iniziale (non muta, ma va documentata la stratificazione) | Nuova migration additiva DROP + CREATE, **non** amendare la storica | S0.6 |
| `scripts/import_from_archive.py` | 75 | `perimeter = "set11"` hardcoded | Regex simile a import_matches.py (script raro, low priority) | S1.3 |
| `frontend_v3/assets/js/dashboard/monolith.js` | 151 | `let currentPerim = 'set11'` | **Out of scope** — `frontend_v3/` non è live (vedi `frontend_v3/docs/MILESTONES.md`). Documentato come escluso. | — |

**Nota**: non toccare `pipelines/digest/vendored/` e `pipelines/kc/vendored/` — sono freeze byte-perfect. La legality filter arriva via `_get_core_legal_sets()` che legge `meta_epochs`, quindi si adatta automaticamente.

**Scope dei frontend alternativi:**
- `frontend/dashboard.html` — **live, produzione** (`metamonitor.app`). Da aggiornare in S0.4 + S1.4.
- `frontend_v3/` — **out of scope** per Set 12 readiness. V3 è lavoro isolato con suo roadmap; se V3 va live prima del rotation S12, verrà trattato separatamente.

---

## 4. Fasi operative

### Fase S0 — Preparazione (da fare subito, 2-3 dev days)

Scopo: **zero match persi il giorno-1** anche se release avviene senza preavviso. Tutto additivo, retrocompatibile, deployabile in produzione ora.

#### S0.1 — Generalizzare importer folder/queue (critico)

File: `backend/workers/match_importer.py`, `scripts/import_matches.py`.

Cambi:
- `get_format_from_folder` / `folder_to_perimeter`:
  ```python
  import re
  _SET_FOLDER_RE = re.compile(r"^SET(\d+)$")

  def get_format_from_folder(folder_name: str) -> str:
      if _SET_FOLDER_RE.match(folder_name):
          return "core"
      return {"TOP": "core", "PRO": "core", "FRIENDS": "core", "INF": "infinity"}.get(folder_name, "other")

  def get_perimeter_from_folder(folder_name: str) -> str:
      m = _SET_FOLDER_RE.match(folder_name)
      if m:
          return f"set{m.group(1)}"
      return {"TOP": "top", "PRO": "pro", "FRIENDS": "friends", "INF": "infinity"}.get(folder_name, "other")
  ```
- `CORE_QUEUES` → check prefissi invece di set fisso:
  ```python
  _CORE_QUEUE_RE = re.compile(r"^S\d+(-EA)?-(BO1|BO3)$")
  _CORE_SET_QUEUE_RE = re.compile(r"^SET\d+$")

  def determine_game_format(queue_name: str | None, perimeter: str) -> str:
      q = (queue_name or '').upper().strip()
      if _CORE_QUEUE_RE.match(q) or _CORE_SET_QUEUE_RE.match(q):
          return 'core'
      if q in INF_QUEUES:
          return 'infinity'
      if perimeter == 'inf' or perimeter == 'infinity':
          return 'infinity'
      return 'other'
  ```
- `PERIM_PRIORITY`: usa `defaultdict(int)` con bonus per `setNN` = 1, mantieni pro=3, top=2, inf=2.

Retrocompat: folder `SET11` continua a essere letto come `set11`/core. Folder `SET12` futuro → `set12`/core automaticamente, zero code change a release-day.

Smoke test: copiare un match JSON esistente in una finta cartella `SETXX/` temporanea, lanciare `import_matches.py --dry-run`, verificare che `perimeter='setXX'`.

#### S0.2 — Canary filesystem-level (diagnostic)

File: nuovo `scripts/monitor_unmapped_matches.py`.

**Correzione v2 (post-review codex)**: la versione originale guardava solo `matches` inseriti (`perimeter='other'` / `game_format='other'`). Ma il failure mode più pericoloso è **match scartati prima dell'insert** (legality gate che li droppa, `_parse_match_file` che ritorna `None` per folder ignoto, ecc.). Serve canary **filesystem-level** che confronta file sul disco vs insert.

Logica:
1. **Filesystem count**: per le ultime 24h, contare file JSON in `/mnt/.../matches/YYMMDD/*/` raggruppati per folder name (es. `SET11`, `SET12`, `TOP`, `PRO`, `INF`, `FRIENDS`, `OTHER`, `JA`, o folder nuovi).
2. **DB insert count**: `SELECT perimeter, COUNT(*) FROM matches WHERE imported_at >= NOW() - INTERVAL '24 hours' GROUP BY perimeter;`
3. **Skip cache count**: leggere `scripts/.import_skip_cache` per contare quanti ID sono in persistent skip.
4. **Drop count**: diff filesystem vs insert vs skip. I "silent drop" sono file che non risultano né in matches né in skip → legality gate o parse failure.
5. Alert se:
   - Nuovo folder mai visto prima (es. `SET12` appare per la prima volta) → mail INFO "New folder detected"
   - `drop_rate > 10%` per un folder noto → mail WARN "Unexpected drop spike"
   - `unmapped_perimeter > 50/day` → mail WARN "Unmapped matches"

Output schema:
```
{
  "date": "2026-04-21",
  "folders_on_fs": {"SET11": 1234, "TOP": 234, "PRO": 89, "OTHER": 12, "SET12": 45},  # last 24h
  "folders_new_today": ["SET12"],
  "db_inserts_by_perimeter": {"set11": 1230, "top": 234, "pro": 89, "other": 5, "set12": 43},
  "skip_cache_new": 8,
  "silent_drops": {"SET11": 4, "SET12": 2, "OTHER": 7}
}
```

Pattern identico a `scripts/monitor_kc_freshness.py` per mail (SMTP via `/tmp/.smtp_pass`).

Cron: `05 7 * * * cd /mnt/.../App_tool && venv/bin/python scripts/monitor_unmapped_matches.py` (07:05 UTC, subito dopo KC freshness).

**Funzione critica**: se duels.ink introduce un folder/queue inaspettato, la mail arriva **al primo giorno** invece che dopo settimane di match silent-dropped.

#### S0.3 — SET_MAP extension + admin endpoint per cache invalidation

File: `backend/workers/static_importer.py`, `backend/api/admin.py`.

**Correzione v2 (post-review codex)**: la versione originale chiamava `reset_checkers()` a fine `import_cards_db()`. Problema: `static_importer` gira come processo separato (modulo CLI, cron Dom 04:45). Il reset invalida la cache **nel processo importer**, non nel processo uvicorn che serve l'API. Il `LegalityChecker` dentro uvicorn resta stale finché non si restarta. **Cross-process invalidation richiede un canale esplicito.**

Cambi:

**1. SET_MAP estensibile via env** (invariato rispetto a v1):
```python
SET_MAP = {
    "TFC": "1", "ROF": "2", "ITI": "3", "URR": "4",
    "SSK": "5", "AZU": "6", "ABM": "7", "SIX": "8",
    "TMF": "9", "PSC": "10", "FLB": "11",
    # Set 12 code: inserire al reveal, fallback via env
}
_EXTRA_SET_CODE = os.environ.get("EXTRA_SET_CODE")
_EXTRA_SET_NUM = os.environ.get("EXTRA_SET_NUM", "12")
if _EXTRA_SET_CODE:
    SET_MAP[_EXTRA_SET_CODE] = _EXTRA_SET_NUM
```

**2. Admin endpoint per reset cross-process**:

`backend/api/admin.py` aggiunge:
```python
@router.post("/reset-legality-cache", dependencies=[Depends(require_admin)])
def reset_legality_cache():
    """Invalidate in-process LegalityChecker cache.

    Call after static_importer refresh (cards cache changed) or after
    meta_epochs migration (legal_sets changed), without restarting uvicorn.
    """
    from backend.services.legality_service import reset_checkers
    reset_checkers()
    # Also clear KC prompt builder's cached legal_sets
    from pipelines.kc import build_prompt
    build_prompt._core_legal_sets = None
    return {"status": "ok", "reset": ["legality_checkers", "kc_legal_sets"]}
```

**3. Orchestrazione cron**: aggiungere wrapper shell `scripts/refresh_static_and_reset.sh`:
```bash
#!/bin/bash
set -e
cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool
venv/bin/python -m backend.workers.static_importer
curl -s -X POST -H "X-Admin-Token: $APPTOOL_ADMIN_TOKEN" \
     http://127.0.0.1:8100/api/v1/admin/reset-legality-cache
```
Sostituire cron `Dom 04:45` da `static_importer` diretto a questo wrapper.

**4. Dashboard cache invalidation** (opzionale, solo al cutover S1):
```python
@router.post("/refresh-dashboard", dependencies=[Depends(require_admin)])
def refresh_dashboard():
    from backend.api.dashboard import _rebuild_cache
    from backend.models import SessionLocal
    db = SessionLocal()
    try:
        _rebuild_cache(db)
    finally:
        db.close()
    return {"status": "ok"}
```

**Verifica**: `duels_ink_cards_cache.json` al refresh post-release deve contenere carte Set 12 con tag `legality: ["core_s12"]` o `["core"]`. `_legality_matches` le accetta già.

**Smoke test S0.3**:
```bash
# 1. Modifica manuale meta_epochs per simulare nuova epoch
# 2. curl POST /api/v1/admin/reset-legality-cache
# 3. curl /api/v1/dashboard-data?refresh=true
# 4. Verifica che blob contenga i nuovi legal_sets
```

#### S0.4 — `default_core_perimeter` nel blob

File: `backend/services/snapshot_assembler.py`, `frontend/dashboard.html`.

Cambi backend:
- Aggiungere costante:
  ```python
  DEFAULT_CORE_PERIMETER = os.environ.get("APPTOOL_DEFAULT_CORE_PERIMETER", "set11")
  ```
- Nel blob finale:
  ```python
  blob["default_core_perimeter"] = DEFAULT_CORE_PERIMETER
  ```
- Sostituire tutte le liste `["set11", "top", "pro"]` con:
  ```python
  [DEFAULT_CORE_PERIMETER, "top", "pro"]
  ```
  (righe 691, 702, 731 e qualunque altra trovi in review).

Cambi frontend:
- Introdurre `getCoreDefaultPerimeter()` helper che ritorna `DATA.default_core_perimeter || 'set11'`.
- Sostituire tutti i `'set11'` hardcoded nel codice perimetro-aware.

Retrocompat: se il blob non ha `default_core_perimeter` → fallback `'set11'`. Se env var non settata → `'set11'`. Zero breaking change.

Al D-day si cambia una env var sul VPS + restart uvicorn, niente altro.

#### S0.5 — Migration `meta_epochs` in cassetto

File: `db/migrations/versions/<hash>_set12_launch.py` (non eseguire finché la data non è nota).

Struttura:
```python
"""set12_launch: close Set11 settled, open Set12 launch epoch"""
revision = "<hash>"
down_revision = "b7c2e9d41058"

SET12_RELEASE_DATE = os.environ.get("SET12_RELEASE_DATE")  # es. "2026-05-15"
SET12_LEGAL_SETS = os.environ.get("SET12_LEGAL_SETS", "3,4,5,6,7,8,9,10,11,12")  # rotation-survivors

def upgrade():
    if not SET12_RELEASE_DATE:
        raise RuntimeError("SET12_RELEASE_DATE env var not set")
    op.execute(f"""
        UPDATE meta_epochs SET ended_at = DATE '{SET12_RELEASE_DATE}' - INTERVAL '1 day'
        WHERE name = 'Set11 settled' AND ended_at IS NULL;
    """)
    legal_sets_sql = "ARRAY[" + SET12_LEGAL_SETS + "]"
    op.execute(f"""
        INSERT INTO meta_epochs (name, started_at, ended_at, legal_sets, notes)
        VALUES ('Set12 launch', DATE '{SET12_RELEASE_DATE}', NULL,
                {legal_sets_sql}, 'Set 12 release epoch');
    """)
```

Eseguibile in <1 min al D-day con `SET12_RELEASE_DATE=2026-... SET12_LEGAL_SETS=... alembic upgrade head`.

#### S0.6 — Partial index migration (performance)

File: `db/migrations/versions/<new>_generalize_matches_lookup_index.py`, `backend/models/match.py`.

**Problema (rilevato in review v2)**: l'indice parziale `idx_matches_lookup` in [backend/models/match.py:44](../backend/models/match.py) è vincolato a `perimeter IN ('set11', 'top', 'pro', 'friends')`. Post-cutover, match con `perimeter='set12'` fanno **seq-scan** sulla tabella `matches` (200K+ righe) invece di usare l'indice. Le query core degradano da <150ms a 1-5s.

Migration:
```python
"""generalize_matches_lookup_index_for_future_sets"""
revision = "<hash>"
down_revision = "<last>"

def upgrade():
    op.drop_index("idx_matches_lookup", table_name="matches",
                  postgresql_where=text("perimeter IN ('set11', 'top', 'pro', 'friends')"))
    op.create_index(
        "idx_matches_lookup",
        "matches",
        ["game_format", "deck_a", "deck_b", sa.literal_column("played_at DESC")],
        postgresql_where=text("perimeter NOT IN ('other')"),
    )
```

Aggiornare anche `backend/models/match.py:44` con lo stesso `postgresql_where`.

**Razionale**: `perimeter NOT IN ('other')` è future-proof (include `set11`, `set12`, `set13`, ...) e esclude solo la categoria residua `'other'` che non è mai query-pattern reale.

Esecuzione: `CREATE INDEX CONCURRENTLY` + `DROP INDEX` separati, **no-lock** su produzione. Da fare in S0 finché la tabella ha solo perimeter attuali (drop rapido). Se lasciato a S1, la ricreazione dell'indice può prendere 10-30s di scan completo.

**Smoke test**:
```sql
EXPLAIN ANALYZE
SELECT * FROM matches
WHERE game_format = 'core' AND deck_a = 'AmAm' AND deck_b = 'AmSa'
  AND played_at > NOW() - INTERVAL '30 days'
  AND perimeter = 'set12'
LIMIT 10;
```
Deve mostrare `Index Scan using idx_matches_lookup` anche con `perimeter='set12'`.

---

### Fase S1 — Transition window (release-day, coordinato)

Scopo: servire contemporaneamente match S11 (pre-rotation, già nel DB) e S12 (nuovi) durante i primi 30gg.

#### S1.1 — Apply migration `meta_epochs`

Eseguire la migration S0.5 con le 3 env var note (data, rotation, legal_sets). Smoke test:
```bash
venv/bin/python3 -c "
from backend.models import SessionLocal
from backend.services.meta_epoch_service import get_current_epoch
db = SessionLocal()
e = get_current_epoch(db)
print(e.name, e.started_at, e.legal_sets)
"
```
Deve stampare `Set12 launch <date> [<legal_sets>]`.

Impatto automatico:
- `pipelines/kc/build_prompt.py:_get_core_legal_sets` prenderà i nuovi `legal_sets` al prossimo batch (Mar 00:00 / 01:00).
- `pipelines/digest/generator.py` userà la nuova `since = max(current_epoch.started_at, NOW() - 30d)` → window efficace parte a 0gg e cresce fino a 30gg.
- `monitor_kc_freshness.py` potrebbe segnalare STALE per i primi 7gg post-release (window effettiva ridotta). È atteso; aggiungere override temporaneo o estendere la soglia freshness finché window effettiva < 14gg.

#### S1.2 — Refresh cards DB immediato

```bash
cd /mnt/.../App_tool && venv/bin/python -m backend.workers.static_importer
```
Questo:
1. Rilegge `cards_db.json` + `duels_ink_cards_cache.json` (che deve già avere carte S12).
2. Upserta in `cards` table con `image_path` corretto (dopo aver aggiunto `SET_MAP[<S12_CODE>]`).
3. Rigenera `consensus_lists` + `reference_decklists` da ultimo snapshot inkdecks.
4. Invoca `reset_checkers()` → il `LegalityChecker` core vedrà le nuove carte come legali.

Verifica: `SELECT COUNT(*) FROM cards WHERE set_code = '<S12_CODE>';` deve essere > 0.

Se `duels_ink_cards_cache.json` non ha ancora S12 (dipende dal fetcher upstream), aspettare che venga aggiornato prima di procedere. Intanto i match S12 nel DB saranno marcati `format='other'` per via del gate legality (carte unknown passano, ma se duels.ink le marca illegal passa la gate). **Double-check al D-day**.

#### S1.3 — Dual perimeter nel blob + overlap aggregate policy

File: `backend/services/snapshot_assembler.py`, `backend/services/tech_service.py`, `backend/services/rogue_scout_service.py`, `backend/services/history_service.py`, `backend/api/monitor.py`.

**1. Aggiungere a `PERIMETER_CONFIG`**:
```python
"set12": (["set12"], "core", "SET12 High ELO (≥1300)", 1300, None),
"friends_core_s12": (["set12", "top", "pro"], "core", "Friends (Core S12)", None, "friends"),
# Overlap aggregate: comprende ENTRAMBI set11 + set12 durante 30gg transition
"core_overlap": (["set11", "set12", "top", "pro"], "core", "Core (S11+S12 overlap)", 1300, None),
```

Tenere `set11` attivo per storico window (30gg). I match S11 nel DB continuano a essere visibili ma decadono naturalmente.

Settare sul VPS:
```
APPTOOL_DEFAULT_CORE_PERIMETER=set12
```

Restart uvicorn + bust cache dashboard (`POST /api/v1/admin/refresh-dashboard` o `?refresh=true`).

**2. Overlap aggregate policy** (decisione emersa in review v2):

Durante i 30gg post-release, features "core aggregate" (es. meta share globale, tech tornado "all core", trend settimanale) hanno 3 possibili politiche:

| Policy | Comportamento | Pro | Contro |
|---|---|---|---|
| **A. Hard cutover** | Da giorno-1, feature core mostra solo `set12` | Pulito, nessuna contaminazione S11 | Primi 7gg hanno sample minimo, Deck Fitness degradato |
| **B. Soft overlap** | Durante 30gg, feature core mostra `set11+set12` aggregati | Sample stabile, nessun buco UX | Mischia meta in rotation con meta stabile (può nascondere shift S12) |
| **C. Dual view** | UI mostra entrambi in colonne affiancate | Massima trasparenza | Complessità UX, doppio lavoro frontend |

**Scelta decisa 2026-04-22 — A (hard cutover)**.

Razionale (aggiornato post-discussione utente):
- L'intent KC è esplicito: post-release, le killer curves devono operare **solo su Set 12**, mai su un mix set11+set12. Policy B (soft overlap aggregato) contaminerebbe i digest KC con carte ruotate fuori, rischiando consigli obsoleti.
- I match `set11` spariscono in fretta: pochi giorni dopo il reveal gli utenti migrano al nuovo meta, il volume di match set11 precipita. La finestra 30gg-overlap perde senso.
- Policy A è già supportata dal design S0: `APPTOOL_DEFAULT_CORE_PERIMETER=set12` flippa il digest filter a `{set12, top, pro, friends}`, escludendo `set11` dal prompt KC alla fonte (vedi `pipelines/digest/generator.py:_ACTIVE_CORE_PERIMETERS`). I match `set11` restano in `matches` come storico ma non finiscono nei digest.
- `core_overlap` / picker S11/S12 (S1.4) diventano opzionali: non li implementiamo se non emerge necessità. Conseguenza: il label button "SET11 High ELO" va sostituito da "SET12 High ELO" (hardcoded in `frontend/dashboard.html:5031,5244`) al cutover.

**3. Cache invalidation sequence al cutover**:
```bash
# Ordine obbligatorio — tutti i processi devono vedere lo stesso APPTOOL_DEFAULT_CORE_PERIMETER
echo "APPTOOL_DEFAULT_CORE_PERIMETER=set12" | sudo tee -a /etc/apptool.env
export EXTRA_SET_CODE=<S12_3letter_code>              # anche in /etc/apptool.env
SET12_RELEASE_DATE=YYYY-MM-DD SET12_LEGAL_SETS=... \
    venv/bin/alembic upgrade head                      # S1.1 — meta_epochs cutover
sudo systemctl restart lorcana-api                     # uvicorn legge /etc/apptool.env
APP_ROOT=/mnt/.../App_tool scripts/refresh_static_and_reset.sh  # S1.2 — cards DB + cache reset
TOKEN=$(sudo grep APPTOOL_ADMIN_TOKEN /etc/apptool.env | cut -d= -f2)
curl -X POST -H "X-Admin-Token: $TOKEN" \
    http://127.0.0.1:8100/api/v1/admin/refresh-dashboard  # rebuild blob con set12
```

**⚠️ Cron env propagation — CRITICO per KC**:

I cron `generate_digests.py` (Mar 00:00) e `generate_killer_curves.py` (Mar 01:30) girano come processi separati da uvicorn. Senza `APPTOOL_DEFAULT_CORE_PERIMETER` esplicito nell'env della cron, i digest useranno il fallback `set11` anche dopo il flip — **il batch KC del martedì successivo al cutover produrrebbe curve basate sul perimeter sbagliato**.

Fix da applicare al cutover (una volta sola):
```bash
# In /etc/apptool.env
APPTOOL_DEFAULT_CORE_PERIMETER=set12

# Modificare le due cron entry per sourcare /etc/apptool.env prima di lanciare lo script.
# Esempio (crontab -e):
0 0 * * 2 set -a; . /etc/apptool.env; set +a; \
    cd /mnt/.../App_tool && venv/bin/python scripts/generate_digests.py --format all \
    >> /var/log/lorcana-digest.log 2>&1

30 1 * * 2 set -a; . /etc/apptool.env; set +a; \
    cd /mnt/.../App_tool && OPENAI_API_KEY=$(cat /tmp/.openai_key) \
    venv/bin/python scripts/generate_killer_curves.py --format all \
    >> /var/log/lorcana-kc.log 2>&1
```

Verifica post-cutover, prima del primo martedì:
```bash
APPTOOL_DEFAULT_CORE_PERIMETER=set12 venv/bin/python3 -c "
from pipelines.digest.generator import _ACTIVE_CORE_PERIMETERS
assert 'set12' in _ACTIVE_CORE_PERIMETERS and 'set11' not in _ACTIVE_CORE_PERIMETERS
print('digest filter OK — KC batch del martedì vedrà solo set12')
"
```

#### S1.4 — Frontend picker temporaneo S11/S12

File: `frontend/dashboard.html`.

Aggiungere toggle S11/S12 in tab bar Monitor/Coach/Lab (pattern identico al Core/Infinity toggle implementato 16/04).

```js
const SET_SCOPE_KEY = 'lorcana_set_scope';
function getActiveSetScope() {
    return localStorage.getItem(SET_SCOPE_KEY) || DATA.default_core_perimeter || 'set12';
}
```

Quando attivo `set11`, i perimeter passati agli endpoint diventano `set11`/friends_core. Quando `set12`, diventano `set12`/friends_core_s12.

Durata toggle: 30gg dopo release. Default `set12` dal giorno-1.

---

### Fase S2 — Stabilizzazione (30gg dopo release)

- Rimuovere picker S11/S12 dal frontend (tab bar + localStorage key).
- `set11` resta come perimeter legacy in `PERIMETER_CONFIG` ma non appare più nella UI.
- Digest / KC generati con epoch "Set11 settled" restano in PG ma con `is_current=false` (naturale al nuovo batch).
- Considerare cleanup di `cards` table per carte ruotate fuori: non necessario (image_path resta valido, legality filter le esclude dai nuovi KC).

---

## 5. Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---|---|
| Duels.ink rinomina queue in modo non previsto (es. `S12B-BO1`, `CORE-S12-BO1`) | Match persi | Canary S0.2 (spike in `perimeter='other'` → mail) + regex permissiva S0.1 |
| Ravensburger cambia schema code set (non numerico, o prefix 2-letter) | `SET_MAP` rotto, image_path vuoto | Fallback in `_load_cards_db` che estrae da `id="12-231"` esiste già (`static_importer.py:72`) |
| Rotation Core aggressiva (drop Set 1-3) | KC Core storici diventano illegal post-cutover, frontend mostra `is_current=false` | Post-filter `build_prompt._build_core_legality_guard` già pulisce; `is_current=false` automatico al nuovo batch |
| Early access non ufficiale con legality ambigua | Match misti contaminano digest Core | Queue prefix `S12-EA-` trattato come perimeter separato (opzionale `set12_ea`) — altrimenti caduta in core default |
| Inkdecks tarda ad aggiornare liste S12 | Consensus stale, `buildDeckCompare()` vuoto | Fix 20/04 fail-safe già in place: `is_current` non viene azzerato, resta il consensus S11 fino al primo snapshot S12 |
| `duels_ink_cards_cache.json` non aggiornato al release | Nuove carte S12 trattate come unknown (passano silent) | Verificare manualmente refresh prima di S1.2; se fetcher upstream in ritardo, match con carte unknown passano (non è blocker) |
| `monitor_kc_freshness.py` segnala STALE per 7gg post-release | Mail spam `monitorteamfe@gmail.com` | Soglia dinamica: se `days_since_epoch_start < 14`, soglia `fresh_7d >= 20` invece di `>= 100` |

---

## 6. Open questions (da chiudere prima di S1)

1. **Data release Set 12 ufficiale?** — monitorare sito Ravensburger (`reference_lorcana_calendar.md`).
2. **Set code 3-letter?** — noto solo al reveal ufficiale.
3. **Rotation Core: quali set escono?** — annuncio ufficiale ~1 mese prima del release.
4. **Early access duels.ink esiste?** — da osservare sul sito.
5. **Nomi queue esatti S12?** — attivabile dal browser ai primi match.
6. **`duels_ink_cards_cache.json` fetcher upstream** — aggiorna automaticamente al reveal o va forzato? Documentare in `reference_smtp_setup.md` o memoria dedicata.

---

## 7. Effort stimato

| Fase | Effort | Rischio | Quando |
|---|---|---|---|
| S0 (preparazione) | 2.5–3.5 dev days | Zero (tutto additivo) | Subito (questa settimana) |
| S1 (release-day) | 1 dev day | Medio (coordinato) | Giorno reveal data ufficiale |
| S2 (cleanup) | 0.5 dev day | Zero | 30gg dopo release |

Delta v2: +0.5 dev day su S0 per aggiungere `pipelines/digest/generator.py` fix (S0.1), admin endpoint (S0.3), partial index migration (S0.6), canary filesystem (S0.2 riscritto).

---

## 8. Checklist esecutiva

### S0 pre-release
- [x] **S0.1a** — Regex folder/queue in `match_importer.py` + `import_matches.py` + test dry-run *(done 2026-04-22, E2E verified below)*
- [x] **S0.1b** — Generalizzato `pipelines/digest/generator.py` `PERIMETERS` con `_is_core_perimeter()` + SQL regex `~ '^set[0-9]+$'` *(done 2026-04-22)*
- [x] **S0.2** — `scripts/monitor_unmapped_matches.py` filesystem-level (FS vs DB vs skip_cache diff); **cron 07:05 UTC da installare manualmente sul VPS** (entry di esempio in fondo al file, vedi §9)
- [x] **S0.3a** — `SET_MAP` env-extensible in `static_importer.py` (`EXTRA_SET_CODE` single + `EXTRA_SET_MAP` JSON) *(done 2026-04-22)*
- [x] **S0.3b** — Admin endpoint `POST /api/v1/admin/reset-legality-cache` + `POST /api/v1/admin/refresh-dashboard` con gate `require_admin_or_server_token` (header `X-Admin-Token`, fallback JWT admin) *(done 2026-04-22)*
- [x] **S0.3c** — Wrapper `scripts/refresh_static_and_reset.sh` presente; **update crontab Dom 04:45 + setting `APPTOOL_ADMIN_TOKEN` in `/etc/apptool.env` da fare manualmente sul VPS** (vedi §9)
- [x] **S0.4** — `default_core_perimeter` nel blob (`snapshot_assembler.py`) + helper frontend `getCoreDefaultPerimeter()` in `frontend/dashboard.html` *(done 2026-04-22; label `SET11 High ELO` restano come UI string, rinominate a S1.4)*
- [x] **S0.5** — Migration `7894044b7dd3_set12_launch_meta_epoch.py` in cassetto (guard aborta senza `SET12_RELEASE_DATE`/`SET12_LEGAL_SETS`) *(done 2026-04-22)*
- [x] **S0.6** — Migration `7dec24a98839_generalize_matches_lookup_partial_index.py` scritta + `backend/models/match.py:44` aggiornato a `perimeter NOT IN ('other')` *(done 2026-04-22; **DB apply ancora pending** — azione in §9)*
- [x] **S0 E2E smoke test**: folder fake `/tmp/set12_e2e/260426/SET12/` + match SSt-vs-ESt copiato, `parse_match_file` ritorna `perimeter=set12` / `game_format=core` / queue `S11-BO3` accettata via regex `_CORE_QUEUE_RE`. `APPTOOL_DEFAULT_CORE_PERIMETER=set12` flippa `PERIMETER_CONFIG` e `friends_core` a `['set12','top','pro']` senza ulteriori modifiche. *(eseguito 2026-04-22 07:30 UTC)*

---

## 9. Azioni VPS — eseguite 2026-04-22 07:30–07:45 UTC

Quattro azioni "shared-state" applicate in sequenza dopo il merge del codice S0.

| Azione | Stato | Dettaglio |
|---|---|---|
| `alembic upgrade 7dec24a98839` | FATTO | Indice `idx_matches_lookup` ora con `WHERE (perimeter <> 'other')`, 9.8 MB, copre 303399/303402 righe. Planner usa il nuovo indice su `perimeter='set11'`. |
| Token admin + systemd drop-in | FATTO | `openssl rand -hex 32` → `/etc/apptool.env` (0600 root). `/etc/systemd/system/lorcana-api.service.d/admin-token.conf` con `EnvironmentFile=-/etc/apptool.env`. `systemctl restart lorcana-api`. |
| Smoke test admin endpoint | FATTO | token valido → `200 {"status":"ok","reset":["legality_checkers","kc_legal_sets"]}`; senza token → 401; token sbagliato → 401. `refresh-dashboard` → `200 {"status":"ok","refreshed":"dashboard_blob"}`. |
| Crontab swap + canary | FATTO | Dom 04:45: `refresh_static_and_reset.sh` (era `static_importer` diretto). Canary `scripts/monitor_unmapped_matches.py` alle 07:05 UTC. Backup del crontab precedente in `/tmp/crontab_backup_1776843879.bak`. |

**Quick verify** (copia-incolla su VPS):
```bash
# alembic
venv/bin/alembic current       # deve stampare 7dec24a98839
# systemd admin token
sudo systemctl cat lorcana-api | grep EnvironmentFile
# endpoint
TOKEN=$(sudo grep APPTOOL_ADMIN_TOKEN /etc/apptool.env | cut -d= -f2)
curl -sS -X POST -H "X-Admin-Token: $TOKEN" http://127.0.0.1:8100/api/v1/admin/reset-legality-cache
# crontab
crontab -l | grep -E "refresh_static_and_reset|monitor_unmapped_matches"
```

---

## 9a. Azioni manuali originariamente pianificate (archivio)

1. **Apply partial index migration** (no-lock, concurrent):
   ```bash
   cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool
   venv/bin/alembic upgrade 7dec24a98839
   # NON usare `upgrade head` — lo step successivo (7894044b7dd3) e' la cassetto S0.5
   # e aborta senza SET12_RELEASE_DATE, che non vogliamo ancora settare.
   ```
   Post-apply: verificare `EXPLAIN ANALYZE SELECT ... WHERE perimeter='set11' AND ...` usi `idx_matches_lookup`.

2. **Install wrapper + cron + token** (per far sì che il cache-reset cross-process dopo `static_importer` funzioni sul serio):
   ```bash
   # a) genera token
   APPTOOL_ADMIN_TOKEN=$(openssl rand -hex 32)
   # b) salvalo in /etc/apptool.env (0600 root)
   echo "APPTOOL_ADMIN_TOKEN=$APPTOOL_ADMIN_TOKEN" | sudo tee -a /etc/apptool.env
   sudo chmod 0600 /etc/apptool.env
   # c) rilancia uvicorn caricando l'env (il token deve essere anche nel processo uvicorn)
   fuser -k 8100/tcp; export APPTOOL_ADMIN_TOKEN=$APPTOOL_ADMIN_TOKEN; \
       nohup venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8100 --workers 1 &
   # d) sostituisci la riga cron static_importer
   crontab -e
   # rimuovi: 45 4 * * 0 cd .../App_tool && venv/bin/python -m backend.workers.static_importer >> /var/log/lorcana-import.log 2>&1
   # aggiungi: 45 4 * * 0 cd .../App_tool && scripts/refresh_static_and_reset.sh >> /var/log/lorcana-import.log 2>&1
   ```

3. **Install canary cron** (`scripts/monitor_unmapped_matches.py`, 07:05 UTC):
   ```bash
   crontab -e
   # aggiungi:
   5 7 * * * cd /mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool && venv/bin/python scripts/monitor_unmapped_matches.py >> /var/log/lorcana-monitor.log 2>&1
   ```
   Il primo run è silenzioso per design (bootstrap state file). A partire dal secondo run, manda mail al primo folder mai visto (es. `SET12`).

4. **Al release-day Set 12** (S1), sequenza obbligatoria:
   ```bash
   # i. aggiornare SET_MAP se il 3-letter code non è ancora in SET_MAP
   export EXTRA_SET_CODE=<S12_CODE>
   # ii. applicare migration S0.5 con env puntati
   SET12_RELEASE_DATE=YYYY-MM-DD SET12_LEGAL_SETS=3,4,5,6,7,8,9,10,11,12 \
       venv/bin/alembic upgrade head
   # iii. refresh cards DB + reset cache cross-process
   APP_ROOT=/mnt/.../App_tool scripts/refresh_static_and_reset.sh
   # iv. flip default perimeter nel blob
   #     aggiungere APPTOOL_DEFAULT_CORE_PERIMETER=set12 a /etc/apptool.env, restart uvicorn
   # v. refresh dashboard blob
   curl -X POST -H "X-Admin-Token: $APPTOOL_ADMIN_TOKEN" \
        http://127.0.0.1:8100/api/v1/admin/refresh-dashboard
   ```

### S1 release-day
- [ ] **S1.1** — Applicare migration con `SET12_RELEASE_DATE` + `SET12_LEGAL_SETS`
- [ ] **S1.2** — Force refresh `static_importer.py` + verify cards S12 in PG (`SELECT COUNT(*) FROM cards WHERE set_code = '<S12>';`)
- [ ] **S1.3a** — Aggiungere `set12` + `friends_core_s12` + `core_overlap` a `PERIMETER_CONFIG`
- [ ] **S1.3b** — Parametrizzare `rogue_scout_service`, `tech_service`, `history_service`, `api/monitor.py` con `active_core_perimeter()`
- [ ] **S1.3c** — Setare env `APPTOOL_DEFAULT_CORE_PERIMETER=set12` + restart uvicorn
- [ ] **S1.3d** — Cache invalidation sequence: `reset-legality-cache` + `refresh-dashboard` via admin endpoint
- [ ] **S1.4** — Aggiungere picker S11/S12 in tab bar (Monitor/Coach/Lab)
- [ ] **S1 E2E smoke test**:
  - [ ] File JSON match S12 in `/mnt/.../matches/YYMMDD/SET12/` viene importato con `perimeter='set12'`, `game_format='core'`
  - [ ] `GET /api/v1/dashboard-data?refresh=true` contiene chiave `blob.set12.*`
  - [ ] `venv/bin/python -c "from pipelines.digest.generator import generate_digest; ..."` su matchup S12 ritorna digest non-None
  - [ ] Frontend Monitor tab con picker `set12` mostra Deck Fitness + Matchup Matrix
  - [ ] KC batch Mar 01:00 legge `current_epoch.legal_sets` → inclusi set12
- [ ] Aggiornare `docs/TODO.md` e `CLAUDE.md` con lo stato post-release

### S2 30gg dopo
- [ ] Rimuovere picker S11/S12 + localStorage key
- [ ] Rimuovere perimeter `core_overlap` da `PERIMETER_CONFIG`
- [ ] Aggiornare `ARCHITECTURE.md` §2 e `CLAUDE.md` con nuovo default
- [ ] Audit KC `is_current=false` su epoch Set11 settled

---

*Draft v3.1 2026-04-22 — S0 chiuso end-to-end (codice in repo + alembic applicata + systemd/crontab aggiornati). Valida fino all'annuncio ufficiale Set 12, poi aggiornare con data, rotation, code.*

---

## Appendix A — Review codex v0.118.0 (21/04/2026 pomeriggio)

Feedback integrati in v2:

| Finding | Severity | Dove risolto |
|---|---|---|
| `reset_checkers()` cross-process bug (static_importer ≠ uvicorn) | Alta | S0.3 riscritto con admin endpoint |
| Canary solo DB-level, miss silent drop | Alta | S0.2 riscritto filesystem-level (FS vs DB diff) |
| `pipelines/digest/generator.py:93` PERIMETERS hardcoded | Alta | §3 inventory + S0.1b |
| `backend/models/match.py:44` partial index IN-list | Media | §3 inventory + S0.6 nuova |
| `scripts/import_from_archive.py:75` hardcoded | Bassa | §3 inventory (S1.3) |
| `frontend_v3/.../monolith.js:151` hardcoded | N/A | §3 inventory marked out-of-scope |
| DATE granularity `meta_epochs` vs UTC release hour | Media | §2 caveat documentato |
| Cache dashboard 2h TTL invalidation post-cutover | Media | S0.3 + S1.3d admin endpoint |
| E2E smoke-test mancante | Media | §8 checklist esplicita |
| Overlap aggregate policy (S11+S12) non decisa | Media | S1.3 nuova sezione policy A/B/C |
| `legality_service.FORMAT_QUEUE_PREFIXES` non future-proof | Bassa | Già coperto da regex S0.1a (queue prefix check dinamico) |

Review tool: `codex exec` read-only, log completo in `/tmp/codex_review_set12.log`.

# Istruzioni Killer Curves — Compact

## Input
- **Digest**: contiene aggregati, loss profiles (fast/typical/slow), 18-21 example games compatte, cards_db pre-lookup.
- **Curve esistenti** (se aggiornamento): usa come base, aggiorna se i dati cambiano.
- NON leggere altri file. Tutto è nel digest.

## Come procedere

### Fase 1: Leggi il quadro
Dal digest identifica:
1. **Tipo matchup** da `avg_trend`: trend ~0 fino T4-T5 poi crollo = svolta; negativo da T1 = pressione
2. **Componente** da `component_primary`: draw = card advantage, board = wipe, lore = burst
3. **Carte chiave** da `card_examples`: top 10 per frequenza al turno critico
4. **Combo** da `combos`: coppie giocate insieme
5. **Alert** da `alert_losses`: CLOCK/RUSH/BURST/ENGINE/ATTRITO — guidano il tipo di risposta
6. **Lore speed**: se `reach_15` mostra 15L a T4-T5, questa è la Killer Curve #1 (lore rush)

### Fase 2: Loss Profiles
3 bucket: fast (≤p25), typical (p25-p75), slow (≥p75).
Per ogni bucket: count, causes, mechanics flags, wipe_rate, lore_t4, top_cards, 12 example_game_ids.

**Mechanics flags**: WIPE, RECURSION, RAMP_CHAIN, SYNERGY_BURST, HAND_STRIP, LORE_FLOOD.
- Flag ≥15% nel bucket → probabilmente merita curva dedicata
- Stesse carte ma risposte diverse → curve separate
- Stesse carte e stessa risposta → merge

### Fase 3: Ricostruisci curve dai game reali
Leggi le example_games nel digest. Per ogni profilo:
- Identifica sequenze turno per turno reali (carte, ink, lore)
- Costruisci worst case ink-fattibile combinando i pattern più frequenti

**Formato turno nel digest:**
`T4: [ink=8/5] | Cinderella - Dream Come True(4)+Clarabelle - Clumsy Guest(1)`
- `[ink=8/5]` = 8 ink disponibili (inkwell reale con ramp), 5 spesi questo turno
- `(4)` = ink_paid reale dal log (costo effettivo pagato)
- `(5S)` = Shift, ink_paid = shift_cost (non il full cost della carta)
- `(0♪)` = Song cantata, ink_paid = 0 (il singer paga exertandosi)
- `(0♪ST8)` = Sing Together 8 cantata, ink_paid = 0 (più characters si exertano, costi sommati >= 8)
- **REGOLA**: ink_cost nella tua sequence DEVE corrispondere al costo reale: card_db cost per play normale, shift_cost per shift, 0 per song cantata (normale o Sing Together). NON inventare costi ridotti.
- **REGOLA Sing Together**: se la Song ha "Sing Together N" nell'ability (es. Under the Sea, Sing Together 8), ink_cost = 0 e is_sung = true. Servono 1+ characters ready con SOMMA costi >= N. Tutti i singers si exertano. È DIVERSO dal singing normale (un solo singer con cost >= song cost).
- **REGOLA**: total_ink non può superare l'inkwell reale visibile nei game. Se le carte non ci stanno → riduci carte nel turno.

### Fase 4: Risposte
Per ogni curva, proponi risposta con carte del NOSTRO deck:
- **Proattivo**: kill/bounce/tuck la carta setup prima del turno critico
- **Reattivo**: riduci impatto (svuota mano vs draw engine, non popolare board vs wipe)
- **Punitivo**: lascia agire poi rimuovi (exerted → challengeable)

Verifica: Ward blocca "chosen" (serve challenge o "all opposing"). Evasive: solo Evasive sfida.

### Fase 5: Scrivi JSON

```json
{
  "metadata": {
    "our_deck": "<SIGLA>", "opp_deck": "<SIGLA>",
    "date": "<YYYY-MM-DD>",
    "based_on_games": N, "based_on_losses": N
  },
  "curves": [
    {
      "id": 1,
      "name": "Nome descrittivo",
      "type": "svolta|pressione",
      "frequency": {"loss_count": N, "total_loss": N, "pct": N},
      "critical_turn": {"turn": N, "component": "draw|board|lore", "swing": -N},
      "key_cards": ["carta1", "carta2"],
      "combo": ["carta1 [SHIFT]", "carta2 [SONG]", "carta3 [SING TOGETHER 8]"],
      "sequence": {
        "T1": {
          "plays": [
            {"card": "Nome Completo", "ink_cost": N, "role": "descrizione"}
          ],
          "total_ink": N, "lore_this_turn": N
        }
      },
      "impact": {"avg_draw": N, "avg_kill": N, "avg_bounce": N, "avg_lore_burst": N},
      "response": {
        "strategy": "piano tattico",
        "cards": ["nostra carta1", "nostra carta2"],
        "ink_required": N, "turn_needed": N
      },
      "example_game_ids": [N, N],
      "worst_case_validated": true,
      "validation": {
        "ink": "OK/FAIL — dettaglio turno per turno",
        "shift": "OK/N/A — base in board?",
        "song": "OK/N/A — singer cost >= song cost, oppure Sing Together: somma costi singers >= N?",
        "frequency": "vista in N/M loss"
      }
    }
  ]
}
```

### Checklist per turno
- [ ] Carta esiste nel cards_db del digest e nei colori avversario
- [ ] ink_cost = costo ESATTO dal cards_db: `cost` per play normale, `shift_cost` per shift, `0` per song cantata. MAI un valore diverso.
- [ ] total_ink = somma ink_cost del turno. Deve essere ≤ inkwell reale (vedi `[ink=N/S]` nei game example)
- [ ] Shift: base con STESSO NOME in board turno prima
- [ ] Song normale: singer ready (non exerted) con cost ≥ song cost. Singer si exerta.
- [ ] Sing Together N: 1+ characters ready, SOMMA costi >= N. Tutti si exertano. ink_cost = 0, is_sung = true. Es. Under the Sea (Sing Together 8): 3 characters con costi 3+3+2=8 bastano.
- [ ] SHIFT+SING SAME TURN: se shifti su base dry, il pezzo shiftato è ready e può cantare SUBITO. Metti shift + song nello STESSO turno (es. T5: shift Clarabelle + sing You're Welcome). NON splittarli su due turni.
- [ ] Max 4 copie per carta
- [ ] response.cards SOLO nei colori del NOSTRO deck

## Regole ferree
- NON cercare pattern — Python li ha già trovati. Leggi aggregates.
- NON inventare carte — tutto dal digest cards_db.
- Verifica ink e prerequisiti per ogni turno.
- Ragiona meccanicamente, non usare WR%.
- DB > log per ability scope.

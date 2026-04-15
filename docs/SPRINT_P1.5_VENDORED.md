# Sprint P1.5 - Vendored digest bridge freeze

Obiettivo: rimuovere il bridge runtime verso il tree analytics esterno per la
pipeline digest, senza riscrivere logica e senza cambiare output.

## Cosa fa P1.5

- congela `loader.py`, `gen_archive.py`, `investigate.py`, `cards_dict.py` dentro
  `pipelines/digest/vendored/`
- fa puntare `pipelines/digest/generator.py` solo ai moduli vendored
- aggiunge `scripts/diff_digest_vendored.py` per verificare parita' output
- lascia la logica invariata: i fix sono limitati a import path e packaging

## Criteri di uscita

- `rg -n "analisidef" pipelines/digest` -> zero match
- `python3 scripts/diff_digest_vendored.py --format core --limit 10` -> `DIFFS=0`
- smoke: `python3 scripts/generate_digests.py --format core --limit 3`

## Note operative

- La harness confronta lo stesso `generate_digest()` con due set di moduli:
  legacy esterno e vendored locale.
- `_provenance` viene ignorato nel confronto, il resto deve essere identico.
- Se una coppia produce `None` da entrambe le parti resta valida: il floor
  `min_games` e' parte del contratto del generator.

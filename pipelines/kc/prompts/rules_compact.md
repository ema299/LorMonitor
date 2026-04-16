# Lorcana Rules — Compact Reference

## Quest
- Only characters can quest. Character must be dry (in play since start of turn).
- To quest: exert character → gain lore equal to character's Lore value {L}.

## Challenge
- Only dry, ready characters can challenge. Target must be EXERTED opposing character.
- Challenger exerts → both deal damage equal to their STR to each other.
- If damage >= WILL → character is banished.
- Challenger +N: gains +N STR only while challenging (not when being challenged).

## Characters
- Must be dry to quest, challenge, or exert as cost. Dry = in play since beginning of turn.
- Drying = played this turn. Cannot quest/challenge/exert. Abilities still work.

## Actions & Songs
- Actions: played from hand, resolve effect, go to discard. Never enter play.
- Songs: actions with "Song" classification. Can be sung for free by exerting a character with ink cost >= song cost. Singer must be ready (dry).
- Sing Together N: exert 1+ characters whose total ink cost >= N to sing for free. All singers exert. DIFFERENT from normal singing: normal = 1 singer with cost >= song cost. Sing Together = sum of multiple singers' costs >= N. Example: Under the Sea (Sing Together 8) — exert 3 characters with costs 3+3+2=8. ink_cost = 0 (free).

## Shift
- Pay shift_cost (NOT ink_cost) to play on top of a character with SAME NAME already in play.
- Shifted character inherits state (dry/exerted/damage) from the character below.
- If shifted onto a dry character, the shifted character IS dry (can quest/challenge/SING immediately — same turn).
- SHIFT + SING SAME TURN: shift onto dry base → shifted character is ready → exert it to sing a song (if ink_cost >= song cost). Both plays go in the SAME turn entry. This is the strongest opening pattern — never split across two turns.
- Stack: when shifted character leaves play, all cards under it go to same zone.

## Keywords
- **Bodyguard**: may enter exerted. Opponents must challenge this character if able.
- **Challenger +N**: +N STR while challenging only.
- **Evasive**: can only be challenged by characters with Evasive.
- **Reckless**: can't quest. Must challenge each turn if able.
- **Resist +N**: damage dealt reduced by N. Stacks. If reduced to 0, no damage dealt.
- **Rush**: can challenge the turn it's played (doesn't need to be dry).
- **Support**: when this quests, may add its STR to another chosen character's STR this turn.
- **Ward**: opponents can't choose this card when resolving effects. Challenge still works. "All opposing" effects still work.
- **Vanish**: when chosen by opponent for action effect, banish this character.
- **Singer N**: counts as cost N for singing songs (not actual ink cost change).

## Damage
- Damage counters represent damage. "Put damage counter" ≠ "deal damage" (Resist doesn't apply to put).
- Character banished when damage >= WILL.

## Dual Ink
- Some cards have two colors (e.g., Into the Unknown is amethyst/sapphire).
- Dual ink cards can ONLY be included in decks that contain BOTH colors.
- Example: Into the Unknown (amethyst/sapphire) → only playable in Amethyst-Sapphire deck, NOT in Amber-Amethyst or Emerald-Sapphire.
- In the cards_db, dual ink cards have `"ink": "amethyst/sapphire"`, `"colors": ["amethyst", "sapphire"]`, `"dual_ink": true`.

## Ink
- Each turn: may add 1 card from hand to inkwell (if card has inkwell symbol).
- Turn N = N ink available (1 ink per card in inkwell, 1 added per turn).
- Ramp effects (e.g., Sail the Azurite Sea) add extra inkwell = +1 ink that turn and after.

/**
 * inkdecks.com Browser Export Script
 *
 * HOW TO USE:
 * 1. Open inkdecks.com in your browser (you're already logged in / past Cloudflare)
 * 2. Navigate to a deck page, e.g.:
 *    https://inkdecks.com/lorcana-metagame/deck-bluwu-steel-oppa-ghentgang-style-509544
 * 3. Open browser console (F12 → Console)
 * 4. Paste this entire script and press Enter
 * 5. It extracts the decklist and downloads a JSON file
 *
 * For BULK export from a metagame listing page:
 * 1. Go to https://inkdecks.com/lorcana-metagame/core
 * 2. Open console, paste the script, it finds all deck links and fetches each one
 */

(async function() {
  'use strict';

  // --- SINGLE DECK PAGE ---
  function extractDeckFromPage(doc, url) {
    const rows = doc.querySelectorAll('#decklist .card-list-item');
    if (!rows.length) return null;

    const cards = [];
    rows.forEach(row => {
      const qty = parseInt(row.dataset.quantity) || 0;
      const type = row.dataset.cardType || '';
      const link = row.querySelector('a');
      if (!link) return;
      // Card name: <b>Name -</b> Title  OR  <b>Name</b>
      const bold = link.querySelector('b');
      let name = link.textContent.trim().replace(/\s+/g, ' ');
      // Clean up whitespace around " - "
      name = name.replace(/\s*-\s*/g, ' - ').trim();

      // Ink color from img alt
      const inkImg = row.querySelector('td:nth-child(4) img');
      const ink = inkImg ? inkImg.alt : '';

      cards.push({ name, qty, type, ink });
    });

    // Deck metadata
    const title = doc.querySelector('.page-title')?.textContent?.trim() || '';
    const meta = doc.querySelector('.card-body .small')?.textContent?.trim() || '';

    // Extract player from title "DeckName by PlayerName"
    const byMatch = title.match(/by\s+(.+)$/i);
    const player = byMatch ? byMatch[1].trim() : '';
    const deckName = byMatch ? title.replace(/\s+by\s+.+$/i, '').trim() : title;

    // Extract rank and event
    const rankMatch = meta.match(/(\d+(?:st|nd|rd|th))\s+at\s+(.+?)(?:\s+\d+\s+players|\s+on\s+)/i);
    const rank = rankMatch ? rankMatch[1] : '';
    const event = rankMatch ? rankMatch[2].trim() : '';

    // Extract date
    const dateMatch = meta.match(/(\d{4}-\d{2}-\d{2})/);
    const date = dateMatch ? dateMatch[1] : '';

    // Extract inks from breadcrumb or card inks
    const inks = [...new Set(cards.map(c => c.ink).filter(Boolean))];

    return {
      name: deckName,
      player,
      rank,
      event,
      date,
      inks,
      url: url || window.location.href,
      cards,
      total_cards: cards.reduce((s, c) => s + c.qty, 0),
    };
  }

  // --- DETECT MODE ---
  const isListingPage = window.location.pathname.includes('/lorcana-metagame') &&
                        !window.location.pathname.includes('/deck-');
  const isDeckPage = document.querySelector('#decklist .card-list-item');

  if (isDeckPage) {
    // Single deck page
    const deck = extractDeckFromPage(document);
    if (deck) {
      console.log('Extracted deck:', deck.name, '-', deck.cards.length, 'unique cards,', deck.total_cards, 'total');
      const blob = new Blob([JSON.stringify(deck, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `inkdecks_deck_${deck.inks.join('-')}_${Date.now()}.json`;
      a.click();
      console.log('Downloaded!');
    } else {
      console.error('No decklist found on this page');
    }
    return;
  }

  if (isListingPage) {
    // Metagame listing page — find all deck links
    const deckLinks = [...document.querySelectorAll('a[href*="/lorcana-metagame/deck-"]')];
    const uniqueUrls = [...new Set(deckLinks.map(a => a.href))];
    console.log(`Found ${uniqueUrls.length} deck links. Fetching...`);

    const results = { fetched_at: new Date().toISOString(), archetypes: {} };
    let fetched = 0;
    let errors = 0;

    for (const url of uniqueUrls) {
      try {
        const resp = await fetch(url);
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const deck = extractDeckFromPage(doc, url);
        if (deck && deck.cards.length > 0) {
          // Group by ink combo
          const archKey = deck.inks.sort().join('-') || 'unknown';
          if (!results.archetypes[archKey]) results.archetypes[archKey] = [];
          results.archetypes[archKey].push(deck);
          fetched++;
          console.log(`[${fetched}/${uniqueUrls.length}] ${deck.inks.join('/')} - ${deck.player} (${deck.cards.length} cards)`);
        }
      } catch (e) {
        errors++;
        console.warn(`Error fetching ${url}:`, e.message);
      }
      // Small delay to avoid rate limiting
      await new Promise(r => setTimeout(r, 500));
    }

    console.log(`\nDone: ${fetched} decks fetched, ${errors} errors`);
    console.log('Archetypes:', Object.keys(results.archetypes).map(k => `${k}: ${results.archetypes[k].length}`).join(', '));

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `inkdecks_metagame_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    console.log('Downloaded!');
    return;
  }

  console.error('Not on an inkdecks deck page or metagame listing. Navigate to one of:\n' +
    '  - https://inkdecks.com/lorcana-metagame/core (bulk export)\n' +
    '  - https://inkdecks.com/lorcana-metagame/deck-... (single deck)');
})();

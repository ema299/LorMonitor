(function () {
  'use strict';

  const IA_BLUEPRINT = [
    {
      id: 'home',
      label: 'Home',
      summary: 'Sintesi operativa, briefing e ingresso del profilo nella nuova IA.',
      legacy: ['Home', 'Profile'],
      ownership: 'Command surface',
    },
    {
      id: 'play',
      label: 'Play',
      summary: 'Coach, piani matchup e superfici orientate alla decisione.',
      legacy: ['Coach', 'Play'],
      ownership: 'In-match decisions',
    },
    {
      id: 'meta',
      label: 'Meta',
      summary: 'Meta share, trend, matrix e lettura del field.',
      legacy: ['Dashboard', 'Meta'],
      ownership: 'Field reading',
    },
    {
      id: 'deck',
      label: 'Deck',
      summary: 'Consensus list, curve, confronto liste e tuning.',
      legacy: ['Deck'],
      ownership: 'Build quality',
    },
    {
      id: 'improve',
      label: 'Improve',
      summary: 'Tracking personale, review e coaching di crescita.',
      legacy: ['Improve'],
      ownership: 'Skill loop',
    },
    {
      id: 'pro',
      label: 'Pro Tools',
      summary: 'Analitiche dense e strumenti deep-work non esposti come prima superficie.',
      legacy: ['Pro Tools'],
      ownership: 'Deep analysis',
    },
    {
      id: 'community',
      label: 'Community',
      summary: 'Feed, creator, segnali sociali e superfici di scoperta.',
      legacy: ['Community'],
      ownership: 'Social layer',
    },
    {
      id: 'events',
      label: 'Events',
      summary: 'Tornei, calendario e momenti di attivazione nel mondo reale.',
      legacy: ['Events'],
      ownership: 'Calendar surface',
    },
  ];

  const FOUNDATIONS = [
    {
      title: 'Spazio separato',
      copy: 'La V3 vive in un workspace dedicato e non tocca il live.',
      status: 'locked',
    },
    {
      title: 'Nuova shell',
      copy: 'Topbar, nav, state e router isolati per iterare senza accoppiarsi al monolite.',
      status: 'ready',
    },
    {
      title: 'IA target',
      copy: 'Le otto superfici target sono gia mappate e leggibili.',
      status: 'ready',
    },
    {
      title: 'Wiring live',
      copy: 'Gli hook verso gli input reali restano previsti ma non ancora collegati in questa fase.',
      status: 'next',
    },
  ];

  const MIGRATION_TRACK = [
    {
      phase: 'V3-1',
      title: 'Baseline fedele del live',
      outcome: 'Portare gli stessi oggetti nel nuovo spazio senza cambiare il comportamento.',
      status: 'next',
    },
    {
      phase: 'V3-2',
      title: 'Isolamento tecnico',
      outcome: 'Separare bootstrap, asset e dipendenze operative quanto basta per lavorare sicuri.',
      status: 'active',
    },
    {
      phase: 'V3-3',
      title: 'Slim del monolite',
      outcome: 'Tagliare il debito strutturale senza perdere densita informativa.',
      status: 'next',
    },
    {
      phase: 'V3-4',
      title: 'Riposizionamento oggetti',
      outcome: 'Rimappare le superfici nella nuova IA dopo aver stabilizzato la base.',
      status: 'next',
    },
  ];

  window.V3 = window.V3 || {};
  window.V3.LiveAdapter = {
    IA_BLUEPRINT,
    FOUNDATIONS,
    MIGRATION_TRACK,
  };
})();

// Minimal UI i18n. Language: localStorage['lrcgen.lang'] (en / ko / de),
// otherwise the browser language, otherwise English.
// Usage: I18n.t('autosave.restored', { time: '12:00' })
(function () {
  const SUPPORTED = ['en', 'ko', 'de'];

  const MESSAGES = {
    'autosave.restored': {
      en: 'A newer autosave ({time}) was restored automatically.',
      ko: '더 최신 자동 저장본({time})을 자동으로 복원했습니다.',
      de: 'Neuerer Autosave-Stand ({time}) wurde automatisch wiederhergestellt.',
    },
    'autosave.time_recent': {
      en: 'just now',
      ko: '방금 전',
      de: 'vor kurzem',
    },
    'player.no_lyrics': {
      en: 'No lyrics available for this track.',
      ko: '이 트랙에는 가사가 없습니다.',
      de: 'Keine Lyrics für diesen Track vorhanden.',
    },
  };

  function detectLang() {
    let stored = '';
    try { stored = (localStorage.getItem('lrcgen.lang') || '').slice(0, 2).toLowerCase(); } catch (_) {}
    if (SUPPORTED.includes(stored)) return stored;
    const nav = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return SUPPORTED.includes(nav) ? nav : 'en';
  }

  const lang = detectLang();

  function t(key, vars) {
    const entry = MESSAGES[key];
    if (!entry) return key;
    let text = entry[lang] || entry.en;
    if (vars) for (const k in vars) text = text.split('{' + k + '}').join(String(vars[k]));
    return text;
  }

  window.I18n = { lang, t };
})();

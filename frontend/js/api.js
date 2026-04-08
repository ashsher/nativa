/**
 * api.js - Nativa API client module (IIFE pattern).
 *
 * Exposes window.Api with named methods for backend endpoints.
 * Requests include Telegram InitData auth headers accepted by AuthMiddleware.
 */

window.ApiError = class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
};

window.Api = (() => {
  const BASE = '/api';
  let _initData = '';

  function setInitData(d) {
    _initData = d || '';
  }

  function getActiveLanguageId() {
    const langs = window.currentUser && Array.isArray(window.currentUser.languages)
      ? window.currentUser.languages
      : [];
    if (langs.length > 0 && langs[0] && langs[0].language_id) {
      return langs[0].language_id;
    }
    return 1;
  }

  async function request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };

    if (_initData) {
      headers['X-Telegram-Init-Data'] = _initData;
      headers['Authorization'] = `Bearer ${_initData}`;
    }

    const options = { method, headers };
    if (body !== undefined) options.body = JSON.stringify(body);

    let res;
    try {
      res = await fetch(BASE + path, options);
    } catch (networkErr) {
      showToast("Tarmoq xatosi. Internetni tekshiring.", 'error');
      throw networkErr;
    }

    if (res.status === 429) {
      let quotaType = 'default';
      try {
        const errBody = await res.json();
        quotaType = errBody.quota_type || 'default';
      } catch (_) {}

      if (window.Payment) Payment.showUpgradeModal(quotaType);
      throw new window.ApiError('QUOTA', 'Kunlik limit tugadi');
    }

    if (res.status === 401) {
      showToast("Sessiya tugadi. Qayta kiring.", 'error');
      throw new window.ApiError('AUTH', 'Autentifikatsiya xatosi');
    }

    if (!res.ok) {
      showToast("Server xatosi. Keyinroq urinib ko'ring.", 'error');
      throw new window.ApiError('HTTP', `HTTP ${res.status}`);
    }

    if (res.status === 204) return null;
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return null;
    return res.json();
  }

  return {
    validateSession: (d) => {
      setInitData(d);
      return request('POST', '/auth/validate', { init_data: d });
    },

    getMe: () => request('GET', '/users/me'),
    updateMe: (data) => request('PUT', '/users/me', data),

    processVideo: (url, languageId = getActiveLanguageId()) =>
      request('POST', '/video/process', { url, language_id: languageId }),

    translate: (word, langCode = 'en') =>
      request(
        'GET',
        '/reading/translate?word=' + encodeURIComponent(word) + '&lang_code=' + encodeURIComponent(langCode)
      ),

    processReading: (payload, languageId = getActiveLanguageId()) => {
      const content = payload && payload.url
        ? payload.url
        : (payload && payload.text ? payload.text : '');
      return request('POST', '/reading/process', { content, language_id: languageId });
    },

    explainAI: (text, contextMode) =>
      request('POST', '/ai/explain', {
        text,
        context: `mode:${contextMode || 'reading'}`,
        language_code: 'en',
      }),

    getVocabulary: () => request('GET', '/vocabulary/'),
    addWord: (word, translation, exampleSentences = null, languageId = getActiveLanguageId()) =>
      request('POST', '/vocabulary/', {
        word,
        translation: translation || word,
        example_sentences: exampleSentences,
        language_id: languageId,
      }),
    deleteWord: (id) => request('DELETE', '/vocabulary/' + id),
    getReviewWords: () => request('GET', '/vocabulary/review'),
    submitRating: (id, rating) => request('POST', '/vocabulary/review', { vocab_id: id, rating }),

    getMatches: () => request('GET', '/speaking/matches'),
    connectSpeaker: (partnerUserId, languageId = getActiveLanguageId()) =>
      request('POST', '/speaking/connect', { partner_user_id: partnerUserId, language_id: languageId }),

    getPaymentStatus: () => request('GET', '/payment/status'),
    verifyPayment: (ref, starsAmount = 200) =>
      request('POST', '/payment/verify', { transaction_ref: ref, stars_amount: starsAmount }),

    request,
  };
})();

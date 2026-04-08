/**
 * api.js — Nativa API client module (IIFE pattern).
 *
 * Exposes window.Api with named methods for every backend endpoint.
 * All requests attach the Telegram InitData as a Bearer-style header
 * so the backend middleware can authenticate the caller.
 *
 * Error handling hierarchy:
 *   429 → quota exceeded  → Payment.showUpgradeModal()
 *   401 → session expired → showToast + redirect hint
 *   !ok → generic server error → showToast
 *   network → no connection    → showToast
 */

// Custom error class exposed globally so other modules can instanceof-check it.
window.ApiError = class ApiError extends Error {
  /**
   * @param {string} code — machine-readable error code ('QUOTA', 'AUTH', 'HTTP', 'NETWORK')
   * @param {string} message — human-readable description
   */
  constructor(code, message) {
    super(message);    // pass message to built-in Error
    this.code = code;  // machine-readable code for callers to branch on
  }
};

// Immediately-Invoked Function Expression keeps all internals private.
window.Api = (() => {
  // BASE URL for all API requests.
  // Using a relative path means the nginx proxy routes /api/* → backend:8000.
  const BASE = '/api';

  // _initData holds the raw Telegram.WebApp.initData string.
  // It is set once during app init via setInitData() and reused for every request.
  let _initData = '';

  /**
   * setInitData — store the Telegram initData string for use in Authorization headers.
   * Called by validateSession() immediately after the Telegram SDK is ready.
   * @param {string} d — raw initData query string from window.Telegram.WebApp.initData
   */
  function setInitData(d) {
    // Store the raw initData so every subsequent request can send it.
    _initData = d || '';
  }

  /**
   * request — private async HTTP helper.
   * Wraps fetch() with:
   *   - JSON serialisation of request body
   *   - Telegram InitData authentication header
   *   - Centralised error handling for 429 / 401 / generic HTTP / network errors
   *
   * @param {string} method — HTTP method ('GET', 'POST', 'PUT', 'DELETE')
   * @param {string} path   — endpoint path relative to BASE, e.g. '/auth/validate'
   * @param {object} [body] — optional request body; serialised to JSON
   * @returns {Promise<any>} — parsed JSON response body
   */
  async function request(method, path, body) {
    // Build headers; always send JSON content-type and Telegram auth.
    const headers = {
      'Content-Type': 'application/json',
      // Custom auth scheme recognised by the backend auth middleware.
      'Authorization': `TelegramInitData ${_initData}`,
    };

    // Build the fetch options object.
    const options = { method, headers };

    // Only attach a body for non-GET requests when body data is provided.
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }

    let res;
    try {
      // Perform the fetch. The URL is BASE + path, e.g. '/api/auth/validate'.
      res = await fetch(BASE + path, options);
    } catch (networkErr) {
      // Network-level failure (offline, DNS failure, CORS preflight error).
      // Show a user-visible toast then re-throw so the caller can handle it.
      showToast("Tarmoq xatosi. Internetni tekshiring.", 'error');
      throw networkErr;
    }

    // 429 Too Many Requests — the user has hit their daily quota.
    if (res.status === 429) {
      // Determine which quota type was exceeded from the response if possible.
      let quotaType = 'default';
      try {
        // Try to parse the quota type from the error detail field.
        const errBody = await res.json();
        quotaType = errBody.quota_type || 'default';
      } catch (_) {
        // If parsing fails, fall back to a generic message.
      }
      // Show the upgrade modal to prompt the user to get Premium.
      if (window.Payment) {
        Payment.showUpgradeModal(quotaType);
      }
      // Throw a typed error so callers can detect quota exhaustion.
      throw new window.ApiError('QUOTA', 'Kunlik limit tugadi');
    }

    // 401 Unauthorised — the Telegram InitData is invalid or expired.
    if (res.status === 401) {
      // Inform the user their session has expired and they need to reopen the app.
      showToast("Sessiya tugadi. Qayta kiring.", 'error');
      throw new window.ApiError('AUTH', 'Autentifikatsiya xatosi');
    }

    // Any other non-2xx status code is a generic server error.
    if (!res.ok) {
      showToast("Server xatosi. Keyinroq urinib ko'ring.", 'error');
      throw new window.ApiError('HTTP', `HTTP ${res.status}`);
    }

    // Parse and return the JSON response body.
    return res.json();
  }

  // ── Public API object ────────────────────────────────────────────────────
  // Each property is a named function corresponding to one backend endpoint.
  // All functions return Promises.

  return {

    /**
     * validateSession — validate Telegram InitData with the backend and
     * receive the current user object.
     * Also stores the initData so subsequent requests are authenticated.
     * @param {string} d — raw initData from Telegram.WebApp.initData
     */
    validateSession: (d) => {
      // Store initData before making the request so the auth header is set.
      setInitData(d);
      // POST the initData to the backend for HMAC validation.
      return request('POST', '/auth/validate', { init_data: d });
    },

    /**
     * getMe — fetch the full profile of the currently authenticated user.
     */
    getMe: () => request('GET', '/user/me'),

    /**
     * updateMe — update editable profile fields.
     * @param {object} data — { city, country, interests, hobbies }
     */
    updateMe: (data) => request('PUT', '/user/me', data),

    /**
     * processVideo — submit a YouTube URL for transcript extraction and tokenisation.
     * @param {string} url — full YouTube video URL
     */
    processVideo: (url) => request('POST', '/video/process', { youtube_url: url }),

    /**
     * translate — translate a single word.
     * Results are Redis-cached on the backend after the first call.
     * @param {string} w    — the word to translate
     * @param {string} lang — target language code, defaults to 'en'
     */
    translate: (w, lang) =>
      request('GET', '/translate?word=' + encodeURIComponent(w) + '&lang=' + (lang || 'en')),

    /**
     * processReading — submit an article URL or raw text for tokenisation.
     * @param {object} p — { url: string } or { text: string }
     */
    processReading: (p) => request('POST', '/reading/process', p),

    /**
     * explainAI — send selected text to Gemini 1.5 Flash for a grammar explanation.
     * @param {string} t — highlighted text selection
     * @param {string} m — context mode: 'video' or 'reading'
     */
    explainAI: (t, m) => request('POST', '/ai/explain', { highlighted_text: t, context_mode: m }),

    /**
     * getVocabulary — retrieve the user's full saved vocabulary deck.
     */
    getVocabulary: () => request('GET', '/vocabulary'),

    /**
     * addWord — add a new word to the user's vocabulary deck.
     * language_id: 1 = English (default target language).
     * @param {string} w — the word to add
     */
    addWord: (w) => request('POST', '/vocabulary', { word: w, language_id: 1 }),

    /**
     * deleteWord — remove a word from the deck by its database ID.
     * @param {number} id — vocabulary item ID
     */
    deleteWord: (id) => request('DELETE', '/vocabulary/' + id),

    /**
     * getReviewWords — get all vocabulary items due for review today (SM-2 schedule).
     */
    getReviewWords: () => request('GET', '/vocabulary/review'),

    /**
     * submitRating — record the user's SM-2 quality rating for a reviewed word.
     * @param {number} id — vocab item ID
     * @param {number} r  — quality rating 0..5
     */
    submitRating: (id, r) => request('POST', '/vocabulary/review', { vocab_id: id, rating: r }),

    /**
     * getMatches — get recommended speaking partner profiles.
     * Matches are ranked by Jaccard similarity of shared interests.
     */
    getMatches: () => request('GET', '/speaking/matches'),

    /**
     * connectSpeaker — initiate a speaking match with another user.
     * Returns { telegram_deep_link } for Telegram.WebApp.openTelegramLink().
     * @param {number} id — target user's database user_id
     */
    connectSpeaker: (id) => request('POST', '/speaking/connect', { target_user_id: id }),

    /**
     * getPaymentStatus — check whether the current user has an active premium subscription.
     */
    getPaymentStatus: () => request('GET', '/payment/status'),

    /**
     * verifyPayment — verify a completed Telegram Stars payment and activate premium.
     * @param {string} ref — transaction reference / charge ID
     */
    verifyPayment: (ref) => request('POST', '/payment/verify', { transaction_ref: ref }),

    /**
     * getRecommended — fetch the curated list of beginner-friendly content.
     * Populated by the 0002 Alembic migration seed data.
     */
    getRecommended: () => request('GET', '/content/recommended'),

    /**
     * request — expose the private request function so payment.js can call
     * /payment/create-invoice directly (which has no dedicated named method).
     * @param {string} method
     * @param {string} path
     * @param {object} [body]
     */
    request,
  };
})();

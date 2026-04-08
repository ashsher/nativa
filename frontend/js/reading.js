/**
 * reading.js — Reading mode module.
 *
 * Handles:
 *   1. Pill toggle between URL and text paste input modes.
 *   2. Submitting the article to the backend for tokenisation.
 *   3. Rendering tokenised paragraphs with clickable word tokens.
 *   4. Word count and estimated reading time in the header.
 *   5. Text selection → floating AI button → AiPopup.show().
 *   6. Back button to return to the input state.
 */

/**
 * renderReadingView — called by app.js onTabActivated('reading').
 * Wires all form controls. Idempotent via _wired flag.
 */
function renderReadingView() {
  // Guard: only wire events once to prevent duplicate listeners.
  if (renderReadingView._wired) return;
  renderReadingView._wired = true;

  // ── Pill toggle buttons ────────────────────────────────────────────────
  // "Havola" pill: switch to URL input mode.
  const urlPill  = document.getElementById('reading-tab-url');
  // "Matn" pill: switch to raw text paste mode.
  const textPill = document.getElementById('reading-tab-text');

  if (urlPill) {
    urlPill.addEventListener('click', () => {
      // Activate the URL input group, hide the text input group.
      setReadingMode('url');
    });
  }

  if (textPill) {
    textPill.addEventListener('click', () => {
      // Activate the text input group, hide the URL input group.
      setReadingMode('text');
    });
  }

  // ── Submit button ─────────────────────────────────────────────────────
  const submitBtn = document.getElementById('reading-submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', submitReading);
  }

  // ── Back button (inside article state) ────────────────────────────────
  const backBtn = document.getElementById('reading-back-btn');
  if (backBtn) {
    backBtn.addEventListener('click', showReadingInputState);
  }

  // ── Text selection AI handler ──────────────────────────────────────────
  wireReadingSelectionHandler();
}

/**
 * setReadingMode — toggle between 'url' and 'text' input modes.
 * Updates the active pill button and shows/hides the correct input group.
 *
 * @param {'url'|'text'} mode — the mode to activate
 */
function setReadingMode(mode) {
  // Input groups for URL and text.
  const urlGroup  = document.getElementById('reading-url-input-group');
  const textGroup = document.getElementById('reading-text-input-group');
  // Pill buttons.
  const urlPill   = document.getElementById('reading-tab-url');
  const textPill  = document.getElementById('reading-tab-text');

  if (mode === 'url') {
    // Show URL input, hide text area.
    if (urlGroup)  urlGroup.style.display  = 'block';
    if (textGroup) textGroup.style.display = 'none';
    // Mark URL pill as active, remove from text pill.
    if (urlPill)  urlPill.classList.add('pill-toggle__btn--active');
    if (textPill) textPill.classList.remove('pill-toggle__btn--active');
  } else {
    // Show text area, hide URL input.
    if (urlGroup)  urlGroup.style.display  = 'none';
    if (textGroup) textGroup.style.display = 'block';
    // Mark text pill as active.
    if (textPill) textPill.classList.add('pill-toggle__btn--active');
    if (urlPill)  urlPill.classList.remove('pill-toggle__btn--active');
  }
}

/**
 * submitReading — collect input, call the backend, and render the article.
 */
async function submitReading() {
  // Determine which mode is active by checking which pill has the active class.
  const urlPill = document.getElementById('reading-tab-url');
  const isUrlMode = urlPill && urlPill.classList.contains('pill-toggle__btn--active');

  // Build the request payload based on the active input mode.
  let payload;
  if (isUrlMode) {
    // URL mode: read from the URL input field.
    const url = document.getElementById('reading-url-input').value.trim();
    if (!url) {
      showToast("Iltimos, havola kiriting.", 'error');
      return;
    }
    payload = { url };
  } else {
    // Text mode: read from the textarea.
    const text = document.getElementById('reading-text-input').value.trim();
    if (!text) {
      showToast("Iltimos, matn kiriting.", 'error');
      return;
    }
    payload = { text };
  }

  // Show loading skeleton while the backend processes the article.
  showReadingLoadingSkeleton();

  let data;
  try {
    // Send the article payload to the backend for tokenisation.
    data = await Api.processReading(payload);
  } catch (e) {
    // api.js has already shown an error toast; restore input state.
    showReadingInputState();
    return;
  }

  // Hide the input state, reveal the article state.
  const inputState   = document.querySelector('.reading-input-state');
  const articleState = document.getElementById('reading-article-state');
  if (inputState)   inputState.style.display   = 'none';
  if (articleState) articleState.style.display = 'block';

  // Calculate and display word count + estimated reading time.
  const wordCount = data.word_count || 0;
  // Average reading speed: 200 words per minute; ceil to avoid "0 minutes".
  const minutes   = Math.ceil(wordCount / 200);
  const statsEl   = document.getElementById('reading-stats');
  if (statsEl) {
    statsEl.textContent = `${wordCount} so'z | ~${minutes} daqiqa`;
  }

  // Render the tokenised article content.
  renderArticle(data);
}

/**
 * renderArticle — build the article DOM from the backend response.
 * Each paragraph becomes a <p class="paragraph"> with word token spans.
 *
 * @param {object} data — backend response with data.paragraphs array
 */
function renderArticle(data) {
  // Get the article container.
  const container = document.getElementById('article-container');
  if (!container) return;

  // Clear any previous article content.
  container.innerHTML = '';

  // Build a fragment for efficient DOM insertion.
  const frag = document.createDocumentFragment();

  // Each element in paragraphs is an array of token objects.
  const paragraphs = data.paragraphs || [];
  paragraphs.forEach(tokens => {
    // Create a paragraph element.
    const p = document.createElement('p');
    p.className = 'paragraph';

    // Build each word token within the paragraph.
    (tokens || []).forEach(tok => {
      // Create a clickable word span.
      const span = document.createElement('span');
      span.className    = 'word-token';
      span.textContent  = tok.display || tok.word; // displayed text (may have punctuation)
      span.dataset.word = tok.word;                 // clean word for translation

      // Clicking a word token opens the translation popup.
      span.addEventListener('click', () => {
        if (window.Popup) Popup.show(span);
      });

      p.appendChild(span);
      // Preserve a space between tokens for readability.
      p.appendChild(document.createTextNode(' '));
    });

    frag.appendChild(p);
  });

  // Mount all paragraphs to the DOM.
  container.appendChild(frag);
}

/**
 * showReadingInputState — restore the input form and hide the article state.
 * Called by the back button click handler.
 */
function showReadingInputState() {
  // Show the input form.
  const inputState = document.querySelector('.reading-input-state');
  if (inputState) inputState.style.display = 'block';

  // Hide the article reading state.
  const articleState = document.getElementById('reading-article-state');
  if (articleState) articleState.style.display = 'none';

  // Clear the article container so stale content doesn't flash next time.
  const container = document.getElementById('article-container');
  if (container) container.innerHTML = '';
}

/**
 * showReadingLoadingSkeleton — replace article container with skeleton lines
 * while the backend processes the article.
 */
function showReadingLoadingSkeleton() {
  // Switch to article state to show the skeleton in the right container.
  const inputState   = document.querySelector('.reading-input-state');
  const articleState = document.getElementById('reading-article-state');
  if (inputState)   inputState.style.display   = 'none';
  if (articleState) articleState.style.display = 'block';

  // Build skeleton lines of varying widths to simulate paragraph text.
  const container = document.getElementById('article-container');
  if (!container) return;
  let html = '';
  const lineWidths = ['100%','95%','90%','80%','100%','85%','70%','100%','92%','60%'];
  lineWidths.forEach(w => {
    html += `<div class="skeleton" style="height:16px;width:${w};margin-bottom:10px;"></div>`;
  });
  container.innerHTML = html;
}

/**
 * wireReadingSelectionHandler — listen for text selection inside the article
 * container and show the floating AI button for grammar explanations.
 * Mirrors the same logic in video.js but scoped to the article container.
 */
function wireReadingSelectionHandler() {
  // Listen globally; filter to article container.
  document.addEventListener('selectionchange', () => {
    const sel = window.getSelection();
    // If nothing is selected, hide the AI float button.
    if (!sel || sel.isCollapsed || sel.toString().trim().length === 0) {
      const floatBtn = document.getElementById('ai-float-btn');
      if (floatBtn) floatBtn.style.display = 'none';
      return;
    }

    // Check if the selection is inside the article container.
    const range     = sel.getRangeAt(0);
    const container = document.getElementById('article-container');
    if (!container || !container.contains(range.commonAncestorContainer)) {
      return; // selection is outside article; don't interfere
    }

    // Position the floating AI button near the selection.
    const rect = range.getBoundingClientRect();
    const btn  = document.getElementById('ai-float-btn');
    if (!btn) return;

    // Show button just above the selection.
    btn.style.display  = 'block';
    btn.style.position = 'fixed';
    btn.style.top      = (rect.top  - 40 + window.scrollY) + 'px';
    btn.style.left     = (rect.left + window.scrollX)       + 'px';

    // Replace click handler each time to capture the current selection text.
    btn.onclick = () => {
      const selectedText = sel.toString().trim();
      // Open AI popup in 'reading' context.
      if (window.AiPopup) AiPopup.show(selectedText, 'reading');
      // Hide the floating button immediately.
      btn.style.display = 'none';
    };
  });
}

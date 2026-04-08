/**
 * popup.js — Word translation popup module (IIFE pattern).
 *
 * Shows a bottom-sheet popup when a word token is tapped.
 * Features:
 *   - Instant skeleton rendering for perceived performance.
 *   - Fetches translation + examples + pronunciation URL from backend.
 *   - Audio playback via Web Audio API.
 *   - Save word to vocabulary deck.
 *   - Close via X button or backdrop tap.
 */

const Popup = (() => {
  // The word currently displayed in the popup.
  let currentWord = null;

  // The currently playing Audio instance (if any); stored to allow pause on close.
  let currentAudio = null;

  /**
   * show — display the popup for the given word token element.
   * Shows a skeleton immediately, then fetches the translation data.
   *
   * @param {HTMLElement} wordElement — the .word-token span that was clicked
   */
  async function show(wordElement) {
    // Extract the clean word from the data-word attribute of the clicked span.
    currentWord = wordElement.dataset.word || wordElement.textContent.trim();

    // Show the skeleton immediately so the popup appears instantly (perceived performance).
    renderSkeleton();

    // Make the popup visible by removing the hidden class.
    document.getElementById('word-popup').classList.remove('popup--hidden');
    // Show the semi-transparent backdrop behind the popup.
    document.getElementById('popup-backdrop').classList.remove('popup-backdrop--hidden');

    try {
      // Fetch translation data from the backend (Redis-cached after first call).
      const data = await Api.translate(currentWord);
      // Render the actual translation content replacing the skeleton.
      renderContent(data);
    } catch (e) {
      // If the API call fails, show a graceful fallback state instead of crashing.
      // api.js already showed a toast; here we update the popup content.
      document.getElementById('popup-word').textContent        = currentWord;
      document.getElementById('popup-translation').textContent = 'Tarjima topilmadi';
      // Clear the examples skeleton.
      document.getElementById('popup-examples').innerHTML = '';
    }
  }

  /**
   * hide — close the popup and stop any playing audio.
   */
  function hide() {
    // Add back the hidden class to slide the popup off-screen.
    document.getElementById('word-popup').classList.add('popup--hidden');
    // Hide the backdrop.
    document.getElementById('popup-backdrop').classList.add('popup-backdrop--hidden');
    // Stop and discard any playing audio to avoid background noise after closing.
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
  }

  /**
   * renderSkeleton — fill the popup content areas with animated skeleton
   * placeholder elements while the translation data is loading.
   */
  function renderSkeleton() {
    // Large skeleton for the word heading (Syne font, ~32px).
    document.getElementById('popup-word').innerHTML =
      '<div class="skeleton" style="height:32px;width:120px"></div>';

    // Medium skeleton for the translation line.
    document.getElementById('popup-translation').innerHTML =
      '<div class="skeleton" style="height:20px;width:180px"></div>';

    // Two skeleton lines for the example sentences section.
    document.getElementById('popup-examples').innerHTML =
      '<div class="skeleton" style="height:16px;width:100%;margin-top:8px"></div>' +
      '<div class="skeleton" style="height:16px;width:80%;margin-top:6px"></div>';
  }

  /**
   * renderContent — replace the skeleton with real translation data.
   *
   * @param {object} data — backend response:
   *   { word, translation, pronunciation_url, examples: [{sentence, translation}] }
   */
  function renderContent(data) {
    // Render the word in the popup heading.
    // CSS applies --font-display (Syne) to .popup__word automatically.
    document.getElementById('popup-word').textContent = data.word || currentWord;

    // Render the translation below the word.
    document.getElementById('popup-translation').textContent = data.translation || '';

    // Wire the audio button if a pronunciation URL was returned.
    if (data.pronunciation_url) {
      const audioBtn = document.getElementById('popup-audio-btn');
      // Replace any previous click handler with a new one for this word.
      audioBtn.onclick = () => {
        // Stop any currently playing audio before starting a new one.
        if (currentAudio) currentAudio.pause();
        // Create a new Audio object with the TTS MP3 URL from Cloudflare R2.
        currentAudio = new Audio(data.pronunciation_url);
        // Start playback immediately.
        currentAudio.play();
      };
    }

    // Render up to 3 example sentences in the examples section.
    const examplesEl = document.getElementById('popup-examples');
    examplesEl.innerHTML = ''; // clear skeleton

    if (data.examples && data.examples.length > 0) {
      // Limit to 3 examples to keep the popup compact.
      data.examples.slice(0, 3).forEach(ex => {
        // Create a container div for each example sentence + translation pair.
        const div = document.createElement('div');
        div.className = 'popup__example';
        // Sentence in English; translation in Uzbek below it.
        div.innerHTML =
          `<p class="popup__example-sentence">${ex.sentence}</p>` +
          `<p class="popup__example-translation">${ex.translation}</p>`;
        examplesEl.appendChild(div);
      });
    }

    // Wire the Save button to add this word to the vocabulary deck.
    document.getElementById('popup-save-btn').onclick = () => {
      handleSave(data.word || currentWord);
    };
  }

  /**
   * handleSave — add the word to the vocabulary deck via the API.
   * Updates the save button with visual feedback on success.
   *
   * @param {string} word — the word to save
   */
  async function handleSave(word) {
    const btn = document.getElementById('popup-save-btn');
    try {
      // Call the backend to add the word to the user's vocabulary deck.
      await Api.addWord(word);

      // Visually confirm the save: change button text and apply the savePop animation.
      btn.textContent = '✓ Saqlandi';
      btn.classList.add('btn--saved'); // triggers CSS savePop + green background

      // After 2 seconds, revert the button to its original state.
      setTimeout(() => {
        btn.textContent = '📚 Saqlash';
        btn.classList.remove('btn--saved');
      }, 2000);
    } catch (e) {
      // Error handling (quota modal or toast) is done by api.js; nothing to do here.
    }
  }

  // ── DOMContentLoaded: wire close controls ───────────────────────────────
  // Close button and backdrop are wired once the DOM is ready.
  document.addEventListener('DOMContentLoaded', () => {
    // Close button inside the popup panel.
    document.getElementById('popup-close-btn').addEventListener('click', hide);
    // Backdrop click (outside the popup) also closes it.
    document.getElementById('popup-backdrop').addEventListener('click', hide);
  });

  // Expose only show() and hide() to the outside world.
  return { show, hide };
})();

// Assign to window so other modules (video.js, reading.js) can call Popup.show().
window.Popup = Popup;

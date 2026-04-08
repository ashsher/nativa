/**
 * ai_popup.js — AI Grammar Explanation popup module (IIFE pattern).
 *
 * Shows a bottom-sheet popup with a Gemini 1.5 Flash grammar explanation
 * for the user-selected text. Features a typewriter word-by-word animation
 * so the response feels like it is being written in real-time.
 */

const AiPopup = (() => {
  // Handle for the typewriter setInterval; stored so we can cancel it on close.
  let typewriterTimer = null;

  /**
   * show — display the AI popup for the selected text.
   * Shows the loading spinner immediately, then streams the Gemini response
   * as a typewriter animation once received.
   *
   * @param {string} selectedText — the text the user highlighted
   * @param {string} contextMode  — 'video' or 'reading' (passed to backend for context)
   */
  async function show(selectedText, contextMode) {
    // Display the selected text as a blockquote so the user knows what was analysed.
    document.getElementById('ai-popup-quote').textContent = '"' + selectedText + '"';

    // Clear any previous response text from the last usage.
    document.getElementById('ai-response').textContent = '';

    // Show the loading spinner while we wait for the Gemini API response.
    document.getElementById('ai-loading').style.display = 'flex';

    // Make the AI popup visible by removing the hidden class.
    document.getElementById('ai-popup').classList.remove('popup--hidden');

    // Show the backdrop behind the AI popup.
    document.getElementById('ai-popup-backdrop').classList.remove('popup-backdrop--hidden');

    try {
      // Call the backend AI explain endpoint.
      // The backend calls Gemini 1.5 Flash with the selected text and context mode.
      const data = await Api.explainAI(selectedText, contextMode);

      // Hide the loading spinner once the response arrives.
      document.getElementById('ai-loading').style.display = 'none';

      // Start the typewriter animation with the explanation text.
      // data.explanation is the primary field; data.response is a fallback alias.
      typewriterEffect(
        data.explanation || data.response || '',
        document.getElementById('ai-response')
      );
    } catch (e) {
      // Hide spinner on error (api.js already showed a toast).
      document.getElementById('ai-loading').style.display = 'none';
      // Show a localised error message in the response area.
      document.getElementById('ai-response').textContent = 'Javob olishda xatolik yuz berdi.';
    }
  }

  /**
   * hide — close the AI popup, stop the typewriter, and clean up the selection.
   */
  function hide() {
    // Add back the hidden class to dismiss the popup.
    document.getElementById('ai-popup').classList.add('popup--hidden');

    // Hide the backdrop.
    document.getElementById('ai-popup-backdrop').classList.add('popup-backdrop--hidden');

    // Stop the typewriter animation if it is still running.
    if (typewriterTimer) {
      clearInterval(typewriterTimer);
      typewriterTimer = null;
    }

    // Also hide the floating AI button if it is still visible.
    const floatBtn = document.getElementById('ai-float-btn');
    if (floatBtn) floatBtn.style.display = 'none';

    // Clear the text selection so the UI is clean after dismissing.
    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
  }

  /**
   * typewriterEffect — animate text into a target element word-by-word.
   * Splits the text on spaces and appends one word every 30ms, creating
   * a reading-paced typewriter effect that feels like the AI is writing.
   *
   * @param {string}      text — the full explanation text to animate
   * @param {HTMLElement} el   — the DOM element to write into
   */
  function typewriterEffect(text, el) {
    // Split the full text into individual words, filtering out empty strings
    // that result from consecutive spaces.
    const words = text.split(' ').filter(w => w.length > 0);

    // Word index counter; starts at 0 (first word).
    let i = 0;

    // Clear any existing text in the target element.
    el.textContent = '';

    // Start an interval that appends one word every 30ms.
    typewriterTimer = setInterval(() => {
      if (i < words.length) {
        // Append the next word with a space before it (except the very first word).
        el.textContent += (i > 0 ? ' ' : '') + words[i];
        i++; // advance the word pointer
      } else {
        // All words have been displayed — stop the interval to free resources.
        clearInterval(typewriterTimer);
        typewriterTimer = null;
      }
    }, 30); // 30ms per word ≈ comfortable reading pace typewriter effect
  }

  // ── DOMContentLoaded: wire close controls ──────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    // Close button inside the AI popup panel.
    document.getElementById('ai-popup-close-btn').addEventListener('click', hide);
    // Backdrop click also closes the AI popup.
    document.getElementById('ai-popup-backdrop').addEventListener('click', hide);
  });

  // Expose show() and hide() publicly.
  return { show, hide };
})();

// Assign to window so video.js and reading.js can call AiPopup.show().
window.AiPopup = AiPopup;

/**
 * ai_popup.js — AI Grammar Explanation popup module (IIFE pattern).
 *
 * Shows a bottom-sheet popup with a Gemini grammar explanation for the
 * user-selected text. The response is parsed from markdown and rendered
 * as styled HTML with a smooth fade-in animation.
 */

const AiPopup = (() => {
  // ── Inline markdown → HTML parser ────────────────────────────────────────

  /**
   * parseInline — convert inline markdown spans to HTML.
   * Handles: **bold**, *italic*, `code`.
   */
  function parseInline(text) {
    return text
      // Bold: **text**
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // Italic: *text* (only single asterisk now that bold is consumed)
      .replace(/\*([^*]+?)\*/g, '<em>$1</em>')
      // Inline code: `text`
      .replace(/`([^`]+?)`/g, '<code class="ai-code">$1</code>');
  }

  /**
   * parseMarkdown — convert a markdown string to an HTML string.
   *
   * Supported syntax:
   *   ## Heading 2   → <h4 class="ai-heading">
   *   ### Heading 3  → <h5 class="ai-heading">
   *   - item         → <ul><li>…</li></ul>
   *   1. item        → <ol><li>…</li></ol>
   *   blank line     → paragraph break
   *   other text     → <p>…</p>
   */
  function parseMarkdown(text) {
    const lines = text.split('\n');
    let html = '';
    let listType = null;   // 'ul' | 'ol' | null

    const closeList = () => {
      if (listType) {
        html += `</${listType}>`;
        listType = null;
      }
    };

    for (const raw of lines) {
      const line = raw.trimEnd();

      // --- Unordered list item: "- text" or "• text" or "* text" ---
      const ulMatch = line.match(/^[\-\*\•]\s+(.+)/);
      if (ulMatch) {
        if (listType !== 'ul') { closeList(); html += '<ul class="ai-list">'; listType = 'ul'; }
        html += `<li>${parseInline(ulMatch[1])}</li>`;
        continue;
      }

      // --- Ordered list item: "1. text" ---
      const olMatch = line.match(/^\d+\.\s+(.+)/);
      if (olMatch) {
        if (listType !== 'ol') { closeList(); html += '<ol class="ai-list">'; listType = 'ol'; }
        html += `<li>${parseInline(olMatch[1])}</li>`;
        continue;
      }

      // For non-list lines, close any open list.
      closeList();

      // --- Heading level 2: "## text" ---
      const h2Match = line.match(/^##\s+(.+)/);
      if (h2Match) {
        html += `<h4 class="ai-heading">${parseInline(h2Match[1])}</h4>`;
        continue;
      }

      // --- Heading level 3: "### text" ---
      const h3Match = line.match(/^###\s+(.+)/);
      if (h3Match) {
        html += `<h5 class="ai-heading ai-heading--sm">${parseInline(h3Match[1])}</h5>`;
        continue;
      }

      // --- Heading level 1: "# text" ---
      const h1Match = line.match(/^#\s+(.+)/);
      if (h1Match) {
        html += `<h3 class="ai-heading ai-heading--lg">${parseInline(h1Match[1])}</h3>`;
        continue;
      }

      // --- Blank line → skip (implicit paragraph spacing via CSS gap) ---
      if (line.trim() === '') continue;

      // --- Normal paragraph ---
      html += `<p class="ai-para">${parseInline(line)}</p>`;
    }

    closeList();
    return html;
  }

  // ── Render with fade-in ───────────────────────────────────────────────────

  /**
   * renderResponse — parse markdown and display the AI response with a
   * subtle fade-in + slide-up animation.
   *
   * @param {string}      text — raw markdown text from Gemini
   * @param {HTMLElement} el   — target DOM element (#ai-response)
   */
  function renderResponse(text, el) {
    el.innerHTML = parseMarkdown(text || '');

    // Reset and trigger CSS animation
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    el.style.transition = 'none';

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transition = 'opacity 380ms ease, transform 380ms ease';
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      });
    });
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /**
   * show — display the AI popup for the selected text.
   *
   * @param {string} selectedText — the text the user highlighted
   * @param {string} contextMode  — 'video' or 'reading'
   */
  async function show(selectedText, contextMode) {
    // Display the quoted text
    document.getElementById('ai-popup-quote').textContent = '\u201c' + selectedText + '\u201d';

    // Clear previous response
    const responseEl = document.getElementById('ai-response');
    responseEl.innerHTML = '';
    responseEl.style.opacity = '0';

    // Show loading spinner
    document.getElementById('ai-loading').style.display = 'flex';

    // Reveal the popup
    document.getElementById('ai-popup').classList.remove('popup--hidden');
    document.getElementById('ai-popup-backdrop').classList.remove('popup-backdrop--hidden');

    try {
      const data = await Api.explainAI(selectedText, contextMode);

      document.getElementById('ai-loading').style.display = 'none';

      renderResponse(
        data.explanation || data.response || '',
        responseEl
      );
    } catch (e) {
      document.getElementById('ai-loading').style.display = 'none';
      responseEl.innerHTML = '<p class="ai-para ai-para--error">Javob olishda xatolik yuz berdi.</p>';
      responseEl.style.opacity = '1';
    }
  }

  /**
   * hide — close the AI popup and clean up.
   */
  function hide() {
    document.getElementById('ai-popup').classList.add('popup--hidden');
    document.getElementById('ai-popup-backdrop').classList.add('popup-backdrop--hidden');

    const floatBtn = document.getElementById('ai-float-btn');
    if (floatBtn) floatBtn.style.display = 'none';

    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
  }

  // ── Wire close controls on DOM ready ─────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('ai-popup-close-btn').addEventListener('click', hide);
    document.getElementById('ai-popup-backdrop').addEventListener('click', hide);
  });

  return { show, hide };
})();

window.AiPopup = AiPopup;

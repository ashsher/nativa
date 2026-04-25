/**
 * video.js — Video mode module.
 *
 * Handles:
 *   1. YouTube URL input form wiring.
 *   2. Dynamic loading of the YouTube IFrame API.
 *   3. Processing the video URL via the backend (transcript + tokenisation).
 *   4. Rendering clickable subtitle segments with word tokens.
 *   5. Subtitle sync loop (500ms polling) with active segment highlighting.
 *   6. Auto-pause feature that pauses playback at the end of each segment.
 *   7. Text selection → floating AI button → AiPopup.show().
 */

// ── Module-level state ──────────────────────────────────────────────────────
// Reference to the YT.Player instance once the IFrame API is ready.
let _ytPlayer = null;

// Whether auto-pause mode is currently enabled.
// Reads the user's saved preference from localStorage (set via Settings).
let _autopauseEnabled = localStorage.getItem('nativa_autopause') === '1';

// The subtitle segments array returned by the backend.
// Each segment: { start, duration, tokens: [{ word, display }] }
let _segments = [];

// setInterval handle for the subtitle sync loop; cleared on cleanup.
let _syncInterval = null;

// Index of the most recently highlighted segment (for efficiency).
let _lastActiveIdx = -1;

/**
 * renderVideoView — called by app.js onTabActivated('video').
 * Wires the URL input form events. This function is idempotent;
 * calling it multiple times on repeated tab visits is safe because
 * we use a flag to prevent double-binding.
 */
function renderVideoView() {
  // Guard: only wire events once to prevent duplicate listeners.
  if (renderVideoView._wired) return;
  renderVideoView._wired = true;

  // Wire the submit button click handler.
  const submitBtn = document.getElementById('video-submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', () => {
      // Read the URL from the input field and trim whitespace.
      const url = document.getElementById('video-url-input').value.trim();
      submitVideoURL(url); // hand off to the main processing function
    });
  }

  // Also allow submitting by pressing Enter in the URL input field.
  const urlInput = document.getElementById('video-url-input');
  if (urlInput) {
    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        submitVideoURL(urlInput.value.trim());
      }
    });
  }

  // Wire the auto-pause toggle button and sync its label to the saved state.
  const autopauseBtn = document.getElementById('autopause-toggle');
  if (autopauseBtn) {
    autopauseBtn.textContent = _autopauseEnabled ? "Avtopauza: Yoq" : "Avtopauza: O'ch";
    autopauseBtn.addEventListener('click', toggleAutopause);
  }

  // Wire the back button to return to the URL input state.
  const backBtn = document.getElementById('video-back-btn');
  if (backBtn) {
    backBtn.addEventListener('click', showVideoInputState);
  }

  // Wire text-selection AI button.
  wireSelectionHandler();
}

/**
 * loadYouTubeAPI — dynamically inject the YouTube IFrame API script tag if
 * it has not been loaded yet. The API calls window.onYouTubeIframeAPIReady
 * when it is ready.
 */
function loadYouTubeAPI() {
  // Skip injection if the script tag is already present in the DOM.
  if (document.getElementById('yt-iframe-api')) return;

  // Create a script element pointing to the official YouTube IFrame API.
  const tag = document.createElement('script');
  tag.id  = 'yt-iframe-api';
  tag.src = 'https://www.youtube.com/iframe_api';

  // Insert before the first existing script tag (standard API loading pattern).
  const firstScript = document.getElementsByTagName('script')[0];
  firstScript.parentNode.insertBefore(tag, firstScript);
}

/**
 * window.onYouTubeIframeAPIReady — global callback invoked by the YT API.
 * At this point the YT namespace is fully available.
 * We store the pending video ID (if any) and create the player.
 */
window.onYouTubeIframeAPIReady = function () {
  // If submitVideoURL already queued a video ID, create the player now.
  if (window._pendingVideoId) {
    createYTPlayer(window._pendingVideoId);
    window._pendingVideoId = null; // clear the pending flag
  }
};

/**
 * createYTPlayer — instantiate a YT.Player inside #youtube-player-container.
 *
 * @param {string} videoId — YouTube video ID (the 'v' query parameter)
 */
function createYTPlayer(videoId) {
  // Destroy an existing player instance before creating a new one.
  if (_ytPlayer) {
    _ytPlayer.destroy();
    _ytPlayer = null;
  }

  // Create a new YT.Player in the container div.
  _ytPlayer = new YT.Player('youtube-player-container', {
    videoId: videoId,       // which video to load
    height: '200',          // player height in px
    width: '100%',          // full container width
    playerVars: {
      autoplay: 0,          // do not autoplay immediately (user taps play)
      rel: 0,               // do not show related videos at the end
      modestbranding: 1,    // minimal YouTube branding
    },
    events: {
      // Once the player is ready, start the subtitle sync loop.
      onReady: () => startSyncLoop(),
    },
  });
}

/**
 * submitVideoURL — validate URL, call the backend, then render the player + subtitles.
 *
 * @param {string} url — raw YouTube URL entered by the user
 */
async function submitVideoURL(url) {
  // Validate that the URL is a legitimate YouTube URL by parsing it and
  // checking the hostname — prevents substring-bypass attacks like
  // "evil.com/youtube.com/watch?v=..." from passing a naive includes() check.
  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch (_) {
    // URL constructor throws if the string is not a valid URL.
    showToast("Iltimos, to'g'ri YouTube havolasini kiriting.", 'error');
    return;
  }
  const hostname = parsedUrl.hostname.toLowerCase();
  // Allow only the exact YouTube hostnames (with or without www.).
  const isYouTube = hostname === 'youtube.com' ||
                    hostname === 'www.youtube.com' ||
                    hostname === 'm.youtube.com' ||
                    hostname === 'music.youtube.com' ||
                    hostname === 'youtu.be';
  if (!isYouTube) {
    showToast("Iltimos, to'g'ri YouTube havolasini kiriting.", 'error');
    return;
  }

  // Show a loading skeleton in the subtitle panel while the backend processes.
  showVideoLoadingSkeleton();

  let data;
  try {
    // Call the backend to extract and tokenise the transcript.
    data = await Api.processVideo(url);
  } catch (e) {
    // Error toast already shown by api.js; restore the input form.
    hideVideoLoadingSkeleton();
    return;
  }

  // Hide the URL input state and reveal the player state.
  const inputState  = document.querySelector('.video-input-state');
  const playerState = document.getElementById('video-player-state');
  if (inputState)  inputState.style.display  = 'none';
  if (playerState) playerState.style.display = 'block';

  // Display the video title in the header row.
  const titleEl = document.getElementById('video-title');
  if (titleEl) titleEl.textContent = data.title || '';

  // Store the segments returned by the backend for the sync loop.
  _segments = data.segments || [];

  // Render the tokenised subtitle text.
  renderSubtitles(_segments);

  // Extract the video ID from the URL to init the YT player.
  const videoId = extractVideoId(url);
  if (!videoId) {
    showToast("Video ID topilmadi.", 'error');
    return;
  }

  // Load the YT IFrame API (no-op if already loaded).
  loadYouTubeAPI();

  // If the YT namespace is already available, create the player immediately.
  // Otherwise onYouTubeIframeAPIReady will create it when the script loads.
  if (window.YT && window.YT.Player) {
    createYTPlayer(videoId);
  } else {
    // Queue the video ID for when the API script finishes loading.
    window._pendingVideoId = videoId;
  }
}

/**
 * extractVideoId — extract the YouTube video ID from various URL formats.
 * Handles:
 *   - https://www.youtube.com/watch?v=VIDEO_ID
 *   - https://youtu.be/VIDEO_ID
 *   - https://www.youtube.com/embed/VIDEO_ID
 *
 * @param {string} url — the YouTube URL
 * @returns {string|null} — the video ID or null if not found
 */
function extractVideoId(url) {
  // Try the ?v= query parameter format first (most common).
  const vParam = new URL(url).searchParams.get('v');
  if (vParam) return vParam;

  // Try the short youtu.be/<id> format.
  const shortMatch = url.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/);
  if (shortMatch) return shortMatch[1];

  // Try the /embed/<id> format.
  const embedMatch = url.match(/\/embed\/([a-zA-Z0-9_-]{11})/);
  if (embedMatch) return embedMatch[1];

  // Try the /shorts/<id> format.
  const shortsMatch = url.match(/\/shorts\/([a-zA-Z0-9_-]{11})/);
  if (shortsMatch) return shortsMatch[1];

  return null; // could not extract video ID
}

/**
 * renderSubtitles — build the subtitle panel DOM from the backend segments array.
 * Each segment becomes a <div class="segment"> containing word token spans.
 *
 * @param {Array} segments — array of { start, duration, tokens: [{word, display}] }
 */
function renderSubtitles(segments) {
  // Get the subtitle panel container.
  const panel = document.getElementById('subtitle-panel');
  if (!panel) return;

  // Clear any previous subtitle content.
  panel.innerHTML = '';

  // Build a document fragment to minimise DOM reflows.
  const frag = document.createDocumentFragment();

  segments.forEach((seg, segIdx) => {
    // Create the segment container div.
    const segEl = document.createElement('div');
    segEl.className = 'segment';
    // Store timing data as data attributes for the sync loop to read.
    segEl.dataset.start    = seg.start;
    segEl.dataset.duration = seg.duration;
    segEl.dataset.idx      = segIdx;

    // Build each word token inside this segment.
    (seg.tokens || []).forEach(tok => {
      // Create a clickable word span.
      const span = document.createElement('span');
      span.className     = 'word-token';
      span.textContent   = tok.display || tok.word; // display form (may include punctuation)
      span.dataset.word  = tok.word;                 // clean word for translation lookup

      // Clicking a word token opens the translation popup.
      span.addEventListener('click', () => {
        if (window.Popup) Popup.show(span);
      });

      segEl.appendChild(span);
      // Add a space between tokens for readability.
      segEl.appendChild(document.createTextNode(' '));
    });

    frag.appendChild(segEl);
  });

  // Mount all segments to the DOM in one operation.
  panel.appendChild(frag);
}

/**
 * startSyncLoop — start a 500ms polling interval that keeps the active
 * subtitle segment in sync with the video's current playback position.
 */
function startSyncLoop() {
  // Clear any existing sync interval to avoid duplicates.
  if (_syncInterval) clearInterval(_syncInterval);

  _syncInterval = setInterval(() => {
    // Guard: player must exist and be in a playing/paused state.
    if (!_ytPlayer || typeof _ytPlayer.getCurrentTime !== 'function') return;

    // Get the current playback time in seconds.
    const t = _ytPlayer.getCurrentTime();

    // Find the segment that covers this time position.
    const activeIdx = _segments.findIndex(seg => {
      const start = parseFloat(seg.start);
      const end   = start + parseFloat(seg.duration);
      return t >= start && t < end;
    });

    // Skip DOM updates if the active segment hasn't changed.
    if (activeIdx === _lastActiveIdx) {
      // Even with no segment change, check auto-pause logic.
      checkAutopause(t);
      return;
    }

    _lastActiveIdx = activeIdx;

    // Remove the active class from all segment elements.
    document.querySelectorAll('.segment').forEach(el => {
      el.classList.remove('segment--active');
    });

    // Highlight the current segment if found.
    if (activeIdx !== -1) {
      const activeEl = document.querySelector(`.segment[data-idx="${activeIdx}"]`);
      if (activeEl) {
        // Add the pulsing active class.
        activeEl.classList.add('segment--active');
        // Smoothly scroll the active segment into view.
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    // Check auto-pause at end of segment.
    checkAutopause(t);
  }, 500); // poll every 500ms
}

/**
 * checkAutopause — if autopause is enabled and the current time is past
 * the end of the active segment, pause the video.
 *
 * @param {number} t — current playback time in seconds
 */
function checkAutopause(t) {
  // Only act if autopause is enabled and a segment is active.
  if (!_autopauseEnabled || _lastActiveIdx === -1) return;

  const seg   = _segments[_lastActiveIdx];
  if (!seg) return;

  const segEnd = parseFloat(seg.start) + parseFloat(seg.duration);

  // If playback has reached or passed the end of the segment, pause.
  if (t >= segEnd) {
    if (_ytPlayer && typeof _ytPlayer.pauseVideo === 'function') {
      _ytPlayer.pauseVideo(); // pause so the user can read the subtitle
    }
    // Move the active index forward so we don't re-pause on the same segment.
    _lastActiveIdx = _lastActiveIdx + 1;
  }
}

/**
 * toggleAutopause — toggle the auto-pause feature on or off and update the button label.
 */
function toggleAutopause() {
  // Flip the boolean.
  _autopauseEnabled = !_autopauseEnabled;

  // Update the button label to reflect the new state.
  const btn = document.getElementById('autopause-toggle');
  if (btn) {
    // "Yoq" = On (Uzbek), "O'ch" = Off
    btn.textContent = _autopauseEnabled ? "Avtopauza: Yoq" : "Avtopauza: O'ch";
  }
}

/**
 * showVideoLoadingSkeleton — replace the subtitle panel content with skeleton
 * placeholder divs while the backend processes the video.
 */
function showVideoLoadingSkeleton() {
  const panel = document.getElementById('subtitle-panel');
  if (!panel) return;

  // Build several skeleton lines to suggest subtitle content is loading.
  let html = '';
  for (let i = 0; i < 6; i++) {
    // Vary skeleton line widths for a natural look.
    const widths = ['90%', '75%', '85%', '60%', '80%', '70%'];
    html += `<div class="skeleton" style="height:18px;width:${widths[i]};margin-bottom:10px;"></div>`;
  }
  panel.innerHTML = html;
}

/**
 * hideVideoLoadingSkeleton — clear the skeleton; called on error before
 * restoring the input form so the panel is clean.
 */
function hideVideoLoadingSkeleton() {
  const panel = document.getElementById('subtitle-panel');
  if (panel) panel.innerHTML = '';
}

/**
 * showVideoInputState — reset the video panel back to the URL input state.
 * Called by the ← Orqaga back button. Mirrors showReadingInputState() in reading.js.
 */
function showVideoInputState() {
  // Stop the subtitle sync loop.
  if (_syncInterval) { clearInterval(_syncInterval); _syncInterval = null; }

  // Destroy the YouTube player so it stops consuming resources.
  if (_ytPlayer) { _ytPlayer.destroy(); _ytPlayer = null; }

  // Clear module state.
  _segments = [];
  _lastActiveIdx = -1;

  // Clear subtitle panel content.
  const panel = document.getElementById('subtitle-panel');
  if (panel) panel.innerHTML = '';

  // Clear the URL input so the user can paste a new link immediately.
  const urlInput = document.getElementById('video-url-input');
  if (urlInput) urlInput.value = '';

  // Show the input state, hide the player state.
  const inputState  = document.querySelector('.video-input-state');
  const playerState = document.getElementById('video-player-state');
  if (playerState) playerState.style.display = 'none';
  if (inputState)  inputState.style.display  = '';
}

/**
 * wireSelectionHandler — listen for text selection events inside the subtitle
 * panel and show the floating AI button near the selected text.
 * Uses both selectionchange (desktop) and touchend (mobile/Telegram WebView).
 * Called once during renderVideoView().
 */
function wireSelectionHandler() {
  function tryShowAiButton() {
    const btn = document.getElementById('ai-float-btn');
    if (!btn) return;

    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.toString().trim().length === 0) {
      btn.style.display = 'none';
      return;
    }

    let range;
    try {
      range = sel.getRangeAt(0);
    } catch (_) {
      btn.style.display = 'none';
      return;
    }

    // Only activate inside the subtitle panel.
    const panel = document.getElementById('subtitle-panel');
    if (!panel || !panel.contains(range.commonAncestorContainer)) {
      btn.style.display = 'none';
      return;
    }

    const selectedText = sel.toString().trim();
    if (selectedText.length < 2) {
      btn.style.display = 'none';
      return;
    }

    const rect = range.getBoundingClientRect();
    // rect can be zeroed on mobile while the finger is still down — bail.
    if (rect.width === 0 && rect.height === 0) return;

    // Make button temporarily visible so offsetWidth is accurate.
    btn.style.visibility = 'hidden';
    btn.style.display    = 'inline-flex';

    const margin = 8;
    const btnW   = btn.offsetWidth  || 90;
    const btnH   = btn.offsetHeight || 38;

    // Prefer above the selection; fall back to below if too close to top.
    let top = rect.top - btnH - margin;
    if (top < margin) top = rect.bottom + margin;

    const left = Math.min(
      Math.max(margin, rect.left + rect.width / 2 - btnW / 2),
      window.innerWidth - btnW - margin
    );

    btn.style.position   = 'fixed';
    btn.style.zIndex     = '430';
    btn.style.top        = `${top}px`;
    btn.style.left       = `${left}px`;
    btn.style.visibility = 'visible';
    btn.dataset.selection = selectedText;

    btn.onclick = (event) => {
      event.preventDefault();
      const text = (btn.dataset.selection || '').trim();
      if (!text) return;
      if (window.AiPopup) AiPopup.show(text, 'video');
      btn.style.display = 'none';
    };
  }

  // Desktop: selectionchange fires reliably after mouse-up.
  document.addEventListener('selectionchange', tryShowAiButton);

  // Mobile: re-evaluate after the finger lifts so the rect is settled.
  document.addEventListener('touchend', () => {
    setTimeout(tryShowAiButton, 120);
  }, { passive: true });
}

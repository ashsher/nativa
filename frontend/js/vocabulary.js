/**
 * vocabulary.js — Vocabulary / SRS flashcard module.
 *
 * Implements a complete SM-2-compatible spaced-repetition review session:
 *   1. Overview state: word list + due count + manual add.
 *   2. Review session: flip cards → rate difficulty → backend records next review date.
 *   3. Session complete state: shows reviewed count.
 *
 * The backend computes the SM-2 scheduling; this module handles all UI logic.
 */

// ── Module-level state ──────────────────────────────────────────────────────
// All vocabulary items fetched from the backend.
let _vocabItems = [];

// Words due for review today (fetched via Api.getReviewWords()).
let _reviewQueue = [];

// How many cards have been reviewed in the current session.
let _reviewedCount = 0;

// Total cards in the session (length of _reviewQueue at start).
let _totalCount = 0;

/**
 * renderVocabView — called by app.js onTabActivated('vocab').
 * Loads the vocabulary list from the backend.
 */
function renderVocabView() {
  // Load and render the vocabulary overview.
  loadVocabList();

  // Wire the add-word button (idempotent via flag).
  if (!renderVocabView._wired) {
    renderVocabView._wired = true;

    // Wire the "Qo'shish" (Add) button.
    const addBtn = document.getElementById('add-word-btn');
    if (addBtn) addBtn.addEventListener('click', addWord);

    // Allow submitting the add-word form with Enter key.
    const addInput = document.getElementById('add-word-input');
    if (addInput) {
      addInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') addWord();
      });
    }

    // Wire the "Takrorlashni boshlash" (Start review) button.
    const startBtn = document.getElementById('start-review-btn');
    if (startBtn) startBtn.addEventListener('click', startReview);

    // Wire the review state back button.
    const reviewBackBtn = document.getElementById('review-back-btn');
    if (reviewBackBtn) {
      reviewBackBtn.addEventListener('click', showVocabOverview);
    }

    // Wire the complete state back button.
    const completeBackBtn = document.getElementById('complete-back-btn');
    if (completeBackBtn) {
      completeBackBtn.addEventListener('click', () => {
        showVocabOverview();
        loadVocabList(); // refresh counts after the session
      });
    }

    // Wire the flashcard click to flip it.
    const flashcard = document.getElementById('flashcard');
    if (flashcard) {
      flashcard.addEventListener('click', flipCard);
    }

    // Wire all rating buttons via event delegation on their container.
    const ratingButtons = document.getElementById('rating-buttons');
    if (ratingButtons) {
      ratingButtons.addEventListener('click', (e) => {
        // Walk up the DOM tree to find the closest button with a data-rating attribute.
        const btn = e.target.closest('[data-rating]');
        if (btn) {
          // Read the rating value (0, 2, 4, or 5) and submit it.
          submitRating(parseInt(btn.dataset.rating, 10));
        }
      });
    }
  }
}

/**
 * loadVocabList — fetch all vocabulary items from the backend and render them.
 * Also updates the total count and due count badges.
 */
async function loadVocabList() {
  try {
    // Fetch the full vocabulary deck.
    _vocabItems = await Api.getVocabulary();
  } catch (e) {
    // Error toast shown by api.js; nothing else to do here.
    return;
  }

  // Fetch due words separately to get an accurate due count for today.
  let dueWords = [];
  try {
    dueWords = await Api.getReviewWords();
  } catch (e) {
    // Non-fatal; due count will just show 0.
  }

  // Update the total word count badge.
  const totalBadge = document.getElementById('vocab-total-badge');
  if (totalBadge) {
    totalBadge.textContent = `${_vocabItems.length} so'z`;
  }

  // Update the due-today badge.
  const dueBadge = document.getElementById('vocab-due-badge');
  if (dueBadge) {
    dueBadge.textContent = `${dueWords.length} bugun`;
  }

  // Enable the start review button only if there are words due today.
  const startBtn = document.getElementById('start-review-btn');
  if (startBtn) {
    startBtn.disabled = dueWords.length === 0;
  }

  // Render the word list.
  renderVocabList(_vocabItems);
}

/**
 * renderVocabList — build the vocabulary list DOM from the items array.
 *
 * @param {Array} items — array of { vocab_id, word, translation, ... }
 */
function renderVocabList(items) {
  const listEl = document.getElementById('vocab-list');
  if (!listEl) return;

  // Clear any previous list items.
  listEl.innerHTML = '';

  // Show an empty-state message if the user has no saved words.
  if (!items || items.length === 0) {
    listEl.innerHTML = '<p class="text-secondary" style="text-align:center;padding:2rem 0;">Hali so\'z saqlanmagan. Video yoki maqoladan so\'z qo\'shing.</p>';
    return;
  }

  // Build each vocabulary card.
  const frag = document.createDocumentFragment();
  items.forEach(item => {
    // Create the card container.
    const card = document.createElement('div');
    card.className  = 'vocab-card';
    card.dataset.id = item.vocab_id;

    // Word text in display font.
    const wordEl = document.createElement('div');
    wordEl.className   = 'vocab-card__word';
    wordEl.textContent = item.word || '';

    // Translation in secondary text style.
    const transEl = document.createElement('div');
    transEl.className   = 'vocab-card__translation';
    transEl.textContent = item.translation || '';

    // Delete button to remove the word from the deck.
    const delBtn = document.createElement('button');
    delBtn.className   = 'btn btn--ghost btn--sm vocab-card__delete';
    delBtn.textContent = '✕';
    delBtn.setAttribute('aria-label', `${item.word} ni o'chirish`);

    // Wire the delete button to remove this specific word.
    delBtn.addEventListener('click', async () => {
      try {
        // Call the backend delete endpoint.
        await Api.deleteWord(item.vocab_id);
        // Remove this card from the DOM immediately for instant feedback.
        card.remove();
        // Update the total count badge by decrementing.
        const totalBadge = document.getElementById('vocab-total-badge');
        if (totalBadge) {
          const current = parseInt(totalBadge.textContent, 10) || 0;
          totalBadge.textContent = `${Math.max(0, current - 1)} so'z`;
        }
      } catch (e) {
        // Error toast shown by api.js.
      }
    });

    // Assemble the card.
    card.appendChild(wordEl);
    card.appendChild(transEl);
    card.appendChild(delBtn);
    frag.appendChild(card);
  });

  listEl.appendChild(frag);
}

/**
 * addWord — read the add-word input, POST to the backend, and refresh the list.
 */
async function addWord() {
  const input = document.getElementById('add-word-input');
  if (!input) return;

  // Trim whitespace and validate the input is not empty.
  const word = input.value.trim();
  if (!word) {
    showToast("Iltimos, so'z kiriting.", 'error');
    return;
  }

  try {
    // Get translation first because backend requires translation in payload.
    const translationData = await Api.translate(word);
    const translation = (translationData && translationData.translation) ? translationData.translation : word;

    // Add the word to the deck via the API.
    await Api.addWord(word, translation, translationData.examples || null);
    // Clear the input field for the next word.
    input.value = '';
    // Show success feedback.
    showToast(`"${word}" qo'shildi!`, 'success');
    // Refresh the vocabulary list to show the new word.
    loadVocabList();
  } catch (e) {
    // Error toast shown by api.js (including quota modal if limit reached).
  }
}

/**
 * startReview — fetch words due today and start the flashcard session.
 */
async function startReview() {
  let dueWords;
  try {
    // Get words due for review today from the backend (SM-2 schedule).
    dueWords = await Api.getReviewWords();
  } catch (e) {
    return; // api.js showed error toast
  }

  if (!dueWords || dueWords.length === 0) {
    showToast("Bugun takrorlanadigan so'z yo'q.", 'default');
    return;
  }

  // Initialise review session state.
  _reviewQueue    = [...dueWords]; // copy so we can safely splice/push
  _totalCount     = dueWords.length;
  _reviewedCount  = 0;

  // Switch to the review state (hide overview, show review).
  document.getElementById('vocab-overview-state').style.display = 'none';
  document.getElementById('vocab-review-state').style.display   = 'block';
  document.getElementById('vocab-complete-state').style.display = 'none';

  // Show the first card.
  showNextCard();
}

/**
 * showNextCard — display the next card in the review queue,
 * or end the session if the queue is empty.
 */
function showNextCard() {
  // If the queue is empty, the session is complete.
  if (_reviewQueue.length === 0) {
    showSessionComplete();
    return;
  }

  // The current card is always the front of the queue.
  const card = _reviewQueue[0];

  // Update the progress counter text, e.g. "3/12".
  const counter = document.getElementById('review-counter');
  if (counter) {
    counter.textContent = `${_reviewedCount}/${_totalCount}`;
  }

  // Update the progress bar fill percentage.
  const fill = document.getElementById('review-progress-fill');
  if (fill) {
    const pct = _totalCount > 0 ? (_reviewedCount / _totalCount) * 100 : 0;
    fill.style.width = pct + '%';
  }

  // Render the card front: the word in large Syne font.
  const cardFront = document.getElementById('card-front');
  if (cardFront) {
    cardFront.innerHTML = `<span class="card__word">${card.word}</span>`;
  }

  // Render the card back: translation + optional pronunciation hint.
  const cardBack = document.getElementById('card-back');
  if (cardBack) {
    cardBack.innerHTML = `<span class="card__translation">${card.translation || ''}</span>`;
  }

  // Remove the flipped class so the card shows its front face.
  document.getElementById('flashcard').classList.remove('card--flipped');

  // Hide rating buttons until the card is flipped.
  document.getElementById('rating-buttons').style.display = 'none';

  // Show the "tap to flip" hint text.
  const hint = document.getElementById('flip-hint');
  if (hint) {
    hint.style.display = 'block';
    hint.textContent   = 'So\'zni ko\'rish uchun bosing';
  }
}

/**
 * flipCard — flip the flashcard to reveal the back face.
 * After the flip, shows the rating buttons with staggered animation.
 */
function flipCard() {
  const card = document.getElementById('flashcard');
  if (!card) return;

  // If the card is already flipped, don't flip it back — wait for a rating.
  if (card.classList.contains('card--flipped')) return;

  // Add the flipped class to trigger the 3D CSS rotation.
  card.classList.add('card--flipped');

  // After the flip animation completes (400ms), show the rating buttons.
  setTimeout(() => {
    // Show rating buttons (CSS ratingIn animation staggers their entrance).
    document.getElementById('rating-buttons').style.display = 'grid';
    // Hide the flip hint since the card is now face-up.
    const hint = document.getElementById('flip-hint');
    if (hint) hint.style.display = 'none';
  }, 400); // matches the card flip transition duration in animations.css
}

/**
 * submitRating — record the user's SM-2 quality rating for the current card.
 *
 * @param {number} rating — 0 (forgot), 2 (hard), 4 (good), or 5 (easy)
 */
async function submitRating(rating) {
  // The current card is always at index 0 of the review queue.
  const card = _reviewQueue[0];
  if (!card) return;

  try {
    // POST the rating to the backend. The backend updates the SM-2 schedule.
    await Api.submitRating(card.vocab_id, rating);
  } catch (e) {
    // Non-fatal: rating submission failure shouldn't block the review session.
    // The word will just be shown again at the next scheduled interval.
  }

  // Remove the reviewed card from the front of the queue.
  _reviewQueue.shift();
  _reviewedCount++; // increment reviewed count for progress display

  // If the rating is below "good" threshold (3), push the card to the back
  // of the queue so it appears again in this session (spaced repetition within session).
  if (rating < 3) {
    _reviewQueue.push(card);
  }

  // Show the next card (or the completion screen if the queue is now empty).
  showNextCard();
}

/**
 * showSessionComplete — transition to the session complete state.
 */
function showSessionComplete() {
  // Hide the review state.
  document.getElementById('vocab-review-state').style.display = 'none';
  // Show the completion celebration screen.
  document.getElementById('vocab-complete-state').style.display = 'block';

  // Update the completion stats message.
  const statsEl = document.getElementById('session-complete-stats');
  if (statsEl) {
    statsEl.textContent = `Bugun ${_reviewedCount} ta so'z takrorlandi`;
  }
}

/**
 * showVocabOverview — return from review or complete state to the overview.
 */
function showVocabOverview() {
  // Hide review and complete states.
  document.getElementById('vocab-review-state').style.display   = 'none';
  document.getElementById('vocab-complete-state').style.display = 'none';
  // Show the overview state.
  document.getElementById('vocab-overview-state').style.display = 'block';
}

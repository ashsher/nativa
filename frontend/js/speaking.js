/**
 * speaking.js — Speaking partners module.
 *
 * Loads matched speaking partners from the backend (scored by shared interests),
 * renders partner cards, and connects two users via a Telegram deep link.
 */

/**
 * renderSpeakingView — called by app.js onTabActivated('speak').
 * Triggers a fresh partner match load each time the tab is activated.
 */
function renderSpeakingView() {
  // Wire the "Go to profile" button in the empty state (once only).
  if (!renderSpeakingView._wired) {
    renderSpeakingView._wired = true;

    // The empty-state button sends the user to the profile tab to add interests.
    const goToProfileBtn = document.getElementById('go-to-profile-btn');
    if (goToProfileBtn) {
      goToProfileBtn.addEventListener('click', () => {
        // Switch to the profile tab so the user can fill in their interests.
        if (typeof switchTab === 'function') switchTab('profile');
      });
    }
  }

  // Load speaking partner matches from the backend.
  loadMatches();
}

/**
 * loadMatches — fetch partner matches from the backend and render them.
 * If no matches are returned and the user has no interests, show the empty state.
 */
async function loadMatches() {
  let matches;
  try {
    // Get matches ranked by Jaccard similarity of shared interests.
    matches = await Api.getMatches();
  } catch (e) {
    // Error toast already shown by api.js.
    return;
  }

  // Determine whether to show the empty state.
  const hasInterests = window.currentUser &&
    window.currentUser.interests &&
    window.currentUser.interests.length > 0;

  // Hide both states before deciding which to show.
  const partnerList  = document.getElementById('partner-list');
  const emptyState   = document.getElementById('speak-empty-state');

  if (!matches || matches.length === 0) {
    // No matches found.
    if (!hasInterests) {
      // User hasn't filled in interests yet — prompt them to complete profile.
      if (partnerList)  partnerList.innerHTML = '';
      if (emptyState)   emptyState.style.display = 'block';
    } else {
      // User has interests but no matches yet — show a friendly message.
      if (emptyState)   emptyState.style.display = 'none';
      if (partnerList)  partnerList.innerHTML =
        '<p class="text-secondary" style="text-align:center;padding:2rem 0;">Hozircha mos suhbat sherigi topilmadi. Keyinroq qaytib ko\'ring.</p>';
    }
    return;
  }

  // Matches found — hide the empty state and render the partner cards.
  if (emptyState) emptyState.style.display = 'none';
  renderPartnerList(matches);
}

/**
 * renderPartnerList — build partner card DOM elements from the matches array.
 *
 * @param {Array} partners — array of match objects:
 *   { user_id, first_name, shared_interests, similarity_score }
 */
function renderPartnerList(partners) {
  const listEl = document.getElementById('partner-list');
  if (!listEl) return;

  // Clear previous partner cards.
  listEl.innerHTML = '';

  // Build a document fragment for efficient insertion.
  const frag = document.createDocumentFragment();

  partners.forEach(partner => {
    // Create the partner card container.
    const card = document.createElement('div');
    card.className = 'partner-card';

    // Partner name in large Syne display font.
    const nameEl = document.createElement('div');
    nameEl.className   = 'partner-card__name';
    nameEl.textContent = partner.first_name || 'Foydalanuvchi';

    // Similarity score, e.g. "73% umumiy qiziqish".
    const scoreEl = document.createElement('div');
    scoreEl.className   = 'partner-card__score';
    // Round the similarity score to nearest integer percentage.
    const pct = Math.round((partner.similarity_score || 0) * 100);
    scoreEl.textContent = `${pct}% umumiy qiziqish`;

    // Shared interests chips row.
    const chipsEl = document.createElement('div');
    chipsEl.className = 'partner-card__chips';

    // Render each shared interest as a small pill chip.
    const sharedInterests = partner.shared_interests || [];
    sharedInterests.forEach(interest => {
      const chip = document.createElement('span');
      chip.className   = 'interest-chip';
      chip.textContent = interest;
      chipsEl.appendChild(chip);
    });

    // "Yozish" (Write / Connect) button to initiate a Telegram conversation.
    const connectBtn = document.createElement('button');
    connectBtn.className   = 'btn btn--primary btn--full';
    connectBtn.textContent = 'Yozish';

    // Wire the connect button to call connectPartner with this partner's user_id.
    connectBtn.addEventListener('click', () => {
      connectPartner(partner.user_id);
    });

    // Assemble the card.
    card.appendChild(nameEl);
    card.appendChild(scoreEl);
    card.appendChild(chipsEl);
    card.appendChild(connectBtn);
    frag.appendChild(card);
  });

  listEl.appendChild(frag);
}

/**
 * connectPartner — initiate a speaking match with the target user.
 * On success, opens the Telegram deep link so the users can start chatting.
 *
 * @param {number} targetUserId — the database user_id of the partner
 */
async function connectPartner(targetUserId) {
  let data;
  try {
    // POST to the backend to create the match record and get the deep link.
    data = await Api.connectSpeaker(targetUserId);
  } catch (e) {
    // Error (including quota) handled by api.js.
    return;
  }

  // Open the Telegram deep link using the Mini-App SDK.
  // This opens a conversation with the matched user inside Telegram.
  if (data && data.telegram_deep_link) {
    window.Telegram.WebApp.openTelegramLink(data.telegram_deep_link);
  } else {
    showToast("Aloqa o'rnatishda xatolik.", 'error');
  }
}

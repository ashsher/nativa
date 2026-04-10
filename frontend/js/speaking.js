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

// Avatar background/text colour palette — cycled by user_id.
const _AVATAR_PALETTES = [
  { bg: '#dbeafe', color: '#1d4ed8' },  // blue
  { bg: '#dcfce7', color: '#16a34a' },  // green
  { bg: '#fce7f3', color: '#be185d' },  // pink
  { bg: '#fef3c7', color: '#b45309' },  // amber
  { bg: '#f3e8ff', color: '#7c3aed' },  // purple
];

/**
 * renderPartnerList — build partner card DOM elements from the matches array.
 *
 * @param {Array} partners — array of match objects:
 *   { user_id, first_name, username, shared_interests, shared_hobbies, similarity_score }
 */
function renderPartnerList(partners) {
  const listEl = document.getElementById('partner-list');
  if (!listEl) return;

  // Clear previous partner cards.
  listEl.innerHTML = '';

  // Build a document fragment for efficient insertion.
  const frag = document.createDocumentFragment();

  partners.forEach(partner => {
    // ── Card shell ──────────────────────────────────────────────────────────
    const card = document.createElement('div');
    card.className = 'partner-card';

    // ── Avatar (initials circle, colour-coded by user_id) ──────────────────
    const palette = _AVATAR_PALETTES[(partner.user_id || 0) % _AVATAR_PALETTES.length];
    const avatarEl = document.createElement('div');
    avatarEl.className = 'partner-card__avatar-placeholder';
    avatarEl.style.background = palette.bg;
    avatarEl.style.color      = palette.color;
    avatarEl.textContent = (partner.first_name || '?').charAt(0).toUpperCase();

    // ── Body column ─────────────────────────────────────────────────────────
    const bodyEl = document.createElement('div');
    bodyEl.className = 'partner-card__body';

    // Name + score pill on the same row.
    const nameRowEl = document.createElement('div');
    nameRowEl.className = 'partner-card__name-row';

    const nameEl = document.createElement('div');
    nameEl.className   = 'partner-card__name';
    nameEl.textContent = partner.first_name || 'Foydalanuvchi';

    const pct = Math.round((partner.similarity_score || 0) * 100);
    const scoreEl = document.createElement('span');
    scoreEl.className   = 'partner-card__score';
    scoreEl.textContent = `${pct}% mos`;

    nameRowEl.appendChild(nameEl);
    nameRowEl.appendChild(scoreEl);

    // @username line (only shown when available).
    const usernameEl = document.createElement('div');
    usernameEl.className   = 'partner-card__username';
    usernameEl.textContent = partner.username ? `@${partner.username}` : '';

    // Shared interests + hobbies as accent chips.
    const allShared = [
      ...(partner.shared_interests || []),
      ...(partner.shared_hobbies   || []),
    ];
    const chipsEl = document.createElement('div');
    chipsEl.className = 'partner-card__interests';
    allShared.forEach(tag => {
      const chip = document.createElement('span');
      chip.className   = 'interest-chip is-match';
      chip.textContent = tag;
      chipsEl.appendChild(chip);
    });

    // "Yozish" (Write / Connect) button.
    const connectBtn = document.createElement('button');
    connectBtn.className   = 'btn btn--primary partner-card__connect-btn';
    connectBtn.textContent = 'Yozish';
    connectBtn.addEventListener('click', () => connectPartner(partner.user_id));

    // Assemble body.
    bodyEl.appendChild(nameRowEl);
    if (partner.username) bodyEl.appendChild(usernameEl);
    if (allShared.length > 0) bodyEl.appendChild(chipsEl);
    bodyEl.appendChild(connectBtn);

    // Assemble card.
    card.appendChild(avatarEl);
    card.appendChild(bodyEl);
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

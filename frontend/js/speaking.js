/**
 * speaking.js — Speaking partners module.
 *
 * Loads matched speaking partners from the backend (scored by shared interests),
 * filters to ≥ 51% similarity, renders partner cards, and connects two users
 * via a Telegram deep link.
 */

/** Minimum similarity score (0–1) required to show a partner. */
const MIN_SIMILARITY = 0.51;

/**
 * renderSpeakingView — called by app.js onTabActivated('speak').
 * Triggers a fresh partner match load each time the tab is activated.
 */
function renderSpeakingView() {
  // Wire the "Go to profile" button in the empty state (once only).
  if (!renderSpeakingView._wired) {
    renderSpeakingView._wired = true;

    const goToProfileBtn = document.getElementById('go-to-profile-btn');
    if (goToProfileBtn) {
      goToProfileBtn.addEventListener('click', () => {
        if (typeof switchTab === 'function') switchTab('profile');
      });
    }
  }

  loadMatches();
}

/**
 * loadMatches — fetch partner matches from the backend, filter by similarity,
 * and render them. Shows the empty state when no qualified matches exist.
 */
async function loadMatches() {
  let matches;
  try {
    matches = await Api.getMatches();
  } catch (e) {
    return;
  }

  // Keep only partners with similarity ≥ 51 %.
  const qualified = (matches || []).filter(
    p => (p.similarity_score || 0) >= MIN_SIMILARITY
  );

  const hasInterests = window.currentUser &&
    window.currentUser.interests &&
    window.currentUser.interests.length > 0;

  const partnerList = document.getElementById('partner-list');
  const emptyState  = document.getElementById('speak-empty-state');

  if (qualified.length === 0) {
    if (!hasInterests) {
      if (partnerList) partnerList.innerHTML = '';
      if (emptyState)  emptyState.style.display = 'block';
    } else {
      if (emptyState)  emptyState.style.display = 'none';
      if (partnerList) partnerList.innerHTML =
        '<p class="speak-empty-msg">Hozircha 51% dan yuqori mos suhbat sherigi topilmadi. Qiziqishlaringizni to\'ldirib, keyinroq qaytib ko\'ring.</p>';
    }
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  renderPartnerList(qualified);
}

/**
 * renderPartnerList — build partner card DOM elements from the matches array.
 *
 * @param {Array} partners — array of match objects:
 *   { user_id, first_name, username, shared_interests, shared_hobbies, similarity_score }
 */
function renderPartnerList(partners) {
  const listEl = document.getElementById('partner-list');
  if (!listEl) return;

  listEl.innerHTML = '';
  const frag = document.createDocumentFragment();

  partners.forEach(partner => {
    const pct = Math.round((partner.similarity_score || 0) * 100);

    // ── Card shell ──────────────────────────────────────────────────────────
    const card = document.createElement('div');
    card.className = 'partner-card';

    // ── Score bar at the top of the card ────────────────────────────────────
    const scoreBar = document.createElement('div');
    scoreBar.className = 'partner-card__score-bar';

    const scoreFill = document.createElement('div');
    scoreFill.className = 'partner-card__score-fill';
    scoreFill.style.width = `${pct}%`;
    // Colour: green ≥ 75%, yellow ≥ 60%, blue otherwise.
    scoreFill.style.background =
      pct >= 75 ? 'linear-gradient(90deg,#16a34a,#22c55e)' :
      pct >= 60 ? 'linear-gradient(90deg,#b45309,#f59e0b)' :
                  'linear-gradient(90deg,#2563eb,#60a5fa)';

    scoreBar.appendChild(scoreFill);
    card.appendChild(scoreBar);

    // ── Card body ────────────────────────────────────────────────────────────
    const bodyEl = document.createElement('div');
    bodyEl.className = 'partner-card__body';

    // Top row: name on the left, pct pill on the right.
    const nameRowEl = document.createElement('div');
    nameRowEl.className = 'partner-card__name-row';

    const nameEl = document.createElement('div');
    nameEl.className   = 'partner-card__name';
    nameEl.textContent = partner.first_name || 'Foydalanuvchi';

    const scoreEl = document.createElement('span');
    scoreEl.className   = 'partner-card__score';
    scoreEl.textContent = `${pct}% mos`;

    nameRowEl.appendChild(nameEl);
    nameRowEl.appendChild(scoreEl);

    // @username line.
    const usernameEl = document.createElement('div');
    usernameEl.className   = 'partner-card__username';
    usernameEl.textContent = partner.username ? `@${partner.username}` : '';

    // Shared interests + hobbies chips.
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

    // "Yozish" button.
    const connectBtn = document.createElement('button');
    connectBtn.className   = 'btn btn--primary partner-card__connect-btn';
    connectBtn.textContent = 'Yozish';
    connectBtn.addEventListener('click', () => connectPartner(partner.user_id));

    // Assemble body.
    bodyEl.appendChild(nameRowEl);
    if (partner.username) bodyEl.appendChild(usernameEl);
    if (allShared.length > 0) bodyEl.appendChild(chipsEl);
    bodyEl.appendChild(connectBtn);

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
    data = await Api.connectSpeaker(targetUserId);
  } catch (e) {
    return;
  }

  if (data && data.telegram_deep_link) {
    window.Telegram.WebApp.openTelegramLink(data.telegram_deep_link);
  } else {
    showToast("Aloqa o'rnatishda xatolik.", 'error');
  }
}

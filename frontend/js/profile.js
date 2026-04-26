/**
 * profile.js â€” User profile module with tag chip inputs.
 *
 * Features:
 *   - Loads and displays the user's Telegram profile info.
 *   - Renders an avatar using Telegram photo or a coloured initial circle.
 *   - Editable city and country fields.
 *   - Tag chip inputs for interests and hobbies (Enter or comma to add).
 *   - Premium status section showing quota usage or expiry date.
 */

// â”€â”€ Module-level state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Arrays of tag strings for interests and hobbies (mutable via chip input).
let _interests = [];
let _hobbies   = [];

// ── Curated suggestion lists ───────────────────────────────────────────────────
// Labels are in Uzbek so complete beginners can understand and select them.
// Values saved to the backend are also Uzbek so Jaccard similarity compares
// the same canonical strings across all users.
const INTERESTS_SUGGESTIONS = [
  'Texnologiya', 'Fan', 'San\'at', 'Musiqa', 'Sport', 'Kino', 'Kitoblar',
  'Sayohat', 'Oshpazlik', 'Fotografiya', 'O\'yinlar', 'Moda', 'Biznes',
  'Tarix', 'Psixologiya', 'Sog\'liq', 'Tabiat', 'Moliya', 'Siyosat',
  'Tillar',
];

const HOBBIES_SUGGESTIONS = [
  'Futbol', 'Basketbol', 'O\'qish', 'Rasm chizish', 'Qo\'shiq aytish', 'Raqsga tushish',
  'Suzish', 'Sayr qilish', 'Yoga', 'Dasturlash', 'Video o\'yinlar', 'Pishirish',
  'Fotografiya', 'Velosipedda yurish', 'Yugurish', 'Shaxmat', 'Yozish', 'Sayohat qilish',
  'Bog\'dorchilik', 'Fitnes',
];

/**
 * renderProfileView â€” called by app.js onTabActivated('profile').
 * Wires form events once and loads the profile.
 */
function renderProfileView() {
  // Wire form events on first visit only.
  if (!renderProfileView._wired) {
    renderProfileView._wired = true;

    // Wire the profile form submit event.
    const form = document.getElementById('profile-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault(); // prevent default browser form submission
        submitProfile();
      });
    }

    // Wire the interests and hobbies tag inputs (Enter/comma to add).
    wireTagInput('interests-input', () => _interests, (tags) => { _interests = tags; }, 'interests-tags');
    wireTagInput('hobbies-input',   () => _hobbies,   (tags) => { _hobbies   = tags; }, 'hobbies-tags');

    // Wire settings modal open/close.
    wireSettingsModal();
  }

  // Load fresh profile data from the backend.
  loadProfile();
}

/**
 * loadProfile â€” fetch the user's profile and render all sections.
 */
async function loadProfile() {
  let user;
  try {
    // Fetch the full user profile object from the backend.
    user = await Api.getMe();
    // Keep the global currentUser reference up to date.
    window.currentUser = user;
  } catch (e) {
    // api.js shows an error toast; nothing else to do here.
    return;
  }

  // ── Identity ──────────────────────────────────────────────────────────────
  const fullNameEl = document.getElementById('profile-full-name');
  if (fullNameEl) {
    fullNameEl.textContent = [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || 'Foydalanuvchi';
  }

  const usernameEl = document.getElementById('profile-username');
  if (usernameEl) {
    usernameEl.textContent = user.username ? '@' + user.username : '';
  }

  // Location line: city + country (shown below username in hero).
  const locationEl = document.getElementById('profile-location');
  if (locationEl) {
    const parts = [user.city, user.country].filter(Boolean);
    locationEl.textContent = parts.length ? parts.join(', ') : '';
  }

  // Avatar.
  renderAvatar(user);

  // ── Stats row ─────────────────────────────────────────────────────────────
  const interestCount = Array.isArray(user.interests) ? user.interests.length : 0;
  const hobbyCount    = Array.isArray(user.hobbies)   ? user.hobbies.length   : 0;
  const statInterests = document.getElementById('stat-interests');
  const statHobbies   = document.getElementById('stat-hobbies');
  const statPlan      = document.getElementById('stat-plan');
  if (statInterests) statInterests.textContent = interestCount;
  if (statHobbies)   statHobbies.textContent   = hobbyCount;
  if (statPlan)      statPlan.textContent       = user.is_premium ? 'Premium' : 'Bepul';

  // ── Form fields ───────────────────────────────────────────────────────────
  const cityInput    = document.getElementById('profile-city');
  const countryInput = document.getElementById('profile-country');
  if (cityInput)    cityInput.value    = user.city    || '';
  if (countryInput) countryInput.value = user.country || '';

  // Interests chips + suggestions.
  _interests = Array.isArray(user.interests) ? [...user.interests] : [];
  const removeInterestTag = (removed) => {
    _interests = _interests.filter(t => t !== removed);
    renderTagChips('interests-tags', _interests, removeInterestTag);
    renderSuggestions('interests-suggestions', INTERESTS_SUGGESTIONS,
      () => _interests, (v) => { _interests = v; }, 'interests-tags');
  };
  renderTagChips('interests-tags', _interests, removeInterestTag);
  renderSuggestions('interests-suggestions', INTERESTS_SUGGESTIONS,
    () => _interests, (v) => { _interests = v; }, 'interests-tags');

  // Hobbies chips + suggestions.
  _hobbies = Array.isArray(user.hobbies) ? [...user.hobbies] : [];
  const removeHobbyTag = (removed) => {
    _hobbies = _hobbies.filter(t => t !== removed);
    renderTagChips('hobbies-tags', _hobbies, removeHobbyTag);
    renderSuggestions('hobbies-suggestions', HOBBIES_SUGGESTIONS,
      () => _hobbies, (v) => { _hobbies = v; }, 'hobbies-tags');
  };
  renderTagChips('hobbies-tags', _hobbies, removeHobbyTag);
  renderSuggestions('hobbies-suggestions', HOBBIES_SUGGESTIONS,
    () => _hobbies, (v) => { _hobbies = v; }, 'hobbies-tags');

  // Premium section.
  renderPremiumSection(user);
}

/**
 * renderAvatar â€” display the user's Telegram profile photo or a fallback
 * coloured circle with their first initial.
 *
 * @param {object} user â€” user object from the backend
 */
function renderAvatar(user) {
  const avatarEl = document.getElementById('profile-avatar');
  if (!avatarEl) return;

  // Try to get the photo URL from the Telegram SDK's initDataUnsafe.
  const twaUser     = window.Telegram && window.Telegram.WebApp &&
                      window.Telegram.WebApp.initDataUnsafe &&
                      window.Telegram.WebApp.initDataUnsafe.user;
  const photoUrl    = twaUser && twaUser.photo_url;

  if (photoUrl) {
    // Use the Telegram profile photo as an <img> element.
    avatarEl.innerHTML = `<img src="${photoUrl}" alt="Profil rasmi" class="profile-avatar__img" />`;
  } else {
    // Fallback: generate a coloured circle with the first initial.
    // Pick a deterministic hue based on the user's telegram_id for variety.
    const hue     = ((user.telegram_id || 0) * 137) % 360; // golden-angle colour distribution
    const initial = (user.first_name || 'U').charAt(0).toUpperCase();
    avatarEl.innerHTML = `
      <div class="profile-avatar__initial"
           style="background:hsl(${hue},60%,40%);color:#fff;font-family:var(--font-display);
                  font-size:1.5rem;font-weight:700;display:flex;align-items:center;
                  justify-content:center;width:100%;height:100%;border-radius:50%;">
        ${initial}
      </div>
    `;
  }
}

/**
 * renderTagChips â€” render a list of tags as removable chip elements.
 *
 * @param {string}   containerId â€” ID of the .tags container div
 * @param {string[]} tags        â€” array of tag strings to render
 * @param {Function} onRemove    â€” callback called with the removed tag string
 */
function renderTagChips(containerId, tags, onRemove) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // Clear existing chips.
  container.innerHTML = '';

  // Build a chip for each tag.
  tags.forEach(tag => {
    const chip = document.createElement('span');
    chip.className = 'tag-chip';

    // Tag text node.
    const textNode = document.createTextNode(tag);
    chip.appendChild(textNode);

    // Remove button (x) inside each chip.
    const removeBtn = document.createElement('button');
    removeBtn.className   = 'tag-chip__remove';
    removeBtn.textContent = 'x';
    removeBtn.setAttribute('aria-label', `${tag} ni olib tashlash`);
    removeBtn.setAttribute('type', 'button'); // prevent form submission on click

    // Wire the remove button to invoke the onRemove callback.
    removeBtn.addEventListener('click', () => {
      onRemove(tag); // notify parent to update the array and re-render
    });

    chip.appendChild(removeBtn);
    container.appendChild(chip);
  });
}

/**
 * wireTagInput â€” attach Enter/comma key event handlers to a tag input field.
 * When the user presses Enter or types a comma, the current input value is
 * added as a new chip (if non-empty and not a duplicate).
 *
 * @param {string}   inputId     â€” ID of the text input element
 * @param {Function} getArray    â€” returns the current tags array (getter)
 * @param {Function} setArray    â€” replaces the tags array (setter)
 * @param {string}   containerId â€” ID of the .tags container to re-render into
 */
function wireTagInput(inputId, getArray, setArray, containerId) {
  const input = document.getElementById(inputId);
  if (!input) return;

  input.addEventListener('keydown', (e) => {
    // Trigger chip creation on Enter key or comma character.
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault(); // prevent form submission / comma insertion

      // Trim and strip trailing commas from the input value.
      const value = input.value.trim().replace(/,+$/, '');
      if (!value) return; // ignore empty input

      const current = getArray();

      // Prevent duplicate tags (case-insensitive check).
      if (current.some(t => t.toLowerCase() === value.toLowerCase())) {
        input.value = ''; // clear input but don't add duplicate
        return;
      }

      // Add the new tag to the array.
      const updated = [...current, value];
      setArray(updated);

      // Re-render chips with the updated array.
      const onRemove = (removed) => {
        const after = getArray().filter(t => t !== removed);
        setArray(after);
        renderTagChips(containerId, after, onRemove);
      };
      renderTagChips(containerId, updated, onRemove);

      // Clear the input field ready for the next tag.
      input.value = '';
    }
  });
}

/**
 * renderSuggestions — render a row of clickable preset chips below a tag input.
 * Selected chips turn solid blue; clicking again does nothing (already added).
 *
 * @param {string}   containerId — ID of the .suggestion-chips div
 * @param {string[]} suggestions — full list of suggestion strings
 * @param {Function} getArray    — returns the current tag array
 * @param {Function} setArray    — replaces the tag array
 * @param {string}   tagsId     — ID of the .tags container to re-render
 */
function renderSuggestions(containerId, suggestions, getArray, setArray, tagsId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = '';

  suggestions.forEach(tag => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.textContent = tag;
    chip.className = 'suggestion-chip';

    const current = getArray();
    if (current.some(t => t.toLowerCase() === tag.toLowerCase())) {
      chip.classList.add('is-selected');
    }

    function activateChip() {
      const arr = getArray();
      if (arr.some(t => t.toLowerCase() === tag.toLowerCase())) return;

      const updated = [...arr, tag];
      setArray(updated);

      const onRemove = (removed) => {
        const after = getArray().filter(t => t !== removed);
        setArray(after);
        renderTagChips(tagsId, after, onRemove);
        renderSuggestions(containerId, suggestions, getArray, setArray, tagsId);
      };
      renderTagChips(tagsId, updated, onRemove);
      renderSuggestions(containerId, suggestions, getArray, setArray, tagsId);
    }

    // Support both click (desktop) and touchend (mobile Telegram WebView).
    chip.addEventListener('click', activateChip);
    chip.addEventListener('touchend', (e) => {
      e.preventDefault(); // prevent the ghost click that follows touchend
      activateChip();
    });

    container.appendChild(chip);
  });
}

/**
 * submitProfile â€” collect form data and save it to the backend.
 */
async function submitProfile() {
  // Read city and country from the text inputs.
  const city    = (document.getElementById('profile-city').value    || '').trim();
  const country = (document.getElementById('profile-country').value || '').trim();

  // Disable the save button while the request is in flight.
  const saveBtn = document.getElementById('profile-save-btn');
  if (saveBtn) saveBtn.disabled = true;

  try {
    // PUT the updated profile to the backend.
    const updated = await Api.updateMe({
      city,
      country,
      interests: _interests,
      hobbies:   _hobbies,
    });

    // Update the global currentUser with the latest profile data.
    window.currentUser = updated;

    // Show a success toast in Uzbek.
    showToast("Profil saqlandi!", 'success');
  } catch (e) {
    // Error toast shown by api.js.
  } finally {
    // Re-enable the save button regardless of success or failure.
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * renderPremiumSection â€” display the user's current plan in the premium section.
 *
 * Free users see:   quota usage stats + "Premium olish" button.
 * Premium users see: "Premium âš¡" badge + subscription expiry date.
 *
 * @param {object} user â€” the user object from the backend
 */
function renderPremiumSection(user) {
  const section = document.getElementById('premium-section');
  if (!section) return;

  if (user.is_premium) {
    let expiryStr = '';
    if (user.premium_expires_at) {
      const d = new Date(user.premium_expires_at);
      const dd = String(d.getDate()).padStart(2, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const yyyy = d.getFullYear();
      expiryStr = `${dd}.${mm}.${yyyy}`;
    }

    section.innerHTML = `
      <div class="premium-card premium-card--active">
        <div class="premium-card__head">
          <span class="badge badge--accent">Premium</span>
          <span class="premium-card__spark">*</span>
        </div>
        <h3 class="premium-card__title">Premium faol</h3>
        <p class="premium-card__meta">Obuna: ${expiryStr || 'Faol'}</p>
      </div>
    `;
    return;
  }

  const aiUsed = user.daily_ai_count || 0;
  const srsUsed = user.daily_srs_count || 0;
  const speakUsed = user.daily_speak_count || 0;

  section.innerHTML = `
    <div class="premium-card">
      <div class="premium-card__head">
        <span class="badge">Bepul reja</span>
      </div>
      <h3 class="premium-card__title">Cheksiz imkoniyatga o'ting</h3>
      <p class="premium-card__meta">AI: ${aiUsed}/10 • SRS: ${srsUsed}/10 • Gaplash: ${speakUsed}/5</p>
      <button class="btn btn--primary btn--full premium-card__cta" id="profile-upgrade-btn">
        Premium olish - $2/oy
      </button>
    </div>
  `;

  const upgradeBtn = document.getElementById('profile-upgrade-btn');
  if (upgradeBtn) {
    upgradeBtn.addEventListener('click', () => {
      if (window.Payment) Payment.showUpgradeModal('profile');
    });
  }
}

/**
 * wireSettingsModal — open/close the settings modal and persist preference changes.
 * Called once from renderProfileView().
 */
function wireSettingsModal() {
  const openBtn  = document.getElementById('profile-settings-btn');
  const modal    = document.getElementById('settings-modal');
  const closeBtn = document.getElementById('settings-close-btn');
  const overlay  = document.getElementById('settings-overlay');
  if (!modal) return;

  function openSettings() {
    // Sync toggle states before showing.
    const discoverableEl = document.getElementById('setting-discoverable');
    const autopauseEl    = document.getElementById('setting-autopause');
    const similarityEl   = document.getElementById('setting-similarity');
    const descEl         = document.getElementById('similarity-desc');

    // is_discoverable comes from the server (stored in DB).
    if (discoverableEl) {
      discoverableEl.checked = window.currentUser?.is_discoverable !== false;
    }
    if (autopauseEl) {
      autopauseEl.checked = localStorage.getItem('nativa_autopause') === '1';
    }
    if (similarityEl) {
      const saved = parseInt(localStorage.getItem('nativa_min_similarity') || '10', 10);
      similarityEl.value = saved;
      if (descEl) descEl.textContent = `Minimum moslik: ${saved}%`;
    }
    modal.classList.remove('modal--hidden');
  }

  function closeSettings() {
    modal.classList.add('modal--hidden');
  }

  if (openBtn)  openBtn.addEventListener('click', openSettings);
  if (closeBtn) closeBtn.addEventListener('click', closeSettings);
  if (overlay)  overlay.addEventListener('click', closeSettings);

  // Discoverability toggle: persisted to the server (affects what others see).
  const discoverableEl = document.getElementById('setting-discoverable');
  if (discoverableEl) {
    discoverableEl.addEventListener('change', async () => {
      const val = discoverableEl.checked;
      try {
        const updated = await Api.user.updateMe({ is_discoverable: val });
        if (window.currentUser) window.currentUser.is_discoverable = updated.is_discoverable;
      } catch (_) {
        // Revert the toggle if the API call failed.
        discoverableEl.checked = !val;
        showToast("Sozlamani saqlashda xatolik yuz berdi.", 'error');
      }
    });
  }

  // Auto-pause toggle: persist to localStorage immediately.
  const autopauseEl = document.getElementById('setting-autopause');
  if (autopauseEl) {
    autopauseEl.addEventListener('change', () => {
      localStorage.setItem('nativa_autopause', autopauseEl.checked ? '1' : '0');
    });
  }

  // Similarity slider: persist to localStorage and update label.
  const similarityEl = document.getElementById('setting-similarity');
  const descEl       = document.getElementById('similarity-desc');
  if (similarityEl) {
    similarityEl.addEventListener('input', () => {
      const val = similarityEl.value;
      localStorage.setItem('nativa_min_similarity', val);
      if (descEl) descEl.textContent = `Minimum moslik: ${val}%`;
    });
  }
}

// Expose loadProfile globally so payment.js can call it after a successful payment.
window.loadProfile = loadProfile;



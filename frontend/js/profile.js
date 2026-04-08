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

    // Wire the interests tag input.
    wireTagInput('interests-input', () => _interests, (tags) => { _interests = tags; }, 'interests-tags');
    // Wire the hobbies tag input.
    wireTagInput('hobbies-input',   () => _hobbies,   (tags) => { _hobbies   = tags; }, 'hobbies-tags');
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

  // â”€â”€ Render the display section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Full name from Telegram data.
  const fullNameEl = document.getElementById('profile-full-name');
  if (fullNameEl) {
    // Combine first and last name, trimming trailing whitespace.
    fullNameEl.textContent = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
  }

  // Telegram username, e.g. "@alisher".
  const usernameEl = document.getElementById('profile-username');
  if (usernameEl) {
    usernameEl.textContent = user.username ? '@' + user.username : '';
  }

  // Render the avatar.
  renderAvatar(user);

  // â”€â”€ Pre-fill the editable form fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const cityInput    = document.getElementById('profile-city');
  const countryInput = document.getElementById('profile-country');
  if (cityInput)    cityInput.value    = user.city    || '';
  if (countryInput) countryInput.value = user.country || '';

  // Pre-fill interests array and render chips.
  _interests = Array.isArray(user.interests) ? [...user.interests] : [];
  const removeInterestTag = (removed) => {
    _interests = _interests.filter(t => t !== removed);
    renderTagChips('interests-tags', _interests, removeInterestTag);
  };
  renderTagChips('interests-tags', _interests, removeInterestTag);

  // Pre-fill hobbies array and render chips.
  _hobbies = Array.isArray(user.hobbies) ? [...user.hobbies] : [];
  const removeHobbyTag = (removed) => {
    _hobbies = _hobbies.filter(t => t !== removed);
    renderTagChips('hobbies-tags', _hobbies, removeHobbyTag);
  };
  renderTagChips('hobbies-tags', _hobbies, removeHobbyTag);

  // â”€â”€ Render the premium status section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// Expose loadProfile globally so payment.js can call it after a successful payment.
window.loadProfile = loadProfile;



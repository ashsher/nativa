/**
 * profile.js — User profile module with tag chip inputs.
 *
 * Features:
 *   - Loads and displays the user's Telegram profile info.
 *   - Renders an avatar using Telegram photo or a coloured initial circle.
 *   - Editable city and country fields.
 *   - Tag chip inputs for interests and hobbies (Enter or comma to add).
 *   - Premium status section showing quota usage or expiry date.
 */

// ── Module-level state ──────────────────────────────────────────────────────
// Arrays of tag strings for interests and hobbies (mutable via chip input).
let _interests = [];
let _hobbies   = [];

/**
 * renderProfileView — called by app.js onTabActivated('profile').
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
 * loadProfile — fetch the user's profile and render all sections.
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

  // ── Render the display section ─────────────────────────────────────────
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

  // ── Pre-fill the editable form fields ─────────────────────────────────
  const cityInput    = document.getElementById('profile-city');
  const countryInput = document.getElementById('profile-country');
  if (cityInput)    cityInput.value    = user.city    || '';
  if (countryInput) countryInput.value = user.country || '';

  // Pre-fill interests array and render chips.
  _interests = Array.isArray(user.interests) ? [...user.interests] : [];
  renderTagChips('interests-tags', _interests, (removed) => {
    // Remove the tag from the array and re-render.
    _interests = _interests.filter(t => t !== removed);
    renderTagChips('interests-tags', _interests, arguments.callee);
  });

  // Pre-fill hobbies array and render chips.
  _hobbies = Array.isArray(user.hobbies) ? [...user.hobbies] : [];
  renderTagChips('hobbies-tags', _hobbies, (removed) => {
    _hobbies = _hobbies.filter(t => t !== removed);
    renderTagChips('hobbies-tags', _hobbies, arguments.callee);
  });

  // ── Render the premium status section ─────────────────────────────────
  renderPremiumSection(user);
}

/**
 * renderAvatar — display the user's Telegram profile photo or a fallback
 * coloured circle with their first initial.
 *
 * @param {object} user — user object from the backend
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
 * renderTagChips — render a list of tags as removable chip elements.
 *
 * @param {string}   containerId — ID of the .tags container div
 * @param {string[]} tags        — array of tag strings to render
 * @param {Function} onRemove    — callback called with the removed tag string
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

    // Remove button (×) inside each chip.
    const removeBtn = document.createElement('button');
    removeBtn.className   = 'tag-chip__remove';
    removeBtn.textContent = '×';
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
 * wireTagInput — attach Enter/comma key event handlers to a tag input field.
 * When the user presses Enter or types a comma, the current input value is
 * added as a new chip (if non-empty and not a duplicate).
 *
 * @param {string}   inputId     — ID of the text input element
 * @param {Function} getArray    — returns the current tags array (getter)
 * @param {Function} setArray    — replaces the tags array (setter)
 * @param {string}   containerId — ID of the .tags container to re-render into
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
      renderTagChips(containerId, updated, (removed) => {
        // Inline onRemove: filter and re-render.
        const after = getArray().filter(t => t !== removed);
        setArray(after);
        renderTagChips(containerId, after, arguments.callee);
      });

      // Clear the input field ready for the next tag.
      input.value = '';
    }
  });
}

/**
 * submitProfile — collect form data and save it to the backend.
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
 * renderPremiumSection — display the user's current plan in the premium section.
 *
 * Free users see:   quota usage stats + "Premium olish" button.
 * Premium users see: "Premium ⚡" badge + subscription expiry date.
 *
 * @param {object} user — the user object from the backend
 */
function renderPremiumSection(user) {
  const section = document.getElementById('premium-section');
  if (!section) return;

  if (user.is_premium) {
    // Format the expiry date as DD.MM.YYYY.
    let expiryStr = '';
    if (user.premium_expires_at) {
      const d = new Date(user.premium_expires_at);
      // Zero-pad day and month for consistent formatting.
      const dd   = String(d.getDate()).padStart(2, '0');
      const mm   = String(d.getMonth() + 1).padStart(2, '0');
      const yyyy = d.getFullYear();
      expiryStr = `${dd}.${mm}.${yyyy}`;
    }

    // Render the Premium badge and expiry.
    section.innerHTML = `
      <span class="badge badge--accent">Premium ⚡</span>
      <p class="text-secondary" style="margin-top:0.5rem;">Obuna: ${expiryStr || 'Faol'}</p>
    `;
  } else {
    // Free user: show quota usage and upgrade button.
    // Quota counts come from the user object if the backend exposes them.
    const aiUsed      = user.daily_ai_count      || 0;
    const srsUsed     = user.daily_srs_count     || 0;
    const speakUsed   = user.daily_speak_count   || 0;

    section.innerHTML = `
      <span class="badge" style="background:var(--color-bg-surface);color:var(--color-text-secondary);">Bepul reja</span>
      <p class="text-secondary" style="margin-top:0.5rem;font-size:var(--text-sm);">
        AI: ${aiUsed}/10 | SRS: ${srsUsed}/10 | Gaplash: ${speakUsed}/5
      </p>
      <button class="btn btn--primary btn--full" id="profile-upgrade-btn" style="margin-top:0.75rem;">
        Premium olish — $2/oy ⚡
      </button>
    `;

    // Wire the upgrade button to open the payment modal.
    const upgradeBtn = document.getElementById('profile-upgrade-btn');
    if (upgradeBtn) {
      upgradeBtn.addEventListener('click', () => {
        // Show the premium upgrade modal with a generic profile prompt.
        if (window.Payment) Payment.showUpgradeModal('profile');
      });
    }
  }
}

// Expose loadProfile globally so payment.js can call it after a successful payment.
window.loadProfile = loadProfile;

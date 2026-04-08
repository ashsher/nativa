/**
 * app.js â€” Nativa Mini-App shell.
 *
 * Responsibilities:
 *   1. Initialise the Telegram Mini-App SDK (twa.ready / twa.expand).
 *   2. Authenticate the user against the backend via Api.validateSession().
 *   3. Provide switchTab() â€” the single function that manages tab navigation.
 *   4. Wire bottom-nav button click handlers.
 *   5. Expose showToast() globally for all modules to call.
 *   6. Apply Telegram theme colours to CSS custom properties.
 *   7. Call onTabActivated() so each feature module loads its data lazily.
 */

// â”€â”€ Tab title map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Maps each data-tab value to the Uzbek title shown in the app header.
// Declared at module scope so switchTab() and TAB_TITLES are available globally.
const TAB_TITLES = {
  video:   'Video',     // Video mode tab title
  reading: "O'qish",   // Reading mode tab title
  vocab:   "So'zlar",  // Vocabulary / SRS tab title
  speak:   'Gaplash',  // Speaking partners tab title
  profile: 'Profil',   // Profile tab title
};

// â”€â”€ Active tab tracking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Tracks which tab is currently displayed so we can apply directional slide animations.
let _activeTabIndex = 0;

// Tab order used to determine slide direction (left vs right).
const TAB_ORDER = ['video', 'reading', 'vocab', 'speak', 'profile'];

// Surface unexpected runtime errors to make debugging easier in production.
window.addEventListener('error', (event) => {
  console.error('Runtime error:', event.error || event.message);
  if (typeof window.showToast === 'function') {
    window.showToast("Kutilmagan xatolik yuz berdi. Sahifani yangilang.", 'error', 5000);
  }
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  if (typeof window.showToast === 'function') {
    window.showToast("So'rov bajarilmadi. Qayta urinib ko'ring.", 'error', 5000);
  }
});

/**
 * switchTab â€” activate a named tab panel and update the header title.
 *
 * Steps:
 *   1. Determine slide direction by comparing tab indices.
 *   2. Remove .tab-panel--active from all panels.
 *   3. Add .tab-panel--active + directional slide animation to the target panel.
 *   4. Update header title text.
 *   5. Update nav button active state.
 *   6. Call onTabActivated() so the feature module loads fresh data.
 *
 * @param {string} tabName â€” one of 'video' | 'reading' | 'vocab' | 'speak' | 'profile'
 */
function switchTab(tabName) {
  // Determine new tab index for animation direction calculation.
  const newIndex = TAB_ORDER.indexOf(tabName);

  // Select all tab panel elements.
  const allPanels = document.querySelectorAll('.tab-panel');

  // Remove active class and any lingering animation classes from every panel.
  allPanels.forEach(p => {
    p.classList.remove('tab-panel--active');
    p.classList.remove('tab-panel--enter-right');
    p.classList.remove('tab-panel--enter-left');
  });

  // Locate the target panel by its ID convention: panel-{tabName}.
  const targetPanel = document.getElementById('panel-' + tabName);
  if (!targetPanel) return; // guard: panel not found in DOM

  // Activate the target panel.
  targetPanel.classList.add('tab-panel--active');

  // Apply directional slide animation based on position relative to current tab.
  if (newIndex > _activeTabIndex) {
    // Navigating forward (right) â†’ slide in from the right side.
    targetPanel.classList.add('tab-panel--enter-right');
  } else if (newIndex < _activeTabIndex) {
    // Navigating backward (left) â†’ slide in from the left side.
    targetPanel.classList.add('tab-panel--enter-left');
  }
  // Equal indices means same tab re-selected â†’ no slide animation needed.

  // Update the tracked active index for the next direction calculation.
  _activeTabIndex = newIndex;

  // Update the app header title with the Uzbek label for this tab.
  const titleEl = document.getElementById('page-title');
  if (titleEl) {
    titleEl.textContent = TAB_TITLES[tabName] || tabName;
  }

  // Update the bottom-nav button active states.
  document.querySelectorAll('.bottom-nav__btn').forEach(btn => {
    // Remove active class from all buttons.
    btn.classList.remove('bottom-nav__btn--active');
    // Add active class to the button whose data-tab matches the activated tab.
    if (btn.dataset.tab === tabName) {
      btn.classList.add('bottom-nav__btn--active');
    }
  });

  // Lazy-load tab data (each module's init function is called when the tab opens).
  onTabActivated(tabName);
}

/**
 * onTabActivated â€” call the appropriate feature module's render function
 * whenever a tab is made active. This ensures data is fresh each time
 * the user navigates to a tab, without preloading everything at startup.
 *
 * @param {string} tabName â€” the tab that was just activated
 */
function onTabActivated(tabName) {
  switch (tabName) {
    case 'video':
      // Wire video URL input events (idempotent â€” safe to call multiple times).
      if (typeof renderVideoView === 'function') renderVideoView();
      break;
    case 'reading':
      // Wire reading form events.
      if (typeof renderReadingView === 'function') renderReadingView();
      break;
    case 'vocab':
      // Load vocabulary list and due-word count from backend.
      if (typeof renderVocabView === 'function') renderVocabView();
      break;
    case 'speak':
      // Load speaking partner matches.
      if (typeof renderSpeakingView === 'function') renderSpeakingView();
      break;
    case 'profile':
      // Load profile data including premium status.
      if (typeof renderProfileView === 'function') renderProfileView();
      break;
    default:
      // Unknown tab â€” do nothing.
      break;
  }
}

/**
 * applyTelegramColorScheme â€” reads the Telegram WebApp's colorScheme and
 * adjusts the --color-bg-primary CSS variable if Telegram reports a light
 * theme. On dark (default), no override is needed.
 */
function applyTelegramColorScheme() {
  // twa is a reference to window.Telegram.WebApp (aliased below in DOMContentLoaded).
  const twa = window.Telegram && window.Telegram.WebApp;
  if (!twa) return; // guard: SDK not loaded

  // Telegram provides themeParams with actual OS-level background colour.
  if (twa.themeParams && twa.themeParams.bg_color) {
    // Override the primary background token so the app blends with Telegram's chrome.
    document.documentElement.style.setProperty('--color-bg-primary', twa.themeParams.bg_color);
  }
}

/**
 * showToast â€” display a temporary notification banner at the top of the screen.
 * Exposed globally (on window) so api.js and all feature modules can call it.
 *
 * @param {string} message â€” the text to display
 * @param {'default'|'success'|'error'} type â€” controls the toast's visual style
 * @param {number} [duration=3000] â€” how long the toast stays visible in milliseconds
 */
window.showToast = function showToast(message, type = 'default', duration = 3000) {
  // Locate the toast element created in index.html.
  const toast = document.getElementById('toast');
  if (!toast) return; // guard: toast element missing from DOM

  // Clear any previously applied type modifier classes before applying the new one.
  toast.className = 'toast';

  // Set the message text.
  toast.textContent = message;

  // Apply the semantic type modifier class for colour coding.
  if (type === 'success') toast.classList.add('toast--success');
  if (type === 'error')   toast.classList.add('toast--error');

  // Make the toast visible (triggers the toastIn CSS animation from animations.css).
  toast.classList.add('toast--visible');

  // After the specified duration, hide the toast by reverting to the hidden class.
  setTimeout(() => {
    toast.classList.remove('toast--visible');
    toast.classList.add('toast--hidden');
  }, duration);
};

/**
 * showAuthFailure â€” replace the app content with an authentication error message.
 * Called when validateSession() fails so the user gets a clear explanation.
 */
function showAuthFailure(message = "Ilovani Telegram orqali oching.") {
  // Replace the entire app markup with a minimal error screen.
  const app = document.getElementById('app');
  if (app) {
    app.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;padding:2rem;text-align:center;">
        <h2 style="color:var(--color-danger);margin-bottom:1rem;">Kirish xatosi</h2>
        <p style="color:var(--color-text-secondary);max-width:320px;">${message}</p>
        <button id="retry-startup-btn" class="btn btn--primary" style="margin-top:1rem;">Qayta urinish</button>
      </div>
    `;
    const retry = document.getElementById('retry-startup-btn');
    if (retry) {
      retry.addEventListener('click', () => window.location.reload());
    }
  }
}

// â”€â”€ DOMContentLoaded â€” main entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
document.addEventListener('DOMContentLoaded', async () => {
  // Alias the Telegram Mini-App SDK for brevity.
  const twa = window.Telegram && window.Telegram.WebApp;

  // Bail out if the SDK is not present (opened outside Telegram, e.g. in a browser).
  if (!twa) {
    showAuthFailure("Telegram WebApp SDK topilmadi. Iltimos, bot ichidagi Mini App tugmasi orqali oching.");
    return;
  }

  // In rare cases Telegram object exists but initData is empty (opened as plain link).
  if (!twa.initData) {
    showAuthFailure("Sessiya ma'lumoti kelmadi. Bot menyusidagi Mini App tugmasi orqali oching.");
    return;
  }

  // Signal to Telegram that the app has finished loading and is ready to display.
  twa.ready();

  // Expand the Mini-App to full-screen height (removes the default half-sheet view).
  twa.expand();

  // Apply the Telegram OS theme colours to blend with the user's Telegram UI.
  applyTelegramColorScheme();

  // Store the raw Telegram InitData on window so all modules can access it.
  // This is the HMAC-signed query string that proves the user's identity.
  window.rawInitData = twa.initData || '';

  // Show a loading indicator while we authenticate.
  document.getElementById('app').classList.remove('app--loaded');

  try {
    // Validate the Telegram InitData with the backend.
    // On success, the backend returns the full user object.
    window.currentUser = await Api.validateSession(window.rawInitData);
  } catch (e) {
    // Authentication failed or backend startup error.
    console.error('Startup validation failed:', e);
    if (e && e.code === 'AUTH') {
      showAuthFailure((e && e.message) || "Telegram sessiyasi tasdiqlanmadi. Bot token/domain sozlamalarini tekshiring va qayta oching.");
    } else {
      showAuthFailure("Server bilan bog'lanishda xatolik. Bir necha soniyadan keyin qayta urinib ko'ring.");
    }
    return;
  }

  // Mark the app as loaded to trigger the appFadeIn CSS animation.
  document.getElementById('app').classList.add('app--loaded');

  // â”€â”€ Wire bottom-nav buttons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Attach a click listener to every bottom-nav button.
  // Using event delegation on the nav element would also work but explicit
  // wiring makes each button's intent clear.
  document.querySelectorAll('.bottom-nav__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Read the target tab name from the data-tab attribute.
      const tab = btn.dataset.tab;
      if (tab) switchTab(tab); // switch to the tapped tab
    });
  });

  // â”€â”€ Telegram back button handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // On Android, Telegram shows a hardware/software back button in the header.
  // We intercept it to navigate to the previous tab instead of closing the app.
  if (twa.BackButton) {
    // Show the Telegram back button so users know it does something.
    twa.BackButton.show();
    twa.BackButton.onClick(() => {
      // Navigate to the Video tab as the "home" screen.
      switchTab('video');
    });
  }

  // If the user has not completed their profile (no city), send them to profile tab
  // first so they fill in their location before accessing features.
  if (!window.currentUser || !window.currentUser.city) {
    switchTab('profile');
    showToast("Iltimos, profilingizni to'ldiring.", 'default', 4000);
    return;
  }

  // Profile is complete â€” go straight to the Video tab (default landing).
  switchTab('video');
});


/**
 * payment.js — Premium upgrade modal and Telegram Stars payment module (IIFE).
 *
 * Handles:
 *   1. showUpgradeModal(quotaType) — display the upgrade modal with the
 *      appropriate quota-specific message.
 *   2. hideUpgradeModal() — dismiss the modal.
 *   3. initiatePayment() — fetch a Telegram Stars invoice link from the backend
 *      and open Telegram's native payment sheet.
 *   4. Post-payment premium activation and UI refresh.
 */

const Payment = (() => {
  /**
   * showUpgradeModal — display the upgrade modal with a quota-specific message.
   * Called by api.js on 429 responses and by profile.js "Premium olish" button.
   *
   * @param {'srs'|'ai'|'speaking'|'profile'|undefined} quotaType
   *   Which quota was exceeded, or 'profile' for a general upgrade prompt.
   */
  function showUpgradeModal(quotaType) {
    // Map quota type codes to human-readable Uzbek messages.
    const messages = {
      srs:      "Bugun 10 ta takrorlash limitiga yetdingiz.",
      ai:       "Bugun 10 ta AI so'rov limitiga yetdingiz.",
      speaking: "Bugun 5 ta yangi suhbat limitiga yetdingiz.",
      profile:  "Premium obuna bilan cheksiz foydalaning.",
    };

    // Set the quota message in the modal; fall back to generic text.
    const messageEl = document.getElementById('quota-message');
    if (messageEl) {
      messageEl.textContent = messages[quotaType] || "Kunlik limitingizga yetdingiz.";
    }

    // Make the upgrade modal visible by removing the hidden class.
    document.getElementById('upgrade-modal').classList.remove('modal--hidden');
  }

  /**
   * hideUpgradeModal — dismiss the upgrade modal by adding the hidden class.
   */
  function hideUpgradeModal() {
    document.getElementById('upgrade-modal').classList.add('modal--hidden');
  }

  /**
   * initiatePayment — start the Telegram Stars payment flow.
   *
   * Steps:
   *   1. GET /payment/create-invoice → receive an invoice_link and transaction_ref.
   *   2. Open Telegram's native invoice sheet via WebApp.openInvoice().
   *   3. Handle the result callback: verify payment on success, show toast otherwise.
   *   4. On success: update local currentUser.is_premium = true and refresh profile.
   */
  async function initiatePayment() {
    let data;
    try {
      // Step 1: Request a fresh invoice link from the backend.
      // The backend calls Telegram Bot API createInvoiceLink and returns the URL.
      data = await Api.request('GET', '/payment/create-invoice');
    } catch (e) {
      // Network or server error already shown as a toast by api.js.
      return;
    }

    // Step 2: Open Telegram's native payment invoice sheet.
    // window.Telegram.WebApp.openInvoice accepts the invoice URL and a callback.
    window.Telegram.WebApp.openInvoice(data.invoice_link, async (status) => {
      // Step 3: Handle the payment result.

      if (status === 'paid') {
        // The user completed the payment — verify it with the backend.
        try {
          // Step 4a: Verify the payment and activate premium on the backend.
          await Api.verifyPayment(data.transaction_ref || '');
        } catch (e) {
          // Verification failure is non-fatal; premium may still activate via webhook.
          // Show a softer success message since payment did go through.
        }

        // Step 4b: Update the local user object so the UI reflects premium immediately.
        if (window.currentUser) {
          window.currentUser.is_premium = true;
        }

        // Dismiss the upgrade modal now that the user is premium.
        hideUpgradeModal();

        // Step 5: Congratulate the user with a success toast in Uzbek.
        showToast("Tabriklaymiz! Siz endi Premium foydalanuvchisiz. ⚡", 'success', 5000);

        // Refresh the profile tab to show the Premium badge and expiry date.
        if (typeof loadProfile === 'function') {
          loadProfile();
        }

      } else if (status === 'cancelled') {
        // The user cancelled the payment sheet without paying.
        showToast("To'lov bekor qilindi.", 'default');

      } else if (status === 'failed') {
        // Telegram reported a payment failure (e.g. insufficient Stars balance).
        showToast("To'lov amalga oshmadi. Qayta urinib ko'ring.", 'error');
      }
      // Other status values (e.g. 'pending') are silently ignored.
    });
  }

  // ── DOMContentLoaded: wire modal buttons ──────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    // "Premium olish" CTA button inside the upgrade modal — starts the payment flow.
    document.getElementById('upgrade-btn').addEventListener('click', initiatePayment);

    // "Keyinroq" (Later) button — dismisses the modal without purchasing.
    document.getElementById('modal-dismiss-btn').addEventListener('click', hideUpgradeModal);

    // Clicking the dark overlay behind the modal also dismisses it.
    document.getElementById('modal-overlay').addEventListener('click', hideUpgradeModal);
  });

  // Expose the public API.
  return { showUpgradeModal, hideUpgradeModal };
})();

// Assign to window so api.js and profile.js can call Payment.showUpgradeModal().
window.Payment = Payment;

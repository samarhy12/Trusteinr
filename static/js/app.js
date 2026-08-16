// Register service worker for PWA support
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

document.addEventListener("DOMContentLoaded", () => {
  // ---- Prevent double-submission on every form (critical for financial actions) ----
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      // If the form has its own validation/confirm that can cancel submission,
      // respect that — only lock the button once the submit is actually proceeding.
      requestAnimationFrame(() => {
        if (event.defaultPrevented) return;
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && !submitBtn.disabled) {
          submitBtn.dataset.originalText = submitBtn.innerHTML;
          submitBtn.disabled = true;
          submitBtn.classList.add("opacity-70", "cursor-not-allowed");
          submitBtn.innerHTML = '<span class="inline-flex items-center gap-2">'
            + '<svg class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">'
            + '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
            + '<path class="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>'
            + '</svg>Please wait…</span>';
        }
      });
    });
  });

  // ---- Loan schedule live preview (loans/new) ----
  const principalInput = document.querySelector("[data-loan-principal]");
  const startDateInput = document.querySelector("[data-loan-start]");
  const termInputs = document.querySelectorAll("[data-loan-term]");
  const durationInput = document.querySelector("[data-loan-duration]");
  const rateInput = document.querySelector("[data-loan-rate]");
  const rateChoiceInputs = document.querySelectorAll('input[name="interest_choice"]');
  const previewBox = document.querySelector("[data-loan-preview]");

  if (principalInput && previewBox) {
    const standardRatePct = previewBox.dataset.standardRate || "10";

    const updatePreview = () => {
      const principal = principalInput.value;
      const start = startDateInput ? startDateInput.value : "";
      const termEl = document.querySelector("[data-loan-term]:checked");
      const term = termEl ? termEl.value : "daily";
      const duration = durationInput ? durationInput.value : "";
      const rateChoiceEl = document.querySelector('input[name="interest_choice"]:checked');
      const rateChoice = rateChoiceEl ? rateChoiceEl.value : "standard";
      const ratePct = rateChoice === "custom" && rateInput ? rateInput.value : standardRatePct;

      if (!principal || Number(principal) <= 0 || !duration || Number(duration) <= 0 || !ratePct || Number(ratePct) <= 0) {
        previewBox.innerHTML = '<p class="text-ink-400 text-sm">Fill in the loan amount, duration and interest rate to see the repayment schedule.</p>';
        return;
      }

      const params = new URLSearchParams({
        principal, term_type: term, start_date: start,
        duration_value: duration, rate_pct: ratePct,
      });
      fetch(`/loans/preview?${params.toString()}`)
        .then((r) => r.json())
        .then((data) => {
          if (!data.ok) {
            previewBox.innerHTML = '<p class="text-ink-400 text-sm">Enter valid loan details to preview the schedule.</p>';
            return;
          }
          previewBox.innerHTML = `
            <div class="field mb-4">
              <label>Total interest (${ratePct}%/month)</label>
              <div class="ledger-figure text-lg">GHS ${data.total_interest}</div>
            </div>
            <div class="field mb-4">
              <label>Total repayable</label>
              <div class="ledger-figure text-lg text-navy-800">GHS ${data.total_repayable}</div>
            </div>
            <div class="field mb-4">
              <label>Installment (&times; ${data.num_installments})</label>
              <div class="ledger-figure text-lg">GHS ${data.installment}</div>
            </div>
            <div class="field">
              <label>Loan matures on</label>
              <div class="font-semibold">${data.end_date}</div>
            </div>
          `;
        })
        .catch(() => {});
    };

    principalInput.addEventListener("input", updatePreview);
    if (startDateInput) startDateInput.addEventListener("change", updatePreview);
    if (durationInput) durationInput.addEventListener("input", updatePreview);
    if (rateInput) rateInput.addEventListener("input", updatePreview);
    termInputs.forEach((el) => el.addEventListener("change", updatePreview));
    rateChoiceInputs.forEach((el) => el.addEventListener("change", updatePreview));
    updatePreview();
  }
});

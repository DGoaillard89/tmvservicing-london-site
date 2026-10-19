// ---------------------------------------------------------------------------
// "Get a quote" enquiry form.
// Submissions go to the Cloudflare Worker relay "konda-enquiries", which holds
// the Airtable token and creates the CRM record. The token is NEVER in this site.
//
// This domain (tmvservicing.london, with and without www) is in the relay's ALLOWED_ORIGINS (worker/wrangler.toml in the Konda repo).
// If ENQUIRY_ENDPOINT is ever emptied, the form asks visitors to phone instead.
// ---------------------------------------------------------------------------
const ENQUIRY_ENDPOINT = "https://konda-enquiries.daniel-10c.workers.dev";
const ENQUIRY_TYPE = "TMV Servicing";
const PHONE = "020 3633 6064";

(() => {
  // Pages in sub-folders (blog/, areas/) set data-root="../" so links still work.
  const ROOT = document.body.dataset.root || "";

  document.body.insertAdjacentHTML(
    "beforeend",
    `
  <dialog class="enquiry" id="enquiry" aria-labelledby="enquiry-title">
    <button class="enquiry__close" type="button" aria-label="Close" data-close-enquiry>
      <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" /></svg>
    </button>

    <form class="enquiry__form" id="enquiry-form" novalidate>
      <span class="eyebrow">Free, no-obligation quote</span>
      <h2 id="enquiry-title">Get in touch</h2>
      <p class="enquiry__lede">Tell us about your building and roughly how many TMVs you've got (a guess is fine). We'll come back with a fixed quote.</p>

      <div class="field-grid">
        <label class="field">
          <span>Name</span>
          <input name="name" type="text" autocomplete="name" required maxlength="120" />
          <em class="field__msg">Please enter your name.</em>
        </label>
        <label class="field">
          <span>Email</span>
          <input name="email" type="email" autocomplete="email" required maxlength="200" />
          <em class="field__msg">Please enter a valid email address.</em>
        </label>
        <label class="field">
          <span>Phone</span>
          <input name="phone" type="tel" autocomplete="tel" required maxlength="40" />
          <em class="field__msg">Please enter a valid phone number.</em>
        </label>
        <label class="field">
          <span>Postcode</span>
          <input name="postcode" type="text" autocomplete="postal-code" required maxlength="12" />
          <em class="field__msg">Please enter a valid UK postcode.</em>
        </label>
        <label class="field field--full">
          <span>How can we help?</span>
          <textarea name="message" rows="4" required maxlength="5000" placeholder="e.g. 40-flat mansion block in Maida Vale, around 60 TMVs, nobody's serviced them in a while"></textarea>
          <em class="field__msg">Please tell us a little about your enquiry.</em>
        </label>
      </div>

      <!-- Spam trap: hidden from people, bots tend to fill it in -->
      <input class="enquiry__trap" name="company_website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true" />

      <p class="enquiry__error" id="enquiry-error" role="alert"></p>

      <button class="btn btn--brick enquiry__submit" type="submit">
        <span class="enquiry__submit-label">Send enquiry</span>
        <span class="enquiry__spinner" aria-hidden="true"></span>
      </button>
      <p class="enquiry__small">Prefer to talk? Call <a href="tel:+442036336064">${PHONE}</a>. We only use your details to respond to this enquiry. See our <a href="${ROOT}privacy.html">privacy notice</a>.</p>
    </form>

    <div class="enquiry__done" id="enquiry-done" hidden>
      <div class="enquiry__tick">
        <svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
      </div>
      <h2>Thanks, we've got it.</h2>
      <p class="enquiry__lede">One of the team will be in touch shortly. If it's urgent, call us on ${PHONE}.</p>
      <button class="btn btn--brick" type="button" data-close-enquiry>Close</button>
    </div>
  </dialog>`
  );

  const dialog = document.getElementById("enquiry");
  const form = document.getElementById("enquiry-form");
  const done = document.getElementById("enquiry-done");
  const errorEl = document.getElementById("enquiry-error");
  const submit = form.querySelector(".enquiry__submit");

  // Buttons can name a service, e.g. data-open-enquiry="TMV servicing",
  // which pre-fills the message so the visitor doesn't have to type it.
  function open(topic) {
    form.hidden = false;
    done.hidden = true;
    errorEl.textContent = "";
    if (topic && !form.elements.message.value.trim()) {
      form.elements.message.value = `I'm interested in: ${topic}.\n\n`;
    }
    dialog.showModal();
    document.body.classList.add("modal-open");
    form.elements.name.focus();
  }

  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-open-enquiry]");
    if (trigger) open(trigger.dataset.openEnquiry);
  });
  dialog.querySelectorAll("[data-close-enquiry]").forEach((b) => b.addEventListener("click", () => dialog.close()));
  dialog.addEventListener("close", () => document.body.classList.remove("modal-open"));

  // Close when clicking the dimmed backdrop
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });

  const checks = {
    name: (v) => v.length >= 2,
    email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
    phone: (v) => v.replace(/\D/g, "").length >= 10,
    postcode: (v) => /^[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}$/.test(v),
    message: (v) => v.length >= 2,
  };

  function validate() {
    let first = null;
    for (const [name, check] of Object.entries(checks)) {
      const input = form.elements[name];
      const ok = check(input.value.trim());
      input.closest(".field").classList.toggle("is-invalid", !ok);
      input.setAttribute("aria-invalid", String(!ok));
      if (!ok && !first) first = input;
    }
    if (first) {
      errorEl.textContent = "Please check the highlighted fields.";
      first.focus();
      return false;
    }
    errorEl.textContent = "";
    return true;
  }

  form.addEventListener("input", (e) => {
    const field = e.target.closest(".field");
    if (field?.classList.contains("is-invalid")) {
      field.classList.remove("is-invalid");
      e.target.removeAttribute("aria-invalid");
    }
  });

  // Tidy the postcode into capitals with a single space, e.g. "w45py" -> "W4 5PY"
  const formatPostcode = (v) => {
    const pc = v.replace(/\s+/g, "").toUpperCase();
    return pc.length > 3 ? `${pc.slice(0, -3)} ${pc.slice(-3)}` : pc;
  };
  form.elements.postcode.addEventListener("blur", (e) => {
    if (checks.postcode(e.target.value.trim())) e.target.value = formatPostcode(e.target.value);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validate()) return;

    if (!ENQUIRY_ENDPOINT) {
      errorEl.innerHTML = `Our online form isn't quite ready yet. Please call us on <a href="tel:+442036336064">${PHONE}</a>.`;
      return;
    }

    const data = Object.fromEntries(
      ["name", "email", "phone", "postcode", "message", "company_website"].map((k) => [k, form.elements[k].value.trim()])
    );
    data.postcode = formatPostcode(data.postcode);
    data.enquiryType = ENQUIRY_TYPE;

    submit.disabled = true;
    submit.classList.add("is-sending");
    try {
      const res = await fetch(ENQUIRY_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      form.reset();
      form.hidden = true;
      done.hidden = false;
    } catch (err) {
      console.error("Enquiry failed:", err);
      errorEl.innerHTML = `Sorry, something went wrong sending your enquiry. Please try again, or call us on <a href="tel:+442036336064">${PHONE}</a>.`;
    } finally {
      submit.disabled = false;
      submit.classList.remove("is-sending");
    }
  });
})();

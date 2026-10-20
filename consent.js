// Cookie consent, Google Tag Manager and ad-tracking events.
//
// GTM_ID is filled in by the marketing agency, e.g. "GTM-ABC1234".
// While it's empty nothing loads, no banner shows and no cookies are set.
//
// How it works ("basic" Google Consent Mode v2):
//  - Consent defaults are all "denied" and GTM is NOT loaded until the visitor
//    accepts analytics or advertising cookies in the banner.
//  - The choice is kept in localStorage "cookie_consent" and can be changed any
//    time from the "Cookie settings" button in the footer.
//  - Events are pushed to window.dataLayer whether or not GTM is loaded:
//      generate_lead  (enquiry.js, on a successful form submit)
//      enquiry_open   (enquiry.js, when the quote form opens)
//      phone_click    (here, on any tel: link)
//  - Ad click IDs and UTM tags from the landing URL are kept in memory (and in
//    sessionStorage once consent is given) so enquiry.js can note them on the lead.

const GTM_ID = "";

(() => {
  const KEY = "cookie_consent";
  const ATTRIB_KEY = "ad_attrib";
  const ATTRIB_PARAMS = ["gclid", "gbraid", "wbraid", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
  const root = document.body.dataset.root || "";

  window.dataLayer = window.dataLayer || [];
  function gtag() {
    window.dataLayer.push(arguments);
  }

  gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
    functionality_storage: "granted",
    security_storage: "granted",
    wait_for_update: 500,
  });

  // ---- Stored choice ------------------------------------------------------
  function readChoice() {
    try {
      const c = JSON.parse(localStorage.getItem(KEY));
      return c && c.v === 1 ? c : null;
    } catch {
      return null;
    }
  }

  function saveChoice(analytics, ads) {
    const c = { v: 1, analytics: !!analytics, ads: !!ads, ts: new Date().toISOString() };
    try {
      localStorage.setItem(KEY, JSON.stringify(c));
    } catch {}
    return c;
  }

  // ---- Attribution (gclid / UTM) ------------------------------------------
  let attrib = {};
  try {
    attrib = JSON.parse(sessionStorage.getItem(ATTRIB_KEY)) || {};
  } catch {}
  const params = new URLSearchParams(location.search);
  const fromUrl = {};
  ATTRIB_PARAMS.forEach((k) => {
    const v = params.get(k);
    if (v) fromUrl[k] = v.slice(0, 200);
  });
  if (Object.keys(fromUrl).length) attrib = fromUrl; // a new ad click replaces the old one

  function keepAttrib(choice) {
    if (!choice || !(choice.analytics || choice.ads) || !Object.keys(attrib).length) return;
    try {
      sessionStorage.setItem(ATTRIB_KEY, JSON.stringify(attrib));
    } catch {}
  }

  // ---- GTM ----------------------------------------------------------------
  let gtmLoaded = false;
  function applyChoice(choice) {
    gtag("consent", "update", {
      analytics_storage: choice.analytics ? "granted" : "denied",
      ad_storage: choice.ads ? "granted" : "denied",
      ad_user_data: choice.ads ? "granted" : "denied",
      ad_personalization: choice.ads ? "granted" : "denied",
    });
    keepAttrib(choice);
    if (!gtmLoaded && GTM_ID && (choice.analytics || choice.ads)) {
      gtmLoaded = true;
      window.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
      const s = document.createElement("script");
      s.async = true;
      s.src = "https://www.googletagmanager.com/gtm.js?id=" + encodeURIComponent(GTM_ID);
      document.head.appendChild(s);
    }
  }

  // ---- Banner -------------------------------------------------------------
  let banner;
  function buildBanner() {
    banner = document.createElement("div");
    banner.className = "cc";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-labelledby", "cc-title");
    banner.setAttribute("aria-describedby", "cc-text");
    banner.hidden = true;
    banner.innerHTML = `
      <div class="cc__inner">
        <div class="cc__copy">
          <h2 class="cc__title" id="cc-title">Cookies, briefly</h2>
          <p id="cc-text">We'd like to use Google Analytics to see how the site is used, and Google Ads cookies so we can measure our adverts and show them to people who've visited before. They only switch on if you say yes. <a href="${root}privacy.html#cookies">More in our privacy notice</a>.</p>
        </div>
        <form class="cc__choose" hidden>
          <label class="cc__opt"><input type="checkbox" name="analytics" /> <span><b>Analytics</b> Counting visits and which pages help.</span></label>
          <label class="cc__opt"><input type="checkbox" name="ads" /> <span><b>Advertising</b> Measuring our Google ads and showing them to past visitors.</span></label>
        </form>
        <div class="cc__actions">
          <button type="button" class="cc__btn" data-cc="accept">Accept all</button>
          <button type="button" class="cc__btn" data-cc="reject">Reject all</button>
          <button type="button" class="cc__btn cc__btn--quiet" data-cc="choose" aria-expanded="false">Choose</button>
          <button type="button" class="cc__btn" data-cc="save" hidden>Save choices</button>
        </div>
      </div>`;
    document.body.appendChild(banner);

    const choose = banner.querySelector(".cc__choose");
    const chooseBtn = banner.querySelector('[data-cc="choose"]');
    const saveBtn = banner.querySelector('[data-cc="save"]');

    banner.addEventListener("click", (e) => {
      const action = e.target.closest("[data-cc]")?.dataset.cc;
      if (!action) return;
      if (action === "accept") decide(true, true);
      if (action === "reject") decide(false, false);
      if (action === "save") decide(choose.elements.analytics.checked, choose.elements.ads.checked);
      if (action === "choose") {
        const opening = choose.hidden;
        choose.hidden = !opening;
        saveBtn.hidden = !opening;
        chooseBtn.setAttribute("aria-expanded", String(opening));
        if (opening) choose.elements.analytics.focus();
      }
    });
    banner.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && readChoice()) hideBanner();
    });
  }

  let returnFocus = null;
  function showBanner(fromButton) {
    if (!banner) buildBanner();
    const c = readChoice();
    const choose = banner.querySelector(".cc__choose");
    choose.elements.analytics.checked = !!c?.analytics;
    choose.elements.ads.checked = !!c?.ads;
    banner.hidden = false;
    document.body.classList.add("cc-open");
    if (fromButton) {
      returnFocus = fromButton;
      banner.querySelector('[data-cc="accept"]').focus();
    }
  }

  function hideBanner() {
    banner.hidden = true;
    document.body.classList.remove("cc-open");
    if (returnFocus) returnFocus.focus();
    returnFocus = null;
  }

  function decide(analytics, ads) {
    const c = saveChoice(analytics, ads);
    applyChoice(c);
    hideBanner();
  }

  // ---- Phone clicks -------------------------------------------------------
  document.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="tel:"]');
    if (!a) return;
    let where = "body";
    if (a.closest(".mobile-bar")) where = "mobile_bar";
    else if (a.closest("header, .site-header, .strip")) where = "header";
    else if (a.closest("footer")) where = "footer";
    else if (a.closest(".hero, .page-hero")) where = "hero";
    window.dataLayer.push({ event: "phone_click", link_location: where, page_path: location.pathname });
  });

  // ---- Public helpers for enquiry.js ---------------------------------------
  window.siteTracking = {
    attribution: () => ({ ...attrib }),
    push: (obj) => window.dataLayer.push(obj),
  };

  // ---- Start --------------------------------------------------------------
  if (!GTM_ID) return; // not configured: no banner, no cookies, no third-party scripts

  document.querySelectorAll("[data-cookie-settings]").forEach((b) => {
    b.hidden = false;
    b.addEventListener("click", () => showBanner(b));
  });

  const existing = readChoice();
  if (existing) applyChoice(existing);
  else showBanner();
})();

(function () {
  const STORAGE_KEY = "meltix_cart";
  const PROMO_KEY = "meltix_cart_promo";
  const FALLBACK_IMAGE = "/static/images/meltix-logo.png";
  const config = window.MeltixCheckoutConfig || {};

  const refs = {};
  let cart = [];
  let totals = { subtotal: 0, shipping_fee: 0, discount_amount: 0, total: 0 };
  let isProcessing = false;

  // ── Utilities ──────────────────────────────────────────────────
  function byId(id) { return document.getElementById(id); }

  function safeParse(raw, fallback) {
    try { const p = JSON.parse(raw); return p ?? fallback; }
    catch { return fallback; }
  }

  function normalizeQty(v) {
    const n = Number(v || 1);
    return Number.isFinite(n) && n > 0 ? Math.max(1, Math.round(n)) : 1;
  }

  function normalizeCustomText(v) {
    return typeof v === "string" ? v.trim() : "";
  }

  function formatPrice(v) {
    const n = Number(v) || 0;
    return "₹ " + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n);
  }

  function escapeHtml(v) {
    return String(v ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function lockBodyScroll() {
    document.documentElement.classList.add("modal-open");
    document.body.classList.add("modal-open");
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
  }

  function unlockBodyScroll() {
    document.documentElement.classList.remove("modal-open");
    document.body.classList.remove("modal-open");
    document.documentElement.style.overflow = "";
    document.body.style.overflow = "";
  }

  function requestJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok && !data.success && !data.message)
        data.message = "Something went wrong. Please try again.";
      return data;
    });
  }

  // ── Cart ───────────────────────────────────────────────────────
  function loadCart() {
    const parsed = safeParse(localStorage.getItem(STORAGE_KEY), []);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => {
      if (!item || item.id == null) return null;
      return {
        id: String(item.id),
        name: String(item.name || "Meltix Creation"),
        price: Number(item.price) || 0,
        qty: normalizeQty(item.qty),
        image: String(item.image || FALLBACK_IMAGE),
        customText: normalizeCustomText(item.customText),
        fragrance: String(item.fragrance || item.scent || "").trim(),
      };
    }).filter(Boolean);
  }

  function getLocalSubtotal() {
    return cart.reduce((s, i) => s + i.price * i.qty, 0);
  }

  function clearCheckoutCart() {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(PROMO_KEY);
    cart = [];
  }

  // ── Totals ─────────────────────────────────────────────────────
  function setTotals(next) {
    totals = {
      subtotal:        Number(next?.subtotal) || 0,
      shipping_fee:    Number(next?.shipping_fee) || 0,
      discount_amount: Number(next?.discount_amount) || 0,
      total:           Number(next?.total) || 0,
    };
    refs.summarySubtotal.textContent = formatPrice(totals.subtotal);
    refs.summaryShipping.textContent  = formatPrice(totals.shipping_fee);
    refs.summaryDiscount.textContent  = "- " + formatPrice(totals.discount_amount);
    refs.summaryTotal.textContent     = formatPrice(totals.total);

    const label = `Proceed to Pay ${formatPrice(totals.total)}`;
    if (refs.payNowBtn)    refs.payNowBtn.textContent    = label;
    if (refs.drawerPayBtn) refs.drawerPayBtn.textContent = `Save & ${label}`;
    if (refs.heroBagTotal) refs.heroBagTotal.textContent = formatPrice(totals.total);
    if (refs.heroCartCount) {
      refs.heroCartCount.textContent = String(cart.reduce((s, i) => s + i.qty, 0));
    }
  }

  // ── Status messages ────────────────────────────────────────────
  function showStatus(el, message, type) {
    if (!el) return;
    el.textContent = message;
    el.classList.remove("is-error", "is-success");
    el.classList.add("is-visible", type === "success" ? "is-success" : "is-error");
  }
  function clearStatus(el) {
    if (!el) return;
    el.textContent = "";
    el.classList.remove("is-visible", "is-error", "is-success");
  }

  function setProcessing(state) {
    isProcessing = Boolean(state);
    if (refs.payNowBtn)    refs.payNowBtn.disabled    = isProcessing || !cart.length;
    if (refs.drawerPayBtn) refs.drawerPayBtn.disabled = isProcessing;

    const label = isProcessing ? "Processing..." : `Proceed to Pay ${formatPrice(totals.total)}`;
    if (refs.payNowBtn)    refs.payNowBtn.textContent    = isProcessing ? "Processing..." : label;
    if (refs.drawerPayBtn) refs.drawerPayBtn.textContent = isProcessing ? "Processing..." : `Save & ${label}`;
  }

  // ── Render items ───────────────────────────────────────────────
  function renderItems() {
    if (!cart.length) {
      refs.emptyState.classList.remove("is-hidden");
      refs.items.style.display = "none";
      setTotals({ subtotal: 0, shipping_fee: 0, discount_amount: 0, total: 0 });
      if (refs.payNowBtn) refs.payNowBtn.disabled = true;
      return;
    }
    refs.emptyState.classList.add("is-hidden");
    refs.items.style.display = "";

    refs.items.innerHTML = cart.map((item) => {
      const custom = item.customText
        ? `<p class="summary-item-custom"><strong>Custom Text:</strong> ${escapeHtml(item.customText)}</p>`
        : "";
      return [
        '<article class="summary-item">',
        `  <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}'">`,
        "  <div>",
        `    <h3 class="summary-item-title">${escapeHtml(item.name)}</h3>`,
        `    <p class="summary-item-meta">Qty: ${item.qty} • ${formatPrice(item.price)} each</p>`,
        custom,
        "  </div>",
        "</article>",
      ].join("");
    }).join("");

    const sub = getLocalSubtotal();
    setTotals({ subtotal: sub, shipping_fee: 0, discount_amount: 0, total: sub });
  }

  // ── Prefill helpers ────────────────────────────────────────────
  function setInputValue(id, value) {
    const el = byId(id);
    if (el) el.value = value || "";
  }

  function applyPrefill() {
    const p = config.prefill || {};
    const sh = p.shipping || {};
    const bi = p.billing  || {};
    setInputValue("checkoutName",       p.name  || "");
    setInputValue("checkoutEmail",      p.email || "");
    setInputValue("checkoutPhone",      p.phone || "");
    setInputValue("shippingLine1",      sh.line1       || "");
    setInputValue("shippingLine2",      sh.line2       || "");
    setInputValue("shippingCity",       sh.city        || "");
    setInputValue("shippingState",      sh.state       || "");
    setInputValue("shippingPostalCode", sh.postal_code || "");
    setInputValue("shippingCountry",    sh.country     || "India");
    setInputValue("billingLine1",       bi.line1       || "");
    setInputValue("billingLine2",       bi.line2       || "");
    setInputValue("billingCity",        bi.city        || "");
    setInputValue("billingState",       bi.state       || "");
    setInputValue("billingPostalCode",  bi.postal_code || "");
    setInputValue("billingCountry",     bi.country     || "India");
    refs.billingSameAsShipping.checked = p.billing_same_as_shipping !== false;
    syncBillingVisibility();
  }

  // ── Check if user details are complete ─────────────────────────
  function hasCompleteDetails() {
    const p  = config.prefill || {};
    const sh = p.shipping || {};
    return !!(
      p.name  && p.name.trim()  &&
      p.phone && p.phone.trim() &&
      p.email && p.email.trim() &&
      sh.line1       && sh.line1.trim()       &&
      sh.city        && sh.city.trim()        &&
      sh.state       && sh.state.trim()       &&
      sh.postal_code && sh.postal_code.trim()
    );
  }

  // ── Drawer ─────────────────────────────────────────────────────
  function openDrawer() {
    refs.drawerOverlay.classList.add("is-open");
    lockBodyScroll();
  }

  function closeDrawer() {
    refs.drawerOverlay.classList.remove("is-open");
    unlockBodyScroll();
    clearStatus(refs.drawerStatus);
  }

  // ── Billing visibility ─────────────────────────────────────────
  function syncBillingRequirements() {
    const same = refs.billingSameAsShipping.checked;
    refs.billingRequiredInputs.forEach((input) => {
      input.required = !same;
      if (same) { input.setCustomValidity(""); input.classList.remove("is-invalid"); }
    });
  }

  function syncBillingVisibility() {
    refs.billingCard.classList.toggle("is-hidden", refs.billingSameAsShipping.checked);
    syncBillingRequirements();
  }

  // ── Form validation ────────────────────────────────────────────
  function clearInputError(input) {
    if (!input) return;
    input.setCustomValidity("");
    input.classList.remove("is-invalid");
  }

  function setInputError(input, message) {
    if (!input) return;
    input.setCustomValidity(message || "Please fill out this field.");
    input.classList.add("is-invalid");
  }

  function applyCustomValidation() {
    const phoneDigits = refs.phone.value.replace(/\D/g, "");
    const shPin       = refs.shippingPostalCode.value.replace(/\D/g, "");
    if (refs.phone.value.trim() && (phoneDigits.length < 10 || phoneDigits.length > 15))
      setInputError(refs.phone, "Please enter a valid phone number.");
    if (refs.shippingPostalCode.value.trim() && shPin.length !== 6)
      setInputError(refs.shippingPostalCode, "PIN Code must be 6 digits.");
    if (!refs.billingSameAsShipping.checked) {
      const biPin = refs.billingPostalCode.value.replace(/\D/g, "");
      if (refs.billingPostalCode.value.trim() && biPin.length !== 6)
        setInputError(refs.billingPostalCode, "Billing PIN Code must be 6 digits.");
    }
  }

  function validateForm() {
    clearStatus(refs.drawerStatus);
    refs.allInputs.forEach(clearInputError);
    syncBillingRequirements();
    applyCustomValidation();
    const ok = refs.form.reportValidity();
    refs.allInputs.forEach((input) => {
      if (input.checkValidity()) input.classList.remove("is-invalid");
      else                       input.classList.add("is-invalid");
    });
    if (!ok) {
      const first = refs.form.querySelector(":invalid");
      if (first) first.focus();
      showStatus(refs.drawerStatus, "Please complete all required delivery details.", "error");
    }
    return ok;
  }

  // ── Build payload ──────────────────────────────────────────────
  function buildAddress(prefix) {
    return {
      name:        refs.name.value.trim(),
      line1:       byId(prefix + "Line1").value.trim(),
      line2:       byId(prefix + "Line2").value.trim(),
      city:        byId(prefix + "City").value.trim(),
      state:       byId(prefix + "State").value.trim(),
      postal_code: byId(prefix + "PostalCode").value.trim(),
      country:     byId(prefix + "Country").value.trim() || "India",
    };
  }

  function buildPayload() {
    const same      = refs.billingSameAsShipping.checked;
    const shipping  = buildAddress("shipping");
    const billing   = same ? { ...shipping } : buildAddress("billing");
    return {
      name:                    refs.name.value.trim(),
      phone:                   refs.phone.value.trim(),
      email:                   refs.email.value.trim().toLowerCase(),
      billing_same_as_shipping: same,
      shipping,
      billing,
      coupon_code: String(localStorage.getItem(PROMO_KEY) || "").trim().toUpperCase(),
      items: cart.map((item) => ({
        id:         item.id,
        qty:        item.qty,
        customText: item.customText,
        fragrance:  item.fragrance,
      })),
    };
  }

  // ── Payment flow ───────────────────────────────────────────────
  function handleVerificationSuccess(result) {
    unlockBodyScroll();
    clearCheckoutCart();
    renderItems();
    showStatus(refs.mainStatus, `Payment verified. Order ${result.order?.order_id || ""} placed successfully.`, "success");
    if (refs.payNowBtn)    { refs.payNowBtn.disabled = true;    refs.payNowBtn.textContent    = "Order Confirmed ✦"; }
    if (refs.drawerPayBtn) { refs.drawerPayBtn.disabled = true; refs.drawerPayBtn.textContent = "Order Confirmed ✦"; }
    const redirectUrl = result.success_url || config.profileUrl || "/profile";
    window.setTimeout(() => { window.location.href = redirectUrl; }, 1400);
  }

  function launchRazorpay(orderData, payload) {
    const keyId = orderData.key_id || config.razorpayKeyId;
    if (!window.Razorpay || !keyId) throw new Error("Razorpay is not configured right now.");

    return new Promise((resolve, reject) => {
      let settled = false;
      function rejectOnce(err) {
        if (settled) return; settled = true;
        unlockBodyScroll();
        reject(err instanceof Error ? err : new Error(String(err || "Payment could not be completed.")));
      }
      function resolveOnce(res) {
        if (settled) return; settled = true;
        unlockBodyScroll();
        resolve(res);
      }

      const rz = new window.Razorpay({
        key:        keyId,
        amount:     orderData.amount_paise,
        currency:   orderData.currency || "INR",
        name:       "Meltix",
        description:"Secure atelier checkout",
        order_id:   orderData.razorpay_order_id,
        prefill:    { name: payload.name, email: payload.email, contact: payload.phone },
        notes:      { shipping_pin: payload.shipping.postal_code },
        theme:      { color: "#d4a373" },
        modal:      { ondismiss() { rejectOnce(new Error("Payment window was closed before completion.")); } },
        handler: async function (response) {
          try {
            const result = await requestJson(config.verifyPaymentUrl, {
              razorpay_order_id:   response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature:  response.razorpay_signature,
            });
            if (result.success) { resolveOnce(result); return; }
            rejectOnce(new Error(result.message || "Payment verification failed."));
          } catch (err) { rejectOnce(err); }
        },
      });
      rz.on("payment.failed", (e) => {
        rejectOnce(new Error(e?.error?.description || "Payment could not be completed."));
      });
      if (document.activeElement && typeof document.activeElement.blur === "function") {
        document.activeElement.blur();
      }

      lockBodyScroll();

      try {
        requestAnimationFrame(() => {
          try {
            rz.open();
          } catch (innerErr) {
            rejectOnce(innerErr);
          }
        });
      } catch (err) {
        rejectOnce(err);
      }
    });
  }

  async function proceedToPayment(payload) {
    setProcessing(true);
    try {
      const createResult = await requestJson(config.createPaymentUrl, payload);
      if (!createResult.success) throw new Error(createResult.message || "Unable to create payment order.");
      if (createResult.summary) setTotals(createResult.summary);
      const verifyResult = await launchRazorpay(createResult, payload);
      handleVerificationSuccess(verifyResult);
    } catch (err) {
      unlockBodyScroll();
      showStatus(refs.mainStatus, err.message || "Checkout failed. Please try again.", "error");
      setProcessing(false);
    }
  }

  // ── Pay button click (main card) ────────────────────────────────
  async function handlePayNow() {
    if (isProcessing || !cart.length) return;
    clearStatus(refs.mainStatus);

    if (hasCompleteDetails()) {
      // Details exist → prefill form values from config and go straight to payment
      applyPrefill();
      await proceedToPayment(buildPayload());
    } else {
      // Details missing → open drawer
      openDrawer();
    }
  }

  // ── Drawer pay button ───────────────────────────────────────────
  async function handleDrawerPay() {
    if (isProcessing) return;
    if (!validateForm()) return;
    const payload = buildPayload();
    closeDrawer();
    await proceedToPayment(payload);
  }

  // ── Events ─────────────────────────────────────────────────────
  function bindEvents() {
    refs.payNowBtn.addEventListener("click", handlePayNow);
    refs.drawerPayBtn.addEventListener("click", handleDrawerPay);
    refs.closeDrawerBtn.addEventListener("click", closeDrawer);

    refs.drawerOverlay.addEventListener("click", (e) => {
      if (e.target === refs.drawerOverlay) closeDrawer();
    });

    refs.billingSameAsShipping.addEventListener("change", syncBillingVisibility);

    refs.allInputs.forEach((input) => {
      input.addEventListener("input", () => {
        clearInputError(input);
        if (refs.drawerStatus.classList.contains("is-error")) clearStatus(refs.drawerStatus);
      });
    });
  }

  // ── Init ───────────────────────────────────────────────────────
  function initRefs() {
    refs.form                   = byId("checkoutForm");
    refs.name                   = byId("checkoutName");
    refs.phone                  = byId("checkoutPhone");
    refs.email                  = byId("checkoutEmail");
    refs.shippingPostalCode     = byId("shippingPostalCode");
    refs.billingPostalCode      = byId("billingPostalCode");
    refs.billingSameAsShipping  = byId("billingSameAsShipping");
    refs.billingCard            = byId("billingAddressCard");
    refs.items                  = byId("checkoutItems");
    refs.summarySubtotal        = byId("summarySubtotal");
    refs.summaryShipping        = byId("summaryShipping");
    refs.summaryDiscount        = byId("summaryDiscount");
    refs.summaryTotal           = byId("summaryTotal");
    refs.payNowBtn              = byId("payNowBtn");
    refs.drawerPayBtn           = byId("drawerPayBtn");
    refs.mainStatus             = byId("checkoutStatus");
    refs.drawerStatus           = byId("drawerStatus");
    refs.emptyState             = byId("checkoutEmptyState");
    refs.heroBagTotal           = byId("heroBagTotal");
    refs.heroCartCount          = byId("heroCartCount");
    refs.drawerOverlay          = byId("detailsDrawerOverlay");
    refs.closeDrawerBtn         = byId("closeDrawerBtn");
    refs.allInputs              = Array.from(refs.form.querySelectorAll("input"));
    refs.billingRequiredInputs  = [
      byId("billingLine1"), byId("billingCity"),
      byId("billingState"), byId("billingPostalCode"), byId("billingCountry"),
    ];
  }

  function init() {
    initRefs();
    cart = loadCart();
    applyPrefill();
    renderItems();
    bindEvents();
    setProcessing(false);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else
    init();
})();

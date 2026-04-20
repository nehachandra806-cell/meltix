(function () {
  const STORAGE_KEY = "meltix_cart";
  const PROMO_KEY = "meltix_cart_promo";
  const FALLBACK_IMAGE = "/static/images/meltix-logo.png";
  const config = window.MeltixCheckoutConfig || {};

  const refs = {};
  let cart = [];
  let totals = {
    subtotal: 0,
    shipping_fee: 0,
    discount_amount: 0,
    total: 0,
  };
  let isProcessing = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function safeParse(raw, fallback) {
    try {
      const parsed = JSON.parse(raw);
      return parsed ?? fallback;
    } catch (error) {
      return fallback;
    }
  }

  function normalizeCustomText(value) {
    const text = typeof value === "string" ? value.trim() : "";
    return text || "";
  }

  function normalizeQty(value) {
    const parsed = Number(value || 1);
    return Number.isFinite(parsed) && parsed > 0 ? Math.max(1, Math.round(parsed)) : 1;
  }

  function formatPrice(value) {
    const amount = Number(value) || 0;
    return "₹ " + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(amount);
  }

  function loadCart() {
    const parsed = safeParse(localStorage.getItem(STORAGE_KEY), []);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .map((item) => {
        if (!item || item.id == null) {
          return null;
        }

        return {
          id: String(item.id),
          name: String(item.name || "Meltix Creation"),
          price: Number(item.price) || 0,
          qty: normalizeQty(item.qty),
          image: String(item.image || FALLBACK_IMAGE),
          customText: normalizeCustomText(item.customText),
          fragrance: String(item.fragrance || item.scent || "").trim(),
        };
      })
      .filter(Boolean);
  }

  function getLocalSubtotal() {
    return cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
  }

  function setTotals(nextTotals) {
    totals = {
      subtotal: Number(nextTotals?.subtotal) || 0,
      shipping_fee: Number(nextTotals?.shipping_fee) || 0,
      discount_amount: Number(nextTotals?.discount_amount) || 0,
      total: Number(nextTotals?.total) || 0,
    };

    refs.summarySubtotal.textContent = formatPrice(totals.subtotal);
    refs.summaryShipping.textContent = formatPrice(totals.shipping_fee);
    refs.summaryDiscount.textContent = "- " + formatPrice(totals.discount_amount);
    refs.summaryTotal.textContent = formatPrice(totals.total);
    refs.payNowBtn.textContent = `Proceed to Pay ${formatPrice(totals.total)}`;
  }

  function showStatus(message, type) {
    refs.status.textContent = message;
    refs.status.classList.remove("is-error", "is-success");
    refs.status.classList.add("is-visible");
    refs.status.classList.add(type === "success" ? "is-success" : "is-error");
  }

  function clearStatus() {
    refs.status.textContent = "";
    refs.status.classList.remove("is-visible", "is-error", "is-success");
  }

  function setProcessing(nextState) {
    isProcessing = Boolean(nextState);
    refs.payNowBtn.disabled = isProcessing || !cart.length;
    if (isProcessing) {
      refs.payNowBtn.textContent = "Processing...";
    } else {
      refs.payNowBtn.textContent = `Proceed to Pay ${formatPrice(totals.total)}`;
    }
  }

  function renderItems() {
    if (!cart.length) {
      refs.emptyState.classList.remove("is-hidden");
      refs.summaryContent.style.display = "none";
      setTotals({ subtotal: 0, shipping_fee: 0, discount_amount: 0, total: 0 });
      return;
    }

    refs.emptyState.classList.add("is-hidden");
    refs.summaryContent.style.display = "";
    refs.items.innerHTML = cart.map((item) => {
      const customMarkup = item.customText
        ? `<p class="summary-item-custom"><strong>Custom Text:</strong> ${escapeHtml(item.customText)}</p>`
        : "";

      return [
        '<article class="summary-item">',
        `  <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}'">`,
        '  <div>',
        `    <h3 class="summary-item-title">${escapeHtml(item.name)}</h3>`,
        `    <p class="summary-item-meta">Qty: ${item.qty} • ${formatPrice(item.price)} each</p>`,
        customMarkup,
        "  </div>",
        "</article>",
      ].join("");
    }).join("");

    const subtotal = getLocalSubtotal();
    setTotals({
      subtotal,
      shipping_fee: 0,
      discount_amount: 0,
      total: subtotal,
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setInputValue(id, value) {
    const input = byId(id);
    if (input) {
      input.value = value || "";
    }
  }

  function applyPrefill() {
    const prefill = config.prefill || {};
    const shipping = prefill.shipping || {};
    const billing = prefill.billing || {};

    setInputValue("checkoutName", prefill.name || "");
    setInputValue("checkoutEmail", prefill.email || "");
    setInputValue("checkoutPhone", prefill.phone || "");
    setInputValue("shippingLine1", shipping.line1 || "");
    setInputValue("shippingLine2", shipping.line2 || "");
    setInputValue("shippingCity", shipping.city || "");
    setInputValue("shippingState", shipping.state || "");
    setInputValue("shippingPostalCode", shipping.postal_code || "");
    setInputValue("shippingCountry", shipping.country || "India");

    setInputValue("billingLine1", billing.line1 || "");
    setInputValue("billingLine2", billing.line2 || "");
    setInputValue("billingCity", billing.city || "");
    setInputValue("billingState", billing.state || "");
    setInputValue("billingPostalCode", billing.postal_code || "");
    setInputValue("billingCountry", billing.country || "India");

    refs.billingSameAsShipping.checked = prefill.billing_same_as_shipping !== false;
    syncBillingVisibility();
  }

  function syncBillingVisibility() {
    const same = refs.billingSameAsShipping.checked;
    refs.billingCard.classList.toggle("is-hidden", same);
  }

  function buildAddress(prefix) {
    return {
      name: refs.name.value.trim(),
      line1: byId(prefix + "Line1").value.trim(),
      line2: byId(prefix + "Line2").value.trim(),
      city: byId(prefix + "City").value.trim(),
      state: byId(prefix + "State").value.trim(),
      postal_code: byId(prefix + "PostalCode").value.trim(),
      country: byId(prefix + "Country").value.trim() || "India",
    };
  }

  function validateForm(payload) {
    if (!payload.name) {
      return "Name is required.";
    }
    if (!/^\d{10,15}$/.test(payload.phone.replace(/\D/g, ""))) {
      return "Please enter a valid phone number.";
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
      return "Please enter a valid email address.";
    }

    const addresses = [
      { label: "Shipping", value: payload.shipping },
      { label: "Billing", value: payload.billing },
    ];

    for (const addressGroup of addresses) {
      const address = addressGroup.value;
      if (!address.line1 || !address.city || !address.state) {
        return `${addressGroup.label} address is incomplete.`;
      }
      if (!/^\d{6}$/.test(address.postal_code)) {
        return `${addressGroup.label} PIN Code must be 6 digits.`;
      }
    }

    return "";
  }

  function buildPayload() {
    const billingSameAsShipping = refs.billingSameAsShipping.checked;
    const shipping = buildAddress("shipping");
    const billing = billingSameAsShipping ? { ...shipping } : buildAddress("billing");

    return {
      name: refs.name.value.trim(),
      phone: refs.phone.value.trim(),
      email: refs.email.value.trim().toLowerCase(),
      billing_same_as_shipping: billingSameAsShipping,
      shipping,
      billing,
      coupon_code: String(localStorage.getItem(PROMO_KEY) || "").trim().toUpperCase(),
      items: cart.map((item) => ({
        id: item.id,
        qty: item.qty,
        customText: item.customText,
        fragrance: item.fragrance,
      })),
    };
  }

  async function createPaymentOrder(payload) {
    const response = await fetch(config.createPaymentUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return response.json();
  }

  async function verifyPayment(responsePayload) {
    const response = await fetch(config.verifyPaymentUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(responsePayload),
    });
    return response.json();
  }

  function clearCheckoutCart() {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(PROMO_KEY);
    cart = [];
  }

  function handleVerificationSuccess(result) {
    clearCheckoutCart();
    renderItems();
    showStatus(`Payment verified. Order ${result.order?.order_id || ""} has been placed successfully.`, "success");
    refs.payNowBtn.disabled = true;
    refs.payNowBtn.textContent = "Order Confirmed";
    window.setTimeout(() => {
      window.location.href = config.profileUrl || "/profile";
    }, 1800);
  }

  async function launchRazorpay(orderData, payload) {
    const keyId = orderData.key_id || config.razorpayKeyId;
    if (!window.Razorpay || !keyId) {
      throw new Error("Razorpay is not configured right now.");
    }

    return new Promise((resolve, reject) => {
      const razorpay = new window.Razorpay({
        key: keyId,
        amount: orderData.amount_paise,
        currency: orderData.currency || "INR",
        name: "Meltix",
        description: "Secure atelier checkout",
        order_id: orderData.razorpay_order_id,
        prefill: {
          name: payload.name,
          email: payload.email,
          contact: payload.phone,
        },
        notes: {
          shipping_pin: payload.shipping.postal_code,
        },
        theme: {
          color: "#d4a373",
        },
        modal: {
          ondismiss() {
            setProcessing(false);
          },
        },
        handler: async function (response) {
          try {
            const result = await verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });

            if (result.success) {
              resolve(result);
              return;
            }

            reject(new Error(result.message || "Payment verification failed."));
          } catch (error) {
            reject(error);
          }
        },
      });

      razorpay.on("payment.failed", function (event) {
        const errorDescription = event?.error?.description || "Payment could not be completed.";
        reject(new Error(errorDescription));
      });

      razorpay.open();
    });
  }

  async function handlePayNow() {
    if (isProcessing || !cart.length) {
      return;
    }

    clearStatus();
    const payload = buildPayload();
    const validationMessage = validateForm(payload);
    if (validationMessage) {
      showStatus(validationMessage, "error");
      return;
    }

    setProcessing(true);

    try {
      const createResult = await createPaymentOrder(payload);
      if (!createResult.success) {
        throw new Error(createResult.message || "Unable to create payment order.");
      }

      if (createResult.summary) {
        setTotals({
          subtotal: createResult.summary.subtotal,
          shipping_fee: createResult.summary.shipping_fee,
          discount_amount: createResult.summary.discount_amount,
          total: createResult.summary.total,
        });
      }

      const verifyResult = await launchRazorpay(createResult, payload);
      handleVerificationSuccess(verifyResult);
    } catch (error) {
      showStatus(error.message || "Checkout failed. Please try again.", "error");
      setProcessing(false);
    }
  }

  function bindEvents() {
    refs.billingSameAsShipping.addEventListener("change", syncBillingVisibility);
    refs.payNowBtn.addEventListener("click", handlePayNow);
  }

  function initRefs() {
    refs.form = byId("checkoutForm");
    refs.name = byId("checkoutName");
    refs.phone = byId("checkoutPhone");
    refs.email = byId("checkoutEmail");
    refs.billingSameAsShipping = byId("billingSameAsShipping");
    refs.billingCard = byId("billingAddressCard");
    refs.items = byId("checkoutItems");
    refs.summarySubtotal = byId("summarySubtotal");
    refs.summaryShipping = byId("summaryShipping");
    refs.summaryDiscount = byId("summaryDiscount");
    refs.summaryTotal = byId("summaryTotal");
    refs.payNowBtn = byId("payNowBtn");
    refs.status = byId("checkoutStatus");
    refs.emptyState = byId("checkoutEmptyState");
    refs.summaryContent = byId("checkoutSummaryContent");
  }

  function init() {
    initRefs();
    cart = loadCart();
    applyPrefill();
    renderItems();
    bindEvents();
    setProcessing(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

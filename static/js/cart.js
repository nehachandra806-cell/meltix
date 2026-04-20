(function () {
  const STORAGE_KEY = "meltix_cart";
  const PROMO_KEY = "meltix_cart_promo";
  const FALLBACK_IMAGE = "/static/images/meltix-logo.png";

  const refs = {};
  let cart = [];
  let promoCode = "";

  function byId(id) {
    return document.getElementById(id);
  }

  function normalizeCustomText(value) {
    const text = typeof value === "string" ? value.trim() : "";
    return text || null;
  }

  function normalizeQty(value) {
    const parsed = Number(value || 1);
    return Number.isFinite(parsed) && parsed > 0 ? Math.max(1, Math.round(parsed)) : 1;
  }

  function normalizeStock(value, fallback = 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed >= 0) {
      return Math.max(0, Math.floor(parsed));
    }
    return Math.max(0, Math.floor(Number(fallback) || 0));
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatPrice(value) {
    const amount = Number(value) || 0;
    return "₹ " + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(amount);
  }

  function safeParse(raw, fallback) {
    try {
      const parsed = JSON.parse(raw);
      return parsed ?? fallback;
    } catch (error) {
      return fallback;
    }
  }

  function normalizeItem(item) {
    if (!item || item.id == null) {
      return null;
    }

    const qty = normalizeQty(item.qty);
    const hasExplicitStock = item.stock != null || item.stock_quantity != null;

    return {
      id: String(item.id),
      name: String(item.name || "Meltix Creation"),
      price: Number(item.price) || 0,
      image: String(item.image || FALLBACK_IMAGE),
      qty,
      stock: hasExplicitStock ? normalizeStock(item.stock ?? item.stock_quantity, 0) : qty,
      customText: normalizeCustomText(item.customText),
    };
  }

  function getItemStock(item) {
    return normalizeStock(item?.stock ?? item?.stock_quantity, 0);
  }

  function showLimitReachedNotice(stock) {
    const availableStock = normalizeStock(stock, 0);
    if (availableStock <= 0) {
      window.alert("This item is out of stock.");
      return;
    }
    window.alert(`Only ${availableStock} left in stock.`);
  }

  function loadCart() {
    const parsed = safeParse(localStorage.getItem(STORAGE_KEY), []);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map(normalizeItem)
      .filter(Boolean);
  }

  function saveCart() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
  }

  function loadPromo() {
    return String(localStorage.getItem(PROMO_KEY) || "").trim().toUpperCase();
  }

  function savePromo() {
    if (promoCode) {
      localStorage.setItem(PROMO_KEY, promoCode);
    } else {
      localStorage.removeItem(PROMO_KEY);
    }
  }

  function getItemCount() {
    return cart.reduce((sum, item) => sum + item.qty, 0);
  }

  function getSubtotal() {
    return cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
  }

  function findExistingItemIndex(item) {
    const targetCustomText = normalizeCustomText(item.customText);
    return cart.findIndex((entry) => (
      String(entry.id) === String(item.id) &&
      normalizeCustomText(entry.customText) === targetCustomText
    ));
  }

  function syncStocks(stockItems) {
    const nextStocks = new Map();
    (Array.isArray(stockItems) ? stockItems : []).forEach((item) => {
      const id = String(item?.id ?? "").trim();
      if (!id) {
        return;
      }
      nextStocks.set(id, normalizeStock(item?.stock ?? item?.stock_quantity, 0));
    });

    if (!nextStocks.size) {
      return;
    }

    let changed = false;
    cart = cart.map((item) => {
      const nextStock = nextStocks.get(String(item.id));
      if (nextStock == null || item.stock === nextStock) {
        return item;
      }
      changed = true;
      return { ...item, stock: nextStock };
    });

    if (changed) {
      saveCart();
      renderCart();
    }
  }

  function setBodyLock(isLocked) {
    document.body.classList.toggle("meltix-cart-open", isLocked);
  }

  function dispatchCartUpdate() {
    document.dispatchEvent(new CustomEvent("meltix:cart-updated", {
      detail: {
        items: cart.map((item) => ({ ...item })),
        count: getItemCount(),
        subtotal: getSubtotal(),
        promoCode,
      },
    }));
  }

  function pulseGhost() {
    if (!refs.ghost) {
      return;
    }
    refs.ghost.classList.remove("meltix-cart-pop");
    void refs.ghost.offsetWidth;
    refs.ghost.classList.add("meltix-cart-pop");
  }

  function signalAddSuccess(button, config) {
    if (!button) {
      pulseGhost();
      return;
    }

    const label = String(config?.label || "ADDED TO BAG ✓");
    const finalDisabled = typeof config?.finalDisabled === "boolean" ? config.finalDisabled : Boolean(button.disabled);
    let labelNode = button.querySelector(".meltix-cart-button-label");
    if (!labelNode) {
      labelNode = document.createElement("span");
      labelNode.className = "meltix-cart-button-label";
      const textParts = [];
      Array.from(button.childNodes).forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          const normalized = String(node.textContent || "").replace(/\s+/g, " ").trim();
          if (normalized) {
            textParts.push(normalized);
          }
          node.remove();
        }
      });
      labelNode.textContent = textParts.join(" ") || "ADD TO CART";
      button.insertBefore(labelNode, button.firstChild);
    }
    const originalLabel = button.dataset.cartOriginalLabel || labelNode.textContent;

    button.dataset.cartOriginalLabel = originalLabel;
    button.classList.add("added-success");
    button.disabled = true;
    labelNode.classList.add("meltix-cart-success-label");
    labelNode.textContent = label;

    window.clearTimeout(button._meltixCartSuccessTimer);
    button._meltixCartSuccessTimer = window.setTimeout(() => {
      labelNode.textContent = originalLabel;
      labelNode.classList.remove("meltix-cart-success-label");
      button.disabled = finalDisabled;
      button.classList.remove("added-success");
    }, Number(config?.duration || 1500));

    pulseGhost();
  }

  function closeCart() {
    if (!refs.root) {
      return;
    }
    refs.root.classList.remove("is-open");
    refs.drawer?.setAttribute("aria-hidden", "true");
    setBodyLock(false);
  }

  function openCart() {
    if (!refs.root || !cart.length) {
      return;
    }
    refs.root.classList.add("is-open");
    refs.drawer?.setAttribute("aria-hidden", "false");
    setBodyLock(true);
  }

  function renderEmptyState() {
    refs.items.innerHTML = [
      '<div class="meltix-cart-empty">',
      "  <div>",
      "    <h3>Your bag is still a whisper.</h3>",
      "    <p>Add a Meltix piece and your Ghost Bag will appear here.</p>",
      "  </div>",
      "</div>",
    ].join("");
  }

  function renderItems() {
    refs.items.innerHTML = cart.map((item, index) => {
      const customMarkup = item.customText
        ? `<p class="meltix-cart-card-custom"><strong>Custom Text:</strong> ${escapeHtml(item.customText)}</p>`
        : "";
      const availableStock = getItemStock(item);
      const isAtLimit = availableStock <= 0 || item.qty >= availableStock;

      return [
        '<article class="meltix-cart-card">',
        `  <img class="meltix-cart-card-thumb" src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}'">`,
        '  <div class="meltix-cart-card-main">',
        `    <h3 class="meltix-cart-card-title">${escapeHtml(item.name)}</h3>`,
        `    <p class="meltix-cart-card-price">${formatPrice(item.price)}</p>`,
        `    ${customMarkup}`,
        "  </div>",
        '  <div class="meltix-cart-card-side">',
        '    <div class="meltix-cart-qty-controls">',
        `      <button type="button" class="meltix-cart-minus" data-action="decrease" data-index="${index}" aria-label="${item.qty > 1 ? "Reduce quantity" : "Remove item"}" title="${item.qty > 1 ? "Reduce quantity" : "Remove item"}">&minus;</button>`,
        `      <div class="meltix-cart-qty-pill">Qty: ${item.qty}</div>`,
        `      <button type="button" class="meltix-cart-plus${isAtLimit ? " is-disabled" : ""}" data-action="increase" data-index="${index}" aria-label="${isAtLimit ? "Stock limit reached" : "Increase quantity"}" title="${isAtLimit ? (availableStock > 0 ? `Only ${availableStock} left in stock` : "Out of stock") : "Increase quantity"}"${isAtLimit ? " disabled" : ""}>+</button>`,
        "    </div>",
        "  </div>",
        "</article>",
      ].join("");
    }).join("");
  }

  function renderCart() {
    if (!refs.root) {
      return;
    }

    const itemCount = getItemCount();
    refs.badge.textContent = String(itemCount);
    refs.subtotal.textContent = formatPrice(getSubtotal());
    refs.root.classList.toggle("has-items", itemCount > 0);
    refs.promoNote.textContent = promoCode ? `Promo saved: ${promoCode}` : "";
    refs.promoInput.value = promoCode;

    if (!cart.length) {
      renderEmptyState();
      closeCart();
    } else {
      renderItems();
    }

    dispatchCartUpdate();
  }

  function addItem(productObj) {
    const normalized = normalizeItem(productObj);
    if (!normalized) {
      return false;
    }
    const availableStock = getItemStock(normalized);

    if (availableStock <= 0) {
      showLimitReachedNotice(availableStock);
      return false;
    }

    const existingIndex = findExistingItemIndex(normalized);
    if (existingIndex >= 0) {
      const existingItem = cart[existingIndex];
      const stockChanged = existingItem.stock !== availableStock;
      existingItem.stock = availableStock;
      const nextQty = existingItem.qty + normalized.qty;
      if (nextQty > availableStock) {
        if (stockChanged) {
          saveCart();
          renderCart();
        }
        showLimitReachedNotice(availableStock);
        return false;
      }
      existingItem.qty = nextQty;
    } else {
      if (normalized.qty > availableStock) {
        showLimitReachedNotice(availableStock);
        return false;
      }
      cart.push(normalized);
    }

    saveCart();
    renderCart();
    pulseGhost();
    return true;
  }

  function increaseItem(index) {
    const item = cart[index];
    if (!item) {
      return false;
    }

    const availableStock = getItemStock(item);
    if (availableStock <= 0 || item.qty >= availableStock) {
      showLimitReachedNotice(availableStock);
      return false;
    }

    item.qty += 1;
    saveCart();
    renderCart();
    return true;
  }

  function decreaseItem(index) {
    const item = cart[index];
    if (!item) {
      return;
    }

    if (item.qty > 1) {
      item.qty -= 1;
    } else {
      cart.splice(index, 1);
    }

    saveCart();
    renderCart();
  }

  function removeItem(index) {
    if (!cart[index]) {
      return;
    }
    cart.splice(index, 1);
    saveCart();
    renderCart();
  }

  function clearCart() {
    cart = [];
    promoCode = "";
    saveCart();
    savePromo();
    renderCart();
  }

  function applyPromo() {
    promoCode = refs.promoInput.value.trim().toUpperCase();
    savePromo();
    renderCart();
  }

  function handleCheckout() {
    document.dispatchEvent(new CustomEvent("meltix:checkout", {
      detail: {
        items: cart.map((item) => ({ ...item })),
        count: getItemCount(),
        subtotal: getSubtotal(),
        promoCode,
      },
    }));
  }

  function bindEvents() {
    refs.ghost.addEventListener("click", openCart);
    refs.close.addEventListener("click", closeCart);
    refs.overlay.addEventListener("click", closeCart);
    refs.checkout.addEventListener("click", handleCheckout);
    refs.promoBtn.addEventListener("click", applyPromo);
    refs.promoInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyPromo();
      }
    });
    refs.items.addEventListener("click", (event) => {
      const button = event.target.closest("[data-action]");
      if (!button) {
        return;
      }
      const index = Number(button.dataset.index);
      if (!Number.isInteger(index)) {
        return;
      }

      if (button.dataset.action === "increase") {
        increaseItem(index);
        return;
      }

      if (button.dataset.action === "decrease") {
        decreaseItem(index);
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeCart();
      }
    });
  }

  function init() {
    refs.root = byId("meltixGhostCart");
    refs.ghost = byId("meltixCartGhostBtn");
    refs.badge = byId("meltixCartBadge");
    refs.overlay = byId("meltixCartOverlay");
    refs.drawer = byId("meltixCartDrawer");
    refs.close = byId("meltixCartClose");
    refs.items = byId("meltixCartItems");
    refs.subtotal = byId("meltixCartSubtotal");
    refs.promoInput = byId("meltixCartPromoInput");
    refs.promoBtn = byId("meltixCartPromoBtn");
    refs.promoNote = byId("meltixCartPromoNote");
    refs.checkout = byId("meltixCartCheckoutBtn");

    if (!refs.root || !refs.ghost || !refs.drawer) {
      return;
    }

    cart = loadCart();
    promoCode = loadPromo();

    bindEvents();
    renderCart();
  }

  window.MeltixCart = {
    addItem,
    increaseItem,
    syncStocks,
    openCart,
    closeCart,
    clearCart,
    removeItem,
    renderCart,
    signalAddSuccess,
    getItems() {
      return cart.map((item) => ({ ...item }));
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

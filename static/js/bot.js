(function () {
  const INTERACTIVE_ESCAPE_SELECTOR = [
    "a[href]",
    "button",
    "[role='button']",
    "[role='link']",
    "[data-href]",
    "input:not([type='hidden'])",
    "select",
    "textarea",
    "summary",
    "[tabindex]:not([tabindex='-1'])"
  ].join(",");
  const ESCAPE_WHISPER = "I prefer standing in empty spaces. Buttons already get enough attention.";
  const COLLISION_PADDING = 18;
  const LARGE_ZONE_MIN_WIDTH = 220;
  const LARGE_ZONE_MIN_HEIGHT = 180;
  const SEARCH_STEP = 52;

  const CONTEXT_WHISPERS = {
    shop: [
      "Gift, candle, or suggestion?",
      "Budget batao, option dikhata hoon.",
      "Collection chahiye ya quick pick?"
    ],
    general: [
      "Gift chahiye ya product suggestion?",
      "Tell me the collection or budget.",
      "Need a candle, gift, or quick pick?"
    ]
  };
  const ROMAN_HINDI_MARKERS = [
    "acha", "achha", "arre", "batao", "bhai", "bolo", "chaiye", "chahiye", "dekh",
    "dena", "hoon", "hu", "kaisa", "kaise", "karna", "karo", "kya", "kyu", "kyun",
    "lena", "mai", "main", "mera", "mere", "mujhe", "nahi", "nhi", "raha", "rha",
    "suno", "thoda", "toh", "tum", "tumhe", "wala", "wali", "yaar"
  ];

  function safeParse(raw, fallback) {
    try {
      const parsed = JSON.parse(raw);
      return parsed ?? fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatMessageHtml(value) {
    return escapeHtml(value).replace(/\n/g, "<br>");
  }

  function renderProductCard(card) {
    if (!card || !card.redirect_url || !card.image_url) {
      return "";
    }

    const productName = escapeHtml(card.name || "Meltix Pick");
    const imageUrl = escapeHtml(card.image_url);
    const redirectUrl = escapeHtml(card.redirect_url);
    const productId = escapeHtml(card.product_id || "");

    return [
      `<div class="chat-product-card" data-product-card data-redirect-url="${redirectUrl}" data-product-name="${productName}" data-product-id="${productId}" tabindex="0" role="link" aria-label="Open ${productName}">`,
      `<img src="${imageUrl}" alt="${productName}">`,
      `<div class="chat-card-caption">`,
      `<span>${productName}</span>`,
      `</div>`,
      `</div>`
    ].join("");
  }

  function detectUiLanguage(value) {
    const text = String(value || "").trim();
    if (/[\u0900-\u097F]/.test(text)) {
      return "hindi";
    }
    const words = text.toLowerCase().split(/[^a-z]+/).filter(Boolean);
    if (words.some((word) => ROMAN_HINDI_MARKERS.includes(word))) {
      return "hinglish";
    }
    return "english";
  }

  function buildProductCardUrl(card) {
    if (!card) return "";
    const redirectUrl = card.dataset.redirectUrl || "";
    if (!redirectUrl) return "";
    if (redirectUrl.includes("product=") || redirectUrl.includes("product_name=")) {
      return redirectUrl;
    }

    const productId = String(card.dataset.productId || "").trim();
    if (productId) {
      return `${redirectUrl}${redirectUrl.includes("?") ? "&" : "?"}product=${encodeURIComponent(productId)}`;
    }

    const productName = String(card.dataset.productName || "").trim();
    if (productName) {
      return `${redirectUrl}${redirectUrl.includes("?") ? "&" : "?"}product_name=${encodeURIComponent(productName)}`;
    }

    return redirectUrl;
  }

  function shouldIgnoreShortcut(target) {
    if (!target) return false;
    const tagName = (target.tagName || "").toLowerCase();
    return tagName === "input" || tagName === "textarea" || target.isContentEditable;
  }

  function initBot(root) {
    const context = root.dataset.botContext || "general";
    const chatUrl = root.dataset.chatUrl || "/api/bot/chat";
    const prefsKey = `meltix_bot_prefs:${context}`;
    const historyKey = `meltix_bot_history:${context}`;

    const refs = {
      overlay: root.querySelector("[data-bot-overlay]"),
      panel: root.querySelector("[data-bot-panel]"),
      close: root.querySelector("[data-bot-close]"),
      history: root.querySelector("[data-bot-history]"),
      form: root.querySelector("[data-bot-form]"),
      input: root.querySelector("[data-bot-input]"),
      send: root.querySelector(".meltix-bot-send"),
      toast: root.querySelector("[data-bot-toast]"),
      dismiss: root.querySelector("[data-bot-dismiss]"),
      dock: root.querySelector("[data-bot-dock]"),
      launcher: root.querySelector("[data-bot-launcher]"),
      avatar: root.querySelector("[data-bot-avatar]"),
      avatarDrag: root.querySelector("[data-bot-avatar-drag]"),
      whisper: root.querySelector("[data-bot-whisper]"),
      navButtons: Array.from(root.querySelectorAll("[data-bot-action='navigate']"))
    };

    if (!refs.panel || !refs.history || !refs.form || !refs.input || !refs.dock || !refs.launcher) {
      return;
    }

    const navMap = refs.navButtons.reduce((acc, button) => {
      const key = (button.dataset.botLabel || "").trim().toLowerCase();
      if (key) {
        acc[key] = {
          label: button.dataset.botLabel || "",
          href: button.dataset.botHref || "#"
        };
      }
      return acc;
    }, {});

    function readPrefs() {
      return safeParse(localStorage.getItem(prefsKey), {});
    }

    function writePrefs(updates) {
      const next = { ...readPrefs(), ...updates };
      localStorage.setItem(prefsKey, JSON.stringify(next));
      return next;
    }

    function readHistory() {
      const parsed = safeParse(localStorage.getItem(historyKey), []);
      return Array.isArray(parsed) ? parsed : [];
    }

    function writeHistory(nextHistory) {
      localStorage.setItem(historyKey, JSON.stringify(nextHistory.slice(-24)));
    }

    let prefs = readPrefs();
    let history = readHistory();
    let dockX = 0;
    let dockY = 0;
    let whisperLoop = null;
    let whisperHide = null;
    let dragState = null;
    let isSending = false;
    let escapeCooldown = 0;
    let collisionFrame = null;

    const idleSrc = root.dataset.idleSrc || "";
    const welcomeMessage = root.dataset.welcomeMessage || "Welcome to Meltix.";

    if (!history.length) {
      history = [{ role: "assistant", text: welcomeMessage }];
      writeHistory(history);
    }

    function getDefaultPosition() {
      const dockWidth = refs.dock.offsetWidth || 178;
      const dockHeight = refs.dock.offsetHeight || 116;
      return {
        x: Math.max(window.innerWidth - dockWidth - 42, 16),
        y: Math.max(window.innerHeight - dockHeight - 42, 16)
      };
    }

    function clampPosition(x, y) {
      const dockWidth = refs.dock.offsetWidth || 178;
      const dockHeight = refs.dock.offsetHeight || 116;
      return {
        x: Math.min(Math.max(16, x), Math.max(16, window.innerWidth - dockWidth - 16)),
        y: Math.min(Math.max(16, y), Math.max(16, window.innerHeight - dockHeight - 16))
      };
    }

    function applyPosition(x, y, persist) {
      const clamped = clampPosition(x, y);
      dockX = clamped.x;
      dockY = clamped.y;
      refs.dock.style.transform = `translate3d(${dockX}px, ${dockY}px, 0)`;
      if (persist) {
        prefs = writePrefs({ x: dockX, y: dockY });
      }
    }

    function getDockRect(x = dockX, y = dockY) {
      const dockWidth = refs.dock.offsetWidth || 116;
      const dockHeight = refs.dock.offsetHeight || 116;
      return {
        left: x,
        top: y,
        right: x + dockWidth,
        bottom: y + dockHeight,
        width: dockWidth,
        height: dockHeight
      };
    }

    function expandRect(rect, padding) {
      return {
        left: rect.left - padding,
        top: rect.top - padding,
        right: rect.right + padding,
        bottom: rect.bottom + padding
      };
    }

    function centerRect(rect, targetWidth, targetHeight) {
      const width = Math.min(targetWidth, rect.width);
      const height = Math.min(targetHeight, rect.height);
      const left = rect.left + ((rect.width - width) / 2);
      const top = rect.top + ((rect.height - height) / 2);
      return {
        left,
        top,
        right: left + width,
        bottom: top + height,
        width,
        height
      };
    }

    function rectsIntersect(a, b) {
      return !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
    }

    function getInteractiveRects() {
      return Array.from(document.querySelectorAll(INTERACTIVE_ESCAPE_SELECTOR))
        .filter((element) => {
          if (!element || root.contains(element)) return false;
          if (element.disabled) return false;
          const style = window.getComputedStyle(element);
          if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") {
            return false;
          }
          const rect = element.getBoundingClientRect();
          return rect.width > 18 && rect.height > 18;
        })
        .map((element) => {
          const rect = element.getBoundingClientRect();
          const isLargeHoverZone = rect.width >= LARGE_ZONE_MIN_WIDTH && rect.height >= LARGE_ZONE_MIN_HEIGHT;

          if (isLargeHoverZone) {
            const focusRect = centerRect(
              rect,
              Math.max(120, rect.width * 0.42),
              Math.max(120, rect.height * 0.4)
            );
            return expandRect(focusRect, 6);
          }

          return expandRect(rect, COLLISION_PADDING);
        });
    }

    function isBlockedPosition(x, y) {
      const dockRect = getDockRect(x, y);
      return getInteractiveRects().some((rect) => rectsIntersect(dockRect, rect));
    }

    function distanceBetweenPoints(ax, ay, bx, by) {
      return Math.hypot(ax - bx, ay - by);
    }

    function findSafePosition(originX, originY) {
      const dockRect = getDockRect(originX, originY);
      const maxX = Math.max(16, window.innerWidth - dockRect.width - 16);
      const maxY = Math.max(16, window.innerHeight - dockRect.height - 16);
      const candidates = [];

      for (let y = 16; y <= maxY; y += SEARCH_STEP) {
        for (let x = 16; x <= maxX; x += SEARCH_STEP) {
          const clamped = clampPosition(x, y);
          candidates.push(clamped);
        }
      }

      candidates.push(
        clampPosition(originX, originY),
        clampPosition(maxX, maxY),
        clampPosition(16, maxY),
        clampPosition(maxX, 16),
        clampPosition(16, 16),
        getDefaultPosition()
      );

      const unique = [];
      const seen = new Set();

      for (const candidate of candidates) {
        const key = `${candidate.x}:${candidate.y}`;
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(candidate);
        }
      }

      unique.sort((a, b) => {
        const aDistance = distanceBetweenPoints(a.x, a.y, originX, originY);
        const bDistance = distanceBetweenPoints(b.x, b.y, originX, originY);
        return aDistance - bDistance;
      });

      return unique.find((candidate) => !isBlockedPosition(candidate.x, candidate.y)) || getDefaultPosition();
    }

    function escapeInteractiveZone(showMessage) {
      if (root.classList.contains("is-open") || dragState?.active) return false;
      if (!isBlockedPosition(dockX, dockY)) return false;
      const safePosition = findSafePosition(dockX, dockY);
      applyPosition(safePosition.x, safePosition.y, true);

      if (showMessage && Date.now() - escapeCooldown > 1400) {
        escapeCooldown = Date.now();
        window.setTimeout(() => {
          if (!dragState?.active && !root.classList.contains("is-open")) {
            showWhisper(ESCAPE_WHISPER);
          }
        }, 190);
      }

      return true;
    }

    function scheduleCollisionCheck(showMessage) {
      if (dragState?.active || root.classList.contains("is-open")) return;
      if (collisionFrame) {
        window.cancelAnimationFrame(collisionFrame);
      }
      collisionFrame = window.requestAnimationFrame(() => {
        collisionFrame = null;
        escapeInteractiveZone(showMessage);
      });
    }

    function scrollHistoryToBottom() {
      if (!refs.history) return;
      if (typeof refs.history.scrollTo === "function") {
        refs.history.scrollTo({
          top: refs.history.scrollHeight,
          behavior: "smooth"
        });
        return;
      }
      refs.history.scrollTop = refs.history.scrollHeight;
    }

    function renderHistory() {
      refs.history.innerHTML = history.map((entry) => {
        if (entry.role === "product-card") {
          return renderProductCard(entry.productCard);
        }
        const roleClass = entry.role === "user" ? "meltix-bot-message--user" : "meltix-bot-message--assistant";
        const label = entry.role === "user" ? "You" : "Meltix Bot";
        return [
          `<article class="meltix-bot-message ${roleClass}">`,
          `<span class="meltix-bot-message-label">${escapeHtml(label)}</span>`,
          `<div class="meltix-bot-message-copy">${formatMessageHtml(entry.text)}</div>`,
          "</article>"
        ].join("");
      }).join("");
      scrollHistoryToBottom();
    }

    function addMessage(role, text, options = {}) {
      history = history.concat({
        role,
        text: String(text || "").trim(),
        productCard: options.productCard || null
      }).slice(-24);
      writeHistory(history);
      renderHistory();
    }

    function addProductCard(productCard) {
      if (!productCard || !productCard.redirect_url || !productCard.image_url) return;
      history = history.concat({
        role: "product-card",
        text: "",
        productCard
      }).slice(-24);
      writeHistory(history);
      renderHistory();
    }

    function serializeHistoryForApi() {
      return history
        .filter((entry) => entry.role === "user" || entry.role === "assistant")
        .slice(-12)
        .map((entry) => ({
          role: entry.role,
          text: entry.text
        }));
    }

    function setSendingState(state) {
      isSending = Boolean(state);
      refs.input.disabled = isSending;
      if (refs.send) {
        refs.send.disabled = isSending;
        refs.send.textContent = isSending ? "Wait" : "Send";
      }
    }

    function showToast() {
      if (prefs.introDismissed) return;
      refs.toast?.classList.add("is-visible");
    }

    function dismissToast() {
      refs.toast?.classList.remove("is-visible");
      prefs = writePrefs({ introDismissed: true });
    }

    function setAvatarSource(nextSrc) {
      if (!refs.avatar || !nextSrc || refs.avatar.getAttribute("src") === nextSrc) {
        return;
      }
      refs.avatar.setAttribute("src", nextSrc);
      refs.avatar.load();
      const playAttempt = refs.avatar.play();
      if (playAttempt && typeof playAttempt.catch === "function") {
        playAttempt.catch(() => {});
      }
    }

    function ensureVideoPlayback(video) {
      if (!video || typeof video.play !== "function") return;
      const playAttempt = video.play();
      if (playAttempt && typeof playAttempt.catch === "function") {
        playAttempt.catch(() => {});
      }
    }

    function openPanel(focusInput) {
      root.classList.add("is-open");
      refs.panel.setAttribute("aria-hidden", "false");
      prefs = writePrefs({ panelOpen: true, introDismissed: true });
      refs.toast?.classList.remove("is-visible");
      if (focusInput) {
        window.setTimeout(() => refs.input.focus(), 120);
      }
    }

    function closePanel() {
      root.classList.remove("is-open");
      refs.panel.setAttribute("aria-hidden", "true");
      prefs = writePrefs({ panelOpen: false });
    }

    function showWhisper(message) {
      if (!refs.whisper || !message) return;
      refs.whisper.textContent = message;
      refs.whisper.classList.add("is-visible");
      window.clearTimeout(whisperHide);
      whisperHide = window.setTimeout(() => {
        refs.whisper.classList.remove("is-visible");
      }, 3200);
    }

    function cycleWhisper() {
      if (root.classList.contains("is-open") || dragState?.active) return;
      const pool = CONTEXT_WHISPERS[context] || CONTEXT_WHISPERS.general;
      const message = pool[Math.floor(Math.random() * pool.length)];
      showWhisper(message);
    }

    function startWhispers() {
      window.clearInterval(whisperLoop);
      whisperLoop = window.setInterval(cycleWhisper, 18000);
    }

    function queueNavigation(route) {
      if (!route || !route.href || route.href === "#") return;
      window.setTimeout(() => {
        window.location.href = route.href;
      }, 280);
    }

    function getRoute(name) {
      return navMap[String(name || "").trim().toLowerCase()] || null;
    }

    function actionReply(label) {
      switch (String(label || "").toLowerCase()) {
        case "gift sets":
          return "Taking you to the gifting edit. It is the fastest way to find a polished surprise.";
        case "suggestions":
          return "Opening the recommendation room for you now.";
        case "meltix studio":
        case "craft studio":
          return "Stepping into Meltix Studio. This is where the Meltix story deepens.";
        case "feedback":
          return "Opening the feedback desk so you can leave a refined note.";
        case "bug report":
          return "Taking you to the bug report desk right away.";
        case "another section":
        case "head to":
          return "Opening another section of the atelier for you now.";
        default:
          return `Opening ${label} for you now.`;
      }
    }

    function detectNavigationIntent(message) {
      const lower = String(message || "").toLowerCase();
      const wantsNavigation = /(open|take me|go to|chalo|le chalo|redirect|page|section)/.test(lower);
      const checks = [
        { route: getRoute("another section") || getRoute("head to"), regex: /(head to|another section|navigation)/ },
        { route: getRoute("suggestions"), regex: /(suggestion|suggestions|recommendation page)/ },
        { route: getRoute("gift sets"), regex: /(gift set|gift sets|gifting page)/ },
        { route: getRoute("meltix studio") || getRoute("craft studio"), regex: /(meltix studio|craft studio|studio)/ },
        { route: getRoute("feedback"), regex: /(feedback|review page)/ },
        { route: getRoute("bug report"), regex: /(bug report|bug|issue|problem)/ }
      ];

      for (const check of checks) {
        if (check.route && check.regex.test(lower) && (wantsNavigation || lower.trim().length <= 28)) {
          return check.route;
        }
      }

      if (context !== "shop" && /(shop|collections|browse)/.test(lower) && (wantsNavigation || lower.trim().length <= 28)) {
        return { label: "Shop", href: "/shop" };
      }

      return null;
    }

    async function requestBotReply(message, priorHistory) {
      const response = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: priorHistory,
          context
        })
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || "Meltix Bot abhi unavailable hai.");
      }

      return {
        reply: payload.reply || "Welcome. Looking for a gift, a candle, or a suggestion?",
        product_card: payload.product_card || null,
        redirect_url: payload.redirect_url || null
      };
    }

    function getFallbackReply(message) {
      const lower = String(message || "").toLowerCase();
      const language = detectUiLanguage(message);
      if (/(hello|hi|hey|namaste|salam|kaise)/.test(lower)) {
        if (language === "hindi") {
          return "स्वागत है। गिफ्ट, कैंडल, या suggestion चाहिए?";
        }
        if (language === "hinglish") {
          return "Welcome. Gift, candle, ya suggestion chahiye?";
        }
        return "Welcome. Looking for a gift, a candle, or a suggestion?";
      }
      if (/(gift|birthday|anniversary|surprise)/.test(lower)) {
        if (language === "hindi") {
          return "गिफ्ट के लिए budget या occasion बताइए, मैं सही option दिखाऊंगा।";
        }
        if (language === "hinglish") {
          return "Gift ke liye budget ya occasion batao, main sahi option dikhaunga.";
        }
        return "Share the occasion or budget, and I will point you to the right gift.";
      }
      if (language === "hindi") {
        return "कृपया product, budget, ya collection बताइए, मैं सीधे वहीं ले चलता हूँ।";
      }
      if (language === "hinglish") {
        return "Product, budget, ya collection batao, main seedha ussi direction me le chalta hoon.";
      }
      return "Tell me the product, budget, or collection, and I will take you straight there.";
    }

    function getFallbackReply(message) {
      const lower = String(message || "").toLowerCase();
      const language = detectUiLanguage(message);

      if (/(hello|hi|hey|namaste|salam|kaise)/.test(lower)) {
        if (language === "hindi") {
          return "\u0938\u094d\u0935\u093e\u0917\u0924 \u0939\u0948\u0964 \u0917\u093f\u092b\u094d\u091f, \u0915\u0948\u0902\u0921\u0932, \u092f\u093e suggestion \u091a\u093e\u0939\u093f\u090f?";
        }
        if (language === "hinglish") {
          return "Welcome. Gift, candle, ya suggestion chahiye?";
        }
        return "Welcome. Looking for a gift, a candle, or a suggestion?";
      }

      if (/(gift|birthday|anniversary|surprise)/.test(lower)) {
        if (language === "hindi") {
          return "\u0917\u093f\u092b\u094d\u091f \u0915\u0947 \u0932\u093f\u090f budget \u092f\u093e occasion \u092c\u0924\u093e\u0907\u090f, \u092e\u0948\u0902 \u0938\u0939\u0940 option \u0926\u093f\u0916\u093e\u090a\u0902\u0917\u093e\u0964";
        }
        if (language === "hinglish") {
          return "Gift ke liye budget ya occasion batao, main sahi option dikhaunga.";
        }
        return "Share the occasion or budget, and I will point you to the right gift.";
      }

      if (language === "hindi") {
        return "\u0915\u0943\u092a\u092f\u093e product, budget, ya collection \u092c\u0924\u093e\u0907\u090f, \u092e\u0948\u0902 \u0938\u0940\u0927\u0947 \u0935\u0939\u0940\u0902 \u0932\u0947 \u091a\u0932\u0924\u093e \u0939\u0942\u0901\u0964";
      }
      if (language === "hinglish") {
        return "Product, budget, ya collection batao, main seedha ussi direction me le chalta hoon.";
      }
      return "Tell me the product, budget, or collection, and I will take you straight there.";
    }

    async function handlePrompt(rawText) {
      const text = String(rawText || "").trim();
      if (!text || isSending) return;

      const priorHistory = serializeHistoryForApi();
      addMessage("user", text);
      refs.input.value = "";
      refs.input.focus();

      setSendingState(true);
      try {
        const data = await requestBotReply(text, priorHistory);
        addMessage("assistant", data.reply);
        if (data.product_card) {
          addProductCard(data.product_card);
        }
        if (data.redirect_url) {
          window.setTimeout(() => {
            window.location.href = data.redirect_url;
          }, 1500);
        }
      } catch (error) {
        addMessage("assistant", getFallbackReply(text));
      } finally {
        setSendingState(false);
      }
    }

    function handleNavButtonClick(button) {
      const label = button.dataset.botLabel || "Next page";
      const route = {
        label,
        href: button.dataset.botHref || "#"
      };
      addMessage("user", label);
      addMessage("assistant", actionReply(label));
      queueNavigation(route);
    }

    function onPointerDown(event) {
      if (event.button !== 0) return;
      try {
        refs.launcher.setPointerCapture(event.pointerId);
      } catch (_error) {}
      dragState = {
        active: true,
        moved: false,
        startX: event.clientX,
        startY: event.clientY,
        originX: dockX,
        originY: dockY
      };
      root.classList.add("is-dragging");
      refs.whisper?.classList.remove("is-visible");
      dismissToast();
    }

    function onPointerMove(event) {
      if (!dragState?.active) return;
      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;
      if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
        dragState.moved = true;
      }
      applyPosition(dragState.originX + deltaX, dragState.originY + deltaY, false);
    }

    function onPointerUp(event) {
      if (!dragState?.active) return;
      if (typeof event?.pointerId === "number") {
        try {
          refs.launcher.releasePointerCapture(event.pointerId);
        } catch (_error) {}
      }
      const wasMoved = dragState.moved;
      dragState.active = false;
      root.classList.remove("is-dragging");
      applyPosition(dockX, dockY, true);
      dragState = null;
      if (!wasMoved) {
        if (root.classList.contains("is-open")) {
          closePanel();
        } else {
          openPanel(true);
        }
      } else {
        escapeInteractiveZone(true);
      }
    }

    refs.form.addEventListener("submit", (event) => {
      event.preventDefault();
      handlePrompt(refs.input.value);
    });

    refs.history.addEventListener("click", (event) => {
      const card = event.target.closest("[data-product-card]");
      if (!card) return;
      const redirectUrl = buildProductCardUrl(card);
      if (redirectUrl) {
        window.location.href = redirectUrl;
      }
    });

    refs.history.addEventListener("keydown", (event) => {
      const card = event.target.closest("[data-product-card]");
      if (!card) return;
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      const redirectUrl = buildProductCardUrl(card);
      if (redirectUrl) {
        window.location.href = redirectUrl;
      }
    });

    refs.navButtons.forEach((button) => {
      button.addEventListener("click", () => handleNavButtonClick(button));
    });

    refs.close?.addEventListener("click", closePanel);
    refs.overlay?.addEventListener("click", closePanel);
    refs.dismiss?.addEventListener("click", dismissToast);
    refs.launcher.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerup", onPointerUp);

    window.addEventListener("resize", () => {
      applyPosition(dockX, dockY, true);
      scheduleCollisionCheck(false);
    });

    window.addEventListener("scroll", () => {
      scheduleCollisionCheck(false);
    }, { passive: true });

    document.addEventListener("keydown", (event) => {
      if (shouldIgnoreShortcut(event.target)) return;
      const key = event.key.toLowerCase();
      if (key === "c") {
        event.preventDefault();
        openPanel(true);
      } else if (key === "g" || key === "escape") {
        if (root.classList.contains("is-open")) {
          event.preventDefault();
          closePanel();
        }
      }
    });

    const startingPosition = (() => {
      if (Number.isFinite(Number(prefs.x)) && Number.isFinite(Number(prefs.y))) {
        return { x: Number(prefs.x), y: Number(prefs.y) };
      }
      return getDefaultPosition();
    })();

    renderHistory();
    applyPosition(startingPosition.x, startingPosition.y, false);
    setAvatarSource(idleSrc);
    ensureVideoPlayback(refs.avatar);
    ensureVideoPlayback(refs.avatarDrag);
    startWhispers();
    scheduleCollisionCheck(false);

    if (prefs.panelOpen) {
      openPanel(false);
    } else {
      window.setTimeout(showToast, 900);
      window.setTimeout(cycleWhisper, 2200);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      document.querySelectorAll("[data-meltix-bot]").forEach(initBot);
    });
  } else {
    document.querySelectorAll("[data-meltix-bot]").forEach(initBot);
  }
})();

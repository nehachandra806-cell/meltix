(function () {
  const DEFAULT_WHATSAPP_BUSINESS = "919876543210";

  function byId(id) {
    return document.getElementById(id);
  }

  function textOrEmpty(value) {
    return typeof value === "string" ? value : "";
  }

  function firstWordUpper(value) {
    return textOrEmpty(value).trim().split(/\s+/)[0]?.toUpperCase() || "";
  }

  function buildGalleryImages(product) {
    const baseImage = textOrEmpty(product?.image_url) || textOrEmpty(product?.src);
    const rawGallery = Array.isArray(product?.gallery_images) ? product.gallery_images.filter(Boolean) : [];
    const gallery = rawGallery.length ? rawGallery : (baseImage ? [baseImage] : []);
    if (!gallery.length) {
      return [];
    }
    while (gallery.length < 4) {
      gallery.push(gallery[0]);
    }
    return gallery.slice(0, 4);
  }

  function primaryProductImage(product) {
    return buildGalleryImages(product)[0] || textOrEmpty(product?.image_url) || textOrEmpty(product?.image_path) || textOrEmpty(product?.src);
  }

  function normalizeCartCustomText(value) {
    const text = textOrEmpty(value).trim();
    return text || null;
  }

  function normalizeStockValue(value, fallback = 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed >= 0) {
      return Math.max(0, Math.floor(parsed));
    }
    return Math.max(0, Math.floor(Number(fallback) || 0));
  }

  function ensureButtonLabelNode(button, fallbackLabel) {
    if (!button) {
      return null;
    }
    let labelNode = button.querySelector(".meltix-cart-button-label");
    if (labelNode) {
      return labelNode;
    }

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

    labelNode.textContent = textParts.join(" ") || fallbackLabel || "ADD TO CART";
    button.insertBefore(labelNode, button.firstChild);
    return labelNode;
  }

  function setButtonStockState(button, product, options) {
    if (!button) {
      return;
    }

    const stock = normalizeStockValue(product?.stock ?? product?.stock_quantity ?? button.dataset.stock, 0);
    const labelNode = ensureButtonLabelNode(button, options?.defaultLabel || "ADD TO CART");
    const defaultLabel = button.dataset.defaultLabel || textOrEmpty(labelNode?.textContent).trim() || options?.defaultLabel || "ADD TO CART";

    button.dataset.defaultLabel = defaultLabel;
    button.dataset.stock = String(stock);
    button.dataset.productId = String(product?.id || "");

    if (stock <= 0) {
      button.disabled = true;
      button.dataset.outOfStock = "true";
      if (labelNode) {
        labelNode.textContent = options?.outOfStockLabel || "OUT OF STOCK";
      }
      return;
    }

    button.dataset.outOfStock = "false";
    button.disabled = Boolean(options?.disabled);
    if (labelNode) {
      labelNode.textContent = defaultLabel;
    }
  }

  function renderDust(containerId, count) {
    const dustContainer = byId(containerId);
    if (!dustContainer || dustContainer.dataset.coreDustReady === "true") {
      return;
    }
    dustContainer.dataset.coreDustReady = "true";
    for (let index = 0; index < count; index += 1) {
      const particle = document.createElement("div");
      particle.className = "dust";
      particle.style.left = `${Math.random() * 100}vw`;
      particle.style.animationDuration = `${Math.random() * 15 + 10}s`;
      particle.style.animationDelay = `${Math.random() * 10}s`;
      const size = Math.random() * 3 + 1;
      particle.style.width = `${size}px`;
      particle.style.height = `${size}px`;
      dustContainer.appendChild(particle);
    }
  }

  function decodeJwtCredential(response) {
    try {
      const base64Url = response.credential.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split("")
          .map((char) => `%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`)
          .join("")
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error("Could not decode Google credential:", error);
      return null;
    }
  }

  function formatPrice(amount) {
    const parsed = Number(amount || 0);
    return `\u20b9 ${Number.isFinite(parsed) ? parsed : 0}`;
  }

  function setNodeText(id, value) {
    const node = byId(id);
    if (node) {
      node.textContent = textOrEmpty(value);
    }
  }

  function setNodeHtml(id, value) {
    const node = byId(id);
    if (node) {
      node.innerHTML = value || "";
    }
  }

  function toggleNodeDisplay(id, isVisible, displayValue) {
    const node = byId(id);
    if (node) {
      node.style.display = isVisible ? (displayValue || "") : "none";
    }
  }

  function fillPointerList(id, items) {
    const list = byId(id);
    if (!list) {
      return;
    }
    list.innerHTML = "";
    (items || []).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });
  }

  function normalizeIndiaWhatsAppDigits(input) {
    const digits = String(input || "").replace(/\D/g, "");
    if (digits.length === 12 && digits.startsWith("91") && /^[6-9]\d{9}$/.test(digits.slice(2))) {
      return digits;
    }
    if (digits.length === 10 && /^[6-9]\d{9}$/.test(digits)) {
      return `91${digits}`;
    }
    if (digits.length === 11 && digits.startsWith("0") && /^[6-9]\d{9}$/.test(digits.slice(1))) {
      return `91${digits.slice(1)}`;
    }
    return "";
  }

  function bindQuantityControl(config) {
    const input = byId(config.inputId);
    const minus = byId(config.minusId);
    const plus = byId(config.plusId);
    const minimum = Number(config.minimum || 1);
    const initialValue = Number(config.initialValue || minimum);

    if (!input || !minus || !plus) {
      return {
        getValue() {
          return minimum;
        },
        reset() {},
      };
    }

    function readValue() {
      const parsed = Number(input.value || initialValue);
      return Number.isFinite(parsed) && parsed >= minimum ? parsed : minimum;
    }

    function writeValue(nextValue) {
      input.value = String(Math.max(minimum, Number(nextValue || minimum)));
    }

    minus.addEventListener("click", () => writeValue(readValue() - 1));
    plus.addEventListener("click", () => writeValue(readValue() + 1));
    writeValue(initialValue);

    return {
      getValue() {
        return readValue();
      },
      reset() {
        writeValue(initialValue);
      },
    };
  }

  function createLightbox(imageSrc) {
    if (!imageSrc) {
      return;
    }

    let overlay = byId("meltix-lightbox");
    if (overlay) {
      overlay.remove();
    }

    overlay = document.createElement("div");
    overlay.id = "meltix-lightbox";
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.background = "rgba(10, 10, 14, 0.92)";
    overlay.style.display = "flex";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    overlay.style.zIndex = "999999";
    overlay.style.cursor = "zoom-out";

    const image = document.createElement("img");
    image.src = imageSrc;
    image.alt = "Expanded Meltix visual";
    image.style.maxWidth = "92vw";
    image.style.maxHeight = "92vh";
    image.style.objectFit = "contain";
    image.style.boxShadow = "0 24px 60px rgba(0, 0, 0, 0.45)";
    image.style.borderRadius = "18px";

    overlay.appendChild(image);
    overlay.addEventListener("click", () => overlay.remove());
    (byId("product-modal") || byId("productModal") || document.body).appendChild(overlay);
    requestAnimationFrame(() => {
      overlay.style.opacity = "1";
      image.style.transform = "scale(1)";
    });
  }

  function buildAvatarMarkup(review) {
    const avatarFilename = review.author_avatar_filename || review.avatar_filename || "";
    const avatarUrl = review.author_avatar_url || review.avatar_url || "";
    if (avatarUrl) {
      return `<img src="${avatarUrl}" alt="Avatar">`;
    }
    if (avatarFilename) {
      return `<img src="/static/images/avatar/${avatarFilename}" alt="Avatar">`;
    }
    const initial = (review.display_name || review.user_name || "U").charAt(0).toUpperCase();
    return `<div class="avatar-empty-state"><span class="avatar-empty-title" style="color:var(--accent-gold); font-family:'Playfair Display', serif; font-style:italic;">${initial}</span></div>`;
  }

  function buildReviewMarkup(review, currentUserEmail) {
    const userLevel = Number(review.author_level || review.level || 1);
    let vipClass = "";
    if (userLevel === 4) vipClass = "vip-review-lvl4";
    if (userLevel === 5) vipClass = "vip-review-lvl5";
    const deleteMarkup = currentUserEmail && review.author_email === currentUserEmail
      ? `<button class="delete-review-btn" onclick="deleteReview(${review.id})" title="Delete Review">&#128465;</button>`
      : "";
    const likeActive = review.current_user_action === "like" ? "active-like" : "";
    const dislikeActive = review.current_user_action === "dislike" ? "active-dislike" : "";
    const stars = "\u2605".repeat(Number(review.rating || 0));
    const displayName = review.display_name || review.user_name || "Guest";

    return `
<div class="review-item ${vipClass}">
  <div class="review-header-flex">
    <div class="review-user-info">
      <div class="avatar-micro-wrapper">
        <div class="avatar-stage avatar-ring-lvl-${userLevel}">
          <div class="diamond-mark"></div>
          <div class="avatar-ring"></div>
          <div class="avatar-trigger" style="animation:none; box-shadow:none;">
            ${buildAvatarMarkup(review)}
          </div>
        </div>
      </div>
      <div class="review-user-text">
        <p class="review-user">${displayName} <span style="color:#d4a373; font-size:0.8rem; margin-left:5px;">${stars}</span></p>
        <span style="font-size:0.72rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:1px;">Level ${userLevel}</span>
      </div>
    </div>
    ${deleteMarkup}
  </div>
  <p class="review-text" style="margin-top:12px;">"${review.review_text || ""}"</p>
  <div class="review-actions-bar">
    <button class="rev-act-btn ${likeActive}" onclick="handleReviewAction(${review.id}, 'like')">
      <span class="act-icon">&#128077;</span> <span class="cnt">${Number(review.likes || 0)}</span>
    </button>
    <button class="rev-act-btn ${dislikeActive}" onclick="handleReviewAction(${review.id}, 'dislike')">
      <span class="act-icon">&#128078;</span> <span class="cnt">${Number(review.dislikes || 0)}</span>
    </button>
  </div>
</div>`;
  }

  class BaseProductController {
    constructor(config) {
      this.config = config || {};
      this.catalogEndpoint = this.config.catalogEndpoint || "";
      this.profileBootstrapUrl = this.config.profileBootstrapUrl || "/api/profile/bootstrap";
      this.productStatesUrl = this.config.productStatesUrl || "/api/product-states";
      this.googleClientId = this.config.googleClientId || "";
      this.currentUserEmail = this.config.currentUserEmail || "";
      this.currentUserName = this.config.currentUserName || "";
      this.currentUserPicture = this.config.currentUserPicture || "";
      this.currentReviews = [];
      this.activeProductId = null;
      this.products = [];
      this.productMap = new Map();
      this.productsByGroup = new Map();
      this.likedProductIds = new Set();
      this.wishlistProductIds = new Set();
      this.googleButtonRendered = false;
      this.loadCatalogPromise = null;
      this.reviewForm = byId("reviewForm");
      this.reviewText = byId("reviewText");
      this.reviewRating = byId("reviewRating");
      this.displayStars = byId("displayStars");
      this.reviewsList = byId("reviewsList");
      this.loginPrompt = byId("loginToReviewPrompt");
      this.alreadyReviewedMessage = byId("alreadyReviewedMessage");
      this.submitReviewButton = byId("submitReviewBtn");
      this.modalWishlistButton = document.querySelector(this.config.modalWishlistSelector || ".absolute-wishlist");
      this.bindReviewStars();
    }

    bindReviewStars() {
      const stars = Array.from(document.querySelectorAll(".form-star"));
      if (!stars.length || !this.reviewRating) {
        return;
      }

      const paintStars = (value) => {
        stars.forEach((star) => {
          const current = Number(star.dataset.val || 0);
          star.classList.toggle("active", current <= value);
        });
      };

      stars.forEach((star) => {
        star.addEventListener("mouseenter", () => paintStars(Number(star.dataset.val || 0)));
        star.addEventListener("click", () => {
          this.reviewRating.value = String(Number(star.dataset.val || 0));
          paintStars(Number(this.reviewRating.value || 0));
        });
      });

      const starContainer = stars[0]?.parentElement;
      if (starContainer) {
        starContainer.addEventListener("mouseleave", () => paintStars(Number(this.reviewRating.value || 0)));
      }
    }

    bindGlobals(globalMap) {
      Object.entries(globalMap || {}).forEach(([key, fn]) => {
        window[key] = fn;
      });
    }

    isLoggedIn() {
      return Boolean(this.currentUserEmail);
    }

    rememberProducts(items) {
      this.products = Array.isArray(items) ? items : [];
      this.productMap = new Map();
      this.productsByGroup = new Map();
      this.products.forEach((product) => {
        this.productMap.set(Number(product.id), product);
        const groupName = textOrEmpty(product.group_name);
        if (!this.productsByGroup.has(groupName)) {
          this.productsByGroup.set(groupName, []);
        }
        this.productsByGroup.get(groupName).push(product);
      });
    }

    resolveProductTitle(product) {
      const details = product?.details || {};
      return textOrEmpty(details.title) || textOrEmpty(product?.title) || textOrEmpty(product?.name) || "Meltix Creation";
    }

    resolveProductStock(product) {
      return normalizeStockValue(product?.stock ?? product?.stock_quantity, 0);
    }

    syncAddToCartButton(button, product, options) {
      setButtonStockState(button, product, {
        defaultLabel: options?.defaultLabel || "ADD TO CART",
        outOfStockLabel: options?.outOfStockLabel || "OUT OF STOCK",
        disabled: Boolean(options?.disabled),
      });
    }

    addProductToCart(product, options) {
      if (!product || !window.MeltixCart?.addItem) {
        return false;
      }

      const didAdd = window.MeltixCart.addItem({
        id: product.id,
        name: this.resolveProductTitle(product),
        price: Number(product.price || 500),
        image: primaryProductImage(product),
        qty: Math.max(1, Number(options?.qty || 1)),
        stock: this.resolveProductStock(product),
        customText: normalizeCartCustomText(options?.customText),
      });
      if (!didAdd) {
        return false;
      }
      window.MeltixCart.signalAddSuccess?.(options?.button, {
        label: options?.successLabel || "ADDED",
        finalDisabled: options?.finalDisabled,
      });
      return true;
    }

    fillGallery(product) {
      const gallery = buildGalleryImages(product);
      const mainImage = byId("modalMainImage");
      if (mainImage) {
        mainImage.src = gallery[0] || "";
      }
      const legacyMain = byId("modalImage");
      if (legacyMain) {
        legacyMain.src = gallery[0] || "";
      }
      document.querySelectorAll(".thumb-img").forEach((thumb, index) => {
        thumb.src = gallery[index] || gallery[0] || "";
        thumb.classList.toggle("active-thumb", index === 0);
      });
    }

    async loadCatalog() {
      if (this.loadCatalogPromise) {
        return this.loadCatalogPromise;
      }

      this.loadCatalogPromise = fetch(this.catalogEndpoint)
        .then(async (response) => {
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload?.message || "Catalog fetch failed");
          }
          return payload;
        })
        .then((items) => {
          const mappedData = items.map((item) => ({
            id: item.id,
            title: item.name,
            src: `/static/images/${item.image_file}`,
            price: item.price,
            stock: normalizeStockValue(item.stock ?? item.stock_quantity, 0),
            name: item.name,
            group_name: item.group_name,
            collection_label: item.collection_label,
            details: item.details,
            ui_flags: item.ui_flags,
            image_url: item.image_url,
            image_path: item.image_path,
            stock_quantity: normalizeStockValue(item.stock ?? item.stock_quantity, 0),
          }));
          this.rememberProducts(mappedData);
          window.MeltixCart?.syncStocks?.(mappedData);
          return this.refreshProductStates(this.products.map((product) => product.id)).then(() => items);
        })
        .catch((error) => {
          console.error("Catalog load error:", error);
          this.loadCatalogPromise = null;
          throw error;
        });

      return this.loadCatalogPromise;
    }

    async refreshProductStates(productIds) {
      const uniqueIds = [...new Set((productIds || []).map((value) => Number(value)).filter((value) => Number.isInteger(value) && value > 0))];
      if (!uniqueIds.length) {
        this.syncRenderedLikeButtons();
        return;
      }

      uniqueIds.forEach((productId) => {
        this.likedProductIds.delete(String(productId));
        this.wishlistProductIds.delete(String(productId));
      });

      try {
        const response = await fetch(this.productStatesUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_ids: uniqueIds }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
          throw new Error(payload.message || "Product state sync failed");
        }
        (payload.liked_product_ids || []).forEach((productId) => this.likedProductIds.add(String(productId)));
        (payload.wishlist_product_ids || []).forEach((productId) => this.wishlistProductIds.add(String(productId)));
      } catch (error) {
        console.error("Product state error:", error);
      }

      this.syncRenderedLikeButtons();
      if (this.activeProductId !== null) {
        this.setSaveButtonState(this.activeProductId);
      }
    }

    syncRenderedLikeButtons() {
      document.querySelectorAll(".like-btn[data-product-id]").forEach((button) => {
        const productId = button.getAttribute("data-product-id");
        button.classList.toggle("liked", this.likedProductIds.has(String(productId)));
      });
    }

    setSaveButtonState(productId) {
      if (!this.modalWishlistButton) {
        return;
      }
      this.modalWishlistButton.classList.toggle("saved", this.wishlistProductIds.has(String(productId)));
    }
    async handleCredentialResponse(response) {
      const userData = decodeJwtCredential(response);
      if (!userData?.email) {
        return;
      }

      try {
        const bootstrapResponse = await fetch(this.profileBootstrapUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            credential: response.credential,
          }),
        });
        const payload = await bootstrapResponse.json();
        if (!bootstrapResponse.ok || !payload.success) {
          throw new Error(payload.message || "Profile bootstrap failed");
        }

        this.currentUserEmail = textOrEmpty(userData.email).trim().toLowerCase();
        this.currentUserName = textOrEmpty(userData.name);
        this.currentUserPicture = textOrEmpty(userData.picture);
        await this.refreshProductStates(this.getVisibleProductIds());
        if (this.activeProductId !== null) {
          await this.fetchAndRenderReviews(this.activeProductId);
        } else {
          this.toggleAuthFormState();
        }
      } catch (error) {
        console.error("Google sign-in error:", error);
        alert("Google sign-in could not be completed right now.");
      }
    }

    ensureGoogleButtonRendered() {
      const target = byId("google-login-button");
      if (!target || this.googleButtonRendered || !window.google?.accounts?.id || !this.googleClientId) {
        return;
      }
      window.google.accounts.id.initialize({
        client_id: this.googleClientId,
        callback: this.handleCredentialResponse.bind(this),
        auto_select: false,
      });
      window.google.accounts.id.renderButton(target, {
        theme: "filled_black",
        size: "large",
        shape: "rectangular",
      });
      this.googleButtonRendered = true;
    }

    renderReviewSummary(payload) {
      if (!this.displayStars) {
        return;
      }
      const avgRating = Number(payload?.average_rating || 0);
      const totalReviews = Number(payload?.total_reviews || 0);
      if (!totalReviews) {
        this.displayStars.innerHTML = `<span class="rating-text">No reviews yet</span>`;
        return;
      }
      this.displayStars.innerHTML = `<span class="rating-text">${avgRating.toFixed(1)} (${totalReviews} Reviews)</span>`;
    }

    renderReviews(payload) {
      this.currentReviews = Array.isArray(payload?.reviews_data) ? payload.reviews_data : [];
      this.renderReviewSummary(payload);
      if (!this.reviewsList) {
        return;
      }
      if (!this.currentReviews.length) {
        this.reviewsList.innerHTML = `<p class="review-text" style="text-align:center; padding:20px 0;">Be the first to share your experience!</p>`;
        return;
      }
      this.reviewsList.innerHTML = this.currentReviews.map((review) => buildReviewMarkup(review, this.currentUserEmail)).join("");
    }

    toggleAuthFormState() {
      if (!this.reviewForm || !this.loginPrompt || !this.alreadyReviewedMessage) {
        return;
      }

      const alreadyReviewed = Boolean(
        this.currentUserEmail &&
        this.currentReviews.some((review) => textOrEmpty(review.author_email).toLowerCase() === this.currentUserEmail)
      );

      if (!this.isLoggedIn()) {
        this.reviewForm.style.display = "none";
        this.loginPrompt.style.display = "";
        this.alreadyReviewedMessage.style.display = "none";
        this.ensureGoogleButtonRendered();
        return;
      }

      if (alreadyReviewed) {
        this.reviewForm.style.display = "none";
        this.loginPrompt.style.display = "none";
        this.alreadyReviewedMessage.style.display = "";
        return;
      }

      this.reviewForm.style.display = "flex";
      this.reviewForm.classList.remove("locked");
      this.loginPrompt.style.display = "none";
      this.alreadyReviewedMessage.style.display = "none";
    }

    async fetchAndRenderReviews(productId) {
      if (!productId) {
        return;
      }
      try {
        const response = await fetch(`/get_reviews/${productId}`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.message || "Review fetch failed");
        }
        this.renderReviews(payload);
        this.toggleAuthFormState();
      } catch (error) {
        console.error("Review fetch error:", error);
      }
    }

    async submitReview(event) {
      event.preventDefault();
      if (!this.activeProductId) {
        return;
      }

      const reviewText = textOrEmpty(this.reviewText?.value).trim();
      const rating = Number(this.reviewRating?.value || 0);
      if (!rating) {
        alert("Please select a star rating.");
        return;
      }

      if (this.submitReviewButton) {
        this.submitReviewButton.innerText = "Posting...";
      }

      try {
        const response = await fetch("/submit_review", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_id: this.activeProductId,
            review_text: reviewText,
            rating,
          }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
          throw new Error(payload.message || "Review post failed");
        }

        this.reviewForm?.reset();
        if (this.reviewRating) {
          this.reviewRating.value = "0";
        }
        document.querySelectorAll(".form-star").forEach((star) => star.classList.remove("active"));
        await this.fetchAndRenderReviews(this.activeProductId);
      } catch (error) {
        console.error("Review submit error:", error);
        alert(error.message || "Review could not be posted.");
      } finally {
        if (this.submitReviewButton) {
          this.submitReviewButton.innerText = "Post Review";
        }
      }
    }

    async handleReviewAction(reviewId, actionType) {
      if (!this.isLoggedIn()) {
        alert("Please sign in with Google first.");
        return;
      }

      try {
        const response = await fetch("/toggle_review_like", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ review_id: reviewId, action: actionType }),
        });
        const payload = await response.json();
        if (!response.ok || payload.status !== "success") {
          throw new Error(payload.message || "Could not update review reaction");
        }
        await this.fetchAndRenderReviews(this.activeProductId);
      } catch (error) {
        console.error("Review reaction error:", error);
      }
    }

    async deleteReview(reviewId) {
      if (!confirm("Are you sure you want to delete this review?")) {
        return;
      }

      try {
        const response = await fetch(`/delete_review/${reviewId}`, { method: "POST" });
        const payload = await response.json();
        if (!response.ok || payload.status !== "success") {
          throw new Error(payload.message || "Could not delete review");
        }
        await this.fetchAndRenderReviews(this.activeProductId);
      } catch (error) {
        console.error("Delete review error:", error);
      }
    }

    async toggleWishlist() {
      if (!this.isLoggedIn()) {
        alert("Please sign in with Google first.");
        return;
      }

      try {
        const response = await fetch("/toggle_wishlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: this.activeProductId }),
        });
        const payload = await response.json();
        if (!response.ok || payload.status !== "success") {
          throw new Error(payload.message || "Wishlist update failed");
        }
        if (payload.saved_in_wishlist) {
          this.wishlistProductIds.add(String(this.activeProductId));
        } else {
          this.wishlistProductIds.delete(String(this.activeProductId));
        }
        this.setSaveButtonState(this.activeProductId);
      } catch (error) {
        console.error("Wishlist error:", error);
      }
    }

    changeModalImage(element, src) {
      const mainImage = byId("modalMainImage");
      if (mainImage) {
        mainImage.src = src;
      }
      document.querySelectorAll(".thumb-img").forEach((thumb) => thumb.classList.remove("active-thumb"));
      if (element) {
        element.classList.add("active-thumb");
      }
    }

    openLightbox(imageSrc) {
      createLightbox(imageSrc);
    }

    getProduct(productId) {
      return this.productMap.get(Number(productId)) || null;
    }

    getVisibleProductIds() {
      return this.products.map((product) => product.id);
    }
  }

  class CarouselCollectionController extends BaseProductController {
    constructor(config) {
      super(config);
      this.groups = config.groups || [];
      this.groupMeta = new Map(this.groups.map((group) => [group.name, group]));
      this.activeGroup = this.groups[0]?.name || "";
      this.dragArea = byId("drag-area");
      this.track = byId("carousel-track");
      this.scrubber = byId("custom-scrubber");
      this.bgTitle = byId("bg-dynamic-title");
      this.backToOptionsButton = byId("backToOptionsBtn");
      this.productShowcase = byId("product-showcase");
      this.accordionBox = byId("accordion-box");
      this.fabMenu = byId("fab-menu");
      this.fabOptions = byId("fab-options");
      this.stopButton = byId("stop-showcase-btn");
      this.prevButton = byId("showcasePrevBtn");
      this.nextButton = byId("showcaseNextBtn");
      this.indicatorsContainer = byId("showcaseIndicators");
      this.modal = byId("productModal");
      this.showcaseMode = textOrEmpty(this.config.showcaseMode).trim().toLowerCase() || "legacy-3d";
      this.isSnapShowcase = this.showcaseMode === "luxury-snap";
      this.isDragging = false;
      this.isActuallyDragging = false;
      this.isScrubbing = false;
      this.isAutoScrollActive = true;
      this.mouseDownX = 0;
      this.startX = 0;
      this.startScrollLeft = 0;
      this.clickThreshold = 10;
      this.autoScrollFrame = null;
      this.lastAutoScrollTimestamp = 0;
      this.renderFramePending = false;
      this.singleSetWidth = 0;
      this.legacyScrollLoop = this.config.legacyScrollLoop !== false;
      this.reducedMotion = false;
      this.currentIndex = 0;
      this.autoShowcaseInterval = null;
      this.snapCurrentX = 0;
      this.snapBaseOffset = 0;
      this.snapDirection = 1;

      renderDust(config.dustContainerId || "dust-particles", config.dustCount || 50);
      this.reducedMotion = Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
      this.bindCarouselInteractions();
      this.bindBackToOptions();
      this.bindGlobals({
        handleSelection: this.handleSelection.bind(this),
        switchVariant: this.switchVariant.bind(this),
        toggleFabMenu: this.toggleFabMenu.bind(this),
        closeModal: this.closeModal.bind(this),
        submitReview: this.submitReview.bind(this),
        toggleWishlist: this.toggleWishlist.bind(this),
        changeModalImage: this.changeModalImage.bind(this),
        openLightbox: this.openLightbox.bind(this),
        handleReviewAction: this.handleReviewAction.bind(this),
        deleteReview: this.deleteReview.bind(this),
        handleCredentialResponse: this.handleCredentialResponse.bind(this),
      });
    }

    bindCarouselInteractions() {
      if (!this.dragArea || !this.track) {
        return;
      }

      if (this.isSnapShowcase) {
        this.bindSnapCarouselInteractions();
        return;
      }

      this.dragArea.addEventListener("mousedown", (event) => {
        this.isDragging = true;
        this.isActuallyDragging = false;
        this.mouseDownX = event.pageX;
        this.startX = event.pageX;
        this.startScrollLeft = this.dragArea.scrollLeft;
        this.dragArea.style.cursor = "grabbing";
      });

      window.addEventListener("mouseup", () => {
        this.isDragging = false;
        this.dragArea.style.cursor = "grab";
      });

      window.addEventListener("mousemove", (event) => {
        if (!this.isDragging) {
          return;
        }
        event.preventDefault();
        const diff = event.pageX - this.startX;
        this.dragArea.scrollLeft = this.startScrollLeft - diff;
        if (Math.abs(event.pageX - this.mouseDownX) > this.clickThreshold) {
          this.isActuallyDragging = true;
        }
        this.updateScrubber();
        this.scheduleRenderFrame();
      });

      this.dragArea.addEventListener("scroll", () => {
        this.normalizeLoopPosition();
        this.updateScrubber();
        this.scheduleRenderFrame();
      });

      this.scrubber?.addEventListener("input", () => {
        this.isScrubbing = true;
        const maxScroll = Math.max(this.track.scrollWidth - this.dragArea.clientWidth, 0);
        this.dragArea.scrollLeft = (Number(this.scrubber.value || 0) / 100) * maxScroll;
      });
      ["change", "mouseup", "touchend"].forEach((eventName) => {
        this.scrubber?.addEventListener(eventName, () => {
          this.isScrubbing = false;
        });
      });

      this.stopButton?.addEventListener("click", () => {
        this.isAutoScrollActive = !this.isAutoScrollActive;
        this.stopButton.innerText = this.isAutoScrollActive ? "Stop Auto Showcasing" : "Resume Auto Showcasing";
        if (this.isAutoScrollActive) {
          this.lastAutoScrollTimestamp = 0;
          this.startAutoScroll();
        } else if (this.autoScrollFrame) {
          cancelAnimationFrame(this.autoScrollFrame);
        }
      });

      if (this.modal) {
        window.addEventListener("click", (event) => {
          if (event.target === this.modal) {
            this.closeModal();
          }
        });
      }
    }

    bindSnapCarouselInteractions() {
      this.ensureSnapControlLayout();
      this.dragArea.style.cursor = "grab";
      this.dragArea.style.touchAction = "pan-y";

      this.prevButton?.addEventListener("click", () => {
        this.snapDirection = -1;
        this.goToSnapSlide(this.currentIndex - 1);
      });

      this.nextButton?.addEventListener("click", () => {
        this.snapDirection = 1;
        this.goToSnapSlide(this.currentIndex + 1);
      });

      this.dragArea.addEventListener("pointerdown", (event) => {
        if (event.pointerType === "mouse" && event.button !== 0) {
          return;
        }
        if (event.target instanceof Element && event.target.closest(".like-btn")) {
          return;
        }
        this.isDragging = true;
        this.isActuallyDragging = false;
        this.mouseDownX = event.clientX;
        this.startX = event.clientX;
        this.snapCurrentX = event.clientX;
        this.track.style.transition = "none";
        this.stopSnapAutoShowcase();
        this.dragArea.style.cursor = "grabbing";
        if (typeof this.dragArea.setPointerCapture === "function") {
          try {
            this.dragArea.setPointerCapture(event.pointerId);
          } catch (_error) {
            // Ignore pointer capture failures.
          }
        }
      });

      this.dragArea.addEventListener("pointermove", (event) => {
        if (!this.isDragging) {
          return;
        }
        event.preventDefault();
        this.snapCurrentX = event.clientX;
        const diff = this.snapCurrentX - this.startX;
        this.applySnapTransform(this.snapBaseOffset + diff);
        if (Math.abs(this.snapCurrentX - this.mouseDownX) > this.clickThreshold) {
          this.isActuallyDragging = true;
        }
      });

      const endSnapDrag = (event) => {
        if (!this.isDragging) {
          return;
        }
        const wasActuallyDragging = this.isActuallyDragging;
        this.isDragging = false;
        this.dragArea.style.cursor = "grab";
        const metrics = this.getSnapMetrics();
        const diff = this.snapCurrentX - this.startX;
        const threshold = metrics ? metrics.cardWidth / 4 : 80;

        if (Math.abs(diff) > threshold) {
          this.snapDirection = diff > 0 ? -1 : 1;
          this.currentIndex += diff > 0 ? -1 : 1;
        }

        if (!wasActuallyDragging && this.tryOpenSnapCardAtPoint(event?.clientX, event?.clientY)) {
          this.isActuallyDragging = false;
          return;
        }
        this.updateSnapCarousel(true);
        this.resetSnapAutoShowcase();
        window.setTimeout(() => {
          this.isActuallyDragging = false;
        }, 0);
      };

      this.dragArea.addEventListener("pointerup", endSnapDrag);
      this.dragArea.addEventListener("pointercancel", endSnapDrag);
      this.dragArea.addEventListener("lostpointercapture", endSnapDrag);

      this.dragArea.addEventListener("click", (event) => {
        if (event.target instanceof Element && event.target.closest(".like-btn")) {
          return;
        }
        if (!this.isActuallyDragging) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
      }, true);

      this.scrubber?.addEventListener("input", () => {
        const cards = this.getSnapCards();
        const lastIndex = cards.length - 1;
        if (lastIndex < 1) {
          this.scrubber.value = "0";
          return;
        }

        this.isScrubbing = true;
        this.stopSnapAutoShowcase();
        const progress = Math.max(0, Math.min(1, Number(this.scrubber.value || 0) / 100));
        const previewIndex = Math.round(progress * lastIndex);
        if (previewIndex !== this.currentIndex) {
          this.snapDirection = previewIndex > this.currentIndex ? 1 : -1;
        }
        this.previewSnapProgress(progress);
      });

      ["change", "mouseup", "touchend"].forEach((eventName) => {
        this.scrubber?.addEventListener(eventName, () => {
          if (!this.isScrubbing) {
            return;
          }
          this.isScrubbing = false;
          const cards = this.getSnapCards();
          const lastIndex = cards.length - 1;
          const progress = Math.max(0, Math.min(1, Number(this.scrubber?.value || 0) / 100));
          const targetIndex = lastIndex > 0 ? Math.round(progress * lastIndex) : 0;
          this.goToSnapSlide(targetIndex);
        });
      });

      this.productShowcase?.addEventListener("mouseenter", () => {
        this.stopSnapAutoShowcase();
      });

      this.productShowcase?.addEventListener("mouseleave", () => {
        this.resetSnapAutoShowcase();
      });

      window.addEventListener("keydown", (event) => {
        if (!this.productShowcase?.classList.contains("show")) {
          return;
        }
        if (event.key === "ArrowRight") {
          this.goToSnapSlide(this.currentIndex + 1);
        }
        if (event.key === "ArrowLeft") {
          this.goToSnapSlide(this.currentIndex - 1);
        }
      });

      window.addEventListener("resize", () => {
        this.updateSnapCarousel(false);
      });

      if (this.modal) {
        window.addEventListener("click", (event) => {
          if (event.target === this.modal) {
            this.closeModal();
          }
        });
      }
    }

    getSnapCards() {
      return Array.from(this.track?.querySelectorAll(".showcase-product-card") || []);
    }

    ensureSnapControlLayout() {
      const scrubberWrapper = this.scrubber?.closest(".scrubber-wrapper");
      if (!scrubberWrapper) {
        return;
      }

      let scrubberControls = scrubberWrapper.querySelector(".scrubber-controls");
      if (!scrubberControls) {
        scrubberControls = document.createElement("div");
        scrubberControls.className = "scrubber-controls";
        scrubberWrapper.prepend(scrubberControls);
      }

      if (this.prevButton) {
        scrubberControls.appendChild(this.prevButton);
      }
      if (this.scrubber) {
        scrubberControls.appendChild(this.scrubber);
      }
      if (this.nextButton) {
        scrubberControls.appendChild(this.nextButton);
      }

      if (this.indicatorsContainer) {
        this.indicatorsContainer.innerHTML = "";
        this.indicatorsContainer.remove();
        this.indicatorsContainer = null;
      }

      const legacyControls = this.productShowcase?.querySelector(".carousel-controls--luxury, .carousel-controls");
      if (legacyControls && legacyControls !== scrubberControls) {
        legacyControls.remove();
      }
    }

    tryOpenSnapCardAtPoint(clientX, clientY) {
      if (typeof clientX !== "number" || typeof clientY !== "number") {
        return false;
      }

      const target = document.elementFromPoint(clientX, clientY);
      if (!(target instanceof Element)) {
        return false;
      }
      if (target.closest(".like-btn")) {
        return false;
      }

      const card = target.closest(".showcase-product-card");
      const productId = Number(card?.dataset.productId || 0);
      if (!card || !productId) {
        return false;
      }

      this.openModal(productId);
      return true;
    }

    getSnapMetrics() {
      const cards = this.getSnapCards();
      const firstCard = cards[0];
      if (!firstCard || !this.dragArea) {
        return null;
      }
      const trackStyles = window.getComputedStyle(this.track);
      const gap = Number.parseFloat(trackStyles.columnGap || trackStyles.gap || "30") || 30;
      return {
        cards,
        cardWidth: firstCard.getBoundingClientRect().width,
        gap,
        viewportWidth: this.dragArea.clientWidth,
      };
    }

    getSnapOffset(index) {
      const metrics = this.getSnapMetrics();
      if (!metrics) {
        return 0;
      }
      return ((metrics.viewportWidth - metrics.cardWidth) / 2) - (index * (metrics.cardWidth + metrics.gap));
    }

    applySnapTransform(offset) {
      if (this.track) {
        this.track.style.transform = `translateX(${offset}px)`;
      }
    }

    setSnapActiveState(activeIndex, cards = null) {
      const resolvedCards = cards || this.getSnapCards();
      resolvedCards.forEach((card, index) => {
        card.classList.toggle("is-active", index === activeIndex);
      });

      Array.from(this.indicatorsContainer?.children || []).forEach((indicator, index) => {
        indicator.classList.toggle("is-active", index === activeIndex);
      });
    }

    bindBackToOptions() {
      this.backToOptionsButton?.addEventListener("click", (event) => {
        const optionsVisible = Boolean(this.accordionBox && !this.accordionBox.classList.contains("fade-out-active"));
        const showcaseVisible = Boolean(this.productShowcase?.classList.contains("show"));
        const modalVisible = Boolean(this.modal?.classList.contains("show"));

        if (optionsVisible && !showcaseVisible && !modalVisible) {
          return;
        }

        event.preventDefault();
        this.returnToOptions();
      });
    }

    previewSnapProgress(progress) {
      const metrics = this.getSnapMetrics();
      if (!metrics || metrics.cards.length < 2) {
        this.updateSnapCarousel(false);
        return;
      }

      const maxIndex = metrics.cards.length - 1;
      const clampedProgress = Math.max(0, Math.min(1, progress));
      const firstOffset = this.getSnapOffset(0);
      const lastOffset = this.getSnapOffset(maxIndex);
      const previewOffset = firstOffset + ((lastOffset - firstOffset) * clampedProgress);

      if (this.track) {
        this.track.style.transition = "none";
      }
      this.applySnapTransform(previewOffset);
      this.setSnapActiveState(Math.round(clampedProgress * maxIndex), metrics.cards);
    }

    renderSnapIndicators(products) {
      void products;
      this.ensureSnapControlLayout();
    }

    updateSnapCarousel(animate = true) {
      const cards = this.getSnapCards();
      if (!cards.length) {
        return;
      }

      const maxIndex = cards.length - 1;
      this.currentIndex = Math.max(0, Math.min(this.currentIndex, maxIndex));
      this.snapBaseOffset = this.getSnapOffset(this.currentIndex);

      if (this.track) {
        this.track.style.transition = animate
          ? "transform 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)"
          : "none";
      }
      this.applySnapTransform(this.snapBaseOffset);
      this.setSnapActiveState(this.currentIndex, cards);
      this.updateScrubber();
    }

    stopSnapAutoShowcase() {
      if (this.autoShowcaseInterval) {
        window.clearInterval(this.autoShowcaseInterval);
        this.autoShowcaseInterval = null;
      }
    }

    startSnapAutoShowcase() {
      if (!this.isSnapShowcase || this.reducedMotion) {
        return;
      }
      const cards = this.getSnapCards();
      if (cards.length < 2) {
        return;
      }
      this.stopSnapAutoShowcase();
      this.autoShowcaseInterval = window.setInterval(() => {
        if (!this.isDragging && !this.isScrubbing && this.productShowcase?.classList.contains("show")) {
          const lastIndex = cards.length - 1;
          if (this.currentIndex >= lastIndex) {
            this.snapDirection = -1;
          } else if (this.currentIndex <= 0) {
            this.snapDirection = 1;
          }
          this.currentIndex += this.snapDirection;
          this.updateSnapCarousel(true);
        }
      }, Number(this.config.autoShowcaseDelay || 3200));
    }

    resetSnapAutoShowcase() {
      if (!this.productShowcase?.classList.contains("show")) {
        return;
      }
      this.startSnapAutoShowcase();
    }

    goToSnapSlide(index) {
      const previousIndex = this.currentIndex;
      const maxIndex = Math.max(this.getSnapCards().length - 1, 0);
      this.currentIndex = Math.max(0, Math.min(index, maxIndex));
      if (this.currentIndex !== previousIndex) {
        this.snapDirection = this.currentIndex > previousIndex ? 1 : -1;
      }
      this.updateSnapCarousel(true);
      this.resetSnapAutoShowcase();
    }

    updateScrubber() {
      if (!this.scrubber || !this.dragArea || !this.track) {
        return;
      }
      if (this.isSnapShowcase) {
        const cards = this.getSnapCards();
        const maxIndex = cards.length - 1;
        const progress = maxIndex > 0 ? (this.currentIndex / maxIndex) * 100 : 0;
        this.scrubber.value = String(Math.max(0, Math.min(100, progress)));
        return;
      }
      const loopStart = this.singleSetWidth || 0;
      const loopEnd = this.singleSetWidth ? this.singleSetWidth * 2 : 0;
      const progressSpan = loopEnd > loopStart ? (loopEnd - loopStart) : Math.max(this.track.scrollWidth - this.dragArea.clientWidth, 0);
      const normalized = this.singleSetWidth ? (this.dragArea.scrollLeft - loopStart) : this.dragArea.scrollLeft;
      const progress = progressSpan ? (normalized / progressSpan) * 100 : 0;
      this.scrubber.value = String(Math.max(0, Math.min(100, progress)));
    }

    normalizeLoopPosition() {
      if (this.legacyScrollLoop || !this.dragArea || !this.singleSetWidth) {
        return;
      }
      const minBand = this.singleSetWidth;
      const maxBand = this.singleSetWidth * 2;

      while (this.dragArea.scrollLeft < minBand) {
        this.dragArea.scrollLeft += this.singleSetWidth;
      }
      while (this.dragArea.scrollLeft >= maxBand) {
        this.dragArea.scrollLeft -= this.singleSetWidth;
      }
    }

    scheduleRenderFrame() {
      if (this.isSnapShowcase) {
        return;
      }
      if (this.reducedMotion) {
        return;
      }
      if (this.renderFramePending) {
        return;
      }
      this.renderFramePending = true;
      requestAnimationFrame(() => {
        this.renderFramePending = false;
        this.forceRenderFrame();
      });
    }

    forceRenderFrame() {
      if (this.isSnapShowcase) {
        return;
      }
      if (!this.dragArea || !this.track) {
        return;
      }
      const centerPoint = this.dragArea.getBoundingClientRect().left + this.dragArea.clientWidth / 2;
      this.track.querySelectorAll(".img-container").forEach((image) => {
        image.classList.remove("center-glow");
        const imageCenter = image.getBoundingClientRect().left + image.clientWidth / 2;
        const distance = Math.abs(centerPoint - imageCenter);
        const maxDistance = this.dragArea.clientWidth / 1.5;
        let scale = 0.7;
        let opacity = 0.3;
        let zIndex = 1;

        if (distance < maxDistance) {
          const ratio = 1 - distance / maxDistance;
          scale = 0.7 + 0.5 * ratio;
          opacity = 0.3 + 0.7 * ratio;
          zIndex = Math.round(ratio * 10);
        }

        image.style.transform = `scale(${scale})`;
        image.style.opacity = String(opacity);
        image.style.zIndex = String(zIndex);

        if (scale > 1.05) {
          image.classList.add("center-glow");
        }
      });
    }

    startAutoScroll() {
      if (this.isSnapShowcase) {
        this.startSnapAutoShowcase();
        return;
      }
      if (!this.dragArea || !this.track) {
        return;
      }
      if (this.autoScrollFrame) {
        cancelAnimationFrame(this.autoScrollFrame);
      }

      const tick = (timestamp) => {
        const now = Number(timestamp || performance.now());
        if (!this.lastAutoScrollTimestamp) {
          this.lastAutoScrollTimestamp = now;
        }
        const deltaMs = now - this.lastAutoScrollTimestamp;
        this.lastAutoScrollTimestamp = now;
        const frameFactor = Math.max(0.6, Math.min(deltaMs / 16.67, 2));

        const showcaseVisible = !this.productShowcase || this.productShowcase.classList.contains("show");
        if (showcaseVisible && this.isAutoScrollActive && !this.isDragging && !this.isScrubbing) {
          const speed = Number(this.config.autoScrollSpeed || 0.6);
          this.dragArea.scrollLeft += speed * frameFactor;
          if (this.legacyScrollLoop) {
            const maxScroll = Math.max(this.track.scrollWidth - this.dragArea.clientWidth, 0);
            if (maxScroll > 0 && this.dragArea.scrollLeft >= maxScroll - 1) {
              this.dragArea.scrollLeft = 0;
            }
          } else {
            this.normalizeLoopPosition();
          }
          this.updateScrubber();
          this.scheduleRenderFrame();
        }
        this.autoScrollFrame = requestAnimationFrame(tick);
      };

      this.autoScrollFrame = requestAnimationFrame(tick);
    }

    toggleFabMenu() {
      this.fabOptions?.classList.toggle("open");
    }

    async renderGroup(groupName) {
      await this.loadCatalog();
      this.activeGroup = groupName;
      const products = this.productsByGroup.get(groupName) || [];
      this.track && (this.track.innerHTML = "");
      await this.refreshProductStates(products.map((product) => product.id));

      if (this.isSnapShowcase) {
        this.currentIndex = 0;
        this.snapDirection = 1;
        this.stopSnapAutoShowcase();
        this.renderSnapIndicators(products);

        products.forEach((product) => {
          const details = product.details || {};
          const card = document.createElement("article");
          card.className = "img-container showcase-product-card product-card";
          card.dataset.productId = String(product.id);
          card.tabIndex = 0;
          card.setAttribute("role", "button");
          card.setAttribute("aria-label", `Open ${details.title || product.title || product.name || "product"} details`);

          const media = document.createElement("div");
          media.className = "showcase-card-media";
          const image = document.createElement("img");
          image.className = "carousel-img showcase-card-image";
          image.src = product.image_url || product.src || "";
          image.alt = details.title || product.title || product.name || "";
          image.draggable = false;
          media.appendChild(image);
          card.appendChild(media);

          const info = document.createElement("div");
          info.className = "showcase-card-info";

          const title = document.createElement("h3");
          title.className = "showcase-card-title";
          title.textContent = details.title || product.title || product.name || "Hidden Message";
          info.appendChild(title);

          const price = document.createElement("p");
          price.className = "showcase-card-price";
          price.textContent = formatPrice(product.price || 500);
          info.appendChild(price);

          card.appendChild(info);

          card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              this.openModal(product.id);
            }
          });

          card.addEventListener("click", (event) => {
            if (this.isActuallyDragging) {
              return;
            }
            if (event.target instanceof Element && event.target.closest(".like-btn")) {
              return;
            }
            if (this.modal?.classList.contains("show")) {
              return;
            }
            this.openModal(product.id);
          });

          if (this.config.enableLikeButtons !== false) {
            const likeButton = document.createElement("button");
            likeButton.className = "like-btn";
            likeButton.dataset.productId = product.id;
            likeButton.setAttribute("aria-label", `Save ${details.title || product.title || product.name || "product"} for later`);
            likeButton.innerHTML = `
              <svg class="heart-icon" viewBox="0 0 24 24">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"></path>
              </svg>`;
            likeButton.classList.toggle("liked", this.likedProductIds.has(String(product.id)));
            ["pointerdown", "mousedown", "touchstart"].forEach((eventName) => {
              likeButton.addEventListener(eventName, (event) => {
                event.stopPropagation();
              });
            });
            likeButton.addEventListener("click", (event) => {
              event.preventDefault();
              event.stopPropagation();
              this.toggleProductLike(product.id, likeButton);
            });
            card.appendChild(likeButton);
          }

          this.track?.appendChild(card);
        });

        requestAnimationFrame(() => {
          this.updateSnapCarousel(false);
          this.startSnapAutoShowcase();
        });
        return;
      }

      const loopedProducts = this.legacyScrollLoop ? products : [...products, ...products, ...products];
      loopedProducts.forEach((product) => {
        const container = document.createElement("div");
        container.className = "img-container carousel-item";

        const image = document.createElement("img");
        image.className = "carousel-img";
        image.src = product.image_url || product.src || "";
        image.alt = product.title || product.name || "";
        image.draggable = false;
        const handleOpen = () => {
          if (!this.isActuallyDragging) {
            this.openModal(product.id);
          }
        };
        image.addEventListener("click", handleOpen);
        container.addEventListener("click", handleOpen);
        container.appendChild(image);

        if (this.config.enableLikeButtons !== false) {
          const likeButton = document.createElement("button");
          likeButton.className = "like-btn";
          likeButton.dataset.productId = product.id;
          likeButton.innerHTML = `
            <svg class="heart-icon" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"></path>
            </svg>`;
          likeButton.classList.toggle("liked", this.likedProductIds.has(String(product.id)));
          ["pointerdown", "mousedown", "touchstart"].forEach((eventName) => {
            likeButton.addEventListener(eventName, (event) => {
              event.stopPropagation();
            });
          });
          likeButton.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.toggleProductLike(product.id, likeButton);
          });
          container.appendChild(likeButton);
        }

        this.track?.appendChild(container);
      });

      requestAnimationFrame(() => {
        if (this.dragArea) {
          if (this.legacyScrollLoop) {
            this.singleSetWidth = 0;
            this.dragArea.scrollLeft = 0;
          } else {
            this.singleSetWidth = this.track ? Math.max(this.track.scrollWidth / 3, 0) : 0;
            this.dragArea.scrollLeft = this.singleSetWidth || 0;
            this.normalizeLoopPosition();
          }
        }
        this.updateScrubber();
        this.scheduleRenderFrame();
        this.lastAutoScrollTimestamp = 0;
        this.startAutoScroll();
      });
    }

    async toggleProductLike(productId, button) {
      if (!this.isLoggedIn()) {
        alert("Please sign in with Google first.");
        return;
      }
      const isLiked = this.likedProductIds.has(String(productId));
      try {
        const response = await fetch("/like_product", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: productId, action: isLiked ? "unlike" : "like" }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
          throw new Error(payload.message || "Could not update like");
        }
        if (isLiked) {
          this.likedProductIds.delete(String(productId));
        } else {
          this.likedProductIds.add(String(productId));
        }
        button?.classList.toggle("liked", !isLiked);
      } catch (error) {
        console.error("Like toggle error:", error);
      }
    }

    async handleSelection(groupName) {
      await this.loadCatalog();
      const group = this.groupMeta.get(groupName) || {};
      this.accordionBox?.classList.add("fade-out-active");
      if (this.bgTitle) {
        this.bgTitle.innerText = group.watermark || firstWordUpper(groupName);
      }
      await this.renderGroup(groupName);
      window.setTimeout(() => {
        this.productShowcase?.classList.add("show");
        this.fabMenu?.classList.add("show");
      }, Number(this.config.selectionRevealDelay || 800));
    }

    returnToOptions() {
      if (this.modal?.classList.contains("show")) {
        this.modal.classList.remove("show");
        document.body.style.overflow = "";
        this.activeProductId = null;
        if (typeof this.config.onModalClose === "function") {
          this.config.onModalClose();
        }
      }

      this.stopSnapAutoShowcase?.();
      if (this.autoScrollFrame) {
        cancelAnimationFrame(this.autoScrollFrame);
        this.autoScrollFrame = null;
      }
      this.lastAutoScrollTimestamp = 0;
      this.isDragging = false;
      this.isActuallyDragging = false;
      this.isScrubbing = false;
      this.fabOptions?.classList.remove("open");
      this.fabMenu?.classList.remove("show");
      this.productShowcase?.classList.remove("show");
      if (this.productShowcase) {
        this.productShowcase.style.opacity = "";
      }
      this.accordionBox?.classList.remove("fade-out-active");
    }

    async switchVariant(groupName) {
      const group = this.groupMeta.get(groupName) || {};
      this.fabOptions?.classList.remove("open");
      if (this.productShowcase) {
        this.productShowcase.style.opacity = "0";
      }
      window.setTimeout(async () => {
        if (this.bgTitle) {
          this.bgTitle.innerText = group.watermark || firstWordUpper(groupName);
        }
        await this.renderGroup(groupName);
        this.track?.querySelectorAll(".img-container").forEach((image) => image.classList.remove("center-glow"));
        if (this.productShowcase) {
          this.productShowcase.style.opacity = "1";
        }
        this.scheduleRenderFrame();
      }, 500);
    }

    buildUiApi(product) {
      return {
        product,
        controller: this,
        show(id, displayValue) {
          toggleNodeDisplay(id, true, displayValue);
        },
        hide(id) {
          toggleNodeDisplay(id, false);
        },
        setText(id, value) {
          setNodeText(id, value);
        },
        setHtml(id, value) {
          setNodeHtml(id, value);
        },
        fillList(id, items) {
          fillPointerList(id, items);
        },
      };
    }

    async openModal(productId) {
      const product = this.getProduct(productId);
      if (!product) {
        return;
      }

      if (this.isSnapShowcase) {
        this.stopSnapAutoShowcase();
      }
      this.activeProductId = Number(productId);
      const details = product.details || {};
      const groupMeta = this.groupMeta.get(product.group_name) || {};
      setNodeText("modalCategory", this.config.modalCategoryFormatter ? this.config.modalCategoryFormatter(product) : (product.collection_label || groupMeta.modalLabel || ""));
      setNodeText("modalTitle", details.title || product.title || product.name);
      setNodeText("modalSpecialty", details.specialty || "");
      setNodeText("modalProcess", details.process || "");
      setNodeText("modalUsage", details.usage || "");
      setNodeText("modalSignificance", details.significance || "");
      if (details.description_html) {
        setNodeHtml("modalSpecialty", details.description_html);
      }
      this.fillGallery(product);
      Array.from(document.querySelectorAll(".product-price-premium, #modalPrice")).forEach((target) => {
        if (target) {
          target.textContent = formatPrice(product.price || 500);
        }
      });
      this.setSaveButtonState(product.id);
      if (typeof this.config.onProductOpen === "function") {
        this.config.onProductOpen(product, this.buildUiApi(product));
      }
      this.modal?.classList.add("show");
      document.body.style.overflow = "hidden";
      await this.fetchAndRenderReviews(product.id);
    }

    closeModal() {
      this.modal?.classList.remove("show");
      document.body.style.overflow = "";
      this.activeProductId = null;
      if (this.isSnapShowcase) {
        this.resetSnapAutoShowcase();
      }
      if (typeof this.config.onModalClose === "function") {
        this.config.onModalClose();
      }
    }

    getVisibleProductIds() {
      return (this.productsByGroup.get(this.activeGroup) || []).map((product) => product.id);
    }
  }

  class GiftVaultController extends BaseProductController {
    constructor(config) {
      super(config);
      this.categoryMeta = config.categoryMeta || {};
      this.currentCategoryKey = "";
      this.categoryOpenClass = config.categoryOpenClass || "show-modal";
      this.productOpenClass = config.productOpenClass || "show-modal";
      this.categoryModal = byId("category-modal") || byId("categoryModal");
      this.productModal = byId("product-modal") || byId("productModal");
      this.categoryProducts = byId("category-products");
      this.categoryTitle = byId("category-title");
      this.categoryDesc = byId("category-desc");
      this.videoContainer = byId("video-container-box");
      this.videoLoader = byId("catVidLoader");
      this.videoElement = null;
      this.actionQueued = false;
      this.replayQueued = false;
      this.isActionPlaying = false;
      renderDust(config.dustContainerId || "dust-particles", config.dustCount || 50);

      this.bindGlobals({
        openCategory: this.openCategory.bind(this),
        closeCategory: this.closeCategory.bind(this),
        openProductModal: this.openProductModal.bind(this),
        backToCategory: this.backToCategory.bind(this),
        closeProductModal: this.closeProductModal.bind(this),
        changeModalImage: this.changeModalImage.bind(this),
        toggleWishlist: this.toggleWishlist.bind(this),
        submitReview: this.submitReview.bind(this),
        openLightbox: this.openLightbox.bind(this),
        handleReviewAction: this.handleReviewAction.bind(this),
        deleteReview: this.deleteReview.bind(this),
        handleCredentialResponse: this.handleCredentialResponse.bind(this),
        playActionPart: this.playActionPart.bind(this),
      });
    }

    bindGiftProductClicks() {
      if (!this.categoryProducts || this.categoryProducts.dataset.meltixGiftClickReady === "true") {
        return;
      }
      this.categoryProducts.dataset.meltixGiftClickReady = "true";

      this.categoryProducts.addEventListener("click", (event) => {
        const target = event.target instanceof Element ? event.target : event.target?.parentElement;
        const card = target?.closest(".product-card");
        if (!card || !this.categoryProducts.contains(card)) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();

        const cards = Array.from(this.categoryProducts.querySelectorAll(".product-card"));
        const fallbackIndex = cards.indexOf(card);
        const dataIndex = Number(card.dataset.productIndex);
        const productIndex = Number.isInteger(dataIndex) ? dataIndex : fallbackIndex;
        const categoryKey = card.dataset.categoryKey || this.currentCategoryKey;

        if (!categoryKey || !Number.isInteger(productIndex) || productIndex < 0) {
          console.warn("Gift product tap ignored: missing category or index", { categoryKey, productIndex });
          return;
        }

        this.openProductModal(categoryKey, productIndex).catch((error) => {
          console.error("Gift product modal error:", error);
        });
      }, true);
    }

    getProductsForCategory(categoryKey) {
      const meta = this.categoryMeta[categoryKey];
      if (!meta) {
        return [];
      }
      return this.productsByGroup.get(meta.groupName) || [];
    }

    cleanupCategoryVideo() {
      if (!this.videoElement) {
        return;
      }
      this.videoElement.pause();
      this.videoElement.removeAttribute("src");
      this.videoElement.load();
      this.videoElement.remove();
      this.videoElement = null;
    }

    loadCategoryVideo(videoUrl) {
      if (!this.videoContainer || !videoUrl) {
        return;
      }
      if (this.videoLoader) {
        this.videoLoader.style.display = "block";
      }
      this.cleanupCategoryVideo();
      this.videoContainer.textContent = "";

      const videoElement = document.createElement("video");
      videoElement.id = "category-video";
      videoElement.className = "fade-vid";
      videoElement.muted = true;
      videoElement.loop = true;
      videoElement.setAttribute("playsinline", "");
      videoElement.setAttribute("preload", "auto");
      videoElement.src = videoUrl;

      this.videoContainer.appendChild(videoElement);
      this.videoElement = videoElement;
      videoElement.onloadeddata = () => {
        if (this.videoElement !== videoElement) {
          return;
        }
        if (this.videoLoader) {
          this.videoLoader.style.display = "none";
        }
        videoElement.classList.add("vid-ready");
        const playPromise = videoElement.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(() => {});
        }
      };
      videoElement.load();

      window.setTimeout(() => {
        if (this.videoElement !== videoElement) {
          return;
        }
        if (videoElement.readyState >= 2) {
          if (this.videoLoader) {
            this.videoLoader.style.display = "none";
          }
          videoElement.classList.add("vid-ready");
          videoElement.play().catch(() => {});
        }
      }, 300);
    }

    renderCategoryProducts(categoryKey) {
      if (!this.categoryProducts) {
        return;
      }
      const products = this.getProductsForCategory(categoryKey);
      this.categoryProducts.innerHTML = "";
      products.forEach((product, index) => {
        const card = document.createElement("div");
        card.className = "product-card";
        card.dataset.categoryKey = categoryKey;
        card.dataset.productIndex = String(index);
        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");

        let pointerStart = null;
        let lastOpenAt = 0;
        const triggerOpen = () => {
          const now = Date.now();
          if (now - lastOpenAt < 250) {
            return;
          }
          lastOpenAt = now;
          this.openProductModal(categoryKey, index).catch((error) => {
            console.error("Gift product modal error:", error);
          });
        };

        card.addEventListener("pointerdown", (event) => {
          if (event.pointerType === "mouse" && event.button !== 0) {
            pointerStart = null;
            return;
          }
          pointerStart = { x: event.clientX, y: event.clientY };
        });
        card.addEventListener("pointerup", (event) => {
          if (!pointerStart) {
            return;
          }
          const deltaX = Math.abs(event.clientX - pointerStart.x);
          const deltaY = Math.abs(event.clientY - pointerStart.y);
          pointerStart = null;
          if (deltaX < 10 && deltaY < 10) {
            event.preventDefault();
            event.stopPropagation();
            triggerOpen();
          }
        });
        card.addEventListener("pointercancel", () => {
          pointerStart = null;
        });
        card.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          triggerOpen();
        });
        card.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            triggerOpen();
          }
        });

        const image = document.createElement("img");
        image.src = product.image_url || product.image_path || "";
        image.alt = product.title || product.name || "Meltix product";
        image.onerror = function () {
          this.src = "https://via.placeholder.com/300x180/ffffff/b0845a?text=Meltix";
        };
        card.appendChild(image);

        const title = document.createElement("h4");
        title.textContent = product.title || product.name || "Meltix";
        card.appendChild(title);

        const price = document.createElement("div");
        price.className = "price";
        price.textContent = formatPrice(product.price || 500);
        card.appendChild(price);

        this.categoryProducts.appendChild(card);
      });
    }

    playActionPart() {
      if (!this.videoElement) {
        return;
      }
      if (this.videoElement.paused) {
        this.videoElement.play().catch(() => {});
      }
    }

    async openCategory(categoryKey) {
      const meta = this.categoryMeta[categoryKey];
      if (!meta) {
        return;
      }
      this.currentCategoryKey = categoryKey;
      await this.loadCatalog();
      if (this.categoryTitle) {
        this.categoryTitle.textContent = meta.title || "";
      }
      if (this.categoryDesc) {
        this.categoryDesc.textContent = meta.desc || "";
      }
      this.actionQueued = false;
      this.replayQueued = false;
      this.isActionPlaying = false;
      if (meta.video) {
        this.loadCategoryVideo(meta.video);
      }
      this.renderCategoryProducts(categoryKey);
      if (this.categoryModal && this.categoryOpenClass) {
        this.categoryModal.classList.add(this.categoryOpenClass);
      }
    }

    closeCategory() {
      if (this.categoryModal && this.categoryOpenClass) {
        this.categoryModal.classList.remove(this.categoryOpenClass);
      }
      if (this.videoElement) {
        this.cleanupCategoryVideo();
      }
    }

    async openProductModal(categoryKey, index) {
      const meta = this.categoryMeta[categoryKey];
      const products = this.getProductsForCategory(categoryKey);
      const product = products[index];
      if (!product) {
        return;
      }
      this.activeProductId = Number(product.id);
      const details = product.details || {};
      setNodeText("modalTitle", details.title || product.title || product.name);
      setNodeText("modalCategory", meta?.title || product.collection_label || "Meltix Vault Collection");
      setNodeHtml("modalSpecialty", details.description_html || details.specialty || "");
      this.fillGallery(product);
      Array.from(document.querySelectorAll("#modalPrice, .product-price-premium")).forEach((target) => {
        if (target) {
          target.textContent = formatPrice(product.price || 500);
        }
      });
      this.syncAddToCartButton(this.addToCartButton, product);

      if (this.quantityControl) {
        this.quantityControl.reset();
      }
      if (this.categoryModal && this.categoryOpenClass) {
        this.categoryModal.classList.remove(this.categoryOpenClass);
      }
      if (this.videoElement) {
        this.videoElement.pause();
      }
      if (this.productModal) {
        if (this.productOpenClass) {
          this.productModal.classList.add(this.productOpenClass);
        }
        this.productModal.classList.add("show");
      }
      this.refreshProductStates([product.id]).then(() => {
        this.setSaveButtonState(product.id);
      });
      this.fetchAndRenderReviews(product.id);
    }

    backToCategory() {
      if (this.productModal) {
        if (this.productOpenClass) {
          this.productModal.classList.remove(this.productOpenClass);
        }
        this.productModal.classList.remove("show");
      }
      if (this.categoryModal && this.categoryOpenClass) {
        this.categoryModal.classList.add(this.categoryOpenClass);
      }
      if (this.videoElement) {
        this.videoElement.play().catch(() => {});
      }
    }

    closeProductModal() {
      if (this.productModal) {
        if (this.productOpenClass) {
          this.productModal.classList.remove(this.productOpenClass);
        }
        this.productModal.classList.remove("show");
      }
    }
  }

  function createHiddenMessageHook() {
    const messageInput = byId("secretMessageInput");
    const counter = byId("charCounter");
    const addButton = byId("mainAddToCartBtn");
    const quantityControl = bindQuantityControl({
      inputId: "qtyInput",
      minusId: "qtyMinus",
      plusId: "qtyPlus",
      initialValue: 1,
    });
    let listenerAttached = false;
    let cartListenerAttached = false;
    let activeProduct = null;
    let activeController = null;
    const maxChars = messageInput ? Number(messageInput.getAttribute("maxlength") || 20) : 20;
    const syncButtonState = () => {
      if (!addButton) {
        return;
      }
      if (!activeProduct || !activeController) {
        addButton.disabled = true;
        return;
      }
      const text = messageInput?.value.trim() || "";
      const hasValidText = text.length > 0 && text.length <= maxChars;
      activeController.syncAddToCartButton(addButton, activeProduct, {
        disabled: !hasValidText,
      });
    };

    const updateCounter = () => {
      if (!messageInput || !counter) {
        return;
      }
      const length = messageInput.value.length;
      counter.textContent = `${length}/${maxChars}`;
      if (length >= maxChars) {
        counter.style.color = "#ff4d4d";
      } else {
        counter.style.color = "var(--accent-gold)";
      }
    };

    const lockButton = () => {
      syncButtonState();
    };
    const unlockButton = () => {
      if (!addButton || !activeProduct || !activeController) {
        return;
      }
      activeController.syncAddToCartButton(addButton, activeProduct, {
        disabled: false,
      });
    };

    const handleInput = () => {
      if (!messageInput) {
        return;
      }
      updateCounter();
      const text = messageInput.value.trim();
      if (text.length > 0 && text.length <= maxChars) {
        unlockButton();
      } else {
        lockButton();
      }
    };

    if (messageInput && !listenerAttached) {
      messageInput.addEventListener("input", handleInput);
      listenerAttached = true;
    }

    if (addButton && !cartListenerAttached) {
      addButton.addEventListener("click", (event) => {
        event.preventDefault();
        const text = messageInput?.value.trim() || "";
        if (!activeProduct || !activeController || text.length === 0 || text.length > maxChars) {
          lockButton();
          return;
        }
        const didAdd = activeController.addProductToCart(activeProduct, {
          qty: quantityControl.getValue(),
          customText: text,
          button: addButton,
          finalDisabled: true,
        });
        if (!didAdd) {
          return;
        }
        if (messageInput) {
          messageInput.value = "";
        }
        quantityControl.reset();
        updateCounter();
        lockButton();
      });
      cartListenerAttached = true;
    }

    return {
      onProductOpen(product, ui) {
        activeProduct = product || null;
        activeController = ui?.controller || null;
        if (messageInput) {
          messageInput.value = "";
        }
        updateCounter();
        lockButton();
        quantityControl.reset();
      },
      onModalClose() {
        activeProduct = null;
        activeController = null;
        if (messageInput) {
          messageInput.value = "";
        }
        updateCounter();
        lockButton();
      },
    };
  }

  function createSimpleQuantityHook(config) {
    const control = bindQuantityControl({
      inputId: config?.inputId,
      minusId: config?.minusId,
      plusId: config?.plusId,
      initialValue: 1,
    });
    const addButton = byId(config?.addButtonId || "");
    let activeProduct = null;
    let activeController = null;

    if (addButton && addButton.dataset.cartBound !== "true") {
      addButton.dataset.cartBound = "true";
      addButton.addEventListener("click", (event) => {
        event.preventDefault();
        if (!activeProduct || !activeController) {
          return;
        }
        activeController.addProductToCart(activeProduct, {
          qty: control.getValue(),
          customText: typeof config?.getCustomText === "function" ? config.getCustomText() : null,
          button: addButton,
        });
      });
    }

    return {
      onProductOpen(product, ui) {
        activeProduct = product || null;
        activeController = ui?.controller || null;
        activeController?.syncAddToCartButton?.(addButton, activeProduct);
        control.reset();
      },
      onModalClose() {
        activeProduct = null;
        activeController = null;
        if (addButton) {
          addButton.disabled = true;
        }
      },
    };
  }

  function createStoryArtisanHook() {
    const standardUI = byId("standardCheckoutUI");
    const atelierUI = byId("visualRevealAtelier");
    const revealLabel = byId("revealTypeLabel");
    const pointers = byId("craftingPointers");
    const formTrigger = byId("initiateArtisanRequest");
    const formPanel = byId("artisanBespokeForm");
    const commitBtn = byId("storyArtisanCommitBtn");
    const addToCartBtn = byId("storyAddToCartBtn");
    const whatsappInput = byId("artisanWhatsApp");
    const storyInput = byId("artisanStory");
    const quantityControl = bindQuantityControl({
      inputId: "storyQtyInput",
      minusId: "storyQtyMinus",
      plusId: "storyQtyPlus",
      initialValue: 1,
    });

    const pointerItems = [
      "Choose your Visual Reveal storyline",
      "Our artisans craft the reveal capsule",
      "We embed it inside the wax ritual",
      "Hand-delivered story ready to unlock",
    ];
    let activeProductId = null;
    let activeProduct = null;
    let activeController = null;

    window.showArtisanForm = () => {
      if (formTrigger) {
        formTrigger.style.display = "none";
      }
      if (formPanel) {
        formPanel.style.display = "block";
      }
    };

    if (commitBtn) {
      commitBtn.addEventListener("click", () => {
        const digits = normalizeIndiaWhatsAppDigits(whatsappInput?.value || "");
        if (!digits) {
          alert("Please enter a valid Indian WhatsApp number.");
          return;
        }
        const title = textOrEmpty(byId("modalTitle")?.textContent) || "Story Candle";
        const body = [
          "Meltix Visual Reveal Atelier",
          "",
          `Product: ${title}`,
          `Product ID: ${activeProductId || ""}`.trim(),
          "",
          `Customer WhatsApp (digits): ${digits}`,
          "",
          "Story / special instructions:",
          textOrEmpty(storyInput?.value || "") || "(none)",
          "",
          "Commitment fee: INR 250 (non-refundable). Please confirm payment with Meltix.",
        ].join("\n");
        const url = `https://wa.me/${DEFAULT_WHATSAPP_BUSINESS}?text=${encodeURIComponent(body)}`;
        window.open(url, "_blank", "noopener,noreferrer");
      });
    }

    if (addToCartBtn && addToCartBtn.dataset.cartBound !== "true") {
      addToCartBtn.dataset.cartBound = "true";
      addToCartBtn.addEventListener("click", (event) => {
        event.preventDefault();
        if (!activeProduct || !activeController || activeProduct?.ui_flags?.artisan_bespoke) {
          return;
        }
        activeController.addProductToCart(activeProduct, {
          qty: quantityControl.getValue(),
          button: addToCartBtn,
        });
      });
    }

    return {
      onProductOpen(product, ui) {
        activeProductId = product?.id || null;
        activeProduct = product || null;
        activeController = ui?.controller || null;
        const isArtisan = Boolean(product?.ui_flags?.artisan_bespoke);
        activeController?.syncAddToCartButton?.(addToCartBtn, activeProduct, {
          disabled: isArtisan,
        });
        if (standardUI) {
          standardUI.style.display = isArtisan ? "none" : "block";
        }
        if (atelierUI) {
          atelierUI.style.display = isArtisan ? "block" : "none";
        }
        if (revealLabel) {
          revealLabel.textContent = isArtisan ? "Visual Reveal Atelier" : "";
        }
        if (pointers && isArtisan) {
          fillPointerList("craftingPointers", pointerItems);
        }
        if (formTrigger) {
          formTrigger.style.display = "block";
        }
        if (formPanel) {
          formPanel.style.display = "none";
        }
        if (whatsappInput) {
          whatsappInput.value = "";
        }
        if (storyInput) {
          storyInput.value = "";
        }
        quantityControl.reset();
      },
      onModalClose() {
        activeProductId = null;
        activeProduct = null;
        activeController = null;
        if (addToCartBtn) {
          addToCartBtn.disabled = true;
        }
        if (formTrigger) {
          formTrigger.style.display = "block";
        }
        if (formPanel) {
          formPanel.style.display = "none";
        }
      },
    };
  }

  function createBreakArtisanHook() {
    const standardUI = byId("standardCheckoutUI");
    const bespokeUI = byId("bespokeArtisanUI");
    const stressInsight = byId("stressBusterInsight");
    const pointers = byId("bespokePointers");
    const formTrigger = byId("initiateArtisanRequest");
    const formPanel = byId("artisanBespokeForm");
    const commitBtn = byId("breakArtisanCommitBtn");
    const addToCartBtn = byId("breakAddToCartBtn");
    const whatsappInput = byId("breakArtisanWhatsApp");
    const storyInput = byId("breakArtisanStory");
    const quantityControl = bindQuantityControl({
      inputId: "breakQtyInput",
      minusId: "breakQtyMinus",
      plusId: "breakQtyPlus",
      initialValue: 1,
    });

    const pointerItems = [
      "Order to start the surprise",
      "Ship your jewelry to our vault",
      "We embed it in the breakable shell",
      "Hand-delivered mystery to smash",
    ];
    let activeProductId = null;
    let activeProduct = null;
    let activeController = null;

    window.showArtisanForm = () => {
      if (formTrigger) {
        formTrigger.style.display = "none";
      }
      if (formPanel) {
        formPanel.style.display = "block";
      }
    };

    if (commitBtn) {
      commitBtn.addEventListener("click", () => {
        const digits = normalizeIndiaWhatsAppDigits(whatsappInput?.value || "");
        if (!digits) {
          alert("Please enter a valid Indian WhatsApp number.");
          return;
        }
        const title = textOrEmpty(byId("modalTitle")?.textContent) || "Break to Reveal";
        const body = [
          "Meltix Break to Reveal - Bespoke Treasure Hunt",
          "",
          `Product: ${title}`,
          `Product ID: ${activeProductId || ""}`.trim(),
          "",
          `Customer WhatsApp (digits): ${digits}`,
          "",
          "Story / special instructions:",
          textOrEmpty(storyInput?.value || "") || "(none)",
          "",
          "Commitment fee: INR 250 (non-refundable). Please confirm payment with Meltix.",
        ].join("\n");
        const url = `https://wa.me/${DEFAULT_WHATSAPP_BUSINESS}?text=${encodeURIComponent(body)}`;
        window.open(url, "_blank", "noopener,noreferrer");
      });
    }

    if (addToCartBtn && addToCartBtn.dataset.cartBound !== "true") {
      addToCartBtn.dataset.cartBound = "true";
      addToCartBtn.addEventListener("click", (event) => {
        event.preventDefault();
        if (!activeProduct || !activeController || activeProduct?.ui_flags?.artisan_bespoke) {
          return;
        }
        activeController.addProductToCart(activeProduct, {
          qty: quantityControl.getValue(),
          button: addToCartBtn,
        });
      });
    }

    return {
      onProductOpen(product, ui) {
        activeProductId = product?.id || null;
        activeProduct = product || null;
        activeController = ui?.controller || null;
        const isArtisan = Boolean(product?.ui_flags?.artisan_bespoke);
        const showStress = Boolean(product?.ui_flags?.stress_insight);
        activeController?.syncAddToCartButton?.(addToCartBtn, activeProduct, {
          disabled: isArtisan,
        });
        if (standardUI) {
          standardUI.style.display = isArtisan ? "none" : "block";
        }
        if (bespokeUI) {
          bespokeUI.style.display = isArtisan ? "block" : "none";
        }
        if (stressInsight) {
          stressInsight.style.display = !isArtisan && showStress ? "block" : "none";
        }
        if (pointers && isArtisan) {
          fillPointerList("bespokePointers", pointerItems);
        }
        if (formTrigger) {
          formTrigger.style.display = "block";
        }
        if (formPanel) {
          formPanel.style.display = "none";
        }
        if (whatsappInput) {
          whatsappInput.value = "";
        }
        if (storyInput) {
          storyInput.value = "";
        }
        quantityControl.reset();
      },
      onModalClose() {
        activeProductId = null;
        activeProduct = null;
        activeController = null;
        if (addToCartBtn) {
          addToCartBtn.disabled = true;
        }
        if (formTrigger) {
          formTrigger.style.display = "block";
        }
        if (formPanel) {
          formPanel.style.display = "none";
        }
      },
    };
  }

  function mergeHooks(hooks) {
    const hookList = Array.isArray(hooks) ? hooks : [];
    return {
      onProductOpen(product, ui) {
        hookList.forEach((hook) => hook?.onProductOpen?.(product, ui));
      },
      onModalClose() {
        hookList.forEach((hook) => hook?.onModalClose?.());
      },
    };
  }

  function initCarouselCollection(config) {
    const controller = new CarouselCollectionController(config);
    const hooks = mergeHooks(config?.uiHooks || []);
    controller.config.onProductOpen = hooks.onProductOpen;
    controller.config.onModalClose = hooks.onModalClose;
    controller
      .loadCatalog()
      .then(() => {
        const params = new URLSearchParams(window.location.search);
        const requestedProductId = Number(params.get("product") || 0);
        const requestedProductName = textOrEmpty(params.get("product_name")).trim().toLowerCase();
        let requestedProduct = null;

        if (Number.isInteger(requestedProductId) && requestedProductId > 0) {
          requestedProduct = controller.getProduct(requestedProductId);
        }

        if (!requestedProduct && requestedProductName) {
          requestedProduct = controller.products.find((product) => {
            const title = textOrEmpty(product?.title).trim().toLowerCase();
            const name = textOrEmpty(product?.name).trim().toLowerCase();
            return title === requestedProductName || name === requestedProductName;
          }) || null;
        }

        if (requestedProduct) {
          return controller.handleSelection(requestedProduct.group_name).then(() => {
            window.setTimeout(() => {
              controller.openModal(requestedProduct.id).catch?.(() => {});
            }, Number(controller.config.selectionRevealDelay || 800) + 80);
          });
        }
        return null;
      })
      .catch(() => {});
    return controller;
  }

  function initGiftVaultCollection(config) {
    const controller = new GiftVaultController({
      ...config,
      categoryOpenClass: config?.categoryOpenClass || "show-modal",
      productOpenClass: config?.productOpenClass || "show-modal",
    });
    controller.quantityControl = bindQuantityControl({
      inputId: config?.quantityInputId || "giftSetQtyInput",
      minusId: config?.quantityMinusId || "giftSetQtyMinus",
      plusId: config?.quantityPlusId || "giftSetQtyPlus",
      initialValue: 1,
    });
    const addButton = byId(config?.addButtonId || "giftSetAddToCartBtn");
    controller.addToCartButton = addButton;
    if (addButton && addButton.dataset.cartBound !== "true") {
      addButton.dataset.cartBound = "true";
      addButton.addEventListener("click", (event) => {
        event.preventDefault();
        const product = controller.getProduct(controller.activeProductId);
        if (!product) {
          return;
        }
        controller.addProductToCart(product, {
          qty: controller.quantityControl?.getValue?.() || 1,
          button: addButton,
        });
      });
    }
    controller.loadCatalog().catch(() => {});
    return controller;
  }

  window.MeltixCore = {
    initCarouselCollection,
    initGiftVaultCollection,
    createHiddenMessageHook,
    createStoryArtisanHook,
    createBreakArtisanHook,
    createSimpleQuantityHook,
  };
})();

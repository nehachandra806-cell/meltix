(function () {
  const MOBILE_QUERY = window.matchMedia('(max-width: 768px)');
  const FLY_OUT_MS = 400;
  const SWIPE_THRESHOLD = 44;
  const BEHIND_CLASSES = [
    'card-behind-1', 'card-behind-2', 'card-behind-3', 'card-behind-4', 'card-behind-5'
  ];

  const DECK_CLASSES = [
    'card-active', 'card-hidden',
    'card-fly-out', 'card-fly-out-right',
    'card-swiped-right', 'card-prev-entering', 'card-receding-behind',
    'stack-active', 'stack-next', 'stack-prev', 'is-active'
  ].concat(BEHIND_CLASSES);

  function init(config) {
    if (!config || !config.controllerKey || !Array.isArray(config.groups) || !config.groups.length) {
      return;
    }

    let cards = [];
    let activeIndex = 0;
    let animating = false;
    let touchStartX = 0;
    let touchStartY = 0;
    let dragX = 0;
    let gestureAxis = null;
    let touching = false;
    let observer = null;

    let controller = null;
    let deck = null;
    let track = null;
    let prevButton = null;
    let nextButton = null;
    let status = null;

    function isMobile() {
      return MOBILE_QUERY.matches;
    }

    function stopCoreAutoShowcase() {
      controller?.stopSnapAutoShowcase?.();
    }

    function getGroupIndex() {
      return Math.max(config.groups.indexOf(controller.activeGroup), 0);
    }

    function activateTransition() {
      const groupIndex = getGroupIndex();
      if (groupIndex === config.groups.length - 1) {
        window.location.href = config.finalHref || '/shop';
        return;
      }
      window.switchVariant(config.groups[groupIndex + 1]);
    }

    function applyDeckState() {
      if (!cards.length) return;
      activeIndex = Math.max(0, Math.min(activeIndex, cards.length - 1));

      cards.forEach(function (card, index) {
        card.classList.remove.apply(card.classList, DECK_CLASSES);
        card.style.removeProperty('--deck-drag-x');

        const distance = index - activeIndex;
        if (distance === 0) {
          card.classList.add('card-active');
        } else if (distance > 0 && distance <= BEHIND_CLASSES.length) {
          card.classList.add(BEHIND_CLASSES[distance - 1]);
        } else {
          card.classList.add('card-hidden');
        }

        card.setAttribute('aria-hidden', distance === 0 ? 'false' : 'true');
      });

      const activeCard = cards[activeIndex];
      const isTransition = activeCard.classList.contains('deck-transition-card');
      const productCount = Math.max(cards.length - 1, 0);

      status.textContent = isTransition
        ? (activeCard.dataset.deckLabel || 'Discover More')
        : (activeIndex + 1) + ' / ' + productCount;
      prevButton.disabled = animating || activeIndex === 0;
      nextButton.disabled = animating;
      nextButton.textContent = isTransition ? 'Enter' : 'Next';
      stopCoreAutoShowcase();
    }

    function promoteStackDuringFlyOut() {
      const nextCard = cards[activeIndex + 1];
      if (nextCard) {
        nextCard.classList.remove.apply(nextCard.classList, DECK_CLASSES);
        nextCard.classList.add('card-active');
        nextCard.setAttribute('aria-hidden', 'false');
      }

      for (let layer = 1; layer <= BEHIND_CLASSES.length; layer += 1) {
        const behindCard = cards[activeIndex + 1 + layer];
        if (!behindCard) break;
        behindCard.classList.remove.apply(behindCard.classList, DECK_CLASSES);
        behindCard.classList.add(BEHIND_CLASSES[layer - 1]);
      }
    }

    function moveDeckPrev() {
      const activeCard = cards[activeIndex];
      const incomingCard = cards[activeIndex - 1];
      if (!incomingCard) return;

      animating = true;
      prevButton.disabled = true;
      nextButton.disabled = true;
      activeCard.style.removeProperty('--deck-drag-x');
      incomingCard.style.removeProperty('--deck-drag-x');

      incomingCard.classList.remove.apply(incomingCard.classList, DECK_CLASSES);
      incomingCard.classList.add('card-swiped-right');
      void incomingCard.offsetWidth;

      incomingCard.classList.remove('card-swiped-right');
      incomingCard.classList.add('card-active', 'card-prev-entering');
      incomingCard.setAttribute('aria-hidden', 'false');

      activeCard.classList.remove('card-active');
      activeCard.classList.add('card-receding-behind');

      window.setTimeout(function () {
        activeCard.classList.remove('card-receding-behind', 'card-fly-out', 'card-fly-out-right');
        incomingCard.classList.remove('card-prev-entering', 'card-swiped-right');
        activeIndex -= 1;
        animating = false;
        applyDeckState();
      }, FLY_OUT_MS);
    }

    function moveDeck(direction) {
      if (animating || !cards.length) return;
      if (direction < 0 && activeIndex === 0) return;

      if (direction < 0) {
        moveDeckPrev();
        return;
      }

      const activeCard = cards[activeIndex];
      const leavingTransition = activeIndex === cards.length - 1;

      animating = true;
      prevButton.disabled = true;
      nextButton.disabled = true;
      activeCard.style.removeProperty('--deck-drag-x');
      activeCard.classList.remove('card-active');
      BEHIND_CLASSES.forEach(function (cls) { activeCard.classList.remove(cls); });
      activeCard.classList.add('card-fly-out');

      if (!leavingTransition) {
        promoteStackDuringFlyOut();
      }

      void activeCard.offsetWidth;

      window.setTimeout(function () {
        activeCard.classList.remove('card-fly-out', 'card-fly-out-right');

        if (leavingTransition) {
          activateTransition();
          return;
        }

        activeIndex += 1;
        animating = false;
        applyDeckState();
      }, FLY_OUT_MS);
    }

    function createTransitionCard() {
      const groupIndex = getGroupIndex();
      const isFinalGroup = groupIndex === config.groups.length - 1;
      const nextGroup = config.groups[groupIndex + 1] || '';
      const transition = document.createElement('article');
      const finalTitle = config.finalTitle || 'Head to another section';
      const finalCopy = config.finalCopy || 'Continue exploring the atelier.';

      transition.className = 'img-container showcase-product-card product-card deck-transition-card';
      transition.tabIndex = 0;
      transition.setAttribute('role', 'button');
      transition.dataset.deckLabel = isFinalGroup ? 'Another Section' : 'Discover More';
      transition.setAttribute('aria-label', isFinalGroup ? finalTitle : 'Discover ' + nextGroup);
      transition.innerHTML =
        '<div class="mobile-deck-transition-inner">' +
          '<span class="mobile-deck-transition-kicker">' + (isFinalGroup ? 'The Journey Continues' : 'Next Private Door') + '</span>' +
          '<h3 class="mobile-deck-transition-title">' + (isFinalGroup ? finalTitle : 'Discover More') + '</h3>' +
          '<p class="mobile-deck-transition-copy">' + (isFinalGroup ? finalCopy : 'Step into ' + nextGroup + '.') + '</p>' +
          '<span class="mobile-deck-transition-cta">Tap to continue &rarr;</span>' +
        '</div>';

      transition.addEventListener('click', function () { moveDeck(1); });
      transition.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          moveDeck(1);
        }
      });
      return transition;
    }

    function ensureFirstCardVisible() {
      const firstCard = track?.querySelector('.showcase-product-card:not(.deck-transition-card)');
      if (firstCard && !track.querySelector('.card-active')) {
        firstCard.classList.add('card-active');
        firstCard.setAttribute('aria-hidden', 'false');
      }
    }

    function initializeDeck() {
      if (!isMobile()) return;
      if (!track) return;

      track.querySelector('.deck-transition-card')?.remove();
      const productCards = Array.from(track.querySelectorAll('.showcase-product-card:not(.deck-transition-card)'));
      if (!productCards.length) return;

      track.classList.add('deck-initialized');
      track.appendChild(createTransitionCard());
      cards = Array.from(track.querySelectorAll('.showcase-product-card'));
      activeIndex = 0;
      animating = false;

      cards[0].classList.add('card-active');
      cards[0].setAttribute('aria-hidden', 'false');
      applyDeckState();

      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(stopCoreAutoShowcase);
      });
      window.setTimeout(stopCoreAutoShowcase, 100);
    }

    function bindDeckInteractions() {
      const blockCorePointer = function (event) {
        if (event.pointerType === 'touch' && !event.target.closest('.like-btn')) {
          event.stopImmediatePropagation();
        }
      };

      ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (name) {
        deck.addEventListener(name, blockCorePointer, { capture: true, passive: true });
      });

      prevButton.addEventListener('click', function (event) {
        event.preventDefault();
        moveDeck(-1);
      });

      nextButton.addEventListener('click', function (event) {
        event.preventDefault();
        moveDeck(1);
      });

      deck.addEventListener('touchstart', function (event) {
        if (event.touches.length !== 1 || !cards.length || animating) return;
        if (event.target.closest('.like-btn')) return;
        touching = true;
        dragX = 0;
        gestureAxis = null;
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
        stopCoreAutoShowcase();
      }, { passive: true });

      deck.addEventListener('touchmove', function (event) {
        if (!touching || event.touches.length !== 1) return;
        const deltaX = event.touches[0].clientX - touchStartX;
        const deltaY = event.touches[0].clientY - touchStartY;
        if (!gestureAxis && Math.max(Math.abs(deltaX), Math.abs(deltaY)) > 7) {
          gestureAxis = Math.abs(deltaX) > Math.abs(deltaY) ? 'horizontal' : 'vertical';
        }
        if (gestureAxis !== 'horizontal') return;

        event.preventDefault();
        dragX = Math.max(-120, Math.min(120, deltaX));
        cards[activeIndex]?.style.setProperty('--deck-drag-x', dragX + 'px');
      }, { passive: false });

      function finishTouch() {
        if (!touching) return;
        touching = false;
        cards[activeIndex]?.style.removeProperty('--deck-drag-x');
        if (gestureAxis === 'horizontal' && Math.abs(dragX) >= SWIPE_THRESHOLD) {
          moveDeck(dragX < 0 ? 1 : -1);
        } else {
          applyDeckState();
        }
        dragX = 0;
        gestureAxis = null;
        stopCoreAutoShowcase();
      }

      deck.addEventListener('touchend', finishTouch, { passive: true });
      deck.addEventListener('touchcancel', finishTouch, { passive: true });
    }

    function hookController() {
      const originalRenderGroup = controller.renderGroup.bind(controller);
      controller.renderGroup = async function () {
        const result = await originalRenderGroup.apply(controller, arguments);
        initializeDeck();
        return result;
      };
    }

    function boot() {
      if (!isMobile()) return;

      controller = window[config.controllerKey];
      if (controller?._mobileDeckReady) return;

      deck = document.getElementById(config.deckId || 'drag-area');
      track = document.getElementById(config.trackId || 'carousel-track');
      prevButton = document.getElementById(config.prevButtonId || 'mobileDeckPrev');
      nextButton = document.getElementById(config.nextButtonId || 'mobileDeckNext');
      status = document.getElementById(config.statusId || 'mobileDeckStatus');

      if (!controller || !deck || !track || !prevButton || !nextButton || !status) return;

      ensureFirstCardVisible();
      if (observer) observer.disconnect();
      observer = new MutationObserver(ensureFirstCardVisible);
      observer.observe(track, { childList: true });

      bindDeckInteractions();
      hookController();

      if (track.querySelector('.showcase-product-card')) {
        initializeDeck();
      }

      controller._mobileDeckReady = true;
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }

    MOBILE_QUERY.addEventListener('change', function () {
      if (MOBILE_QUERY.matches) boot();
    });
  }

  window.MeltixMobileDeck = { init: init };
})();
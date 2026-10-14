/**
 * Scoped Roadmap interaction for Mentor Roadmap.
 * Handles goal paths + catalog mode, progressive enhancement via authorized HTML requests,
 * latest-request-wins cancellation, loading/error/retry states, safe history URLs, and accessible mobile sheet.
 */
(function () {
  'use strict';

  var root = document.querySelector('.ms-roadmap');
  if (!root) return;

  // Signal enhancement to CSS
  root.classList.add('rm-enhanced');

  var currentAbortController = null;
  var lastFocusedNodeId = null;
  var isNavigatingRelation = false;
  var inertElements = [];

  function isMobileViewport() {
    return window.matchMedia('(max-width: 959px)').matches;
  }

  function getMapBaseUrl() {
    return root.dataset.apiRoot || window.location.pathname;
  }

  function isInternalRoadmapLink(link) {
    if (!link || !link.href) return false;
    if (link.target && link.target !== '_self') return false;
    if (link.hasAttribute('download')) return false;

    var targetUrl;
    try {
      targetUrl = new URL(link.href, window.location.origin);
    } catch (e) {
      return false;
    }

    if (targetUrl.origin !== window.location.origin) return false;

    var path = targetUrl.pathname;
    // Do NOT intercept learn links, login links, or other sections
    if (path.indexOf('/learn') !== -1 || path.indexOf('/login') !== -1 || path.indexOf('/accounts/') !== -1) {
      return false;
    }

    var base = getMapBaseUrl();
    var basePath = new URL(base, window.location.origin).pathname;

    // Must be the roadmap map page
    if (path === basePath || path === basePath + '/') {
      return true;
    }

    return false;
  }

  function hideError() {
    var errEl = root.querySelector('.rm-network-error');
    if (errEl) errEl.hidden = true;
  }

  function showError(message, retryUrl, pushToHistory) {
    var errEl = root.querySelector('.rm-network-error');
    if (!errEl) return;
    var msgEl = errEl.querySelector('.rm-error-text');
    if (msgEl) {
      msgEl.textContent = message || 'Không thể tải dữ liệu lộ trình. Vui lòng thử lại.';
    }
    errEl.hidden = false;
    var retryBtn = errEl.querySelector('.rm-error-retry');
    if (retryBtn) {
      retryBtn.onclick = function () {
        hideError();
        fetchAndSwap(retryUrl, Boolean(pushToHistory));
      };
      retryBtn.focus();
    }
  }

  function clearInertBackground() {
    for (var i = 0; i < inertElements.length; i++) {
      inertElements[i].removeAttribute('inert');
    }
    inertElements = [];
  }

  function setInertBackground(panel, enabled) {
    clearInertBackground();
    if (!enabled || !panel) return;

    var parent = panel.parentElement;
    while (parent && parent !== document.documentElement) {
      for (var i = 0; i < parent.children.length; i++) {
        var child = parent.children[i];
        if (child !== panel && !child.contains(panel) && !child.classList.contains('rm-sheet-backdrop')) {
          if (!child.hasAttribute('inert')) {
            child.setAttribute('inert', '');
            inertElements.push(child);
          }
        }
      }
      parent = parent.parentElement;
    }
  }

  function setupSheetDialog(panel) {
    if (!panel) return;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    setInertBackground(panel, true);

    var backdrop = root.querySelector('.rm-sheet-backdrop');
    if (backdrop) backdrop.hidden = false;

    var closeBtn = panel.querySelector('.rm-detail-close');
    var heading = panel.querySelector('#rm-detail-heading');
    if (closeBtn) {
      closeBtn.focus();
    } else if (heading) {
      heading.focus();
    }
  }

  function tearDownSheetDialog(panel) {
    var backdrop = root.querySelector('.rm-sheet-backdrop');
    if (backdrop) backdrop.hidden = true;

    clearInertBackground();

    if (panel) {
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
    }
  }

  function fetchAndSwap(targetUrl, pushToHistory, triggerNodeId) {
    var parsedUrl;
    try {
      parsedUrl = new URL(targetUrl, window.location.origin);
    } catch (e) {
      window.location.href = targetUrl;
      return;
    }

    // Cancel in-flight request: latest request wins
    if (currentAbortController) {
      currentAbortController.abort();
    }
    var controller = new AbortController();
    currentAbortController = controller;

    if (triggerNodeId) {
      lastFocusedNodeId = triggerNodeId;
    }

    root.classList.add('is-loading');
    var loadingBar = root.querySelector('.rm-loading-bar');
    if (loadingBar) loadingBar.hidden = false;
    hideError();

    fetch(parsedUrl.href, {
      method: 'GET',
      headers: {
        'Accept': 'text/html',
        'X-Requested-With': 'XMLHttpRequest'
      },
      signal: controller.signal
    })
      .then(function (res) {
        if (controller !== currentAbortController) return null;
        if (!res.ok) {
          throw new Error('Yêu cầu không thành công (mã trạng thái: ' + res.status + ')');
        }
        return res.text();
      })
      .then(function (htmlText) {
        if (!htmlText || controller !== currentAbortController) return;

        var parser = new DOMParser();
        var doc = parser.parseFromString(htmlText, 'text/html');
        var newRoot = doc.querySelector('.ms-roadmap');
        if (!newRoot) {
          throw new Error('Dữ liệu máy chủ trả về không hợp lệ.');
        }

        if (doc.title) {
          document.title = doc.title;
        }

        var finder = root.querySelector('.rm-finder[open]');
        if (finder) finder.close();
        clearInertBackground();

        root.innerHTML = newRoot.innerHTML;
        if (newRoot.dataset.mode) {
          root.dataset.mode = newRoot.dataset.mode;
        }
        if (newRoot.dataset.revision) {
          root.dataset.revision = newRoot.dataset.revision;
        }

        root.classList.remove('is-loading');
        var bar = root.querySelector('.rm-loading-bar');
        if (bar) bar.hidden = true;
        currentAbortController = null;

        // Safe history: null state, only clean URL
        if (pushToHistory) {
          history.pushState(null, '', parsedUrl.href);
        }

        afterSwap(parsedUrl);
      })
      .catch(function (err) {
        if (controller !== currentAbortController) return;
        if (err.name === 'AbortError') {
          return;
        }
        root.classList.remove('is-loading');
        var bar = root.querySelector('.rm-loading-bar');
        if (bar) bar.hidden = true;
        currentAbortController = null;
        showError(err.message, targetUrl, pushToHistory);
      });
  }

  function normalizeSearch(value) {
    return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function initTopicFinder() {
    var dialog = root.querySelector('.rm-finder');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    var opener = root.querySelector('.rm-finder-open');
    var fallback = root.querySelector('.rm-goal-change');
    opener.hidden = false;
    fallback.hidden = true;
    var query = dialog.querySelector('#rm-finder-query');
    var results = dialog.querySelector('.rm-finder-results');
    var groups = dialog.querySelector('.rm-finder-groups');
    var filter = dialog.querySelector('.rm-finder-filter');
    var groupName = dialog.querySelector('.rm-finder-group-name');
    var entries = Array.from(results.children).map(function (row, index) {
      var title = normalizeSearch(row.dataset.title);
      var names = [title].concat((row.dataset.aliases || '').split('|').filter(Boolean).map(normalizeSearch));
      var english = row.dataset.title.match(/\(([^)]+)\)/);
      if (english) names.push(normalizeSearch(english[1]));
      return { row: row, index: index, names: names, text: names.join(' ') };
    });
    var group = null;

    function update() {
      var term = normalizeSearch(query.value);
      var tokens = term.split(' ').filter(Boolean);
      var browsing = group !== null || term.length > 0;
      groups.hidden = browsing;
      results.hidden = !browsing;
      filter.hidden = !browsing;
      var matches = [];
      entries.forEach(function (entry) {
        var inGroup = group === null || group === 'all' || entry.row.dataset.group === group;
        var matchesQuery = tokens.every(function (token) { return entry.text.indexOf(token) !== -1; });
        entry.row.hidden = !inGroup || !matchesQuery;
        if (!entry.row.hidden) {
          var rank = !term ? 3 : entry.names.indexOf(term) !== -1 ? 0 : entry.names.some(function (name) { return name.startsWith(term); }) ? 1 : 2;
          matches.push({ entry: entry, rank: rank });
        }
      });
      matches.sort(function (a, b) { return a.rank - b.rank || a.entry.index - b.entry.index; });
      matches.forEach(function (match) { results.appendChild(match.entry.row); });
      dialog.querySelector('.rm-finder-empty').hidden = !browsing || matches.length > 0;
      dialog.querySelector('.rm-finder-status').textContent = browsing ? matches.length + ' chuyên đề phù hợp' : 'Chọn nhóm hoặc nhập tên chuyên đề.';
      dialog.querySelector('.rm-finder-all').textContent = term || group !== null ? 'Tất cả nhóm' : 'Khám phá nhóm';
    }

    opener.onclick = function () {
      group = null;
      query.value = '';
      groupName.textContent = '';
      update();
      dialog.showModal();
      query.focus();
    };
    dialog.querySelector('.rm-finder-close').onclick = function () { dialog.close(); };
    dialog.addEventListener('close', function () { opener.focus(); });
    dialog.addEventListener('keydown', function (event) {
      if (event.key !== 'Tab') return;
      var controls = Array.from(dialog.querySelectorAll('button, input, a[href]')).filter(function (element) {
        return !element.disabled && !element.closest('[hidden]') && element.getClientRects().length > 0;
      });
      var first = controls[0];
      var last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    });
    query.addEventListener('input', update);
    query.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') {
        var first = results.querySelector('li:not([hidden]) a');
        if (!results.hidden && first) { event.preventDefault(); first.focus(); }
      }
    });
    results.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      var links = Array.from(results.querySelectorAll('li:not([hidden]) a'));
      var index = links.indexOf(document.activeElement);
      var next = index + (event.key === 'ArrowDown' ? 1 : -1);
      event.preventDefault();
      if (next < 0) query.focus();
      else if (links[next]) links[next].focus();
    });
    groups.addEventListener('click', function (event) {
      var button = event.target.closest('[data-group-id]');
      if (!button) return;
      group = button.dataset.groupId;
      groupName.textContent = group === 'all' ? '' : button.textContent;
      update();
      query.focus();
    });
    dialog.querySelector('.rm-finder-all').onclick = function () {
      group = null;
      groupName.textContent = '';
      update();
      query.focus();
    };
  }

  function afterSwap(parsedUrl) {
    initTopicFinder();
    if (parsedUrl.hash) {
      var milestone = document.getElementById(parsedUrl.hash.slice(1));
      if (milestone && root.contains(milestone)) {
        tearDownSheetDialog(root.querySelector('.rm-detail-panel'));
        milestone.tabIndex = -1;
        milestone.focus({ preventScroll: true });
        milestone.scrollIntoView({ block: 'start' });
        isNavigatingRelation = false;
        return;
      }
    }

    var panel = root.querySelector('.rm-detail-panel');
    var isPanelOpen = panel && panel.classList.contains('is-open');
    var isMobile = isMobileViewport();

    if (isPanelOpen) {
      lastFocusedNodeId = parsedUrl.searchParams.get('selected') || lastFocusedNodeId;
      panel.scrollTop = 0;
      if (isMobile) {
        setupSheetDialog(panel);
      } else {
        tearDownSheetDialog(panel);
        var activeCard = root.querySelector('.rm-node-card.is-selected');
        if (activeCard && !isNavigatingRelation) {
          activeCard.focus();
        } else {
          var heading = panel.querySelector('#rm-detail-heading');
          if (heading) heading.focus();
        }
      }
    } else {
      tearDownSheetDialog(panel);
      var focused = false;
      if (lastFocusedNodeId) {
        var targetCard = root.querySelector('.rm-node-card[data-node-id="' + lastFocusedNodeId + '"]');
        if (targetCard) {
          targetCard.focus();
          focused = true;
        }
      }
      if (!focused) {
        var rmHeading = root.querySelector('#rm-heading');
        if (rmHeading) rmHeading.focus();
      }
    }

    isNavigatingRelation = false;
  }

  // Delegated click handler on root
  root.addEventListener('click', function (e) {
    // Early return for modified clicks (cmd, ctrl, shift, alt) or non-primary button
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
      return;
    }

    var link = e.target.closest('a');
    if (!link) {
      // Check backdrop click to close mobile sheet
      if (e.target.classList.contains('rm-sheet-backdrop')) {
        var panel = root.querySelector('.rm-detail-panel.is-open');
        var closeBtn = panel ? panel.querySelector('.rm-detail-close') : null;
        if (closeBtn && isInternalRoadmapLink(closeBtn)) {
          e.preventDefault();
          fetchAndSwap(closeBtn.href, true);
        }
      }
      return;
    }

    if (!isInternalRoadmapLink(link)) {
      return;
    }

    e.preventDefault();
    if (link.classList.contains('rm-finder-result')) {
      lastFocusedNodeId = null;
      root.querySelector('.rm-finder').close();
    }

    var isRelation = Boolean(link.closest('.rm-relations-list'));
    if (isRelation) {
      isNavigatingRelation = true;
    }

    var card = link.closest('.rm-node-card');
    var nodeId = card ? card.dataset.nodeId : null;

    fetchAndSwap(link.href, true, nodeId);
  });

  // Keyboard navigation & accessibility (Escape + Tab trapping)
  document.addEventListener('keydown', function (e) {
    if (root.querySelector('.rm-finder[open]')) return;
    var panel = root.querySelector('.rm-detail-panel.is-open');
    if (!panel) return;

    var isMobile = isMobileViewport();

    if (e.key === 'Escape') {
      if (isMobile) {
        var closeBtn = panel.querySelector('.rm-detail-close');
        if (closeBtn && isInternalRoadmapLink(closeBtn)) {
          e.preventDefault();
          fetchAndSwap(closeBtn.href, true);
        }
      }
      return;
    }

    if (e.key === 'Tab' && isMobile) {
      var focusables = Array.from(panel.querySelectorAll('a[href], button:not([disabled]), select, input, summary, [tabindex="0"]')).filter(function (element) {
        var closedDetails = element.closest('details:not([open])');
        return element.getClientRects().length > 0 && (!closedDetails || element === closedDetails.querySelector('summary'));
      });
      if (!focusables.length) return;

      var first = focusables[0];
      var last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !panel.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !panel.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  });

  // Update dialog state and inert background on viewport resize
  window.addEventListener('resize', function () {
    var panel = root.querySelector('.rm-detail-panel');
    var isPanelOpen = panel && panel.classList.contains('is-open');
    if (!isPanelOpen) return;

    if (isMobileViewport()) {
      setupSheetDialog(panel);
    } else {
      tearDownSheetDialog(panel);
    }
  });

  // Browser Back / Forward navigation
  window.addEventListener('popstate', function () {
    // Fresh request to current URL, no history push
    fetchAndSwap(window.location.href, false);
  });

  // Initial setup on page load
  initTopicFinder();
  var initialPanel = root.querySelector('.rm-detail-panel.is-open');
  if (initialPanel) {
    lastFocusedNodeId = new URL(window.location.href).searchParams.get('selected');
  }
  if (initialPanel && isMobileViewport()) {
    setupSheetDialog(initialPanel);
  }
})();

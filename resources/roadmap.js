/**
 * Scoped Roadmap interaction for Mentor Roadmap v2.
 * Handles lazy disclosure, recursive branches, error recovery and inline retry,
 * keyset pagination, history state preservation, and accessible keyboard navigation.
 */
(function () {
  'use strict';

  var root = document.querySelector('.ms-roadmap');
  if (!root) return;

  var apiRoot = root.dataset.apiRoot || '';
  if (apiRoot && apiRoot.charAt(apiRoot.length - 1) !== '/') {
    apiRoot += '/';
  }
  var rootRevision = root.dataset.revision;

  // Signal enhancement to CSS (hides SSR fallback pagination links)
  root.classList.add('rm-enhanced');

  var nodeTemplate = document.getElementById('rm-node-template');

  // Track per-element fetch/retry states without leaking memory
  var pageStates = new WeakMap();
  var restoringHistory = false;

  function getPageState(element) {
    var state = pageStates.get(element);
    if (!state) {
      state = { pending: false, request: null, pages: 1 };
      pageStates.set(element, state);
    }
    return state;
  }

  /**
   * Format progress according to roadmap specification:
   * direct 'Bài tập: AC x/y', subtree 'Cả nhánh: AC x/y' when children;
   * anonymous 'Đăng nhập để xem AC', empty 'Chưa có bài tập', unavailable 'Tiến độ tạm không khả dụng'.
   */
  function formatProgress(val, label) {
    if (!val || typeof val !== 'object') {
      return 'Tiến độ tạm không khả dụng';
    }
    if (val.state === 'available') {
      var solved = val.solved != null ? val.solved : 0;
      var total = val.total != null ? val.total : 0;
      return label + ': AC ' + solved + '/' + total;
    }
    if (val.state === 'anonymous') {
      return 'Đăng nhập để xem AC';
    }
    if (val.state === 'empty') {
      return 'Chưa có bài tập';
    }
    return 'Tiến độ tạm không khả dụng';
  }

  /**
   * Populate/update common node fields safely using DOM textContent.
   */
  function populateNodeFields(nodeEl, item) {
    nodeEl.dataset.title = item.title || '';
    nodeEl.dataset.type = item.type || '';
    nodeEl.dataset.contentState = item.content_state || '';
    var contentStatus = nodeEl.querySelector(':scope > .rm-row .rm-content-status');
    if (contentStatus) contentStatus.hidden = item.content_state !== 'UPCOMING';

    var titleEl = nodeEl.querySelector(':scope > .rm-row .rm-title');
    if (titleEl) {
      titleEl.textContent = item.title;
      if (item.focus_url) titleEl.href = item.focus_url;
    }

    var focusLink = nodeEl.querySelector(':scope > .rm-row .rm-focus-link');
    if (focusLink) {
      if (item.focus_url) focusLink.href = item.focus_url;
      focusLink.textContent = 'Xem nhánh';
      focusLink.hidden = !item.has_children;
      var sr = document.createElement('span');
      sr.className = 'rm-sr';
      sr.textContent = ' ' + item.title;
      focusLink.appendChild(sr);
    }

    var learnLink = nodeEl.querySelector(':scope > .rm-row .rm-learn');
    if (learnLink) {
      if (item.learn_url) {
        learnLink.href = item.learn_url;
        learnLink.textContent = 'Vào học';
        var srL = document.createElement('span');
        srL.className = 'rm-sr';
        srL.textContent = ' ' + item.title;
        learnLink.appendChild(srL);
        learnLink.hidden = false;
      } else {
        learnLink.hidden = true;
        learnLink.removeAttribute('href');
      }
    }

    var directProg = nodeEl.querySelector(':scope > .rm-row .rm-progress-direct');
    if (directProg) {
      directProg.textContent = formatProgress(item.progress, 'Bài tập');
      directProg.dataset.state = item.progress ? item.progress.state : 'unavailable';
      directProg.dataset.complete = String(Boolean(item.progress && item.progress.state === 'available' &&
        item.progress.total > 0 && item.progress.solved === item.progress.total));
    }

    var subtreeProg = nodeEl.querySelector(':scope > .rm-row .rm-progress-subtree');
    if (subtreeProg) {
      if (!item.has_children || !item.subtree_progress || item.subtree_progress.state === 'anonymous') {
        subtreeProg.hidden = true;
        subtreeProg.textContent = '';
      } else {
        subtreeProg.hidden = false;
        subtreeProg.textContent = formatProgress(item.subtree_progress, 'Cả nhánh');
      }
    }
    var depthHint = nodeEl.querySelector(':scope > .rm-row .rm-depth-hint');
    if (depthHint) depthHint.hidden = !item.has_children;
  }

  /**
   * Render a roadmap node safely using DOM textContent.
   */
  function renderNode(item) {
    if (!nodeTemplate) return document.createElement('li');
    var clone = nodeTemplate.content.firstElementChild.cloneNode(true);
    clone.dataset.nodeId = String(item.id);
    var parentLabel = clone.querySelector('.rm-parent');
    var parentNode = item.parent_id ? root.querySelector('.rm-node[data-node-id="' + item.parent_id + '"]') : null;
    if (parentLabel && parentNode) {
      parentLabel.textContent = 'Thuộc: ' + parentNode.dataset.title;
      parentLabel.hidden = false;
    }

    var kindEl = clone.querySelector('.rm-kind');
    if (kindEl) kindEl.textContent = item.type === 'GROUP' ? 'Nhóm kiến thức' : 'Chuyên đề';

    var diffEl = clone.querySelector('.rm-difficulty');
    if (diffEl) {
      var diffMap = { BASIC: 'Cơ bản', INTERMEDIATE: 'Trung cấp', ADVANCED: 'Nâng cao' };
      diffEl.textContent = diffMap[item.difficulty] || '';
    }

    populateNodeFields(clone, item);

    var disclosureBtn = clone.querySelector('.rm-disclosure');
    var branchEl = clone.querySelector('.rm-branch');

    if (item.has_children) {
      var branchId = 'rm-children-' + item.id;
      if (disclosureBtn) {
        disclosureBtn.hidden = false;
        disclosureBtn.setAttribute('aria-expanded', 'false');
        disclosureBtn.setAttribute('aria-controls', branchId);
        disclosureBtn.setAttribute('aria-label', 'Mở nhánh ' + item.title);
        disclosureBtn.textContent = 'Mở nhánh';
      }
      if (branchEl) {
        branchEl.id = branchId;
        branchEl.dataset.parentId = String(item.id);
        branchEl.dataset.endpoint = apiRoot + 'nodes/' + item.id + '/children/';
        branchEl.hidden = true;
        branchEl.dataset.nextCursor = '';
        delete branchEl.dataset.loaded;
      }
    } else {
      if (disclosureBtn) disclosureBtn.hidden = true;
      if (branchEl) branchEl.remove();
    }

    return clone;
  }


  function buildUrl(endpoint, cursor) {
    var sep = endpoint.indexOf('?') === -1 ? '?' : '&';
    var url = endpoint;
    if (cursor) {
      url += sep + 'cursor=' + encodeURIComponent(cursor) + '&limit=50';
    } else {
      url += sep + 'limit=50';
    }
    return url;
  }

  /**
   * Fetch JSON with explicit Accept header and error classification.
   */
  function fetchJson(url) {
    return fetch(url, {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    }).then(function (response) {
      if (response.redirected) {
        var err = new Error('Redirected');
        err.kind = 'redirect';
        throw err;
      }
      var contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        var err = new Error('Non-JSON response');
        err.kind = 'non-json';
        throw err;
      }
      if (response.status === 404) {
        var err = new Error('Not found');
        err.kind = '404';
        throw err;
      }
      if (response.status === 409) {
        return response.json().then(function (data) {
          var err = new Error((data && data.error) ? data.error : 'Stale revision');
          err.kind = '409';
          err.data = data;
          throw err;
        });
      }
      if (!response.ok) {
        var err = new Error('HTTP ' + response.status);
        err.kind = 'http';
        err.status = response.status;
        throw err;
      }
      return response.json();
    });
  }

  function checkRevision(data) {
    if (data && data.tree_revision !== undefined && rootRevision !== undefined) {
      if (String(data.tree_revision) !== String(rootRevision)) {
        var err = new Error('Stale revision');
        err.kind = 'stale';
        throw err;
      }
    }
  }

  /**
   * Render inline error states and actions.
   */
  function handleError(err, statusEl, retryBtn, retryFn) {
    if (!statusEl || !retryBtn) return;
    if (err.kind === '404') {
      statusEl.textContent = 'Nội dung không tồn tại hoặc đã thay đổi. Vui lòng tải lại trang.';
      retryBtn.textContent = 'Tải lại trang';
      retryBtn.hidden = false;
      retryBtn.onclick = function () { window.location.reload(); };
    } else if (err.kind === '409' || err.kind === 'stale') {
      statusEl.textContent = 'Lộ trình đã được cập nhật phiên bản mới. Vui lòng tải lại trang.';
      retryBtn.textContent = 'Tải lại trang';
      retryBtn.hidden = false;
      retryBtn.onclick = function () { window.location.reload(); };
    } else if (err.kind === 'redirect' || err.kind === 'non-json') {
      statusEl.textContent = 'Phiên làm việc đã thay đổi hoặc máy chủ chuyển hướng. Vui lòng tải lại trang.';
      retryBtn.textContent = 'Tải lại trang';
      retryBtn.hidden = false;
      retryBtn.onclick = function () { window.location.reload(); };
    } else {
      statusEl.textContent = 'Không thể kết nối máy chủ. Vui lòng thử lại.';
      retryBtn.textContent = 'Thử lại';
      retryBtn.hidden = false;
      retryBtn.onclick = function () {
        retryBtn.hidden = true;
        statusEl.textContent = '';
        if (typeof retryFn === 'function') retryFn();
      };
    }
  }

  /**
   * Fetch immediate children for a branch (first load or revalidate).
   * Guarantees: collapse-during-load must not reopen; re-expand fresh revalidates without dupes.
   */
  function loadBranch(branch, nodeEl, btn) {
    var state = getPageState(branch);
    if (state.pending) {
      var cachedList = branch.querySelector(':scope > .rm-list');
      if (cachedList) cachedList.hidden = true;
      return state.request.then(function () {
        if (!branch.hidden && branch.isConnected) return loadBranch(branch, nodeEl, btn);
      });
    }
    state.pending = true;

    var statusEl = branch.querySelector(':scope > .rm-status') || branch.querySelector('.rm-status');
    var retryBtn = branch.querySelector(':scope > .rm-retry') || branch.querySelector('.rm-retry');
    var moreBtn = branch.querySelector(':scope > .rm-more') || branch.querySelector('.rm-more');
    var listEl = branch.querySelector(':scope > .rm-list') || branch.querySelector('.rm-list');

    if (statusEl) statusEl.textContent = 'Đang tải nhánh...';
    if (retryBtn) retryBtn.hidden = true;
    if (moreBtn) moreBtn.hidden = true;
    // Cached descendants must not remain visible across an authorization refresh.
    if (listEl) listEl.hidden = true;

    var endpoint = branch.dataset.endpoint || (apiRoot + 'nodes/' + nodeEl.dataset.nodeId + '/children/');
    branch.dataset.endpoint = endpoint;
    var url = buildUrl(endpoint, null);

    state.request = fetchJson(url)
      .then(function (data) {
        checkRevision(data);
        branch.dataset.loaded = 'true';
        state.pages = 1;

        // Collapse-during-load must NOT reopen
        var isStillExpanded = btn.getAttribute('aria-expanded') === 'true' && !branch.hidden;
        if (!isStillExpanded) {
          branch.hidden = true;
          btn.setAttribute('aria-expanded', 'false');
          btn.textContent = 'Mở nhánh';
          btn.setAttribute('aria-label', 'Mở nhánh ' + (nodeEl.dataset.title || ''));
        }

        if (statusEl) statusEl.textContent = '';

        var items = data.items || [];
        if (items.length === 0) {
          if (document.activeElement === btn || branch.contains(document.activeElement)) {
            nodeEl.querySelector('.rm-title').focus();
          }
          btn.hidden = true;
          btn.setAttribute('aria-expanded', 'false');
          branch.hidden = true;
          if (listEl) listEl.replaceChildren();
          return;
        }

        if (listEl) {
          listEl.replaceChildren();
          var seen = new Set();
          items.forEach(function (item) {
            if (!seen.has(item.id)) listEl.appendChild(renderNode(item));
            seen.add(item.id);
          });
          listEl.hidden = false;
        }

        var hasCursor = Boolean(data.next_cursor && data.next_cursor.trim());
        branch.dataset.nextCursor = hasCursor ? data.next_cursor : '';
        if (moreBtn) moreBtn.hidden = !(hasCursor && isStillExpanded);

        saveHistoryState();
      })
      .catch(function (err) {
        if (statusEl && retryBtn) {
          handleError(err, statusEl, retryBtn, function () {
            loadBranch(branch, nodeEl, btn);
          });
        }
      }).finally(function () {
        state.pending = false;
      });
    return state.request;
  }

  /**
   * Keyset pagination: load more items and append with deterministic distinct IDs.
   * Retains prior successful items on network failure.
   */
  function loadMore(pageEl, moreBtn) {
    var state = getPageState(pageEl);
    if (state.pending) return state.request;

    var cursor = pageEl.dataset.nextCursor;
    if (!cursor || !cursor.trim()) {
      moreBtn.hidden = true;
      return;
    }

    state.pending = true;

    var statusEl = pageEl.querySelector(':scope > .rm-status') || pageEl.querySelector('.rm-status');
    var retryBtn = pageEl.querySelector(':scope > .rm-retry') || pageEl.querySelector('.rm-retry');
    var listEl = pageEl.querySelector(':scope > .rm-list') || pageEl.querySelector('.rm-list');

    moreBtn.hidden = true;
    if (retryBtn) retryBtn.hidden = true;
    if (statusEl) statusEl.textContent = 'Đang tải thêm node...';

    var endpoint = pageEl.dataset.endpoint;
    if (!endpoint) {
      if (pageEl.dataset.parentId) {
        endpoint = apiRoot + 'nodes/' + pageEl.dataset.parentId + '/children/';
      } else if (pageEl.id === 'rm-roots') {
        endpoint = apiRoot + '?format=json';
      }
    }
    var url = buildUrl(endpoint, cursor);

    state.request = fetchJson(url)
      .then(function (data) {
        checkRevision(data);
        state.pages += 1;
        if (statusEl) statusEl.textContent = '';

        var items = data.items || [];
        if (listEl) {
          items.forEach(function (item) {
            var existing = listEl.querySelector(':scope > .rm-node[data-node-id="' + item.id + '"]');
            if (!existing) {
              listEl.appendChild(renderNode(item));
            }
          });
        }

        var hasCursor = Boolean(data.next_cursor && data.next_cursor.trim());
        pageEl.dataset.nextCursor = hasCursor ? data.next_cursor : '';
        moreBtn.hidden = !hasCursor;

        saveHistoryState();
      })
      .catch(function (err) {
        // Keep prior successful pages if pagination fails!
        if (listEl && ['404', '409', 'stale', 'redirect', 'non-json'].includes(err.kind)) {
          listEl.hidden = true;
        }
        if (statusEl && retryBtn) {
          handleError(err, statusEl, retryBtn, function () {
            loadMore(pageEl, moreBtn);
          });
        }
      }).finally(function () {
        state.pending = false;
      });
    return state.request;
  }

  /**
   * Handle disclosure toggle.
   * If collapse happens while subtree is focused, returns focus to the disclosure button.
   */
  function handleDisclosureClick(btn) {
    var nodeEl = btn.closest('.rm-node');
    if (!nodeEl) return;
    var branch = nodeEl.querySelector(':scope > .rm-branch') ||
                 document.getElementById(btn.getAttribute('aria-controls'));
    if (!branch) return;

    var isExpanded = btn.getAttribute('aria-expanded') === 'true' && !branch.hidden;

    if (isExpanded) {
      branch.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = 'Mở nhánh';
      btn.setAttribute('aria-label', 'Mở nhánh ' + (nodeEl.dataset.title || ''));

      // Return focus from subtree if activeElement was inside
      if (branch.contains(document.activeElement)) {
        btn.focus();
      }
      saveHistoryState();
    } else {
      branch.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      btn.textContent = 'Thu nhánh';
      btn.setAttribute('aria-label', 'Thu nhánh ' + (nodeEl.dataset.title || ''));

      loadBranch(branch, nodeEl, btn);
      saveHistoryState();
    }
  }

  /**
   * History metadata only: save expanded node IDs, focused control, and scroll position.
   * Never stores private payload.
   */
  function getHistoryMetadata() {
    var expandedIds = [];
    var pageCounts = {};
    root.querySelectorAll('.rm-page').forEach(function (page) {
      var owner = page.closest('.rm-node');
      pageCounts[owner ? owner.dataset.nodeId : 'roots'] = getPageState(page).pages;
    });
    root.querySelectorAll('.rm-node').forEach(function (node) {
      var btn = node.querySelector(':scope > .rm-row .rm-disclosure');
      if (btn && btn.getAttribute('aria-expanded') === 'true') {
        expandedIds.push(node.dataset.nodeId);
      }
    });

    var activeEl = document.activeElement;
    var focusedControl = null;
    if (activeEl && root.contains(activeEl)) {
      if (activeEl.id) {
        focusedControl = '#' + activeEl.id;
      } else {
        var n = activeEl.closest('.rm-node');
        if (n) {
          if (activeEl.classList.contains('rm-disclosure')) {
            focusedControl = '[data-node-id="' + n.dataset.nodeId + '"] .rm-disclosure';
          } else if (activeEl.classList.contains('rm-focus')) {
            focusedControl = '[data-node-id="' + n.dataset.nodeId + '"] .rm-focus';
          } else if (activeEl.classList.contains('rm-learn')) {
            focusedControl = '[data-node-id="' + n.dataset.nodeId + '"] .rm-learn';
          }
        }
      }
    }

    return {
      msRoadmap: true,
      expandedIds: expandedIds,
      pageCounts: pageCounts,
      focusedControl: focusedControl,
      scrollY: window.scrollY,
    };
  }

  function saveHistoryState() {
    if (restoringHistory) return;
    try {
      history.replaceState(getHistoryMetadata(), '');
    } catch (e) {}
  }

  /**
   * Browser Back restoration: restore expanded branches with FRESH reads before using prior data.
   */
  async function restoreFromHistory(state) {
    if (!state || !state.msRoadmap) return;
    restoringHistory = true;
    try {
      async function restorePages(page, key) {
        var count = (state.pageCounts || {})[key] || 1;
        var more = page.querySelector(':scope > .rm-more');
        while (more && getPageState(page).pages < count && page.dataset.nextCursor) {
          var before = getPageState(page).pages;
          await loadMore(page, more);
          if (getPageState(page).pages === before) break;
        }
      }
      await restorePages(document.getElementById('rm-roots'), 'roots');
      // Reconstruct parents and their authorized pages before locating descendants.
      for (var nodeId of state.expandedIds || []) {
        var node = root.querySelector('.rm-node[data-node-id="' + nodeId + '"]');
        if (!node) continue;
        var btn = node.querySelector(':scope > .rm-row .rm-disclosure');
        var branch = node.querySelector(':scope > .rm-branch');
        if (!btn || !branch) continue;
        branch.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        btn.textContent = 'Thu nhánh';
        btn.setAttribute('aria-label', 'Thu nhánh ' + node.dataset.title);
        await loadBranch(branch, node, btn);
        await restorePages(branch, nodeId);
      }
      if (state.focusedControl) {
        var el = root.querySelector(state.focusedControl);
        if (el && el.getClientRects().length) el.focus({ preventScroll: true });
      }
      window.scrollTo(0, state.scrollY || 0);
    } finally {
      restoringHistory = false;
      saveHistoryState();
    }
  }


  function init() {
    // Heading focus when ?focus is present in URL
    var params = new URLSearchParams(window.location.search);
    if (params.has('focus')) {
      var heading = document.getElementById('rm-heading');
      if (heading) {
        heading.focus();
      }
    }

    // Reveal disclosure buttons for nodes with valid children
    root.querySelectorAll('.rm-node').forEach(function (nodeEl) {
      var btn = nodeEl.querySelector(':scope > .rm-row .rm-disclosure');
      var branch = nodeEl.querySelector(':scope > .rm-branch') ||
                   (btn ? document.getElementById(btn.getAttribute('aria-controls')) : null);
      if (btn && branch) {
        btn.hidden = false;
        var isOpened = !branch.hidden;
        btn.setAttribute('aria-expanded', isOpened ? 'true' : 'false');
        btn.textContent = isOpened ? 'Thu nhánh' : 'Mở nhánh';
        btn.setAttribute('aria-label', (isOpened ? 'Thu' : 'Mở') + ' nhánh ' + (nodeEl.dataset.title || ''));
      } else if (btn) {
        btn.hidden = true;
      }
    });

    // Initialize pagination more-buttons on .rm-page elements
    root.querySelectorAll('.rm-page').forEach(function (pageEl) {
      var moreBtn = pageEl.querySelector(':scope > .rm-more') || pageEl.querySelector('.rm-more');
      if (moreBtn) {
        if (pageEl.dataset.nextCursor && pageEl.dataset.nextCursor.trim() !== '') {
          moreBtn.hidden = false;
        } else {
          moreBtn.hidden = true;
        }
      }
    });

    if (history.state && history.state.msRoadmap) {
      restoreFromHistory(history.state);
    } else {
      saveHistoryState();
    }
  }

  // Event delegation on root
  root.addEventListener('click', function (event) {
    var disclosureBtn = event.target.closest('.rm-disclosure');
    if (disclosureBtn && root.contains(disclosureBtn)) {
      event.preventDefault();
      handleDisclosureClick(disclosureBtn);
      return;
    }

    var moreBtn = event.target.closest('.rm-more');
    if (moreBtn && root.contains(moreBtn)) {
      event.preventDefault();
      var pageEl = moreBtn.closest('.rm-page');
      if (pageEl) {
        loadMore(pageEl, moreBtn);
      }
      return;
    }
    if (event.target.closest('a')) saveHistoryState();
  });

  // bfcache restoration
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    // A restored document may belong to a previous account or publication state.
    root.hidden = true;
    window.location.reload();
  });

  // Browser Back/Forward navigation
  window.addEventListener('popstate', function (event) {
    if (event.state && event.state.msRoadmap) {
      restoreFromHistory(event.state);
    }
  });

  // Save scroll position with passive listener
  var scrollDebounce = null;
  window.addEventListener('scroll', function () {
    if (scrollDebounce) return;
    scrollDebounce = setTimeout(function () {
      scrollDebounce = null;
      saveHistoryState();
    }, 250);
  }, { passive: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

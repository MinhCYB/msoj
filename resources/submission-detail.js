(function () {
  'use strict';
  var mounted = new WeakMap();
  function mount(root, options) {
    options = options || {};
    if (mounted.has(root)) return mounted.get(root);
    var timer, controller, disposed = false, reviewDispose;
    var message = document.createElement('p');
    message.className = 'ms-submission-message';
    message.setAttribute('role', 'status');
    root.appendChild(message);
    if (root.querySelector('#ai-review') && window.MSOJAIReview)
      reviewDispose = window.MSOJAIReview.mount(root.querySelector('#ai-review'));
    function schedule() {
      if (!disposed && root.dataset.graded !== 'true') timer = setTimeout(refresh, 2000);
    }
    async function refresh() {
      if (disposed || document.hidden) { schedule(); return; }
      controller = new AbortController();
      try {
        var url = new URL(root.dataset.statusUrl, location.href);
        url.searchParams.set('workspace', '1');
        var response = await fetch(url, { credentials: 'same-origin', signal: controller.signal });
        if (!response.ok || response.redirected) throw new Error();
        var doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        var updated = doc.querySelector('.ms-submission-detail');
        if (!updated || updated.dataset.id !== root.dataset.id) throw new Error();
        root.dataset.graded = updated.dataset.graded;
        var oldResult = root.querySelector('.ms-submission-result');
        var result = updated.querySelector('.ms-submission-result');
        if (oldResult && result) oldResult.replaceWith(result);
        ['.ms-submission-detail-tabs', '.ms-submission-actions'].forEach(function(selector) {
          var oldPanel = root.querySelector(selector), newPanel = updated.querySelector(selector);
          if (selector === '.ms-submission-actions' && root.querySelector('[data-source-code]')) {
            var copyButton = oldPanel && oldPanel.querySelector('[data-copy-source]');
            if (copyButton && newPanel) newPanel.appendChild(copyButton);
          }
          if (oldPanel && newPanel) oldPanel.replaceWith(newPanel);
        });
        prepareRows();
        if (root.dataset.graded === 'true') {
          root.querySelectorAll('[data-submission-action="abort"]').forEach(function (form) { form.remove(); });
          message.textContent = 'Đã chấm xong.';
          if (options.onChange) options.onChange();
        }
      } catch (error) {
        if (disposed) return;
        message.textContent = 'Chưa cập nhật được kết quả. Đang thử kết nối lại; bạn có thể tải lại trang.';
      }
      schedule();
    }
    function click(event) {
      var copy = event.target.closest('[data-copy-source]');
      var resubmit = event.target.closest('[data-submission-resubmit]');
      if (resubmit && !root.closest('.ms-workspace')) {
        event.preventDefault();
        var next = new URL('/problem/' + encodeURIComponent(root.dataset.problemCode), location.href);
        next.searchParams.set('resubmit',root.dataset.id);next.hash='statement';location.assign(next);return;
      }
      if (copy) {
        event.preventDefault();
        var code = root.querySelector('[data-source-code]');
        if (code) {
          var copied = function () {message.textContent = 'Đã sao chép mã nguồn.';};
          var fallback = function () {
            var input = document.createElement('textarea');
            input.value = code.textContent;input.style.position='fixed';input.style.opacity='0';
            root.appendChild(input);input.select();
            var success = document.execCommand('copy');input.remove();
            if (success) copied();else message.textContent = 'Không thể sao chép. Hãy chọn mã nguồn hoặc mở bản thô.';
          };
          if (navigator.clipboard) navigator.clipboard.writeText(code.textContent).then(copied).catch(fallback);
          else fallback();
        }
      }
      var row = event.target.closest('.case-row.toggle');
      if (row && !event.target.closest('a,button,input')) toggleRow(row);
    }
    function toggleRow(row) {
      var feedback=row.nextElementSibling;
      if(!feedback || !feedback.classList.contains('case-feedback'))return;
      var open=row.classList.contains('closed');row.classList.toggle('closed',!open);row.classList.toggle('open',open);row.setAttribute('aria-expanded',String(open));feedback.style.display=open?'table-row':'none';
    }
    function prepareRows() {
      root.querySelectorAll('.case-row.toggle').forEach(function(row){
        if(!row.nextElementSibling || !row.nextElementSibling.classList.contains('case-feedback'))return;
        row.tabIndex=0;row.setAttribute('aria-expanded','false');
        if(window.jQuery)window.jQuery(row).off('click');
      });
    }
    function keydown(event){var row=event.target.closest('.case-row.toggle');if(row&&event.target===row&&(event.key==='Enter'||event.key===' ')){event.preventDefault();toggleRow(row);}}
    async function submit(event) {
      var form = event.target.closest('[data-submission-action]');
      if (!form) return;
      event.preventDefault();
      var action = form.dataset.submissionAction;
      if (!confirm(action === 'rejudge' ? 'Chấm lại bài nộp này?' : 'Dừng chấm bài nộp này?')) return;
      var button = form.querySelector('button,input[type=submit]');
      if (button) button.disabled = true;
      message.textContent = action === 'rejudge' ? 'Đang yêu cầu chấm lại…' : 'Đang yêu cầu dừng chấm…';
      try {
        var response = await fetch(form.action, {method:'POST', body:new FormData(form), credentials:'same-origin'});
        if (!response.ok || response.url.includes('/accounts/login')) throw new Error();
        root.dataset.graded = 'false';
        clearTimeout(timer);
        await refresh();
        if (options.onChange) options.onChange();
      } catch (error) { message.textContent = 'Không thực hiện được thao tác. Kiểm tra quyền truy cập hoặc tải lại trang.'; }
      finally { if (button && button.isConnected) button.disabled = false; }
    }
    root.addEventListener('click', click);
    root.addEventListener('submit', submit);
    root.addEventListener('keydown',keydown);
    prepareRows();
    schedule();
    var dispose = function () {
      disposed = true;
      clearTimeout(timer);
      if (controller) controller.abort();
      if (reviewDispose) reviewDispose();
      root.removeEventListener('click', click);
      root.removeEventListener('submit', submit);
      root.removeEventListener('keydown',keydown);
      mounted.delete(root);
    };
    mounted.set(root, dispose);
    return dispose;
  }
  window.MSOJSubmissionDetail = {mount: mount};
  document.querySelectorAll('.ms-submission-detail').forEach(function (root) { mount(root); });
})();

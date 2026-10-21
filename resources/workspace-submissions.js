(function () {
  'use strict';
  var workspace = document.querySelector('.ms-workspace');
  if (!workspace) return;
  var main = workspace.querySelector('.ms-workspace-main');
  var list = main.querySelector('.ms-workspace-submissions-content');
  var detail = main.querySelector('.ms-workspace-submission-detail');
  var form = document.getElementById('problem_submit');
  var language = document.getElementById('id_language');
  var textarea = document.getElementById('id_source');
  var dispose, request, serial = 0, listTimer;
  var listScroll = 0;
  var draftKey = 'msoj:solution:' + workspace.dataset.userId + ':' + workspace.dataset.problemCode;
  var notice = document.createElement('p');
  notice.className = 'ms-submission-message';
  notice.setAttribute('role', 'status');
  if (form) form.prepend(notice);
  function source() { return window.ace_source ? window.ace_source.getValue() : textarea.value; }
  var draftReady = false;
  function saveDraft() {
    if (!textarea || !language || !draftReady) return;
    try { localStorage.setItem(draftKey, JSON.stringify({language:language.value,source:source()})); }
    catch (error) { notice.textContent = 'Không thể lưu nháp trên trình duyệt. Hãy tải mã nguồn về trước khi rời trang.'; }
  }
  function invalidate() { document.dispatchEvent(new CustomEvent('msoj:submissions-changed')); }
  function setUrl(url) {
    history.pushState(history.state, '', url);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  function selectSubmission(id, panel) {
    var url = new URL(location.href);
    url.searchParams.set('submission', id);
    url.searchParams.set('panel', panel || 'result');
    if (!/^#submission(?:-all|-best)?$/.test(url.hash)) url.hash = 'submission';
    setUrl(url);
  }
  function leaveDetail() {
    serial++;
    if (request) request.abort();
    if (dispose) { dispose(); dispose = null; }
    detail.replaceChildren();
    detail.hidden = true;
    list.hidden = false;
    list.scrollTop=listScroll;
  }
  async function showDetail(id, panel) {
    if (!list.hidden) listScroll=list.scrollTop;
    leaveDetail();
    list.hidden = true;
    detail.hidden = false;
    detail.textContent = 'Đang tải bài nộp…';
    detail.setAttribute('aria-busy', 'true');
    var version = serial;
    request = new AbortController();
    try {
      var url = new URL(panel === 'source' ? '/src/' + id : '/submission/' + id, location.href);
      url.searchParams.set('workspace', '1');
      if (panel === 'review') url.searchParams.set('panel', 'review');
      var response = await fetch(url, {credentials:'same-origin',signal:request.signal});
      if (!response.ok || response.redirected) throw new Error();
      var doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      var root = doc.querySelector('.ms-submission-detail');
      if (!root || root.dataset.problemCode !== workspace.dataset.problemCode) throw new Error();
      if (version !== serial) return;
      var back = document.createElement('button');
      back.type = 'button'; back.className = 'button'; back.textContent = 'Quay lại danh sách';
      back.addEventListener('click', function () {
        var next = new URL(location.href);next.searchParams.delete('submission');next.searchParams.delete('panel');setUrl(next);
      });
      detail.replaceChildren(back, root);
      dispose = window.MSOJSubmissionDetail.mount(root, {onChange:invalidate});
      root.tabIndex = -1;
      root.focus({preventScroll:true});
    } catch (error) {
      if (version !== serial || error.name === 'AbortError') return;
      detail.textContent = 'Không thể mở bài nộp. Bài có thể không thuộc đề này, phiên đăng nhập đã hết hoặc bạn không có quyền xem.';
      var retry = document.createElement('button');retry.type='button';retry.textContent='Thử lại';retry.className='button';
      retry.addEventListener('click', function () { showDetail(id,panel); });detail.appendChild(retry);
      var back = document.createElement('a');back.href=location.pathname+'#submission';back.textContent='Quay lại danh sách';detail.appendChild(back);
    } finally { if (version === serial) detail.removeAttribute('aria-busy'); }
  }
  window.MSOJWorkspaceSubmissions = {
    navigate: function (tab) {
      clearTimeout(listTimer);
      var params = new URL(location.href).searchParams;
      if (/^submission(?:-all|-best)?$/.test(tab) && /^\d+$/.test(params.get('submission') || '')) {
        showDetail(params.get('submission'), ['result','source','review'].includes(params.get('panel')) ? params.get('panel') : 'result');return true;
      }
      leaveDetail();return false;
    },
    listLoaded: function () {
      clearTimeout(listTimer);
      if (list.querySelector('.grading-spinner')) listTimer=setTimeout(invalidate,2500);
    }
  };
  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('a');
    if (!link || !workspace.contains(link)) return;
    if (link.dataset.workspaceTab) {
      event.preventDefault();
      var clean = new URL(location.href); clean.searchParams.delete('submission');clean.searchParams.delete('panel');clean.hash=link.dataset.workspaceTab;
      setUrl(clean);return;
    }
    var target = new URL(link.href,location.href);
    if (target.origin !== location.origin) return;
    if (detail.contains(link) && target.pathname === location.pathname && target.hash && !link.dataset.submissionPanel) {
      var anchor = [...detail.querySelectorAll('[id], [name]')].find(function(node) {return node.id === target.hash.slice(1) || node.getAttribute('name') === target.hash.slice(1);});
      if (anchor) {event.preventDefault();anchor.scrollIntoView({block:'nearest'});return;}
    }
    var match=target.pathname.match(/^\/(submission|src)\/(\d+)$/);
    if (match && (list.contains(link) || detail.contains(link))) {
      event.preventDefault();selectSubmission(match[2],link.dataset.submissionPanel || (match[1]==='src'?'source':'result'));return;
    }
    if (link.hasAttribute('data-submission-resubmit')) {
      event.preventDefault();loadResubmit(detail.querySelector('.ms-submission-detail').dataset.id);
    }
  });
  async function loadResubmit(id) {
    if (!form || !language) return;
    try {
      var response=await fetch('/src/'+id+'?workspace=1',{credentials:'same-origin'});
      if (!response.ok || response.redirected) throw new Error();
      var doc=new DOMParser().parseFromString(await response.text(),'text/html');
      var root=doc.querySelector('.ms-submission-detail');
      if (!root || root.dataset.problemCode!==workspace.dataset.problemCode || root.dataset.canResubmit!=='true') throw new Error();
      var code=root.querySelector('[data-source-code]');
      var lang=root.dataset.languageId;
      if (!code || ![...language.options].some(function(o){return o.value===lang;})) throw new Error();
      if (source().trim() && source()!==code.textContent && !confirm('Mã bài nộp sẽ thay nội dung editor. Nháp hiện tại sẽ được giữ để khôi phục. Tiếp tục?')) return;
      var previous={language:language.value,source:source()};
      try { localStorage.setItem(draftKey+':previous',JSON.stringify(previous)); } catch(error) { throw new Error(); }
      language.value=lang;
      if (window.jQuery) window.jQuery(language).trigger('change');
      textarea.value=code.textContent;
      if (window.ace_source) window.ace_source.setValue(code.textContent,-1);
      saveDraft();
      var url=new URL(location.href);url.searchParams.delete('submission');url.searchParams.delete('panel');url.searchParams.delete('resubmit');url.hash='statement';setUrl(url);
      notice.textContent='Đã đưa mã bài nộp #'+id+' vào editor. Nháp trước vẫn được lưu.';
      var restore=document.createElement('button');restore.type='button';restore.textContent='Khôi phục nháp trước';restore.className='button';
      restore.addEventListener('click',function(){if(!confirm('Khôi phục nháp trước và thay nội dung editor hiện tại?'))return;language.value=previous.language;if(window.jQuery)window.jQuery(language).trigger('change');textarea.value=previous.source;if(window.ace_source)window.ace_source.setValue(previous.source,-1);saveDraft();notice.textContent='Đã khôi phục nháp.';});notice.appendChild(restore);
    } catch(error) { notice.textContent='Không thể tải mã nguồn để nộp lại. Nháp hiện tại chưa bị thay đổi.'; }
  }
  if (form && textarea && language) {
    var initialized=false;
    function initializeDraft() {
      if (initialized || !window.ace_source || typeof window.ace_source.getSession !== 'function') return;
      initialized=true;
      try {
        var saved=JSON.parse(localStorage.getItem(draftKey)||'null');
        if(saved && [...language.options].some(function(o){return o.value===saved.language;})) {
          language.value=saved.language;
          if(window.jQuery)window.jQuery(language).trigger('change');
          textarea.value=saved.source;window.ace_source.setValue(saved.source,-1);
        }
      } catch(error) { notice.textContent='Không đọc được nháp đã lưu.'; }
      draftReady=true;
      var debounce;window.ace_source.getSession().on('change',function(){clearTimeout(debounce);debounce=setTimeout(saveDraft,400);});
      var resubmit=new URL(location.href).searchParams.get('resubmit');if(/^\d+$/.test(resubmit||''))loadResubmit(resubmit);
    }
    if(window.jQuery)window.jQuery('#ace_source').on('ace_load',initializeDraft);
    initializeDraft();
    window.addEventListener('pagehide',saveDraft);
    language.addEventListener('change',saveDraft);
    try {
      var previousDraft=JSON.parse(localStorage.getItem(draftKey+':previous')||'null');
      if(previousDraft){
        var restoreSaved=document.createElement('button');restoreSaved.type='button';restoreSaved.className='button';restoreSaved.textContent='Khôi phục nháp trước khi nộp lại';
        restoreSaved.addEventListener('click',function(){if(!confirm('Thay nội dung editor bằng nháp trước?'))return;language.value=previousDraft.language;if(window.jQuery)window.jQuery(language).trigger('change');textarea.value=previousDraft.source;if(window.ace_source)window.ace_source.setValue(previousDraft.source,-1);saveDraft();notice.textContent='Đã khôi phục nháp.';});notice.appendChild(restoreSaved);
      }
    } catch(error) {}
    var submitting=false;
    form.addEventListener('submit',async function(event){
      if(event.defaultPrevented)return;
      event.preventDefault();if(submitting)return;
      submitting=true;saveDraft();
      var button=form.querySelector('[type=submit]');if(button)button.disabled=true;
      notice.textContent='Đang gửi bài…';
      var data=new FormData(form);data.set('workspace_submission','1');
      try {
        var response=await fetch(form.action||location.pathname,{method:'POST',body:data,credentials:'same-origin',headers:{'Accept':'application/json'}});
        var isJson=(response.headers.get('Content-Type')||'').includes('application/json');
        if(!isJson)throw new Error('Yêu cầu bị từ chối hoặc phiên đăng nhập đã hết. Nháp vẫn được giữ; hãy kiểm tra giới hạn nộp bài và quyền truy cập.');
        var result=await response.json();
        if(!response.ok){var errors=Object.values(result.errors||{}).flat().map(function(e){return e.message;}).join(' ');throw new Error(errors||result.error||'Không gửi được bài. Nháp vẫn được giữ.');}
        if(!result.id || result.problem_code!==workspace.dataset.problemCode)throw new Error('Không xác nhận được bài nộp. Kiểm tra lịch sử trước khi gửi lại.');
        notice.textContent='Đã gửi bài #'+result.id+'.';invalidate();selectSubmission(result.id,'result');
      } catch(error){notice.textContent=error.message||'Mất kết nối. Kiểm tra lịch sử trước khi gửi lại; nháp vẫn được giữ.';}
      finally{submitting=false;if(button)button.disabled=false;}
    });
  }
})();

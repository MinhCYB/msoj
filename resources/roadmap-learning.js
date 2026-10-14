(function () {
    'use strict';
    var root = document.querySelector('.rm-learning');
    if (!root) return;
    root.querySelectorAll('.rm-prose').forEach(function (prose) {
        var headings = Array.from(prose.querySelectorAll('h1, h2, h3, h4, h5, h6'));
        if (!headings.length) return;
        var base = Math.min.apply(null, headings.map(function (heading) { return Number(heading.tagName.slice(1)); }));
        var previous = 2;
        headings.forEach(function (heading) {
            var level = Math.min(6, previous + 1, Number(heading.tagName.slice(1)) - base + 3);
            previous = level;
            if (heading.tagName === 'H' + level) return;
            var replacement = document.createElement('h' + level);
            Array.from(heading.attributes).forEach(function (attribute) {
                replacement.setAttribute(attribute.name, attribute.value);
            });
            replacement.append.apply(replacement, Array.from(heading.childNodes));
            heading.replaceWith(replacement);
        });
    });
    root.querySelectorAll('.rm-prose table, .rm-prose pre').forEach(function (element) {
        var region = document.createElement('div');
        region.className = 'rm-prose-scroll';
        region.tabIndex = 0;
        region.setAttribute('role', 'region');
        region.setAttribute('aria-label', element.tagName === 'TABLE' ? 'Bảng nội dung, cuộn ngang nếu cần' : 'Đoạn mã, cuộn ngang nếu cần');
        element.before(region);
        region.appendChild(element);
    });
    // Never show a learner document restored for a previous authentication state.
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            root.hidden = true;
            window.location.reload();
        }
    });
    var lecture = root.querySelector('.rm-lecture-layout');
    if (!lecture) return;
    var tabs = Array.from(lecture.querySelectorAll('[role="tab"]'));
    var reading = lecture.querySelector('.rm-reading-pane');
    var tools = lecture.querySelector('.rm-reading-tools');
    var status = lecture.querySelector('.rm-resume-status');
    var resume = lecture.querySelector('.rm-resume-reading');
    var savedOffset = Number(lecture.dataset.resumeOffset || 0);
    var revision = Number(lecture.dataset.revision);
    var mobile = window.matchMedia('(max-width: 900px)');
    var tutor = lecture.querySelector('.rm-lecture-tutor');
    var contents = lecture.querySelector('.rm-lecture-contents');
    var headings = Array.from(reading.querySelectorAll('.rm-prose h3, .rm-prose h4, .rm-prose h5, .rm-prose h6'));
    headings.forEach(function (heading, index) {
        heading.id = 'rm-lecture-section-' + index;
        heading.tabIndex = -1;
        var item = document.createElement('li');
        var link = document.createElement('a');
        link.href = '#' + heading.id;
        link.textContent = heading.textContent;
        link.addEventListener('click', function (event) {
            event.preventDefault();
            activate(tabs[0]);
            reading.scrollTop += heading.getBoundingClientRect().top - reading.getBoundingClientRect().top - 24;
            heading.focus({preventScroll: true});
        });
        item.appendChild(link);
        contents.querySelector('ol').appendChild(item);
    });
    contents.hidden = headings.length === 0;
    function activate(tab) {
        tabs.forEach(function (item) {
            var selected = item === tab;
            item.setAttribute('aria-selected', String(selected));
            item.tabIndex = selected ? 0 : -1;
            var panel = document.getElementById(item.getAttribute('aria-controls'));
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-labelledby', item.id);
            panel.hidden = !selected;
        });
        tutor.hidden = mobile.matches && tab !== tabs[3];
        if (!mobile.matches) { tutor.removeAttribute('role'); tutor.setAttribute('aria-labelledby', 'rm-tutor-heading'); }
        tools.hidden = tab !== tabs[0];
    }
    lecture.querySelector('.rm-lecture-tabs').hidden = false;
    lecture.classList.add('is-enhanced');
    activate(tabs[0]);
    mobile.addEventListener('change', function () {
        var active = tabs.find(function (item) { return item.getAttribute('aria-selected') === 'true'; });
        activate(!mobile.matches && active === tabs[3] ? tabs[0] : active);
    });
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () { activate(tab); });
        tab.addEventListener('keydown', function (event) {
            var next;
            var available = tabs.filter(function (item) { return item !== tabs[3] || mobile.matches; });
            var current = available.indexOf(tab);
            if (event.key === 'ArrowRight') next = (current + 1) % available.length;
            else if (event.key === 'ArrowLeft') next = (current + available.length - 1) % available.length;
            else if (event.key === 'Home') next = 0;
            else if (event.key === 'End') next = available.length - 1;
            else return;
            event.preventDefault();
            available[next].focus();
            activate(available[next]);
        });
    });
    var form = lecture.querySelector('.rm-tutor-form');
    var token = form ? form.querySelector('[name="csrfmiddlewaretoken"]').value : '';
    function post(url, data, keepalive) {
        return fetch(url, {
            method: 'POST', credentials: 'same-origin', keepalive: Boolean(keepalive),
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
            body: JSON.stringify(data)
        }).then(function (response) {
            return response.json().catch(function () { return {error: response.status === 403 ? 'access_denied' : 'unavailable'}; })
                .then(function (data) { if (!response.ok) throw data; return data; });
        });
    }
    var stateUrl = lecture.dataset.stateUrl;
    var dirty = false;
    var saving = false;
    var saveTimer;
    var latestOffset = savedOffset;
    var positionVersion = Math.max(Date.now(), Number(lecture.dataset.positionVersion || 0) + 1);
    function offset() {
        var range = reading.scrollHeight - reading.clientHeight;
        return range > 0 ? Math.round(reading.scrollTop / range * 10000) : 0;
    }
    function savePosition(keepalive) {
        if (!dirty || (saving && !keepalive) || !stateUrl) return;
        if (!keepalive) saving = true;
        dirty = false;
        var current = latestOffset;
        post(stateUrl, {offset: current, content_revision: revision, position_version: positionVersion}, true).then(function () {
            status.textContent = 'Đã lưu vị trí đọc · không đánh dấu thành thạo.';
        }).catch(function (error) {
            dirty = true;
            status.textContent = error.error === 'revision_changed' ? 'Bài giảng đã thay đổi. Tải lại trang để lưu vị trí mới.' : 'Chưa lưu được vị trí. Tiếp tục đọc; cuộn lại để thử lưu.';
        }).finally(function () {
            if (!keepalive) saving = false;
            if (dirty && latestOffset !== current) savePosition(false);
        });
    }
    if (stateUrl) {
        resume.hidden = savedOffset <= 0;
        if (savedOffset === 0) {
            dirty = true;
            saveTimer = window.setTimeout(function () { savePosition(false); }, 1200);
        }
        resume.addEventListener('click', function () {
            reading.scrollTop = Math.max(0, reading.scrollHeight - reading.clientHeight) * savedOffset / 10000;
            reading.focus();
            resume.hidden = true;
        });
        reading.addEventListener('scroll', function () {
            if (reading.hidden) return;
            latestOffset = offset();
            positionVersion = Math.max(Date.now(), positionVersion + 1);
            dirty = true;
            window.clearTimeout(saveTimer);
            saveTimer = window.setTimeout(function () { savePosition(false); }, 1200);
        }, {passive: true});
        document.addEventListener('visibilitychange', function () { if (document.hidden) savePosition(true); });
        window.addEventListener('pagehide', function () { savePosition(true); });
    } else status.textContent = 'Đăng nhập để lưu vị trí đọc.';
    if (form) {
        var question = form.querySelector('textarea');
        var send = form.querySelector('.rm-tutor-send');
        var qaStatus = form.querySelector('.rm-tutor-status');
        var log = lecture.querySelector('.rm-tutor-messages');
        send.disabled = false;
        function append(role, content) {
            var message = document.createElement('div');
            message.className = 'rm-tutor-message';
            var label = document.createElement('strong');
            label.textContent = role;
            var text = document.createElement('p');
            text.textContent = content;
            message.append(label, text);
            log.appendChild(message);
            log.scrollTop = log.scrollHeight;
        }
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            if (send.disabled || !question.value.trim()) return;
            var value = question.value.trim();
            send.disabled = true;
            question.readOnly = true;
            form.setAttribute('aria-busy', 'true');
            qaStatus.textContent = 'AI đang soạn và kiểm tra câu trả lời. Bạn có thể tiếp tục đọc bài giảng.';
            post(form.dataset.url, {question: value, content_revision: revision}).then(function (data) {
                append('Bạn', value);
                append('AI', data.answer);
                question.value = '';
                qaStatus.textContent = 'Đã nhận câu trả lời được kiểm tra.';
            }).catch(function (error) {
                var messages = {
                    not_configured: 'Hỏi đáp AI chưa được cấu hình. Bạn vẫn có thể đọc bài giảng và tóm tắt.',
                    rate_limited: 'Bạn đã đạt giới hạn hỏi đáp. Hãy chờ rồi gửi lại câu hỏi.',
                    busy: 'Một câu hỏi đang được xử lý. Hãy chờ trước khi gửi tiếp.',
                    revision_changed: 'Bài giảng đã thay đổi. Sao chép câu hỏi rồi tải lại trang để dùng nội dung mới.',
                    access_denied: 'Phiên đăng nhập hoặc quyền truy cập đã thay đổi. Sao chép câu hỏi rồi đăng nhập lại.',
                    context_limit: 'Bài giảng quá dài để hỏi AI trong một lượt. Hãy đọc nội dung và tóm tắt; không có phần nào được gửi thiếu để AI đoán.',
                    not_found: 'Bài giảng không còn khả dụng. Sao chép câu hỏi rồi quay lại chuyên đề.',
                    contest_restricted: 'Hỏi đáp AI tạm dừng trong lượt thi. Bạn vẫn có thể đọc nội dung được phép truy cập.',
                    review_rejected: 'AI chưa tạo được câu trả lời đạt yêu cầu. Hãy diễn đạt cụ thể hơn hoặc đối chiếu bài giảng.'
                };
                qaStatus.textContent = messages[error.error] || 'Chưa nhận được câu trả lời đã kiểm tra. Câu hỏi vẫn được giữ; bạn có thể gửi lại.';
            }).finally(function () {
                send.disabled = false;
                question.readOnly = false;
                form.removeAttribute('aria-busy');
            });
        });
    }
})();

(function () {
    'use strict';
    var root = document.querySelector('.rm-learning');
    if (!root) return;
    var contentsToggle = root.querySelector('.rm-contents-toggle');
    var navigation = root.querySelector('.rm-document-sidebar');
    if (contentsToggle && navigation) {
        contentsToggle.hidden = false;
        contentsToggle.addEventListener('click', function () {
            var collapsed = root.classList.toggle('rm-contents-collapsed');
            contentsToggle.setAttribute('aria-expanded', String(!collapsed));
            contentsToggle.textContent = collapsed ? 'Hiện mục lục' : 'Ẩn mục lục';
        });
    }
    root.querySelectorAll('.rm-document-lesson').forEach(function (lesson) {
        var first = lesson.querySelector('.rm-reading-pane .rm-prose').firstElementChild;
        var label = document.getElementById(lesson.getAttribute('aria-labelledby'));
        if (first && /^H[1-6]$/.test(first.tagName) && first.textContent.trim() === label.textContent.trim()) first.remove();
    });
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
            Array.from(heading.attributes).forEach(function (attribute) { replacement.setAttribute(attribute.name, attribute.value); });
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
    // Never restore a learner document belonging to a previous authentication state.
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            root.hidden = true;
            window.location.reload();
        }
    });
    var contents = root.querySelector('.rm-document-contents');
    if (!contents) return;
    var mobile = window.matchMedia('(max-width: 900px)');
    function sizeContents() { contents.open = !mobile.matches; }
    sizeContents();
    mobile.addEventListener('change', sizeContents);
    var lessons = Array.from(root.querySelectorAll('.rm-document-lesson'));
    lessons.forEach(function (lesson) {
        var list = root.querySelector('[data-toc-lesson="' + lesson.dataset.lessonId + '"] .rm-toc-subsections');
        lesson.querySelectorAll('.rm-reading-pane .rm-prose h3, .rm-reading-pane .rm-prose h4').forEach(function (heading, index) {
            heading.id = 'rm-lesson-' + lesson.dataset.lessonId + '-section-' + index;
            heading.tabIndex = -1;
            var item = document.createElement('li');
            var link = document.createElement('a');
            link.href = '#' + heading.id;
            link.textContent = heading.textContent;
            item.appendChild(link);
            list.appendChild(item);
        });
    });
    function readingLine() { return mobile.matches ? 150 : 110; }
    function navigate(target) {
        if (mobile.matches) contents.open = false;
        target.scrollIntoView({block: 'start'});
        target.focus({preventScroll: true});
    }
    root.querySelectorAll('.rm-document-sidebar a[href^="#"]').forEach(function (link) {
        link.addEventListener('click', function (event) {
            var target = document.getElementById(link.hash.slice(1));
            if (!target) return;
            event.preventDefault();
            window.history.pushState(null, '', link.hash);
            navigate(target);
            updateContents();
        });
    });
    var toc = Array.from(contents.querySelectorAll('a[href^="#"]')).map(function (link) {
        return {link: link, target: document.getElementById(link.hash.slice(1))};
    }).filter(function (entry) { return entry.target; });
    function updateContents() {
        var active = toc[0];
        toc.forEach(function (entry) {
            if (entry.target.getBoundingClientRect().top <= readingLine() + 8) active = entry;
        });
        // A short exercises section may never reach the top of the viewport.
        if (window.scrollY > 0 && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) active = toc[toc.length - 1];
        toc.forEach(function (entry) {
            if (entry === active) entry.link.setAttribute('aria-current', 'location');
            else entry.link.removeAttribute('aria-current');
        });
    }
    var states = lessons.map(function (lesson) {
        var reading = lesson.querySelector('.rm-reading-pane');
        var status = lesson.querySelector('.rm-resume-status');
        var resume = lesson.querySelector('.rm-resume-reading');
        var revision = Number(lesson.dataset.revision);
        var savedOffset = Number(lesson.dataset.resumeOffset || 0);
        var conversation = root.querySelector('[data-chat-lesson="' + lesson.dataset.lessonId + '"]');
        var form = conversation ? conversation.querySelector('.rm-tutor-form') : null;
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
        var dirty = false;
        var saving = false;
        var saveTimer;
        var latestOffset = savedOffset;
        var positionVersion = Math.max(Date.now(), Number(lesson.dataset.positionVersion || 0) + 1);
        function range() { return Math.max(0, reading.getBoundingClientRect().height - window.innerHeight + readingLine()); }
        function savePosition(keepalive) {
            if (!dirty || (saving && !keepalive) || !lesson.dataset.stateUrl) return;
            if (!keepalive) saving = true;
            dirty = false;
            var current = latestOffset;
            post(lesson.dataset.stateUrl, {offset: current, content_revision: revision, position_version: positionVersion}, keepalive).then(function () {
                status.textContent = 'Đã lưu vị trí đọc · không đánh dấu thành thạo.';
            }).catch(function (error) {
                dirty = true;
                status.textContent = error.error === 'revision_changed' ? 'Bài giảng đã thay đổi. Tải lại trang để lưu vị trí mới.' : 'Chưa lưu được vị trí. Tiếp tục đọc; cuộn lại để thử lưu.';
            }).finally(function () {
                if (!keepalive) saving = false;
                if (dirty && latestOffset !== current) savePosition(false);
            });
        }
        function resumeReading() {
            if (mobile.matches) contents.open = false;
            window.scrollTo({top: window.scrollY + reading.getBoundingClientRect().top - readingLine() + range() * savedOffset / 10000});
            lesson.focus({preventScroll: true});
            resume.hidden = true;
        }
        lesson.querySelector('.rm-reading-tools').hidden = false;
        if (lesson.dataset.stateUrl) {
            resume.hidden = savedOffset <= 0;
            resume.addEventListener('click', resumeReading);
        } else status.textContent = 'Đăng nhập để lưu vị trí đọc.';
        return {
            lesson: lesson,
            resume: resumeReading,
            save: savePosition,
            track: function () {
                if (!lesson.dataset.stateUrl) return;
                var distance = readingLine() - reading.getBoundingClientRect().top;
                latestOffset = range() > 0 ? Math.max(0, Math.min(10000, Math.round(distance / range() * 10000))) : 0;
                positionVersion = Math.max(Date.now(), positionVersion + 1);
                dirty = true;
                window.clearTimeout(saveTimer);
                saveTimer = window.setTimeout(function () { savePosition(false); }, 1200);
            }
        };
    });
    var resumeDocument = root.querySelector('[data-resume-lesson]');
    if (resumeDocument) {
        var savedLesson = states.find(function (state) { return state.lesson.dataset.lessonId === resumeDocument.dataset.resumeLesson; });
        if (savedLesson) {
            resumeDocument.parentElement.hidden = false;
            resumeDocument.addEventListener('click', savedLesson.resume);
        }
    }
    var scrollPending = false;
    window.addEventListener('scroll', function () {
        if (scrollPending) return;
        scrollPending = true;
        window.requestAnimationFrame(function () {
            scrollPending = false;
            updateContents();
            // Save only the chapter under the reading line, never skipped chapters.
            var current = states.find(function (state) {
                var rect = state.lesson.getBoundingClientRect();
                return rect.top <= readingLine() && rect.bottom > readingLine();
            });
            if (current) current.track();
        });
    }, {passive: true});
    document.addEventListener('visibilitychange', function () { if (document.hidden) states.forEach(function (state) { state.save(true); }); });
    window.addEventListener('pagehide', function () { states.forEach(function (state) { state.save(true); }); });
    window.addEventListener('resize', updateContents);
    setupChat();
    function setupChat() {
        var chat = root.querySelector('.rm-chat');
        if (!chat) return;
        var panel = chat.querySelector('.rm-chat-window');
        var toggle = chat.querySelector('.rm-chat-toggle');
        var close = chat.querySelector('.rm-chat-close');
        var select = chat.querySelector('#rm-chat-lesson');
        var follow = chat.querySelector('.rm-chat-follow');
        var pending = chat.querySelector('.rm-chat-pending');
        var unread = chat.querySelector('.rm-chat-unread');
        var narrow = window.matchMedia('(max-width: 600px)');
        var conversations = Array.from(chat.querySelectorAll('.rm-chat-conversation'));
        var forms = Array.from(chat.querySelectorAll('.rm-tutor-form'));
        var opened = false;
        var initialized = false;
        var sending = null;
        var inertElements = [];
        var oldOverflow = null;
        var backdrop = document.createElement('div');
        backdrop.className = 'rm-chat-backdrop';
        backdrop.hidden = true;
        backdrop.setAttribute('aria-hidden', 'true');
        chat.prepend(backdrop);
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'false');
        chat.hidden = false;

        function readingLesson() {
            var current = lessons[0];
            lessons.forEach(function (lesson) {
                if (lesson.getBoundingClientRect().top <= readingLine() + 8) current = lesson;
            });
            return current;
        }
        function selectedConversation() {
            return conversations.find(function (item) { return item.dataset.chatLesson === select.value; });
        }
        function updateFollow() {
            var current = readingLesson();
            follow.hidden = !current || current.dataset.lessonId === select.value;
            if (current) follow.title = document.getElementById(current.getAttribute('aria-labelledby')).textContent;
        }
        function changeLesson(id) {
            select.value = id;
            conversations.forEach(function (item) { item.hidden = item.dataset.chatLesson !== id; });
            var log = selectedConversation().querySelector('.rm-tutor-messages');
            log.scrollTop = log.scrollHeight;
            updateFollow();
            if (!sending) pending.hidden = true;
        }
        function clearModal() {
            inertElements.forEach(function (element) { element.removeAttribute('inert'); });
            inertElements = [];
            if (oldOverflow !== null) { document.body.style.overflow = oldOverflow; oldOverflow = null; }
        }
        function syncModal() {
            clearModal();
            var modal = opened && narrow.matches;
            panel.setAttribute('aria-modal', String(modal));
            backdrop.hidden = !modal;
            toggle.hidden = modal;
            if (!modal) return;
            var parent = chat.parentElement;
            while (parent && parent !== document.documentElement) {
                Array.from(parent.children).forEach(function (child) {
                    if (child !== chat && !child.contains(chat) && !child.hasAttribute('inert')) {
                        child.setAttribute('inert', '');
                        inertElements.push(child);
                    }
                });
                parent = parent.parentElement;
            }
            oldOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';
        }
        function viewportSize() {
            var viewport = window.visualViewport;
            chat.style.setProperty('--rm-chat-viewport', (viewport ? viewport.height : window.innerHeight) + 'px');
            chat.style.setProperty('--rm-chat-keyboard', Math.max(0, window.innerHeight - (viewport ? viewport.height + viewport.offsetTop : window.innerHeight)) + 'px');
        }
        function setOpen(value) {
            opened = value;
            panel.hidden = !value;
            chat.classList.toggle('is-open', value);
            toggle.setAttribute('aria-expanded', String(value));
            if (value) {
                if (!initialized) { changeLesson(readingLesson().dataset.lessonId); initialized = true; }
                unread.hidden = true;
                toggle.setAttribute('aria-label', 'Thu gọn chat Trợ lý bài học');
                updateFollow();
            } else toggle.setAttribute('aria-label', 'Mở chat Trợ lý bài học');
            syncModal();
            viewportSize();
            if (value) {
                var target = selectedConversation().querySelector('textarea, .rm-chat-login a');
                (target || close).focus({preventScroll: true});
            } else toggle.focus({preventScroll: true});
        }
        toggle.setAttribute('aria-label', 'Mở chat Trợ lý bài học');
        toggle.addEventListener('click', function () { setOpen(!opened); });
        close.addEventListener('click', function () { setOpen(false); });
        backdrop.addEventListener('click', function () { setOpen(false); });
        select.addEventListener('change', function () { changeLesson(select.value); });
        follow.addEventListener('click', function () { changeLesson(readingLesson().dataset.lessonId); });
        panel.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') return;
            if (event.key !== 'Tab' || !narrow.matches) return;
            var focusable = Array.from(panel.querySelectorAll('button:not(:disabled), select, textarea, a[href]')).filter(function (element) { return element.getClientRects().length > 0; });
            var first = focusable[0], last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        narrow.addEventListener('change', function () {
            syncModal();
            if (opened && !panel.contains(document.activeElement)) close.focus({preventScroll: true});
        });
        document.addEventListener('keydown', function (event) {
            if (opened && event.key === 'Escape') { event.preventDefault(); setOpen(false); }
        });
        window.addEventListener('scroll', updateFollow, {passive: true});
        window.addEventListener('resize', viewportSize);
        if (window.visualViewport) window.visualViewport.addEventListener('resize', viewportSize);
        viewportSize();

        var errors = {
            not_configured: 'Hỏi đáp AI chưa được cấu hình. Bạn vẫn có thể đọc bài giảng.',
            rate_limited: 'Bạn đã đạt giới hạn hỏi đáp. Hãy chờ rồi gửi lại câu hỏi.',
            busy: 'Một câu hỏi đang được xử lý. Hãy chờ trước khi gửi tiếp.',
            revision_changed: 'Bài giảng đã thay đổi. Sao chép câu hỏi rồi tải lại trang để dùng nội dung mới.',
            access_denied: 'Phiên đăng nhập hoặc quyền truy cập đã thay đổi. Sao chép câu hỏi rồi đăng nhập lại.',
            context_limit: 'Bài giảng quá dài để hỏi AI trong một lượt. Bạn vẫn có thể đọc toàn bộ tài liệu.',
            not_found: 'Bài giảng không còn khả dụng. Sao chép câu hỏi rồi quay lại chuyên đề.',
            contest_restricted: 'Hỏi đáp AI tạm dừng trong lượt thi. Bạn vẫn có thể đọc nội dung được phép truy cập.',
            review_rejected: 'AI chưa tạo được câu trả lời đạt yêu cầu. Hãy hỏi cụ thể hơn hoặc đối chiếu bài giảng.'
        };
        forms.forEach(function (form) {
            var conversation = form.closest('.rm-chat-conversation');
            var id = conversation.dataset.chatLesson;
            var lesson = lessons.find(function (item) { return item.dataset.lessonId === id; });
            var question = form.querySelector('textarea');
            var status = form.querySelector('.rm-tutor-status');
            var log = conversation.querySelector('.rm-tutor-messages');
            var title = document.getElementById(lesson.getAttribute('aria-labelledby')).textContent;
            function append(role, content) {
                var message = document.createElement('div');
                message.className = 'rm-tutor-message';
                message.dataset.role = role;
                var label = document.createElement('strong');
                label.textContent = role === 'user' ? 'Bạn' : 'Trợ lý';
                var text = document.createElement('p');
                text.textContent = content;
                message.append(label, text);
                conversation.querySelector('.rm-chat-empty').hidden = true;
                log.appendChild(message);
                log.scrollTop = log.scrollHeight;
            }
            form.querySelector('.rm-tutor-send').disabled = false;
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                var value = question.value.trim();
                if (sending || !value) return;
                sending = form;
                forms.forEach(function (item) { item.querySelector('.rm-tutor-send').disabled = true; });
                question.readOnly = true;
                form.setAttribute('aria-busy', 'true');
                status.textContent = 'Trợ lý đang soạn và kiểm tra câu trả lời…';
                pending.textContent = 'Đang trả lời về: ' + title;
                pending.hidden = false;
                fetch(form.dataset.url, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value},
                    body: JSON.stringify({question: value, content_revision: Number(lesson.dataset.revision)})
                }).then(function (response) {
                    return response.json().catch(function () { return {error: response.status === 403 ? 'access_denied' : 'unavailable'}; })
                        .then(function (data) { if (!response.ok) throw data; return data; });
                }).then(function (data) {
                    append('user', value);
                    append('assistant', data.answer);
                    question.value = '';
                    status.textContent = '';
                    if (!opened || conversation.hidden) {
                        unread.hidden = false;
                        pending.textContent = 'Đã có câu trả lời về: ' + title;
                        pending.hidden = false;
                    } else pending.hidden = true;
                }).catch(function (error) {
                    status.textContent = errors[error.error] || 'Chưa nhận được câu trả lời đã kiểm tra. Câu hỏi vẫn được giữ; bạn có thể gửi lại.';
                    pending.textContent = 'Chưa gửi được câu hỏi về: ' + title;
                }).finally(function () {
                    sending = null;
                    forms.forEach(function (item) { item.querySelector('.rm-tutor-send').disabled = false; });
                    question.readOnly = false;
                    form.removeAttribute('aria-busy');
                });
            });
        });
    }
    updateContents();
})();

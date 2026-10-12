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
})();

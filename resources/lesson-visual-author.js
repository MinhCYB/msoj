document.addEventListener('DOMContentLoaded', function () {
    'use strict';
    var root = document.querySelector('.mv-author');
    if (!root) return;
    var templates = JSON.parse(document.getElementById('mv-author-templates').textContent);
    var textarea = root.querySelector('#mv-author-document');
    var status = root.querySelector('#mv-author-status');
    var title = root.querySelector('#mv-author-title');
    var summary = root.querySelector('#mv-author-summary');
    function refresh() {
        try { var doc = JSON.parse(textarea.value); title.value = doc.title; summary.value = doc.summary; }
        catch (_) { /* Preserve incomplete JSON while editing. */ }
    }
    function load() {
        textarea.value = JSON.stringify(templates[root.querySelector('#mv-author-template').value], null, 2);
        refresh();
    }
    root.querySelector('#mv-author-load-template').addEventListener('click', load);
    root.querySelector('#mv-author-sync-form').addEventListener('click', function () {
        try {
            var doc = JSON.parse(textarea.value); doc.title = title.value; doc.summary = summary.value;
            textarea.value = JSON.stringify(doc, null, 2); status.textContent = 'Đã cập nhật mô tả trong JSON; bài chưa lưu.';
        } catch (error) { status.textContent = error.message; }
    });
    textarea.addEventListener('change', refresh);
    function arrange(doc) {
        var width = Math.max(1, Math.min(4, Number(root.querySelector('#mv-author-grid-columns').value) || 1));
        doc.layout.areas = [];
        for (var i = 0; i < doc.modules.length; i += width) {
            var row = doc.modules.slice(i, i + width).map(function (module) { return module.id; });
            while (row.length < width) row.push('_');
            doc.layout.areas.push(row);
        }
        doc.layout.readingOrder = doc.modules.map(function (module) { return module.id; });
    }
    root.querySelector('#mv-author-grid').addEventListener('click', function () {
        try { var doc = JSON.parse(textarea.value); arrange(doc); textarea.value = JSON.stringify(doc, null, 2); }
        catch (error) { status.textContent = error.message; }
    });
    root.querySelector('#mv-author-add-module').addEventListener('click', function () {
        try {
            var doc = JSON.parse(textarea.value), type = root.querySelector('#mv-author-module-type').value;
            if (doc.modules.length >= 16) throw Error('Tối đa 16 module.');
            var used = new Set(Object.keys(doc.data).concat(doc.modules.map(function (m) { return m.id; }), (doc.controls || []).map(function (c) { return c.id; }), (doc.bindings || []).map(function (b) { return b.id; })));
            var n = 1;
            while (used.has('module-' + n) || used.has('source-' + n)) n++;
            var module = {id: 'module-' + n, type: type, caption: type}, source = 'source-' + n, data;
            if (['vector', 'queue', 'stack', 'number-line'].includes(type)) data = {type: 'sequence', values: [1, 2, 3]};
            else if (['table', 'chart'].includes(type)) { data = {type: 'table', columns: [{id: 'name', type: 'string'}, {id: 'value', type: 'number'}], rows: [{id: 'row-one', name: 'A', value: 2}]}; if (type === 'chart') Object.assign(module, {kind: 'bar', x: 'name', y: 'value'}); }
            else if (['graph', 'tree'].includes(type)) data = {type: 'graph', nodes: [{id: 'vertex-a'}, {id: 'vertex-b'}], edges: [{id: 'edge-ab', from: 'vertex-a', to: 'vertex-b'}]};
            else if (type === 'matrix') data = {type: 'matrix', values: [[1, 2], [3, 4]]};
            else if (['map', 'set', 'hash-table'].includes(type)) data = {type: 'map', entries: [{id: 'entry-a', key: 'A', value: 1}]};
            else if (['variables', 'call-stack'].includes(type)) data = {type: 'variables', scopes: [{id: 'scope-main', name: 'main', frames: [{id: 'frame-main', procedure: 'main', parameters: {}, locals: {value: 1}}]}]};
            else if (type === 'scene') data = {type: 'scene', width: 300, height: 200, primitives: [{id: 'point-a', type: 'point', x: 50, y: 50, label: 'A'}]};
            else if (type === 'formula') module.tokens = [{type: 'text', value: 'a + b'}];
            else if (type === 'explanation') module.content = [{type: 'text', value: 'Mô tả bước tính.'}];
            else if (type === 'code') module.sources = [{language: 'cpp', sourceCode: 'int value = 1;', lineIds: ['line-value']}];
            else module.text = '';
            if (data) { doc.data[source] = data; module.source = source; }
            doc.modules.push(module); arrange(doc); textarea.value = JSON.stringify(doc, null, 2);
            status.textContent = 'Đã thêm module có dữ liệu mẫu hợp lệ. Sửa dữ liệu, binding và lưới trong JSON rồi xem trước.';
        } catch (error) { status.textContent = error.message; }
    });
    function editor() {
        var field = document.getElementById('id_body');
        if (!field) throw Error('Không tìm thấy trường nội dung bài giảng.');
        var wrapper = field.closest('.main-martor');
        var aceNode = wrapper && wrapper.querySelector('.ace_editor');
        var ace = aceNode && window.ace && window.ace.edit(aceNode);
        return {
            read: function () { return ace ? ace.getValue() : field.value; },
            insert: function (text) {
                if (ace) { ace.insert(text); field.value = ace.getValue(); ace.focus(); }
                else { field.setRangeText(text, field.selectionStart, field.selectionEnd, 'end'); field.focus(); }
                field.dispatchEvent(new Event('input', {bubbles: true}));
                field.dispatchEvent(new Event('change', {bubbles: true}));
            }
        };
    }
    root.querySelector('#mv-author-insert').addEventListener('click', function () {
        try {
            var doc = JSON.parse(textarea.value);
            if (!window.MSOJVisualValidate || !window.MSOJVisualValidate(doc)) throw Error('Tài liệu chưa hợp lệ theo schema v2.');
            editor().insert('\n\n```msoj-visual\n' + JSON.stringify(doc, null, 2) + '\n```\n\n');
            status.textContent = 'Đã chèn tài liệu; xem trước để kiểm tra ngữ nghĩa. Bài chưa được lưu.';
        } catch (error) { status.textContent = error.message; }
    });
    var preview = root.querySelector('#mv-author-preview');
    preview.addEventListener('click', function () {
        var data = new FormData();
        try { data.set('content', editor().read()); } catch (error) { status.textContent = error.message; return; }
        data.set('interactive_preview', '1');
        var csrf = document.querySelector('[name="csrfmiddlewaretoken"]');
        preview.disabled = true;
        status.textContent = 'Đang mở bản xem trước nội dung chưa lưu…';
        fetch(root.dataset.previewUrl, {method: 'POST', credentials: 'same-origin', headers: csrf ? {'X-CSRFToken': csrf.value} : {}, body: data})
            .then(function (response) { if (!response.ok) throw Error('Không mở được bản xem trước. Kiểm tra phiên đăng nhập và quyền biên soạn.'); return response.text(); })
            .then(function (html) { var frame = root.querySelector('iframe'); frame.srcdoc = html; frame.hidden = false; status.textContent = 'Bản xem trước dùng cùng compiler với trang học viên.'; })
            .catch(function (error) { status.textContent = error.message; })
            .finally(function () { preview.disabled = false; });
    });
    load();
});

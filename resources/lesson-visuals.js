/* MSOJ visual document runtime. Document content is data, never executable code. */
(function () {
    'use strict';
    if (window.MSOJVisuals) return;

    var instances = new WeakMap();
    var serial = 0;
    var moduleTypes = new Set([
        'vector', 'queue', 'stack', 'call-stack', 'map', 'set', 'hash-table',
        'matrix', 'variables', 'table', 'chart', 'graph', 'tree', 'scene',
        'number-line', 'formula', 'explanation', 'code', 'output'
    ]);

    function el(tag, className, text) {
        var element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined && text !== null) element.textContent = String(text);
        return element;
    }

    function button(label, handler) {
        var element = el('button', '', label);
        element.type = 'button';
        element.addEventListener('click', handler);
        return element;
    }

    function clone(value) { return JSON.parse(JSON.stringify(value)); }
    function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
    function format(value) {
        return value === null ? 'null' : typeof value === 'object' ? JSON.stringify(value) : String(value);
    }
    function frameData(document, frames, index) { return frames[index].data || document.data; }

    function createTable(columns, rows, caption, select, selectedIds) {
        var table = el('table');
        table.append(el('caption', '', caption));
        var head = el('thead'), headingRow = el('tr');
        columns.forEach(function (column) {
            var heading = el('th', '', column.label || column.id);
            heading.scope = 'col';
            headingRow.append(heading);
        });
        head.append(headingRow);
        table.append(head);
        var body = el('tbody');
        rows.forEach(function (record) {
            var row = el('tr');
            if (select) {
                row.tabIndex = 0;
                row.setAttribute('role', 'button');
                var active = (selectedIds || []).includes(record.id);
                row.setAttribute('aria-selected', String(active));
                if (active) row.classList.add('mv-selected');
                row.addEventListener('click', function () { select(record.id); });
                row.addEventListener('keydown', function (event) {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        select(record.id);
                    }
                });
            }
            columns.forEach(function (column) { row.append(el('td', '', format(record[column.id]))); });
            body.append(row);
        });
        table.append(body);
        var scroll = el('div', 'mv-scroll');
        scroll.tabIndex = 0;
        scroll.setAttribute('role', 'region');
        scroll.setAttribute('aria-label', caption);
        scroll.append(table);
        return scroll;
    }

    function tokenText(tokens, data, controls, derived) {
        return (tokens || []).map(function (token) {
            if (token.type === 'text') return token.value;
            var value = Object.prototype.hasOwnProperty.call(data, token.source) ? data[token.source] :
                Object.prototype.hasOwnProperty.call(controls, token.source) ? controls[token.source] : derived[token.source];
            if (value && value.type === 'sequence') return value.values.map(format).join(', ');
            if (value && value.type === 'map') {
                var entry = value.entries.find(function (item) { return item.id === token.key; });
                return entry ? format(entry.value) : '—';
            }
            if (value && value.type === 'table') return value.rows.map(function (row) { return format(row[token.key]); }).join(', ');
            if (value && value.type === 'matrix') return value.values.map(function (row) { return row.map(format).join(', '); }).join('; ');
            return value === undefined ? '—' : format(value);
        }).join('');
    }

    function renderModule(module, source, frame, state, dispatch, data, highlights) {
        var type = module.type;
        var section = el('section', 'mv-module mv-type-' + type);
        var heading = el('h3', '', module.caption || type);
        heading.id = 'mv-h-' + (++serial);
        section.setAttribute('aria-labelledby', heading.id);
        section.append(heading);

        if (type === 'chart') {
            section.append(el('div', 'mv-chart-fallback', 'Biểu đồ đang tải…'));
            var selection = highlights.selection && highlights.selection.dataId === module.source ? [highlights.selection.itemId] : [];
            if (state.selection && state.selection.dataId === module.source) selection.push(state.selection.id);
            section.append(createTable(source.columns, source.rows, module.caption || 'Dữ liệu biểu đồ', function (id) {
                dispatch({type: 'select', value: {dataId: module.source, id: id}});
            }, selection));
            return section;
        }

        if (type === 'graph' || type === 'tree') {
            var canvas = el('div', 'mv-graph-canvas', 'Đồ thị đang tải…');
            var nodeList = el('ul', 'mv-data-list');
            source.nodes.forEach(function (item) {
                var listItem = el('li', '', item.label || item.id);
                if ((highlights.nodes || []).includes(item.id)) listItem.classList.add('mv-selected');
                nodeList.append(listItem);
            });
            section.append(canvas, nodeList);
            return section;
        }

        if (type === 'scene') {
            var namespace = 'http://www.w3.org/2000/svg';
            var svg = document.createElementNS(namespace, 'svg');
            var markerId = 'mv-arrow-' + (++serial);
            var defs = document.createElementNS(namespace, 'defs');
            var marker = document.createElementNS(namespace, 'marker');
            marker.id = markerId;
            marker.setAttribute('viewBox', '0 0 10 10');
            marker.setAttribute('refX', '9'); marker.setAttribute('refY', '5');
            marker.setAttribute('markerWidth', '6'); marker.setAttribute('markerHeight', '6');
            marker.setAttribute('orient', 'auto-start-reverse');
            var arrowHead = document.createElementNS(namespace, 'path');
            arrowHead.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
            marker.append(arrowHead);
            defs.append(marker);
            svg.append(defs);
            svg.setAttribute('viewBox', '0 0 ' + source.width + ' ' + source.height);
            svg.setAttribute('role', 'img');
            svg.setAttribute('aria-label', module.caption || 'Sơ đồ');
            svg.setAttribute('role', 'img');
            svg.setAttribute('aria-label', module.caption || 'Sơ đồ');
            var movedPoints = {};
            Object.keys(state.derived).forEach(function (id) {
                var value = state.derived[id];
                if (value && value.type === 'scene-point') movedPoints[value.id] = value;
            });
            function pointPosition(id) {
                var primitive = source.primitives.find(function (item) { return item.id === id; });
                var moved = movedPoints[id];
                return primitive ? {x: moved ? moved.x : primitive.x, y: moved ? moved.y : primitive.y,
                    originX: primitive.x, originY: primitive.y} : null;
            }
            source.primitives.forEach(function (primitive) {
                var position = pointPosition(primitive.id);
                var x = position ? position.x : primitive.x;
                var y = position ? position.y : primitive.y;
                var element;
                if (primitive.type === 'point' || primitive.type === 'circle') {
                    element = document.createElementNS(namespace, 'circle');
                    element.setAttribute('cx', x); element.setAttribute('cy', y);
                    element.setAttribute('r', primitive.radius || 5);
                } else if (primitive.type === 'rect') {
                    element = document.createElementNS(namespace, 'rect');
                    element.setAttribute('x', primitive.x); element.setAttribute('y', primitive.y);
                    element.setAttribute('width', primitive.width); element.setAttribute('height', primitive.height);
                } else if (primitive.type === 'segment' || primitive.type === 'arrow') {
                    var start = source.primitives.find(function (item) { return item.type === 'point' && item.x === primitive.x1 && item.y === primitive.y1; });
                    var end = source.primitives.find(function (item) { return item.type === 'point' && item.x === primitive.x2 && item.y === primitive.y2; });
                    var startPosition = start && pointPosition(start.id), endPosition = end && pointPosition(end.id);
                    element = document.createElementNS(namespace, 'line');
                    element.setAttribute('x1', primitive.x1 + (startPosition ? startPosition.x - startPosition.originX : 0));
                    element.setAttribute('y1', primitive.y1 + (startPosition ? startPosition.y - startPosition.originY : 0));
                    element.setAttribute('x2', primitive.x2 + (endPosition ? endPosition.x - endPosition.originX : 0));
                    element.setAttribute('y2', primitive.y2 + (endPosition ? endPosition.y - endPosition.originY : 0));
                    if (primitive.type === 'arrow') element.setAttribute('marker-end', 'url(#' + markerId + ')');
                } else {
                    element = document.createElementNS(namespace, 'text');
                    element.setAttribute('x', primitive.x); element.setAttribute('y', primitive.y);
                    element.textContent = primitive.text;
                }
                element.dataset.itemId = primitive.id;
                if ((highlights.items || {})[module.source] && (highlights.items[module.source] || []).includes(primitive.id) ||
                    (highlights.targets || []).includes(module.source) && (highlights.targets || []).includes(primitive.id)) element.classList.add('mv-selected');
                if (primitive.label) {
                    var title = document.createElementNS(namespace, 'title');
                    title.textContent = primitive.label;
                    element.append(title);
                }
                if (primitive.type === 'point' && primitive.xControl && primitive.yControl) {
                    element.setAttribute('tabindex', '0');
                    element.setAttribute('role', 'slider');
                    element.setAttribute('aria-label', primitive.label || primitive.id);
                    element.setAttribute('aria-valuetext', 'x ' + x + ', y ' + y);
                    function setPoint(nextX, nextY) {
                        var values = {};
                        values[primitive.xControl] = Math.round(nextX);
                        values[primitive.yControl] = Math.round(nextY);
                        dispatch({type: 'set-controls', values: values});
                    }
                    element.addEventListener('keydown', function (event) {
                        var dx = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
                        var dy = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0;
                        if (dx || dy) {
                            event.preventDefault();
                            setPoint(state.controls[primitive.xControl] + dx, state.controls[primitive.yControl] + dy);
                        }
                    });
                    element.addEventListener('pointerdown', function (event) {
                        event.preventDefault();
                        var bounds = svg.getBoundingClientRect();
                        function move(pointer) {
                            setPoint((pointer.clientX - bounds.left) * source.width / bounds.width,
                                (pointer.clientY - bounds.top) * source.height / bounds.height);
                        }
                        function stop(pointer) {
                            window.removeEventListener('pointermove', move);
                            window.removeEventListener('pointerup', stop);
                            window.removeEventListener('pointercancel', stop);
                            if (pointer.type === 'pointerup') move(pointer);
                        }
                        window.addEventListener('pointermove', move, {signal: state.lifecycleSignal});
                        window.addEventListener('pointerup', stop, {once: true, signal: state.lifecycleSignal});
                        window.addEventListener('pointercancel', stop, {once: true, signal: state.lifecycleSignal});
                    });
                } else if (primitive.type === 'point' || primitive.type === 'circle') {
                    element.setAttribute('tabindex', '0'); element.setAttribute('role', 'button');
                    element.addEventListener('click', function () { dispatch({type: 'select', value: primitive.id}); });
                }
                svg.append(element);
            });
            section.append(svg);
            return section;
        }

        if (type === 'variables' || type === 'call-stack') {
            (source.scopes || []).forEach(function (scope) {
                var scopeSection = el('section', 'mv-scope');
                scopeSection.append(el('h4', '', scope.name));
                scope.frames.forEach(function (callFrame) {
                    var details = el('details', 'mv-frame');
                    details.open = true;
                    details.append(el('summary', '', callFrame.procedure + ' · ' + callFrame.id));
                    [['Tham số', callFrame.parameters], ['Biến cục bộ', callFrame.locals]].forEach(function (group) {
                        details.append(el('h5', '', group[0]));
                        var list = el('dl', 'mv-variable-list');
                        Object.keys(group[1] || {}).forEach(function (key) {
                            list.append(el('dt', '', key), el('dd', '', format(group[1][key])));
                        });
                        details.append(list);
                    });
                    scopeSection.append(details);
                });
                section.append(scopeSection);
            });
            if (!source.scopes.length) section.append(el('p', 'mv-empty', 'Không có phạm vi đang hoạt động.'));
            return section;
        }

        if (type === 'vector' || type === 'queue' || type === 'stack') {
            var strip = el('div', 'mv-items');
            var ids = source.itemIds || source.values.map(function (_, index) { return String(index); });
            var selectedItems = (highlights.items || {})[module.source] || [];
            if ((highlights.targets || []).length > 1 && highlights.targets[0] === module.source) selectedItems = selectedItems.concat(highlights.targets.slice(1));
            if (type === 'queue') section.append(el('p', 'mv-help', 'Đầu hàng là phần tử đầu; cuối hàng là phần tử cuối.'));
            if (type === 'stack') section.append(el('p', 'mv-help', 'Đỉnh ngăn xếp là phần tử cuối.'));
            source.values.forEach(function (value, index) {
                var id = ids[index];
                var item = button((type === 'queue' && index === 0 ? 'Đầu · ' : type === 'stack' && index === source.values.length - 1 ? 'Đỉnh · ' : 'Chỉ số ' + index + ' · ') + format(value), function () { dispatch({type: 'select', value: {dataId: module.source, id: id}}); });
                item.className = 'mv-item';
                if ((state.selection && state.selection.id === id && state.selection.dataId === module.source) || selectedItems.includes(id)) item.classList.add('mv-selected');
                item.dataset.itemId = id;
                strip.append(item);
            });
            if (!source.values.length) strip.append(el('p', 'mv-empty', 'Không có phần tử.'));
            section.append(strip);
            return section;
        }
        if (type === 'table') {
            var selectedRows = highlights.selection && highlights.selection.dataId === module.source ? [highlights.selection.itemId] : [];
            if (state.selection && state.selection.dataId === module.source) selectedRows.push(state.selection.id);
            section.append(createTable(source.columns, source.rows, module.caption || 'Dữ liệu', function (id) { dispatch({type: 'select', value: {dataId: module.source, id: id}}); }, selectedRows));
            return section;
        }
        if (type === 'matrix') {
            var columns = (source.values[0] || []).map(function (_, index) { return {id: String(index), label: source.columnLabels && source.columnLabels[index] || 'Cột ' + index}; });
            var cells = highlights.cells && highlights.cells[module.source] || [];
            var targets = highlights.targets || [];
            if (targets[0] === module.source && targets.length > 2) cells = cells.concat([[Number(targets[1]), Number(targets[2])]]);
            var rows = source.values.map(function (values, rowIndex) {
                var record = {id: String(rowIndex)};
                values.forEach(function (value, columnIndex) { record[String(columnIndex)] = value; });
                return record;
            });
            section.append(createTable(columns, rows, module.caption || 'Ma trận', function (id) { dispatch({type: 'select', value: {dataId: module.source, id: id}}); }));
            section.querySelectorAll('tbody tr').forEach(function (row, rowIndex) {
                row.querySelectorAll('td').forEach(function (cell, columnIndex) {
                    if (cells.some(function (coordinate) { return Array.isArray(coordinate) ? coordinate[0] === rowIndex && coordinate[1] === columnIndex : coordinate.row === rowIndex && coordinate.column === columnIndex; })) cell.classList.add('mv-selected');
                });
            });
            return section;
        }
        if (type === 'map' || type === 'set' || type === 'hash-table') {
            var entries = source.entries || [];
            var selectedEntries = (highlights.items || {})[module.source] || [];
            if ((highlights.targets || []).length > 1 && highlights.targets[0] === module.source) selectedEntries = selectedEntries.concat(highlights.targets.slice(1));
            if (type === 'hash-table') {
                var buckets = Array.from({length: 8}, function () { return []; });
                entries.forEach(function (entry) { var key = String(entry.key); var bucketIndex = key.split('').reduce(function (hash, character) { return hash + character.charCodeAt(0); }, 0) % 8; buckets[bucketIndex].push(entry); });
                buckets.forEach(function (bucket, bucketIndex) {
                    var bucketSection = el('section', 'mv-hash-bucket');
                    bucketSection.append(el('h4', '', 'Bucket ' + bucketIndex));
                    bucket.forEach(function (entry) {
                        var entryElement = el('p', 'mv-entry', format(entry.key) + ' → ' + format(entry.value));
                        if (selectedEntries.includes(entry.id)) entryElement.classList.add('mv-selected');
                        bucketSection.append(entryElement);
                    });
                    section.append(bucketSection);
                });
                return section;
            }
            entries.forEach(function (entry) {
                var entryElement = el('p', 'mv-entry', format(entry.key) + (type === 'set' ? '' : ' → ' + format(entry.value)));
                if (selectedEntries.includes(entry.id)) entryElement.classList.add('mv-selected');
                section.append(entryElement);
            });
            if (!entries.length) section.append(el('p', 'mv-empty', 'Không có phần tử.'));
            return section;
        }

        if (type === 'number-line') {
            var values = source.type === 'sequence' ? source.values : source.values.flat();
            var numericValues = values.filter(function (value) { return typeof value === 'number' && Number.isFinite(value); });
            var minimum = Number.isFinite(module.minimum) ? module.minimum : numericValues.length ? Math.min.apply(null, numericValues) : 0;
            var maximum = Number.isFinite(module.maximum) ? module.maximum : numericValues.length ? Math.max.apply(null, numericValues) : 1;
            if (minimum === maximum) { minimum -= 0.5; maximum += 0.5; }
            var numberLine = el('div', 'mv-number-line');
            numberLine.setAttribute('role', 'img');
            numberLine.setAttribute('aria-label', 'Number line from ' + minimum + ' to ' + maximum);
            numericValues.forEach(function (value) {
                if (value < minimum || value > maximum) return;
                var point = el('span', 'mv-number-point', format(value));
                point.style.left = ((value - minimum) / (maximum - minimum) * 100) + '%';
                numberLine.append(point);
            });
            section.append(numberLine, el('p', 'mv-help', 'Khoảng từ ' + minimum + ' đến ' + maximum + '; giá trị: ' + values.map(format).join(', ')));
            return section;
        }

        if (type === 'formula' || type === 'explanation') {
            var text = tokenText(type === 'formula' ? module.tokens : module.content, data, state.controls, state.derived) || frame.text || '';
            section.append(el('p', type === 'formula' ? 'mv-formula' : 'mv-explanation', type === 'formula' ? '\\(' + text + '\\)' : text));
            return section;
        }

        if (type === 'code') {
            var sources = module.sources || [];
            var tabs = el('div', 'mv-code-tabs');
            var activeLanguage = state.languages && state.languages[module.id] || sources[0].language;
            state.languages = state.languages || {};
            sources.forEach(function (sourceItem) {
                var languageButton = button(sourceItem.language === 'cpp' ? 'C++' : 'Python', function () {
                    state.languages[module.id] = sourceItem.language;
                    dispatch({type: 'refresh'});
                });
                languageButton.setAttribute('aria-pressed', String(sourceItem.language === activeLanguage));
                tabs.append(languageButton);
            });
            var selectedSource = sources.find(function (sourceItem) { return sourceItem.language === activeLanguage; }) || sources[0];
            var pre = el('pre', 'mv-code-text'), code = el('code');
            selectedSource.sourceCode.split('\n').forEach(function (line, lineIndex) {
                var lineElement = el('span', 'mv-code-line', line);
                lineElement.dataset.lineId = selectedSource.lineIds[lineIndex];
                if ((frame.lines || []).includes(selectedSource.lineIds[lineIndex])) lineElement.classList.add('mv-code-highlight');
                code.append(lineElement, document.createTextNode('\n'));
            });
            pre.append(code);
            section.append(tabs, pre);
            return section;
        }

        if (type === 'output') {
            section.append(el('pre', 'mv-output', module.text || frame.output || ''));
            return section;
        }
        section.append(el('p', 'mv-empty', 'Không có dữ liệu.'));
        return section;
    }

    var libraries = {};
    function loadLibrary(name) {
        if (libraries[name]) return libraries[name];
        var globalName = name === 'echarts' ? 'echarts' : 'cytoscape';
        if (window[globalName]) return Promise.resolve(window[globalName]);
        var script = document.createElement('script');
        script.src = (window.MSOJ_VISUAL_VENDOR_BASE || '/static/vendor/visual-v2/') + name + '.js';
        script.async = true;
        var promise = new Promise(function (resolve, reject) {
            script.onload = function () { window[globalName] ? resolve(window[globalName]) : reject(Error('Library unavailable')); };
            script.onerror = function () { reject(Error('Library unavailable')); };
            document.head.append(script);
        });
        libraries[name] = promise;
        promise.catch(function () {
            script.remove();
            if (libraries[name] === promise) delete libraries[name];
        });
        return promise;
    }

    function mountDocument(root, payload, options) {
        options = options || {};
        if (!root || !payload || !payload.document || !Array.isArray(payload.frames) || !payload.frames.length) {
            throw new TypeError('Expected compiled {document, frames} payload');
        }
        if (instances.has(root)) instances.get(root).destroy();

        var documentData = clone(payload.document);
        var frames = clone(payload.frames);
        var index = 0, timer = null, destroyed = false, requestId = 0, aborter = null;
        var charts = {}, graphs = {}, listeners = new Set();
        var state = {selection: null, controls: {}, derived: {}, languages: {}};
        var lifecycle = new AbortController();
        state.lifecycleSignal = lifecycle.signal;
        var controller, resizeObserver;

        try {
            if (documentData.version !== 2 || !Array.isArray(documentData.modules) || !documentData.layout) {
                throw Error('Tài liệu trực quan không đúng định dạng v2');
            }
            if (typeof window.MSOJVisualValidate === 'function' && !window.MSOJVisualValidate(documentData)) {
                throw Error('Tài liệu trực quan không hợp lệ theo schema');
            }
            var authoredAreas = clone(documentData.layout.areas);
            var modules = el('div', 'mv-module-grid');
            var slots = [], panels = {}, moduleRoot = {}, arranging = false, draggedId = null;
            var controls = documentData.controls || [];
            var captions = {graph: 'Đồ thị', tree: 'Cây', queue: 'Hàng đợi', stack: 'Ngăn xếp',
                explanation: 'Giải thích', output: 'Đầu ra', code: 'Mã nguồn'};
            function caption(module) { return module.caption || captions[module.type] || module.type; }
            function focusedAreas() {
                if (!documentData.timeline || !documentData.timeline.generator) return clone(authoredAreas);
                var primaryIds = {'for-loop': 'iterations-view', bfs: 'graph-view', dfs: 'graph-view',
                    'matrix-chain': 'cost-view', 'dp-bitmask-matching': 'compatibility-view'};
                var primary = documentData.modules.find(function (module) {
                    return module.id === primaryIds[documentData.timeline.generator];
                }) || documentData.modules.find(function (module) { return module.type !== 'code' && module.type !== 'explanation'; });
                var code = documentData.modules.find(function (module) { return module.type === 'code'; });
                if (!primary || !code) return clone(authoredAreas);
                var rows = [[primary.id, primary.id, code.id, code.id]];
                var supporting = documentData.modules.filter(function (module) {
                    return module !== primary && module !== code && module.type !== 'explanation';
                });
                for (var i = 0; i < supporting.length; i += 2) {
                    var left = supporting[i].id, right = supporting[i + 1] ? supporting[i + 1].id : left;
                    rows.push([left, left, right, right]);
                }
                documentData.modules.filter(function (module) { return module.type === 'explanation'; }).forEach(function (module) {
                    rows.push([module.id, module.id, module.id, module.id]);
                });
                return rows;
            }
            function resizeVisuals() {
                Object.keys(charts).forEach(function (id) { charts[id].instance.resize(); });
                Object.keys(graphs).forEach(function (id) { graphs[id].instance.resize(); graphs[id].instance.fit(undefined, 24); });
            }
            function refreshDestinations() {
                Object.keys(panels).forEach(function (id) {
                    var select = panels[id].querySelector('.mv-move-select');
                    select.replaceChildren();
                    slots.forEach(function (slot, i) {
                        var occupant = slot.element.querySelector('.mv-panel');
                        var label = 'Ô ' + (i + 1) + (occupant ? ' — ' + caption(documentData.modules.find(function (m) { return m.id === occupant.dataset.moduleId; })) : ' — Trống');
                        var option = el('option', '', label);
                        option.value = String(i); option.selected = occupant === panels[id];
                        select.append(option);
                    });
                });
            }
            function moveModule(id, destination) {
                var panel = panels[id], target = slots[destination];
                if (!panel || !target || panel.parentElement === target.element) return;
                var origin = panel.parentElement, other = target.element.querySelector('.mv-panel');
                if (other) origin.append(other);
                target.element.append(panel);
                refreshDestinations(); resizeVisuals();
                layoutStatus.textContent = caption(documentData.modules.find(function (m) { return m.id === id; })) + ' đã chuyển đến ô ' + (Number(destination) + 1) + (other ? '; hai module đã đổi chỗ.' : '.');
                panel.querySelector('.mv-move-select').focus();
            }
            function setLayout(areas) {
                var regions = {}, ordered = [];
                areas.forEach(function (row, y) { row.forEach(function (id, x) {
                    var key = id === '_' ? 'empty-' + y + '-' + x : id;
                    if (!regions[key]) { regions[key] = {id: id, x1: x, x2: x, y1: y, y2: y}; ordered.push(regions[key]); }
                    regions[key].x2 = Math.max(regions[key].x2, x); regions[key].y2 = Math.max(regions[key].y2, y);
                }); });
                // Reuse live panels/canvases; rearranging must not reset timeline or selection.
                slots = ordered.map(function (region, i) {
                    var slot = el('div', 'mv-grid-slot');
                    slot.dataset.slot = String(i);
                    slot.style.gridColumn = (region.x1 + 1) + ' / ' + (region.x2 + 2);
                    slot.style.gridRow = (region.y1 + 1) + ' / ' + (region.y2 + 2);
                    slot.append(el('span', 'mv-slot-label', 'Ô ' + (i + 1)));
                    slot.addEventListener('dragover', function (event) {
                        if (!arranging || !draggedId) return;
                        event.preventDefault(); event.dataTransfer.dropEffect = 'move'; slot.classList.add('mv-drop-target');
                    });
                    slot.addEventListener('dragleave', function (event) { if (!slot.contains(event.relatedTarget)) slot.classList.remove('mv-drop-target'); });
                    slot.addEventListener('drop', function (event) {
                        event.preventDefault(); slot.classList.remove('mv-drop-target');
                        if (arranging && draggedId) moveModule(draggedId, i);
                    });
                    if (panels[region.id]) slot.append(panels[region.id]);
                    return {element: slot};
                });
                modules.style.gridTemplateColumns = 'repeat(' + areas[0].length + ', minmax(0, 1fr))';
                modules.replaceChildren.apply(modules, slots.map(function (slot) { return slot.element; }));
                refreshDestinations(); resizeVisuals();
            }
            controls.forEach(function (control) { state.controls[control.id] = control.value; });
            function applyFrameControls(frame) {
                if (!frame.controls || typeof frame.controls !== 'object') return;
                Object.keys(frame.controls).forEach(function (id) { state.controls[id] = frame.controls[id]; });
                if (Object.prototype.hasOwnProperty.call(frame, 'selection')) state.selection = clone(frame.selection);
            }
            applyFrameControls(frames[0]);

            var shell = el('div', 'mv-document');
            shell.append(el('h2', 'mv-document-title', documentData.title), el('p', 'mv-document-summary', documentData.summary));
            var workspaceBar = el('div', 'mv-workspace-bar');
            var layoutStatus = el('p', 'mv-layout-status');
            layoutStatus.setAttribute('role', 'status');
            var arrangeButton = button('Sắp xếp', function () {
                arranging = !arranging;
                shell.classList.toggle('mv-arranging', arranging);
                arrangeButton.setAttribute('aria-pressed', String(arranging));
                arrangeButton.textContent = arranging ? 'Xong' : 'Sắp xếp';
                layoutHelp.hidden = !arranging;
                layoutStatus.textContent = '';
                resizeVisuals();
            });
            arrangeButton.setAttribute('aria-pressed', 'false');
            var layoutHelp = el('p', 'mv-help', 'Kéo tiêu đề sang ô khác hoặc chọn ô trong danh sách. Ô đã có module sẽ đổi chỗ. Bước chạy được giữ nguyên.');
            layoutHelp.hidden = true;
            workspaceBar.append(el('strong', '', 'Không gian mô phỏng'), arrangeButton,
                button('Bố cục mặc định', function () { setLayout(focusedAreas()); layoutStatus.textContent = 'Đã khôi phục bố cục mặc định; giữ nguyên bước chạy.'; }),
                button('Bố cục bài soạn', function () { setLayout(authoredAreas); layoutStatus.textContent = 'Đang dùng bố cục của bài soạn; giữ nguyên bước chạy.'; }));
            shell.append(workspaceBar, layoutHelp, layoutStatus);
            documentData.modules.forEach(function (module) {
                var panel = el('div', 'mv-panel');
                panel.dataset.moduleId = module.id;
                var header = el('div', 'mv-panel-header');
                var heading = el('h3', '', caption(module));
                heading.id = 'mv-panel-' + (++serial);
                var handle = button('Kéo', function () { panel.querySelector('.mv-move-select').focus(); });
                handle.className = 'mv-drag-handle'; handle.draggable = true;
                handle.setAttribute('aria-label', 'Chuyển ' + caption(module));
                handle.addEventListener('dragstart', function (event) {
                    if (!arranging) { event.preventDefault(); return; }
                    draggedId = module.id; event.dataTransfer.setData('text/plain', module.id); event.dataTransfer.effectAllowed = 'move';
                });
                handle.addEventListener('dragend', function () {
                    draggedId = null;
                    modules.querySelectorAll('.mv-drop-target').forEach(function (slot) { slot.classList.remove('mv-drop-target'); });
                });
                var select = el('select', 'mv-move-select');
                select.setAttribute('aria-label', 'Chuyển ' + caption(module) + ' đến ô');
                select.addEventListener('change', function () { moveModule(module.id, Number(select.value)); });
                header.append(heading, handle, select); panel.append(header); panels[module.id] = panel;
            });
            setLayout(focusedAreas());
            var fieldset = el('fieldset', 'mv-controls');
            fieldset.append(el('legend', '', 'Khám phá hình ảnh'));
            controls.forEach(function (control) {
                if (options.allowInputEdit === false && control.inputKey) return;
                var id = 'mv-' + (++serial) + '-' + control.id;
                var label = el('label', 'mv-control-label', control.label), input;
                if (control.type === 'select') {
                    input = el('select');
                    control.options.forEach(function (option) {
                        var optionElement = el('option', '', option.label);
                        optionElement.value = JSON.stringify(option.value);
                        optionElement.selected = same(option.value, control.value);
                        input.append(optionElement);
                    });
                } else {
                    input = el('input');
                    input.type = control.type === 'boolean' ? 'checkbox' : 'number';
                    if (control.type === 'number') {
                        input.min = control.min; input.max = control.max; input.step = control.step; input.value = control.value;
                    } else input.checked = control.value;
                }
                input.id = id;
                input.dataset.controlId = control.id;
                label.htmlFor = id;
                input.addEventListener('change', function () {
                    var value = control.type === 'boolean' ? input.checked : control.type === 'number' ? Number(input.value) : JSON.parse(input.value);
                    state.controls[control.id] = value;
                    if (documentData.timeline && documentData.timeline.generator && control.inputKey && options.allowInputEdit !== false) regenerate(control, value);
                    else { recompute(); draw(); }
                });
                fieldset.append(label, input);
            });
            var timelineInput = documentData.timeline && documentData.timeline.generator ? clone(documentData.timeline.input) : null;
            var inputEditor;
            if (timelineInput && options.allowInputEdit !== false) {
                var editor = el('fieldset', 'mv-controls');
                editor.append(el('legend', '', 'Thay đổi đầu vào thuật toán'));
                inputEditor = el('textarea', 'mv-input-editor', JSON.stringify(timelineInput, null, 2));
                inputEditor.setAttribute('aria-label', 'Đầu vào thuật toán ở dạng JSON');
                inputEditor.rows = 8;
                var inputError = el('p', 'mv-error', '');
                inputError.hidden = true;
                editor.append(inputEditor, button('Áp dụng và chạy lại', function () {
                    try {
                        var nextInput = JSON.parse(inputEditor.value);
                        if (!nextInput || Array.isArray(nextInput) || typeof nextInput !== 'object') throw Error('Đầu vào phải là một đối tượng JSON.');
                        regenerate(null, nextInput, inputError);
                    } catch (error) {
                        inputError.textContent = error.message;
                        inputError.hidden = false;
                    }
                }), inputError);
                var inputDetails = el('details', 'mv-input-details');
                inputDetails.append(el('summary', '', 'Đầu vào thuật toán'), editor);
                shell.append(inputDetails);
            }
            if (fieldset.children.length > 1) shell.append(fieldset);
            var playback = el('div', 'mv-playback');
            var frameInfo = el('div', 'mv-frame-info');
            frameInfo.setAttribute('aria-live', 'polite'); frameInfo.setAttribute('aria-atomic', 'true');
            playback.append(frameInfo); shell.append(playback, modules);
            var navigation = null, range = null, playButton = null;

            function dispatch(action) {
                if (action.type === 'select') {
                    state.selection = action.value == null ? null : typeof action.value === 'object' ? action.value : {id: String(action.value)};
                } else if (action.type === 'set-controls') {
                    Object.keys(action.values).forEach(function (id) {
                        var control = controls.find(function (item) { return item.id === id; });
                        if (control) state.controls[id] = Math.max(control.min, Math.min(control.max, Number(action.values[id])));
                    });
                    root.querySelectorAll('[data-control-id]').forEach(function (input) {
                        var id = input.dataset.controlId;
                        if (!Object.prototype.hasOwnProperty.call(action.values, id)) return;
                        var control = controls.find(function (item) { return item.id === id; });
                        if (control.type === 'boolean') input.checked = state.controls[id]; else input.value = state.controls[id];
                    });
                } else if (action.type === 'set-control') {
                    var target = controls.find(function (item) { return item.id === action.id; });
                    if (target) state.controls[action.id] = Math.max(target.min, Math.min(target.max, Number(action.value)));
                }
                recompute(); draw();
            }

            function recompute() {
                var currentData = frameData(documentData, frames, index), bindings = {};
                var completed = new Set(), visiting = new Set();
                (documentData.bindings || []).forEach(function (binding) { bindings[binding.id] = binding; });
                state.derived = {};
                function resolve(reference) {
                    if (Object.prototype.hasOwnProperty.call(state.controls, reference)) return state.controls[reference];
                    if (Object.prototype.hasOwnProperty.call(currentData, reference)) return currentData[reference];
                    return bindings[reference] ? derive(bindings[reference]) : undefined;
                }
                function derive(binding) {
                    if (completed.has(binding.id)) return state.derived[binding.id];
                    if (visiting.has(binding.id)) throw Error('Binding cycle');
                    visiting.add(binding.id);
                    var args = binding.args.map(function (reference, index) {
                        if (binding.operation === 'scene-point' && index === 1) return reference;
                        return resolve(reference);
                    });
                    var result;
                    if (binding.operation === 'select') result = {id: String(args[0]), element: String(args[0]), dataId: String(binding.args[1])};
                    else if (binding.operation === 'lookup') {
                        var entry = args[0].entries.find(function (item) { return same(item.key, args[1]); });
                        result = entry ? entry.value : null;
                    } else if (binding.operation === 'slice') result = {type: 'slice', start: Number(args[1]), end: Number(args[2])};
                    else if (binding.operation === 'length') result = args[0].values.length;
                    else if (binding.operation === 'sum') result = args[0].values.reduce(function (sum, value) { return sum + Number(value || 0); }, 0);
                    else if (binding.operation === 'range-sum') result = args[0].values.slice(Number(args[1]), Number(args[2])).reduce(function (sum, value) { return sum + Number(value || 0); }, 0);
                    else if (binding.operation === 'prefix-sum') {
                        var total = 0;
                        result = {type: 'sequence', values: [0].concat(args[0].values.map(function (value) { total += Number(value || 0); return total; }))};
                    } else if (binding.operation === 'scene-point') result = {type: 'scene-point', source: args[0], id: String(args[1]), x: args[2], y: args[3]};
                    else if (binding.operation === 'add') result = Number(args[0]) + Number(args[1]);
                    else if (binding.operation === 'subtract' || binding.operation === 'difference') result = Number(args[0]) - Number(args[1]);
                    else if (binding.operation === 'multiply') result = Number(args[0]) * Number(args[1]);
                    if (typeof result === 'number' && !Number.isFinite(result)) throw Error('Non-finite derived result');
                    visiting.delete(binding.id); completed.add(binding.id); state.derived[binding.id] = result;
                    return result;
                }
                (documentData.bindings || []).forEach(derive);
            }

            function highlightsFor(module, frame) {
                var highlights = clone(frame.highlights || {});
                (documentData.bindings || []).forEach(function (binding) {
                    var selected = state.derived[binding.id];
                    if (binding.target === module.id && binding.operation === 'select' && selected) {
                        highlights.selection = {dataId: selected.dataId, itemId: selected.id};
                    }
                });
                return highlights;
            }

            function notify() {
                var snapshot = controller.getState();
                listeners.forEach(function (listener) { listener(snapshot); });
            }

            function draw() {
                var currentData = frameData(documentData, frames, index), frame = frames[index];
                if (window.MathJax && window.MathJax.typesetClear) {
                    var oldFormulas = Array.from(root.querySelectorAll('.mv-formula'));
                    if (oldFormulas.length) window.MathJax.typesetClear(oldFormulas);
                }
                documentData.layout.readingOrder.forEach(function (id) {
                    var module = documentData.modules.find(function (item) { return item.id === id; });
                    if (!module || !moduleTypes.has(module.type)) throw Error('Unsupported module type');
                    var highlights = highlightsFor(module, frame);
                    var rendered = renderModule(module, module.source ? currentData[module.source] : null, frame, state, dispatch, currentData, highlights);
                    (documentData.bindings || []).filter(function (binding) { return binding.target === module.id; }).forEach(function (binding) {
                        var value = state.derived[binding.id];
                        if (value && value.type === 'sequence' && ['vector', 'queue', 'stack'].includes(module.type)) {
                            rendered = renderModule(module, value, frame, state, dispatch, currentData, highlights);
                        } else if (value && value.type === 'slice' && ['vector', 'queue', 'stack'].includes(module.type)) {
                            var strip = rendered.querySelector('.mv-items');
                            if (strip) Array.from(strip.children).forEach(function (item, itemIndex) {
                                if (itemIndex >= value.start && itemIndex < value.end) item.classList.add('mv-selected');
                            });
                        } else if (value && value.type === 'scene-point') {
                            rendered.querySelectorAll('[data-item-id]').forEach(function (point) {
                                if (point.dataset.itemId === value.id) point.setAttribute('aria-valuetext', 'x ' + value.x + ', y ' + value.y);
                            });
                        } else if (typeof value === 'number') rendered.append(el('output', 'mv-derived-result', binding.id + ': ' + value));
                    });
                var heading = rendered.querySelector('h3');
                if (heading) heading.remove();
                rendered.setAttribute('aria-labelledby', panels[module.id].querySelector('h3').id);
                    var previous = moduleRoot[module.id];
                    if (previous) {
                        ['.mv-chart-fallback', '.mv-graph-canvas'].forEach(function (selector) {
                            var live = previous.querySelector(selector), placeholder = rendered.querySelector(selector);
                            if (live && placeholder) placeholder.replaceWith(live);
                        });
                        previous.replaceWith(rendered);
                } else panels[module.id].append(rendered);
                    moduleRoot[module.id] = rendered;
                });
            frameInfo.textContent = 'Bước ' + (index + 1) + '/' + frames.length + ' · ' + [frame.title, frame.text].filter(Boolean).join(' — ');
                if (range) range.value = String(index);
                if (navigation) {
                    navigation.querySelectorAll('button')[0].disabled = index === 0;
                    navigation.querySelectorAll('button')[1].disabled = index === frames.length - 1;
                }
                Object.keys(charts).forEach(function (id) { charts[id].update(currentData); });
                Object.keys(graphs).forEach(function (id) { graphs[id].update(currentData, frame.highlights || {}); });
                if (window.MathJax && window.MathJax.typesetPromise) {
                    var formulas = Array.from(root.querySelectorAll('.mv-formula'));
                    if (formulas.length) window.MathJax.typesetPromise(formulas).catch(function () {});
                }
                notify();
            }

            function seek(nextIndex) {
                index = Math.max(0, Math.min(frames.length - 1, Math.trunc(nextIndex)));
                var frame = frames[index];
                applyFrameControls(frame);
                root.querySelectorAll('[data-control-id]').forEach(function (input) {
                    var id = input.dataset.controlId;
                    if (!Object.prototype.hasOwnProperty.call(state.controls, id)) return;
                    var control = controls.find(function (item) { return item.id === id; });
                    if (control.type === 'boolean') input.checked = state.controls[id];
                    else if (control.type === 'number') input.value = state.controls[id];
                    else input.value = JSON.stringify(state.controls[id]);
                });
                recompute(); draw();
            }
            function pause() {
                if (timer !== null) { clearInterval(timer); timer = null; }
                if (playButton) playButton.textContent = 'Phát';
            }
            function play() {
                if (frames.length < 2) return;
                pause();
                if (index >= frames.length - 1) seek(0);
                timer = setInterval(function () {
                    if (index >= frames.length - 1) pause(); else seek(index + 1);
                }, 1400);
                if (playButton) playButton.textContent = 'Tạm dừng';
            }
            if (frames.length > 1) {
                navigation = el('div', 'mv-timeline');
                navigation.append(button('Trước', function () { seek(index - 1); }));
                range = el('input'); range.type = 'range'; range.min = '0'; range.max = String(frames.length - 1);
                range.setAttribute('aria-label', 'Bước mô phỏng');
                range.addEventListener('input', function () { seek(Number(range.value)); });
                navigation.append(range, button('Tiếp', function () { seek(index + 1); }),
                    button('Đặt lại', function () { pause(); seek(0); }));
                playButton = button('Phát', function () { timer === null ? play() : pause(); });
                navigation.append(playButton);
                playback.prepend(navigation);
            }
            root.replaceChildren(shell);

            function regenerate(control, value, editorError) {
                var generation = ++requestId;
                if (aborter) aborter.abort();
                aborter = new AbortController();
                pause();
                if (editorError) editorError.hidden = true;
                frameInfo.textContent = 'Đang tạo lại mô phỏng…';
                var nextDocument = clone(documentData);
                if (control && control.inputKey) nextDocument.timeline.input[control.inputKey] = value;
                else nextDocument.timeline.input = clone(value);
                var csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
                fetch('/roadmap/visual-compile/', {
                    method: 'POST', credentials: 'same-origin', signal: aborter.signal,
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf)},
                    body: JSON.stringify({document: nextDocument, input: nextDocument.timeline.input})
                }).then(function (response) {
                    if (!response.ok) throw Error('Compile failed');
                    return response.json();
                }).then(function (result) {
                    if (destroyed || generation !== requestId) return;
                    documentData = result.document; frames = result.frames; index = 0;
                    if (inputEditor) inputEditor.value = JSON.stringify(documentData.timeline.input, null, 2);
                    controls.forEach(function (item) { if (item.inputKey) state.controls[item.id] = documentData.timeline.input[item.inputKey]; });
                    if (range) range.max = String(frames.length - 1);
                    recompute(); draw();
                }).catch(function (error) {
                    if (destroyed || generation !== requestId || error.name === 'AbortError') return;
                    frameInfo.textContent = 'Không thể tạo lại mô phỏng. Trạng thái hợp lệ trước đó được giữ.';
                });
            }

            controller = {
                next: function () { seek(index + 1); }, previous: function () { seek(index - 1); },
                seek: seek, play: play, pause: pause,
                reset: function () { pause(); seek(0); },
                getState: function () {
                    return clone({document: documentData, frame: frames[index], index: index, count: frames.length,
                        data: frameData(documentData, frames, index), selection: state.selection,
                        controls: state.controls, derived: state.derived});
                },
                subscribe: function (listener) { listeners.add(listener); return function () { listeners.delete(listener); }; },
                destroy: function () {
                    if (destroyed) return;
                    destroyed = true; requestId++;
                    lifecycle.abort();
                    if (aborter) aborter.abort();
                    pause();
                    if (resizeObserver) resizeObserver.disconnect();
                    if (window.MathJax && window.MathJax.typesetClear) {
                        var formulas = Array.from(root.querySelectorAll('.mv-formula'));
                        if (formulas.length) window.MathJax.typesetClear(formulas);
                    }
                    Object.keys(charts).forEach(function (id) { charts[id].instance.dispose(); });
                    Object.keys(graphs).forEach(function (id) { graphs[id].instance.destroy(); });
                    listeners.clear(); root.replaceChildren(); instances.delete(root);
                }
            };
            instances.set(root, controller);
            resizeObserver = new ResizeObserver(resizeVisuals);
            resizeObserver.observe(modules);
            recompute(); draw();

            documentData.modules.forEach(function (module) {
                if (module.type === 'chart') {
                    loadLibrary('echarts').then(function (echarts) {
                        if (destroyed) return;
                        moduleRoot[module.id].querySelector('.mv-chart-fallback').textContent = '';
                        var chart = echarts.init(moduleRoot[module.id].querySelector('.mv-chart-fallback'), null, {renderer: 'svg'});
                        function update(currentData) {
                            var tableData = currentData[module.source], rows = tableData.rows;
                            var scatter = module.kind === 'scatter';
                            var selectedId = state.selection && state.selection.dataId === module.source ? state.selection.id : null;
                            var points = rows.map(function (row) {
                                var point = {value: scatter ? [row[module.x], row[module.y]] : row[module.y]};
                                if (row.id === selectedId) point.itemStyle = {borderColor: '#111', borderWidth: 3};
                                return point;
                            });
                            chart.setOption({animation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
                                aria: {enabled: true, description: module.caption || documentData.summary},
                                xAxis: {type: scatter ? 'value' : 'category', name: module.x,
                                    data: scatter ? undefined : rows.map(function (row) { return row[module.x]; })},
                                yAxis: {type: 'value', name: module.y},
                                series: [{type: module.kind, data: points}]}, true);
                        }
                        chart.on('click', function (event) {
                            var row = frameData(documentData, frames, index)[module.source].rows[event.dataIndex];
                            if (row) dispatch({type: 'select', value: {dataId: module.source, id: row.id}});
                        });
                        charts[module.id] = {instance: chart, update: update};
                        update(frameData(documentData, frames, index));
                    }).catch(function () {
                        var target = moduleRoot[module.id] && moduleRoot[module.id].querySelector('.mv-chart-fallback');
                        if (target) target.textContent = 'Biểu đồ không tải được; bảng dữ liệu vẫn hiển thị.';
                    });
                } else if (module.type === 'graph' || module.type === 'tree') {
                    loadLibrary('cytoscape').then(function (cytoscape) {
                        if (destroyed) return;
                        moduleRoot[module.id].querySelector('.mv-graph-canvas').textContent = '';
                        var graph = cytoscape({container: moduleRoot[module.id].querySelector('.mv-graph-canvas'), elements: [],
                            layout: {name: 'preset'}, userZoomingEnabled: false, userPanningEnabled: false,
                            style: [
                                {selector: 'node', style: {label: 'data(label)', 'text-valign': 'center', 'background-color': '#fff', 'border-width': 2, 'border-color': '#567', color: '#222', width: 44, height: 44}},
                                {selector: 'edge', style: {'curve-style': 'bezier', 'target-arrow-shape': module.directed ? 'triangle' : 'none', 'line-color': '#789', 'target-arrow-color': '#789', label: 'data(label)'}},
                                {selector: '.mv-selected', style: {'background-color': '#da8b00', 'line-color': '#da8b00', 'target-arrow-color': '#da8b00'}}
                            ]});
                        function update(currentData, highlights) {
                            var graphData = currentData[module.source], oldPositions = {};
                            graph.nodes().forEach(function (node) { oldPositions[node.id()] = node.position(); });
                            graph.json({elements: graphData.nodes.map(function (node, nodeIndex) {
                                return {data: {id: node.id, label: node.label || node.id}, position: oldPositions[node.id] || {x: 120 + nodeIndex % 4 * 160, y: 80 + Math.floor(nodeIndex / 4) * 120}};
                            }).concat(graphData.edges.map(function (edge) {
                                return {data: {id: edge.id, source: edge.from, target: edge.to, label: edge.weight == null ? '' : String(edge.weight)}};
                            }))});
                            var selectedNodes = (highlights.nodes || []).slice();
                            if (state.selection && state.selection.dataId === module.source) selectedNodes.push(state.selection.id);
                            graph.nodes().removeClass('mv-selected');
                            graph.edges().removeClass('mv-selected');
                            selectedNodes.forEach(function (id) { graph.getElementById(id).addClass('mv-selected'); });
                            (highlights.edges || []).forEach(function (id) { graph.getElementById(id).addClass('mv-selected'); });
                            graph.fit(undefined, 24);
                            graph.nodes().forEach(function (node) { node.toggleClass('mv-selected', selectedNodes.includes(node.id())); });
                        }
                        graph.on('tap', 'node', function (event) { dispatch({type: 'select', value: {dataId: module.source, id: event.target.id()}}); });
                        graphs[module.id] = {instance: graph, update: update};
                        update(frameData(documentData, frames, index), frames[index].highlights || {});
                    }).catch(function () {
                        var target = moduleRoot[module.id] && moduleRoot[module.id].querySelector('.mv-graph-canvas');
                        if (target) target.textContent = 'Đồ thị không tải được; danh sách đỉnh vẫn hiển thị.';
                    });
                }
            });
            return controller;
        } catch (error) {
            if (controller) controller.destroy();
            root.replaceChildren(el('p', 'mv-error', 'Không thể hiển thị hình ảnh: ' + error.message));
            throw error;
        }
    }

    function mount(scope) {
        scope = scope || document;
        var roots = [];
        if (scope.matches && scope.matches('.msoj-visual[data-visual-config]')) roots.push(scope);
        if (scope.querySelectorAll) roots = roots.concat(Array.from(scope.querySelectorAll('.msoj-visual[data-visual-config]')));
        roots.forEach(function (root) {
            if (instances.has(root)) return;
            try { mountDocument(root, JSON.parse(root.getAttribute('data-visual-config'))); }
            catch (error) { root.replaceChildren(el('p', 'mv-error', 'Không thể hiển thị hình ảnh: ' + error.message)); }
        });
    }

    function watch() {
        if (!document.body) return;
        mount(document);
        new MutationObserver(function (records) {
            records.forEach(function (record) {
                record.removedNodes.forEach(function (node) {
                    if (node.nodeType !== 1) return;
                    var roots = [];
                    if (node.matches && node.matches('.msoj-visual')) roots.push(node);
                    if (node.querySelectorAll) roots = roots.concat(Array.from(node.querySelectorAll('.msoj-visual')));
                    roots.forEach(function (root) { var instance = instances.get(root); if (instance) instance.destroy(); });
                });
                record.addedNodes.forEach(function (node) { if (node.nodeType === 1) mount(node); });
            });
        }).observe(document.body, {childList: true, subtree: true});
    }

    window.MSOJVisuals = {mount: mount, mountDocument: mountDocument};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch, {once: true});
    else watch();
})();

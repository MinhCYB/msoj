(function () {
  "use strict";
  var workspace = document.querySelector(".ms-workspace");
  if (!workspace) return;

  var rail = workspace.querySelector(".ms-workspace-rail");
  var main = workspace.querySelector(".ms-workspace-main");
  var comments = workspace.querySelector(".ms-workspace-comments");
  var submissions = main.querySelector(".ms-workspace-submissions");
  var submissionsContent = main.querySelector(".ms-workspace-submissions-content");
  var editorial = main.querySelector(".ms-workspace-editorial");
  var submissionLinks = Array.from(main.querySelectorAll("[data-submission-kind]"));
  var grid = main.querySelector(".ms-workspace-grid");
  var divider = grid.querySelector(".ms-workspace-divider");
  var editorToggle = divider.querySelector(".ms-editor-toggle");
  var editor = grid.querySelector(".ms-workspace-code");
  var ratio = 50;
  function setRatio(value) {
    ratio = Math.max(20, Math.min(80, Math.round(value)));
    grid.style.setProperty("--ws-statement-ratio", String(ratio / 100));
    divider.setAttribute("aria-valuenow", ratio);
  }
  function setEditorVisible(visible) {
    grid.classList.toggle("ms-editor-collapsed", !visible);
    editor.hidden = !visible;
    editorToggle.setAttribute("aria-expanded", String(visible));
    editorToggle.setAttribute(
      "aria-label",
      visible ? "Ẩn trình soạn thảo" : "Hiện trình soạn thảo",
    );
    editorToggle.title = editorToggle.getAttribute("aria-label");
    if (visible && window.ace) {
      var aceNode = editor.querySelector(".ace_editor");
      if (aceNode && ace.edit) ace.edit(aceNode).resize();
    }
  }
  editorToggle.addEventListener("click", function () {
    setEditorVisible(editor.hidden);
  });
  divider.addEventListener("pointerdown", function (event) {
    if (event.target.closest("button") || editor.hidden || matchMedia("(max-width: 850px)").matches)
      return;
    event.preventDefault();
    divider.setPointerCapture(event.pointerId);
    grid.classList.add("ms-resizing");
  });
  divider.addEventListener("pointermove", function (event) {
    if (!divider.hasPointerCapture(event.pointerId)) return;
    var bounds = grid.getBoundingClientRect();
    setRatio(((event.clientX - bounds.left) / bounds.width) * 100);
  });
  function endResize() {
    grid.classList.remove("ms-resizing");
    if (window.ace) {
      var aceNode = editor.querySelector(".ace_editor");
      if (aceNode && ace.edit) ace.edit(aceNode).resize();
    }
  }
  divider.addEventListener("pointerup", endResize);
  divider.addEventListener("pointercancel", endResize);
  divider.addEventListener("keydown", function (event) {
    if (event.target !== divider || editor.hidden) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      setRatio(ratio + (event.key === "ArrowRight" ? 5 : -5));
      endResize();
    }
  });
  var loadedFragments = Object.create(null);
  var pendingRequests = Object.create(null);
  var activeFragmentUrls = Object.create(null);
  var activeSubmissionKind = main.dataset.submissionsMineUrl ? "mine" : "all";
  function isSubmissionTab(tab) {
    return tab === "submission" || tab === "submission-all" || tab === "submission-best";
  }
  function submissionKindForTab(tab) {
    if (tab === "submission-all") return "all";
    if (tab === "submission-best") return "best";
    return main.dataset.submissionsMineUrl ? "mine" : "all";
  }
  function setCurrentTab(tab) {
    var isStatement = tab === "statement";
    var isComments = tab === "comments" || /^comment-\d+$/.test(tab);
    var isSubmissions = isSubmissionTab(tab);
    var isEditorial = tab === "editorial";
    if (isSubmissions) activeSubmissionKind = submissionKindForTab(tab);
    grid.hidden = !isStatement;
    comments.hidden = !isComments;
    submissions.hidden = !isSubmissions;
    editorial.hidden = !isEditorial;

    rail.querySelectorAll("[data-workspace-tab]").forEach(function (link) {
      var active =
        link.dataset.workspaceTab === tab ||
        (link.dataset.workspaceTab === "comments" && isComments) ||
        (link.dataset.workspaceTab === "submission" && isSubmissions);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    submissionLinks.forEach(function (link) {
      var selected =
        link.dataset.workspaceTab === tab ||
        (tab === "submission" && link.dataset.submissionKind === activeSubmissionKind);
      if (selected) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });

    if (isComments && window.jQuery) {
      var $comments = window.jQuery("#comments").first();
      if (/^comment-\d+$/.test(tab)) {
        var pending = $comments.data("set-pending-scroll");
        if (pending) pending("#" + tab);
        var comment = document.getElementById(tab);
        if (comment)
          requestAnimationFrame(function () {
            comment.scrollIntoView({ block: "start" });
          });
      }
      var loadComments = $comments.data("load-comments");
      if (loadComments) loadComments();
    }
    if (isSubmissions) loadWorkspaceFragment(tab);
    if (isEditorial) loadWorkspaceFragment(tab);
    if (isStatement && window.ace) {
      var aceNode = editor.querySelector(".ace_editor");
      if (aceNode && ace.edit)
        requestAnimationFrame(function () {
          ace.edit(aceNode).resize();
        });
    }
  }

  function fragmentUrl(tab) {
    var key =
      tab === "editorial"
        ? "editorialUrl"
        : "submissions" +
          activeSubmissionKind[0].toUpperCase() +
          activeSubmissionKind.slice(1) +
          "Url";
    var value = main.dataset[key];
    if (!value) return null;
    var url = new URL(value, window.location.href);
    if (tab !== "editorial") url.searchParams.set("workspace", "1");
    return url.toString();
  }

  function loadWorkspaceFragment(tab, requestedUrl) {
    var target = tab === "editorial" ? editorial : submissionsContent;
    var url = requestedUrl || activeFragmentUrls[tab] || fragmentUrl(tab);
    var requestKind = tab === "editorial" ? null : activeSubmissionKind;
    if (!url) {
      target.textContent = main.dataset.workspaceError;
      return;
    }
    if (loadedFragments[url]) {
      target.innerHTML = loadedFragments[url];
      initializeWorkspaceFragment(target);
      return;
    }
    if (pendingRequests[url]) return;

    target.textContent = main.dataset.workspaceLoading;
    activeFragmentUrls[tab] = url;
    pendingRequests[url] = true;
    fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (response) {
        if (!response.ok) throw new Error("Workspace fragment request failed");
        return response.text();
      })
      .then(function (html) {
        delete pendingRequests[url];
        loadedFragments[url] = html;
        // A response may finish after the user selected another view. Keep it
        // cached, but don't replace the content of the now-active view.
        var activeHash = window.location.hash.slice(1) || "statement";
        if (
          (tab === "editorial" && activeHash !== "editorial") ||
          (tab !== "editorial" &&
            (!isSubmissionTab(activeHash) || activeSubmissionKind !== requestKind))
        )
          return;
        activeFragmentUrls[activeHash] = url;
        target.innerHTML = html;
        initializeWorkspaceFragment(target);
        if (window.MathJax && window.MathJax.typesetPromise)
          window.MathJax.typesetPromise([target]);
      })
      .catch(function () {
        delete pendingRequests[url];
        var activeHash = window.location.hash.slice(1) || "statement";
        if (
          (tab === "editorial" && activeHash === "editorial") ||
          (tab !== "editorial" &&
            isSubmissionTab(activeHash) &&
            activeSubmissionKind === requestKind)
        )
          target.textContent = main.dataset.workspaceError;
      });
  }

  function initializeWorkspaceFragment(target) {
    target.querySelectorAll(".ms-workspace-submission-filter-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var currentTab = window.location.hash.slice(1) || "submission";
        var url = new URL(fragmentUrl(currentTab), window.location.href);
        url.search = new URLSearchParams(new FormData(form)).toString();
        url.searchParams.set("workspace", "1");
        loadWorkspaceFragment(currentTab, url.toString());
      });
    });
    target.querySelectorAll(".pagination a").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        loadWorkspaceFragment(window.location.hash.slice(1) || "submission", link.href);
      });
    });
  }

  function currentTabFromHash() {
    var hash = location.hash.replace(/^#/, "");
    if (hash === "" || hash === "ms-statement" || hash === "statement") return "statement";
    if (hash === "comments" || /^comment-\d+$/.test(hash)) return hash;
    if (hash === "submission")
      return main.dataset.submissionsMineUrl ? "submission" : "submission-all";
    if (hash === "submission-all" || hash === "submission-best") {
      var key = hash === "submission-all" ? "submissionsAllUrl" : "submissionsBestUrl";
      if (!main.dataset[key])
        return main.dataset.submissionsMineUrl ? "submission" : "submission-all";
      return hash;
    }
    if (hash === "editorial") return main.dataset.editorialUrl ? hash : "statement";
    return "statement";
  }

  function navigateTab(tab, replace) {
    if (isSubmissionTab(tab)) activeSubmissionKind = submissionKindForTab(tab);
    var hash = "#" + tab;
    if (location.hash !== hash) {
      if (replace) history.replaceState(null, "", hash);
      else history.pushState(null, "", hash);
    }
    setCurrentTab(tab);
  }

  function restoreTabFromHistory() {
    setCurrentTab(currentTabFromHash());
  }
  window.addEventListener("hashchange", restoreTabFromHistory);
  window.addEventListener("popstate", restoreTabFromHistory);
  var initialTab = currentTabFromHash();
  if (isSubmissionTab(initialTab)) activeSubmissionKind = submissionKindForTab(initialTab);
  if (initialTab === "statement" && workspace.dataset.commentErrors && !location.hash)
    initialTab = "comments";
  if (
    (!location.hash && initialTab !== "statement") ||
    location.hash === "#submissions" ||
    (location.hash && location.hash !== "#" + initialTab)
  )
    navigateTab(initialTab, true);
  else setCurrentTab(initialTab);

  function sizeWorkspace() {
    var top = workspace.getBoundingClientRect().top;
    workspace.style.setProperty(
      "--ws-available-height",
      Math.max(0, document.documentElement.clientHeight - top) + "px",
    );
  }
  window.addEventListener("resize", sizeWorkspace);
  if (window.ResizeObserver) {
    var observer = new ResizeObserver(sizeWorkspace);
    observer.observe(document.querySelector(".problem-title"));
    var admin = workspace.querySelector(".ms-workspace-admin");
    if (admin) observer.observe(admin);
  }
  if (window.visualViewport) window.visualViewport.addEventListener("resize", sizeWorkspace);
  sizeWorkspace();

  var mentor = document.querySelector(".ms-mentor");
  var launch = rail.querySelector(".ms-mentor-launch");
  var panel = mentor.querySelector(".ms-mentor-panel");
  var mentorDrag = null;
  function mentorLimits() {
    var rect = panel.getBoundingClientRect();
    return {
      minWidth: Math.min(320, window.innerWidth - rect.left - 12),
      maxWidth: Math.max(0, window.innerWidth - rect.left - 12),
      minHeight: Math.min(300, rect.bottom - 12),
      maxHeight: Math.max(0, rect.bottom - Math.max(12, workspace.getBoundingClientRect().top + 8)),
    };
  }
  function bounded(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }
  function clampMentor() {
    if (panel.hidden) return;
    var limits = mentorLimits();
    panel.style.width = Math.min(panel.offsetWidth, limits.maxWidth) + "px";
    panel.style.height = Math.min(panel.offsetHeight, limits.maxHeight) + "px";
  }
  launch.addEventListener("click", function () {
    panel.hidden = false;
    launch.setAttribute("aria-expanded", "true");
    clampMentor();
    panel.dispatchEvent(new Event("mentor:open"));
  });
  panel.querySelector('[data-mentor="minimize"]').addEventListener("click", function () {
    panel.hidden = true;
    mentorDrag = null;
    launch.setAttribute("aria-expanded", "false");
    panel.dispatchEvent(new Event("mentor:close"));
    launch.focus();
  });
  panel.querySelector('[data-mentor="close"]').addEventListener("click", function () {
    panel.hidden = true;
    mentorDrag = null;
    panel.style.width = "";
    panel.style.height = "";
    panel.style.top = "";
    panel.style.bottom = "";
    launch.setAttribute("aria-expanded", "false");
    panel.dispatchEvent(new Event("mentor:close"));
    launch.focus();
  });
  panel.querySelectorAll("[data-resize]").forEach(function (handle) {
    var axis = handle.dataset.resize;
    handle.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || panel.hidden) return;
      event.preventDefault();
      event.stopPropagation();
      var rect = panel.getBoundingClientRect();
      mentorDrag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        width: rect.width,
        height: rect.height,
      };
      panel.classList.add("is-resizing");
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", function (event) {
      if (!mentorDrag || event.pointerId !== mentorDrag.id) return;
      var limits = mentorLimits();
      if (axis !== "top")
        panel.style.width =
          bounded(
            mentorDrag.width + event.clientX - mentorDrag.x,
            limits.minWidth,
            limits.maxWidth,
          ) + "px";
      if (axis !== "right")
        panel.style.height =
          bounded(
            mentorDrag.height + mentorDrag.y - event.clientY,
            limits.minHeight,
            limits.maxHeight,
          ) + "px";
    });
    function finishMentorResize() {
      mentorDrag = null;
      panel.classList.remove("is-resizing");
    }
    handle.addEventListener("pointerup", finishMentorResize);
    handle.addEventListener("pointercancel", finishMentorResize);
    handle.addEventListener("lostpointercapture", finishMentorResize);
    handle.addEventListener("keydown", function (event) {
      if (!event.altKey || !["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key))
        return;
      event.preventDefault();
      var rect = panel.getBoundingClientRect();
      var limits = mentorLimits();
      if (axis !== "top")
        panel.style.width =
          bounded(
            rect.width + (event.key === "ArrowRight" ? 20 : event.key === "ArrowLeft" ? -20 : 0),
            limits.minWidth,
            limits.maxWidth,
          ) + "px";
      if (axis !== "right")
        panel.style.height =
          bounded(
            rect.height + (event.key === "ArrowUp" ? 20 : event.key === "ArrowDown" ? -20 : 0),
            limits.minHeight,
            limits.maxHeight,
          ) + "px";
    });
  });
  window.addEventListener("resize", clampMentor);

  var layer = document.getElementById("ms-annotation-layer");
  var toolbar = document.getElementById("ms-annotation-toolbar");
  var toggle = document.querySelector(".ms-annotate-launch");
  var status = toolbar.querySelector(".ms-annotation-status");
  var color = toolbar.querySelector('input[type="color"]');
  var key = "msoj:annotation:" + workspace.dataset.problemCode;
  var tool = "select",
    marks = [],
    history = [],
    future = [],
    drawing = null,
    erasing = false,
    eraseLastPoint = null,
    erasedInStroke = false;
  var svgNS = "http://www.w3.org/2000/svg";
  var svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("aria-hidden", "true");
  layer.appendChild(svg);
  try {
    var saved = JSON.parse(localStorage.getItem(key) || "[]");
    if (Array.isArray(saved))
      marks = saved
        .filter(function (mark) {
          return (
            mark &&
            ["pen", "highlight", "text", "line", "arrow", "rectangle", "circle"].includes(
              mark.tool,
            ) &&
            typeof mark.color === "string" &&
            Array.isArray(mark.points) &&
            mark.points.length <= 10000 &&
            mark.points.every(function (p) {
              return Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
            })
          );
        })
        .slice(0, 1000);
  } catch (e) {
    status.textContent = "Không thể đọc ghi chú đã lưu trên thiết bị.";
  }

  function save() {
    try {
      localStorage.setItem(key, JSON.stringify(marks));
      status.textContent = "";
    } catch (e) {
      status.textContent = "Không thể lưu ghi chú. Hãy kiểm tra bộ nhớ trình duyệt.";
    }
  }
  function point(event) {
    var rect = layer.getBoundingClientRect();
    return [Math.round(event.clientX - rect.left), Math.round(event.clientY - rect.top)];
  }
  function node(tag, attributes) {
    var element = document.createElementNS(svgNS, tag);
    Object.keys(attributes).forEach(function (name) {
      element.setAttribute(name, attributes[name]);
    });
    return element;
  }
  function render() {
    svg.replaceChildren();
    svg.setAttribute(
      "viewBox",
      "0 0 " + Math.max(1, layer.offsetWidth) + " " + Math.max(1, layer.offsetHeight),
    );
    marks.concat(drawing ? [drawing] : []).forEach(function (mark, index) {
      if (!mark.points.length) return;
      var start = mark.points[0],
        end = mark.points[mark.points.length - 1];
      var attrs = {
        stroke: mark.color,
        "stroke-width": mark.tool === "highlight" ? 18 : 3,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        fill: "none",
      };
      var item;
      if (mark.tool === "text") {
        item = node("text", { x: start[0], y: start[1], fill: mark.color, "font-size": 18 });
        item.textContent = mark.text || "";
      } else if (mark.tool === "rectangle") {
        item = node(
          "rect",
          Object.assign(attrs, {
            x: Math.min(start[0], end[0]),
            y: Math.min(start[1], end[1]),
            width: Math.abs(end[0] - start[0]),
            height: Math.abs(end[1] - start[1]),
          }),
        );
      } else if (mark.tool === "circle") {
        item = node(
          "ellipse",
          Object.assign(attrs, {
            cx: (start[0] + end[0]) / 2,
            cy: (start[1] + end[1]) / 2,
            rx: Math.abs(end[0] - start[0]) / 2,
            ry: Math.abs(end[1] - start[1]) / 2,
          }),
        );
      } else if (mark.tool === "line" || mark.tool === "arrow") {
        item = node("g", {});
        item.appendChild(
          node(
            "line",
            Object.assign(attrs, { x1: start[0], y1: start[1], x2: end[0], y2: end[1] }),
          ),
        );
        if (mark.tool === "arrow") {
          var angle = Math.atan2(end[1] - start[1], end[0] - start[0]);
          for (var sign of [-1, 1])
            item.appendChild(
              node(
                "line",
                Object.assign(attrs, {
                  x1: end[0],
                  y1: end[1],
                  x2: end[0] - 12 * Math.cos(angle + sign * 0.55),
                  y2: end[1] - 12 * Math.sin(angle + sign * 0.55),
                }),
              ),
            );
        }
      } else {
        item = node(
          "polyline",
          Object.assign(attrs, {
            points: mark.points
              .map(function (p) {
                return p.join(",");
              })
              .join(" "),
            "stroke-opacity": mark.tool === "highlight" ? 0.35 : 1,
          }),
        );
      }
      item.dataset.index = index;
      if (mark.tool !== "text" && item.tagName !== "g") item.style.pointerEvents = "stroke";
      svg.appendChild(item);
    });
  }
  function commit() {
    future = [];
    save();
    render();
  }
  function snapshot() {
    history.push(JSON.stringify(marks));
    if (history.length > 50) history.shift();
  }
  function setTool(next) {
    tool = next;
    toolbar.querySelectorAll("[data-tool]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.tool === tool));
    });
    layer.classList.toggle("is-drawing", tool !== "select");
  }
  function setToolbarOpen(open) {
    toolbar.hidden = !open;
    toggle.setAttribute("aria-expanded", String(!toolbar.hidden));
    if (toolbar.hidden) setTool("select");
  }
  toggle.addEventListener("click", function () {
    setToolbarOpen(toolbar.hidden);
  });
  toolbar.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.action === "close") {
      setToolbarOpen(false);
      toggle.focus();
      return;
    }
    if (button.dataset.tool) {
      setTool(button.dataset.tool);
      return;
    }
    if (button.dataset.action === "undo" && history.length) {
      future.push(JSON.stringify(marks));
      marks = JSON.parse(history.pop());
      commitHistory();
    }
    if (button.dataset.action === "redo" && future.length) {
      history.push(JSON.stringify(marks));
      marks = JSON.parse(future.pop());
      commitHistory();
    }
    if (
      button.dataset.action === "clear" &&
      marks.length &&
      window.confirm(
        "Xóa tất cả ghi chú của bài này trên thiết bị? Bạn có thể hoàn tác trong phiên hiện tại.",
      )
    ) {
      snapshot();
      marks = [];
      commit();
    }
  });
  function commitHistory() {
    save();
    render();
  }
  function eraseAt(position) {
    // Hit-test the SVG geometry, not the overlay: the overlay intercepts pointer events.
    var offsets = [
      [0, 0],
      [7, 0],
      [-7, 0],
      [0, 7],
      [0, -7],
    ];
    var items = Array.from(svg.children);
    for (var index = items.length - 1; index >= 0; index--) {
      var item = items[index];
      var segments = item.tagName.toLowerCase() === "g" ? item.children : [item];
      var hit = Array.from(segments).some(function (segment) {
        if (segment.tagName.toLowerCase() === "text") {
          var box = segment.getBBox();
          return (
            position[0] >= box.x - 7 &&
            position[0] <= box.x + box.width + 7 &&
            position[1] >= box.y - 7 &&
            position[1] <= box.y + box.height + 7
          );
        }
        return offsets.some(function (offset) {
          return segment.isPointInStroke(
            new DOMPoint(position[0] + offset[0], position[1] + offset[1]),
          );
        });
      });
      if (hit) {
        if (!erasedInStroke) snapshot();
        erasedInStroke = true;
        marks.splice(index, 1);
        render();
        return;
      }
    }
  }
  function eraseThrough(position) {
    var previous = eraseLastPoint || position;
    var distance = Math.hypot(position[0] - previous[0], position[1] - previous[1]);
    var steps = Math.max(1, Math.ceil(distance / 6));
    for (var step = 0; step <= steps; step++) {
      var fraction = step / steps;
      eraseAt([
        previous[0] + (position[0] - previous[0]) * fraction,
        previous[1] + (position[1] - previous[1]) * fraction,
      ]);
    }
    eraseLastPoint = position;
  }
  layer.addEventListener("pointerdown", function (event) {
    if (tool === "select") return;
    var p = point(event);
    if (tool === "eraser") {
      erasing = true;
      erasedInStroke = false;
      eraseLastPoint = null;
      layer.setPointerCapture(event.pointerId);
      eraseThrough(p);
      return;
    }
    if (tool === "text") {
      var text = window.prompt("Nội dung ghi chú:");
      if (text && text.trim()) {
        snapshot();
        marks.push({
          tool: tool,
          color: color.value,
          points: [p],
          text: text.trim().slice(0, 500),
        });
        commit();
      }
      return;
    }
    snapshot();
    drawing = { tool: tool, color: color.value, points: [p, p] };
    layer.setPointerCapture(event.pointerId);
    render();
  });
  layer.addEventListener("pointermove", function (event) {
    if (erasing) {
      eraseThrough(point(event));
      return;
    }
    if (!drawing) return;
    var p = point(event);
    if (tool === "pen" || tool === "highlight") {
      if (drawing.points.length < 10000) drawing.points.push(p);
    } else drawing.points[1] = p;
    render();
  });
  function finish() {
    if (erasing) {
      erasing = false;
      eraseLastPoint = null;
      if (erasedInStroke) commit();
      return;
    }
    if (!drawing) return;
    marks.push(drawing);
    drawing = null;
    commit();
  }
  layer.addEventListener("pointerup", finish);
  layer.addEventListener("pointercancel", function () {
    if (erasing) {
      erasing = false;
      eraseLastPoint = null;
      if (erasedInStroke) commit();
      return;
    }
    drawing = null;
    history.pop();
    render();
  });
  window.addEventListener("resize", render);
  render();
})();

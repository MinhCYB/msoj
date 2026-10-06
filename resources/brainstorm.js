(function () {
  "use strict";
  var panel = document.getElementById("ms-mentor-panel");
  if (!panel) return;

  var sessionUrl = panel.dataset.sessionUrl;
  var postUrl = panel.dataset.postUrl;
  var turnUrl = panel.dataset.turnUrl;
  var status = panel.querySelector(".ms-mentor-status");
  var alert = panel.querySelector(".ms-mentor-alert");
  var refresh = panel.querySelector(".ms-mentor-refresh");
  var retry = panel.querySelector(".ms-mentor-retry");
  var truncated = panel.querySelector(".ms-mentor-truncated");
  var history = panel.querySelector(".ms-mentor-history");
  var conversation = panel.querySelector(".ms-mentor-conversation");
  var empty = panel.querySelector(".ms-mentor-empty");
  var form = panel.querySelector(".ms-mentor-composer");
  var question = panel.querySelector("#ms-mentor-question");
  var send = panel.querySelector(".ms-mentor-send");
  var timer = null;
  var controller = null;
  var generation = 0;
  var activeTurn = null;
  var submitting = false;
  var available = false;
  var polls = 0;
  var failures = 0;
  var ambiguous = null;
  var inFlight = false;
  var ownTurn = null;
  var ownPayload = null;
  var pendingPayload = null;
  var failedMessage = "";

  function sizeQuestion() {
    if (!question) return;
    question.style.height = "auto";
    question.style.height = Math.min(question.scrollHeight, 112) + "px";
  }

  var errors = {
    brainstorm_disabled: "Mentor hiện chưa khả dụng. Hãy thử lại sau.",
    contest_brainstorm_disabled: "Mentor không khả dụng trong kỳ thi này.",
    contest_scope_ended: "Kỳ thi đã kết thúc. Hãy hỏi ở bài luyện tập.",
    scope_ended: "Kỳ thi đã kết thúc. Lượt hỏi này không được công bố.",
    problem_not_accessible: "Bạn không thể dùng Mentor cho bài này.",
    access_revoked: "Quyền truy cập đã thay đổi. Lượt hỏi này không được công bố.",
    subscription_required: "Bạn cần gói Mentor còn hiệu lực để đặt câu hỏi mới.",
    unsupported_language: "Ngôn ngữ này không hỗ trợ Mentor. Hãy chọn ngôn ngữ mã nguồn.",
    unsupported_problem: "Mentor cần đề bài dạng văn bản để trả lời.",
    invalid_question: "Hãy nhập câu hỏi hợp lệ trước khi gửi.",
    payload_too_large: "Câu hỏi, hướng giải, mã hoặc đề bài quá dài cho Mentor.",
    turn_in_progress: "Mentor đang xử lý một câu hỏi trong hội thoại này.",
    active_turn_limit: "Bạn đang có quá nhiều câu hỏi chưa hoàn tất. Hãy thử lại sau.",
    turn_quota_exceeded: "Bạn đã hết lượt hỏi Mentor hôm nay. Hãy thử lại ngày mai.",
    provider_call_quota_exceeded: "Mentor đã đạt giới hạn sử dụng hôm nay. Hãy thử lại ngày mai.",
    call_budget_exhausted: "Mentor đã hết lượt xử lý cho câu hỏi này. Hãy thử câu hỏi khác sau.",
    idempotency_conflict: "Yêu cầu này đã được dùng với nội dung khác. Hãy kiểm tra hội thoại.",
    review_rejected: "Mentor chưa tạo được câu trả lời phù hợp. Hãy diễn đạt câu hỏi khác đi.",
    queue_unavailable: "Mentor chưa thể bắt đầu. Bản nháp vẫn còn; hãy thử lại sau.",
    not_configured: "Mentor hiện chưa khả dụng. Hãy thử lại sau.",
    authentication_failed: "Mentor hiện chưa khả dụng. Hãy thử lại sau.",
    rate_limited: "Mentor đang bận. Hãy thử lại sau.",
    timeout: "Mentor phản hồi quá lâu. Hãy thử lại sau.",
    upstream_unavailable: "Mentor chưa thể phản hồi. Hãy thử lại sau.",
    invalid_response: "Mentor chưa tạo được câu trả lời phù hợp. Hãy thử lại sau.",
    context_limit: "Mentor không thể xử lý toàn bộ đề và câu hỏi trong một lượt.",
    generator_invalid_output: "Mentor chưa tạo được câu trả lời phù hợp. Hãy hỏi theo cách khác.",
    reviewer_invalid_output: "Mentor chưa xác minh được câu trả lời. Hãy thử lại sau.",
    brainstorm_unavailable: "Mentor chưa thể phản hồi. Hãy thử lại sau.",
  };

  function explain(code) {
    return errors[code] || "Mentor hiện chưa khả dụng. Hãy kiểm tra lại sau.";
  }

  function notify(text) {
    alert.textContent = text || "";
    alert.hidden = !text;
  }

  function controls() {
    if (!form) return;
    question.disabled = !available || submitting || !!activeTurn || !!ambiguous;
    send.disabled = !available || submitting || !!activeTurn || !!ambiguous;
    if (retry) {
      retry.hidden = !ambiguous || !available || !!activeTurn;
      retry.disabled = submitting || inFlight;
    }
  }

  function stop() {
    // Aborting an in-flight POST only stops the browser wait, never the claimed server turn.
    if (submitting && pendingPayload) ambiguous = pendingPayload;
    generation++;
    clearTimeout(timer);
    timer = null;
    if (controller) controller.abort();
    controller = null;
    inFlight = false;
    submitting = false;
  }

  async function request(url, options) {
    var current = new AbortController();
    controller = current;
    inFlight = true;
    try {
      var response = await fetch(
        url,
        Object.assign(
          {
            credentials: "same-origin",
            cache: "no-store",
            signal: current.signal,
            headers: { Accept: "application/json" },
          },
          options || {},
        ),
      );
      var data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        var error = new Error("request_failed");
        error.code = data.error_code;
        error.http = response.status;
        throw error;
      }
      return data;
    } finally {
      if (controller === current) {
        controller = null;
        inFlight = false;
      }
    }
  }

  function addMessage(role, text) {
    var entry = document.createElement("article");
    entry.className = "ms-mentor-message ms-mentor-message-" + role;
    var body = document.createElement("p");
    body.textContent = text || "";
    entry.appendChild(body);
    history.appendChild(entry);
  }

  function renderHistory(rows) {
    history.replaceChildren();
    (Array.isArray(rows) ? rows : []).forEach(function (pair) {
      addMessage("student", pair.question + (pair.approach ? "\n\n" + pair.approach : ""));
      addMessage("ai", pair.answer);
    });
    empty.hidden = !!history.children.length;
    conversation.scrollTop = conversation.scrollHeight;
  }

  function updateSession(data) {
    renderHistory(data.history);
    available = data.available === true && !!form;
    if (data.active_turn && ["pending", "running"].includes(data.active_turn.status)) {
      activeTurn = data.active_turn.turn_id;
      ambiguous = null;
      pendingPayload = null;
      failedMessage = "";
      truncated.hidden = !data.active_turn.history_truncated;
      status.textContent =
        data.active_turn.status === "running" ? "Mentor đang suy nghĩ…" : "Mentor đang phân tích…";
      notify("");
      controls();
      polls = 0;
      schedule(generation);
    } else {
      activeTurn = null;
      if (!ambiguous) notify(failedMessage);
      status.textContent = failedMessage
        ? "Mentor không thể trả lời lượt hỏi này."
        : available
          ? ""
          : "AI Mentor hiện chưa khả dụng.";
      controls();
    }
  }

  function schedule(token) {
    if (panel.hidden || token !== generation || !activeTurn) return;
    clearTimeout(timer);
    if (polls >= 60) {
      status.textContent = "Mentor vẫn đang xử lý. Hãy đợi trong giây lát.";
      if (refresh) refresh.hidden = false;
      return;
    }
    timer = setTimeout(
      function () {
        poll(token);
      },
      Math.min(2500 + polls * 350, 9000),
    );
  }

  async function poll(token) {
    if (panel.hidden || token !== generation || !activeTurn || inFlight) return;
    var id = activeTurn;
    try {
      var data = await request(turnUrl.replace(/\/0\/$/, "/" + encodeURIComponent(id) + "/"));
      if (token !== generation || id !== activeTurn || panel.hidden) return;
      failures = 0;
      if (refresh) refresh.hidden = true;
      truncated.hidden = !data.history_truncated;
      if (data.status === "pending" || data.status === "running") {
        status.textContent =
          data.status === "running" ? "Mentor đang suy nghĩ…" : "Mentor đang phân tích…";
        if (++polls >= 8)
          notify("Mentor đang phân tích mã tại thời điểm bạn gửi. Bạn có thể tiếp tục sửa mã.");
        schedule(token);
      } else if (data.status === "succeeded") {
        activeTurn = null;
        status.textContent = "Đang tải câu trả lời đã duyệt…";
        var loaded = await loadSession(token);
        if (
          loaded &&
          ownTurn === id &&
          token === generation &&
          !panel.hidden &&
          available &&
          ownPayload
        ) {
          if (question.value === ownPayload.question) {
            question.value = "";
            sizeQuestion();
          }
        }
        ownTurn = null;
        ownPayload = null;
      } else if (data.status === "failed") {
        activeTurn = null;
        failedMessage = explain(data.error_code);
        notify(failedMessage);
        status.textContent = "Mentor không thể trả lời lượt hỏi này.";
        ownTurn = null;
        ownPayload = null;
        controls();
      } else {
        throw new Error("invalid_state");
      }
    } catch (error) {
      if (token !== generation || panel.hidden || error.name === "AbortError") return;
      failures++;
      notify(
        error.code
          ? explain(error.code)
          : "Không kiểm tra được tiến độ. Câu hỏi chưa được gửi lại.",
      );
      if (failures < 3)
        timer = setTimeout(
          function () {
            poll(token);
          },
          Math.min(3000 * Math.pow(2, failures), 12000),
        );
      else if (refresh) refresh.hidden = false;
    }
  }

  async function loadSession(token) {
    if (inFlight) return false;
    try {
      var data = await request(sessionUrl);
      if (token !== generation || panel.hidden) return false;
      failures = 0;
      if (refresh) refresh.hidden = true;
      updateSession(data);
      if (ambiguous && !data.active_turn) {
        status.textContent = "Chưa xác nhận được câu hỏi đã gửi hay chưa.";
        notify("Kiểm tra kết nối rồi thử lại.");
        if (refresh) refresh.hidden = false;
      }
      return true;
    } catch (error) {
      if (token !== generation || panel.hidden || error.name === "AbortError") return false;
      available = false;
      controls();
      if (refresh) refresh.hidden = false;
      notify(
        error.code ? explain(error.code) : "Không tải được Mentor. Kiểm tra kết nối rồi thử lại.",
      );
      if (refresh) refresh.hidden = false;
      return false;
    }
  }

  function requestId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    if (window.crypto && crypto.getRandomValues) {
      return Array.from(crypto.getRandomValues(new Uint8Array(16)), function (n) {
        return n.toString(16).padStart(2, "0");
      }).join("");
    }
    return null;
  }

  function editorSnapshot() {
    var select = document.getElementById("id_language");
    var selected = select && select.options[select.selectedIndex];
    var editor = window.ace_source;
    if (!editor || !editor.getSession || !editor.getSession() || !selected || !selected.dataset.key)
      return null;
    if (selected.dataset.fileonly === "True") return { fileOnly: true };
    return { current_code: editor.getSession().getValue(), language_key: selected.dataset.key };
  }

  async function sendTurn(payload, token) {
    submitting = true;
    pendingPayload = payload;
    controls();
    if (refresh) refresh.hidden = true;
    notify("");
    status.textContent = "Đang gửi câu hỏi…";
    try {
      var data = await request(postUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value,
        },
        body: JSON.stringify(payload),
      });
      if (token !== generation || panel.hidden) return;
      ambiguous = null;
      pendingPayload = null;
      failedMessage = "";
      ownTurn = data.turn_id;
      ownPayload = payload;
      if (data.status === "pending" || data.status === "running") {
        activeTurn = data.turn_id;
        polls = 0;
        failures = 0;
        truncated.hidden = !data.history_truncated;
        status.textContent = "Mentor đang suy nghĩ…";
        controls();
        schedule(token);
      } else if (data.status === "succeeded") {
        if (await loadSession(token)) {
          if (question.value === payload.question) {
            question.value = "";
            sizeQuestion();
          }
          ownTurn = null;
          ownPayload = null;
        }
      } else if (data.status === "failed") {
        failedMessage = explain(data.error_code);
        notify(failedMessage);
        status.textContent = "Mentor không thể trả lời lượt hỏi này.";
        ownTurn = null;
        ownPayload = null;
      } else {
        throw new Error("invalid_state");
      }
    } catch (error) {
      if (token !== generation || panel.hidden || error.name === "AbortError") return;
      if (error.http) {
        ambiguous = null;
        pendingPayload = null;
        notify(explain(error.code));
        if (["turn_in_progress", "idempotency_conflict"].includes(error.code) && refresh)
          refresh.hidden = false;
      } else {
        ambiguous = payload;
        pendingPayload = null;
        notify(
          "Chưa xác nhận được yêu cầu đã gửi. Hãy kiểm tra trạng thái hoặc gửi lại cùng yêu cầu; mã và mã định danh của lượt này được giữ nguyên.",
        );
        if (refresh) refresh.hidden = false;
      }
      status.textContent = "Chưa xác nhận được yêu cầu này.";
    } finally {
      if (token === generation) {
        submitting = false;
        controls();
      }
    }
  }

  if (form)
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (submitting || activeTurn || !available || ambiguous || inFlight) return;
      if (!question.value.trim()) {
        notify("Hãy nhập câu hỏi trước khi gửi Mentor.");
        question.focus();
        return;
      }
      var snapshot = editorSnapshot();
      if (!snapshot || snapshot.fileOnly) {
        notify(
          snapshot && snapshot.fileOnly
            ? explain("unsupported_language")
            : "Trình soạn thảo chưa sẵn sàng. Hãy mở trình soạn thảo và chọn ngôn ngữ.",
        );
        return;
      }
      var id = requestId();
      if (!id) {
        notify("Trình duyệt chưa tạo được mã định danh an toàn. Hãy tải lại trang và thử lại.");
        return;
      }
      sendTurn(
        {
          question: question.value,
          approach: "",
          current_code: snapshot.current_code,
          client_request_id: id,
          language_key: snapshot.language_key,
        },
        generation,
      );
    });

  if (form)
    question.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey) || event.shiftKey) return;
      event.preventDefault();
      if (!send.disabled) form.requestSubmit();
    });
  if (form) {
    question.addEventListener("input", sizeQuestion);
    sizeQuestion();
  }

  if (retry) {
    retry.addEventListener("click", function () {
      if (ambiguous && available && !activeTurn && !submitting && !inFlight)
        sendTurn(ambiguous, generation);
    });
  }

  if (refresh) {
    refresh.addEventListener("click", function () {
      if (inFlight) return;
      refresh.hidden = true;
      clearTimeout(timer);
      failures = 0;
      polls = 0;
      loadSession(generation);
    });
  }
  panel.addEventListener("mentor:open", function () {
    stop();
    status.textContent = "Đang tải hội thoại Mentor…";
    notify(failedMessage);
    if (refresh) refresh.hidden = true;
    loadSession(generation);
  });
  panel.addEventListener("mentor:close", stop);
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted && !panel.hidden) {
      stop();
      loadSession(generation);
    }
  });
})();

(function () {
  "use strict";

  var root = document.getElementById("ai-review");
  if (!root) return;
  var url = root.dataset.url,
    canRequest = root.dataset.canRequest === "true";
  var copy = root.querySelector(".ai-review-copy").dataset;
  var status = root.querySelector(".ai-review-status");
  var message = root.querySelector(".ai-review-message");
  var form = root.querySelector(".ai-review-form");
  var button = root.querySelector(".ai-review-request");
  var retryStatus = root.querySelector(".ai-review-retry-status");
  var result = root.querySelector(".ai-review-result");
  var feedback = root.querySelector(".ai-review-feedback");
  var heading = root.querySelector(".ai-review-approaches-heading");
  var approaches = root.querySelector(".ai-review-approaches");
  var pretest = root.querySelector(".ai-review-pretest");
  var unavailable = root.querySelector(".ai-review-unavailable");
  var isPretest = !!root.querySelector(".ai-review-is-pretest");
  var timer = null,
    inflight = null,
    closed = false,
    submitting = false;
  var polls = 0,
    errors = 0,
    maxPolls = 60;

  function reset() {
    clearTimeout(timer);
    timer = null;
    result.hidden = true;
    pretest.hidden = true;
    feedback.textContent = "";
    approaches.replaceChildren();
    heading.hidden = true;
    form.hidden = true;
    retryStatus.hidden = true;
    message.textContent = "";
  }

  function showButton(label) {
    form.hidden = !canRequest;
    button.disabled = !canRequest || submitting;
    button.textContent = label;
  }

  function errorMessage(code) {
    if (["daily_review_quota", "too_many_active_reviews", "rate_limited"].indexOf(code) !== -1)
      return copy.quota;
    if (code === "no_active_subscription") return copy.subscription;
    if (code === "contest_active") return copy.contest;
    if (
      [
        "judge_result_unsupported",
        "file_only_source",
        "text_statement_missing",
        "source_missing",
        "source_too_large",
        "text_statement_too_large",
        "unsupported_context",
        "problem_inaccessible",
      ].indexOf(code) !== -1
    )
      return copy.unsupported;
    if (
      [
        "timeout",
        "authentication_failed",
        "upstream_unavailable",
        "queue_unavailable",
        "review_unavailable",
      ].indexOf(code) !== -1
    )
      return copy.temporary;
    return copy.error;
  }

  function retryable(code) {
    return (
      canRequest &&
      [
        "daily_review_quota",
        "too_many_active_reviews",
        "no_active_subscription",
        "contest_active",
        "judge_result_unsupported",
        "file_only_source",
        "text_statement_missing",
        "source_missing",
        "source_too_large",
        "text_statement_too_large",
        "unsupported_context",
        "problem_inaccessible",
      ].indexOf(code) === -1
    );
  }

  function showUnavailable(text) {
    reset();
    status.textContent = copy.unavailable;
    message.textContent = text || unavailable.textContent.trim() || copy.unsupported;
  }

  function schedule() {
    if (closed) return;
    if (polls >= maxPolls) {
      message.textContent = copy.wait;
      retryStatus.hidden = false;
    } else timer = setTimeout(checkStatus, Math.min(3000 + polls * 250, 10000));
  }

  function render(data) {
    if (closed) return;
    reset();
    errors = 0;
    switch (data.status) {
      case "pending":
      case "running":
        status.textContent = data.status === "pending" ? copy.queued : copy.running;
        if (polls >= 8) message.textContent = copy.wait;
        schedule();
        break;
      case "succeeded":
        status.textContent = copy.complete;
        feedback.textContent = data.overall_feedback || "";
        (Array.isArray(data.approaches) ? data.approaches : []).forEach(function (item) {
          var li = document.createElement("li");
          var title = document.createElement("strong");
          var description = document.createElement("p");
          title.textContent = item.title || "";
          description.textContent = item.description || "";
          li.appendChild(title);
          li.appendChild(description);
          if (item.complexity || item.practicality) {
            var details = document.createElement("small");
            details.textContent = [item.complexity, item.practicality].filter(Boolean).join(" · ");
            li.appendChild(details);
          }
          approaches.appendChild(li);
        });
        heading.hidden = !approaches.children.length;
        result.hidden = false;
        pretest.hidden = !isPretest;
        break;
      case "failed":
        status.textContent = copy.failed;
        message.textContent = errorMessage(data.error_code);
        // Only a failed attempt may be retried; backend enforces quota and entitlement.
        if (retryable(data.error_code)) showButton(copy.retry);
        break;
      case "stale":
        status.textContent = copy.stale;
        message.textContent = copy.staleMessage;
        break;
      default:
        showUnavailable();
    }
  }

  function checkStatus() {
    if (closed || inflight) return;
    clearTimeout(timer);
    inflight = $.ajax({ url: url, type: "GET", dataType: "json", cache: false });
    inflight
      .done(function (data) {
        polls++;
        render(data);
      })
      .fail(function (xhr) {
        reset();
        if (xhr.status === 404) {
          if (unavailable.dataset.reason) showUnavailable();
          else if (canRequest) {
            status.textContent = "";
            showButton(copy.request);
          } else showUnavailable(copy.subscription);
          return;
        }
        if (xhr.status === 403) {
          showUnavailable();
          return;
        }
        errors++;
        message.textContent = copy.network;
        if (errors >= 3) retryStatus.hidden = false;
        else timer = setTimeout(checkStatus, Math.min(3000 * Math.pow(2, errors), 12000));
      })
      .always(function () {
        inflight = null;
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (submitting || !canRequest || closed) return;
    submitting = true;
    button.disabled = true;
    retryStatus.hidden = true;
    message.textContent = copy.queued;
    $.ajax({
      url: url,
      type: "POST",
      dataType: "json",
      headers: { "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value },
    })
      .done(function (data) {
        polls = 0;
        render(data);
      })
      .fail(function (xhr) {
        reset();
        status.textContent = copy.unavailable;
        if (xhr.responseJSON && xhr.responseJSON.error_code) {
          var code = xhr.responseJSON.error_code;
          message.textContent = errorMessage(code);
          // Rejected POST is not an active review; user can retry only on transient errors.
          if (
            canRequest &&
            ["queue_unavailable", "review_unavailable", "timeout"].indexOf(code) !== -1
          )
            showButton(copy.retry);
        } else {
          // The POST may have reached the server: check state before another call.
          message.textContent = copy.network;
          retryStatus.hidden = false;
        }
      })
      .always(function () {
        submitting = false;
        button.disabled = !canRequest;
      });
  });

  retryStatus.addEventListener("click", function () {
    retryStatus.hidden = true;
    polls = 0;
    errors = 0;
    message.textContent = copy.queued;
    checkStatus();
  });
  window.addEventListener("pagehide", function () {
    closed = true;
    clearTimeout(timer);
    if (inflight) inflight.abort();
  });
  window.addEventListener("pageshow", function (event) {
    if (event.persisted && closed) {
      closed = false;
      inflight = null;
      polls = 0;
      checkStatus();
    }
  });
  checkStatus();
})();

(function () {
  "use strict";

  var mountedRoots = typeof WeakMap !== "undefined" ? new WeakMap() : null;

  function mount(root) {
    if (!root) return null;
    if (mountedRoots && mountedRoots.has(root)) {
      return mountedRoots.get(root);
    }

    var url = root.dataset.url,
      canRequest = root.dataset.canRequest === "true";
    var copyNode = root.querySelector(".ai-review-copy");
    if (!copyNode) return null;
    var copy = copyNode.dataset;
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
      if (result) result.hidden = true;
      if (pretest) pretest.hidden = true;
      if (feedback) feedback.textContent = "";
      if (approaches) approaches.replaceChildren();
      if (heading) heading.hidden = true;
      if (form) form.hidden = true;
      if (retryStatus) retryStatus.hidden = true;
      if (message) message.textContent = "";
    }

    function showButton(label) {
      if (!form || !button) return;
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
      if (status) status.textContent = copy.unavailable;
      if (message) {
        var unavailText = unavailable ? unavailable.textContent.trim() : "";
        message.textContent = text || unavailText || copy.unsupported;
      }
    }

    function schedule() {
      if (closed) return;
      if (polls >= maxPolls) {
        if (message) message.textContent = copy.wait;
        if (retryStatus) retryStatus.hidden = false;
      } else timer = setTimeout(checkStatus, Math.min(3000 + polls * 250, 10000));
    }

    function render(data) {
      if (closed) return;
      reset();
      errors = 0;
      switch (data.status) {
        case "pending":
        case "running":
          if (status) status.textContent = data.status === "pending" ? copy.queued : copy.running;
          if (polls >= 8 && message) message.textContent = copy.wait;
          schedule();
          break;
        case "succeeded":
          if (status) status.textContent = copy.complete;
          if (feedback) feedback.textContent = data.overall_feedback || "";
          if (approaches) {
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
            if (heading) heading.hidden = !approaches.children.length;
          }
          if (result) result.hidden = false;
          if (pretest) pretest.hidden = !isPretest;
          break;
        case "failed":
          if (status) status.textContent = copy.failed;
          if (message) message.textContent = errorMessage(data.error_code);
          if (retryable(data.error_code)) showButton(copy.retry);
          break;
        case "stale":
          if (status) status.textContent = copy.stale;
          if (message) message.textContent = copy.staleMessage;
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
          if (closed) return;
          polls++;
          render(data);
        })
        .fail(function (xhr) {
          if (closed) return;
          reset();
          if (xhr.status === 404) {
            if (unavailable && unavailable.dataset.reason) showUnavailable();
            else if (canRequest) {
              if (status) status.textContent = "";
              showButton(copy.request);
            } else showUnavailable(copy.subscription);
            return;
          }
          if (xhr.status === 403) {
            showUnavailable();
            return;
          }
          errors++;
          if (message) message.textContent = copy.network;
          if (errors >= 3) {
            if (retryStatus) retryStatus.hidden = false;
          } else timer = setTimeout(checkStatus, Math.min(3000 * Math.pow(2, errors), 12000));
        })
        .always(function () {
          inflight = null;
        });
    }

    function onSubmit(event) {
      event.preventDefault();
      if (submitting || !canRequest || closed) return;
      submitting = true;
      if (button) button.disabled = true;
      if (retryStatus) retryStatus.hidden = true;
      if (message) message.textContent = copy.queued;
      var csrfInput = form ? form.querySelector("[name=csrfmiddlewaretoken]") : null;
      var csrfToken = csrfInput ? csrfInput.value : "";
      $.ajax({
        url: url,
        type: "POST",
        dataType: "json",
        headers: { "X-CSRFToken": csrfToken },
      })
        .done(function (data) {
          if (closed) return;
          polls = 0;
          render(data);
        })
        .fail(function (xhr) {
          if (closed) return;
          reset();
          if (status) status.textContent = copy.unavailable;
          if (xhr.responseJSON && xhr.responseJSON.error_code) {
            var code = xhr.responseJSON.error_code;
            if (message) message.textContent = errorMessage(code);
            if (
              canRequest &&
              ["queue_unavailable", "review_unavailable", "timeout"].indexOf(code) !== -1
            )
              showButton(copy.retry);
          } else {
            if (message) message.textContent = copy.network;
            if (retryStatus) retryStatus.hidden = false;
          }
        })
        .always(function () {
          submitting = false;
          if (button) button.disabled = !canRequest;
        });
    }

    function onRetry() {
      if (retryStatus) retryStatus.hidden = true;
      polls = 0;
      errors = 0;
      if (message) message.textContent = copy.queued;
      checkStatus();
    }

    function onPageHide() {
      closed = true;
      clearTimeout(timer);
      if (inflight) inflight.abort();
    }

    function onPageShow(event) {
      if (event.persisted && closed) {
        closed = false;
        inflight = null;
        polls = 0;
        checkStatus();
      }
    }

    if (form) form.addEventListener("submit", onSubmit);
    if (retryStatus) retryStatus.addEventListener("click", onRetry);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);

    function dispose() {
      // pagehide may have already closed polling; listener cleanup still runs.
      closed = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      if (inflight) {
        inflight.abort();
        inflight = null;
      }
      if (form) form.removeEventListener("submit", onSubmit);
      if (retryStatus) retryStatus.removeEventListener("click", onRetry);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
      if (mountedRoots) mountedRoots.delete(root);
    }
    dispose.dispose = dispose;

    if (mountedRoots) mountedRoots.set(root, dispose);

    checkStatus();

    return dispose;
  }

  window.MSOJAIReview = {
    mount: mount,
  };

  var autoRoot = document.getElementById("ai-review");
  if (autoRoot) {
    mount(autoRoot);
  }
})();

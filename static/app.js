(function () {
  "use strict";

  // ---------- theme ----------
  function applyTheme(mode) {
    var dark = mode === "dark" || (mode !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }
  function currentMode() {
    try { return localStorage.getItem("theme") || "auto"; } catch (e) { return "auto"; }
  }
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { applyTheme(currentMode()); });

  // ---------- clipboard ----------
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    var input = document.createElement("textarea");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.left = "-9999px";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    document.body.removeChild(input);
    return Promise.resolve();
  }

  function toast(message, kind) {
    var box = document.querySelector(".toasts");
    if (!box) {
      box = document.createElement("div");
      box.className = "toasts";
      document.body.appendChild(box);
    }
    var item = document.createElement("div");
    item.className = "toast " + (kind || "ok");
    item.innerHTML = '<svg class="icon"><use href="#i-' + (kind === "error" ? "alert" : "check") + '"/></svg><span></span>';
    item.querySelector("span").textContent = message;
    box.appendChild(item);
    dismissLater(item);
  }

  function dismissLater(item) {
    var delay = item.classList.contains("error") ? 8000 : 3500;
    setTimeout(function () {
      item.classList.add("hide");
      setTimeout(function () { item.remove(); }, 300);
    }, delay);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".toast").forEach(dismissLater);

    // theme toggle
    var themeBtn = document.querySelector("[data-theme-toggle]");
    if (themeBtn) {
      var labels = { auto: "跟随系统", light: "浅色", dark: "深色" };
      var order = ["auto", "light", "dark"];
      themeBtn.title = "主题：" + labels[currentMode()];
      themeBtn.addEventListener("click", function () {
        var next = order[(order.indexOf(currentMode()) + 1) % order.length];
        try { localStorage.setItem("theme", next); } catch (e) {}
        applyTheme(next);
        themeBtn.title = "主题：" + labels[next];
        toast("主题：" + labels[next]);
      });
    }

    // mobile nav
    document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () { document.body.classList.toggle("nav-open"); });
    });
    document.addEventListener("click", function (e) {
      if (document.body.classList.contains("nav-open") && !e.target.closest(".sidebar, [data-nav-toggle]")) {
        document.body.classList.remove("nav-open");
      }
    });
  });

  document.addEventListener("click", function (e) {
    // copy buttons: data-copy="text" or data-copy-target="#id"
    var copyBtn = e.target.closest("[data-copy], [data-copy-target]");
    if (copyBtn) {
      e.preventDefault();
      var text = copyBtn.dataset.copy;
      if (!text && copyBtn.dataset.copyTarget) {
        var el = document.querySelector(copyBtn.dataset.copyTarget);
        text = el ? (el.value || el.textContent) : "";
      }
      copyText(text).then(function () { toast(copyBtn.dataset.copyMessage || "已复制到剪贴板"); });
      return;
    }

    // check-all helpers: data-check="selector" data-check-value="true|false|toggle"
    var checkBtn = e.target.closest("[data-check]");
    if (checkBtn) {
      e.preventDefault();
      e.stopPropagation();
      var value = checkBtn.dataset.checkValue;
      document.querySelectorAll(checkBtn.dataset.check).forEach(function (box) {
        if (box.closest("[hidden]") || box.closest(".is-filtered")) return;
        box.checked = value === "toggle" ? !box.checked : value === "true";
      });
      document.dispatchEvent(new Event("selection-change"));
    }
  });

  // confirm prompts: <form data-confirm="..."> or <button data-confirm="...">
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var submitter = e.submitter;
    var message = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
    if (form.dataset.confirmAlt && form.querySelector("[data-confirm-switch]:checked")) {
      message = form.dataset.confirmAlt;
    }
    if (message && !window.confirm(message)) {
      e.preventDefault();
      return;
    }
    if (submitter && submitter.matches("[data-loading]")) {
      setTimeout(function () { submitter.classList.add("is-loading"); submitter.disabled = true; }, 0);
    }
  }, true);

  // live filter: <input data-filter="#scope"> filters [data-filter-item] by data-search / text
  document.addEventListener("input", function (e) {
    var input = e.target.closest("[data-filter]");
    if (!input) return;
    var scope = document.querySelector(input.dataset.filter);
    if (!scope) return;
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    scope.querySelectorAll("[data-filter-item]").forEach(function (item) {
      var hay = (item.dataset.search || item.textContent).toLowerCase();
      var match = !q || q.split(/\s+/).every(function (part) { return hay.indexOf(part) !== -1; });
      item.classList.toggle("is-filtered", !match);
      item.hidden = !match;
      if (match) shown++;
    });
    scope.querySelectorAll("[data-filter-group]").forEach(function (group) {
      var any = group.querySelector("[data-filter-item]:not([hidden])");
      group.hidden = !any;
      if (q && any) group.open = true;
    });
    var counter = document.querySelector(input.dataset.filterCount || "");
    if (counter) counter.textContent = shown;
    var empty = scope.querySelector("[data-filter-empty]");
    if (empty) empty.hidden = shown !== 0;
  });

  document.addEventListener("change", function (e) {
    if (e.target.matches("input[type=checkbox]")) {
      document.dispatchEvent(new Event("selection-change"));
    }
    var auto = e.target.closest("[data-autosubmit]");
    if (auto) auto.form.submit();
  });

  // keyboard: "/" focuses search
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !e.target.closest("input, textarea, select")) {
      var search = document.querySelector("[data-filter]");
      if (search) { e.preventDefault(); search.focus(); }
    }
    if (e.key === "Escape" && e.target.matches("[data-filter]")) {
      e.target.value = "";
      e.target.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });

  window.ProxyShare = { toast: toast, copyText: copyText };
})();

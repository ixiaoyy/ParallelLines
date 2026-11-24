/* 平行线第一方流量采集：只记录脱敏路径和显式动作，业务代码从不等待发送结果。 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__parallelLinesTrafficInstalled) return;
  var data = script.dataset;
  var site = data.site || (data.websiteId === "api" ? "api" : "");
  var hosts = {
    games: ["pingxingxian.space", "www.pingxingxian.space"],
    forum: ["forum.pingxingxian.space", "pingxingxian.space"],
    tools: ["tools.pingxingxian.space"],
    chat: ["chat.pingxingxian.space"],
    api: ["api.pingxingxian.space"]
  };
  var local = data.allowLocal === "true" && /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  if (!Object.prototype.hasOwnProperty.call(hosts, site) ||
      (!local && hosts[site].indexOf(location.hostname) === -1)) return;
  var endpoint;
  try {
    endpoint = new URL(data.endpoint || "https://pingxingxian.space/api/v1/site/traffic", location.href);
    if (!local && endpoint.href !== "https://pingxingxian.space/api/v1/site/traffic") return;
    if (local && !/^(localhost|127\.0\.0\.1)$/.test(endpoint.hostname)) return;
  } catch (_) { return; }
  window.__parallelLinesTrafficInstalled = true;

  // 先等待站点加载和空闲；不使用轮询、心跳、持久重试队列或业务请求拦截。
  function idle(callback) {
    if (window.requestIdleCallback) window.requestIdleCallback(callback, { timeout: 2000 });
    else window.setTimeout(callback, 1000);
  }
  if (document.readyState === "complete") idle(start);
  else window.addEventListener("load", function () { idle(start); }, { once: true });

  function start() {
    var queue = [];
    var timer = 0;
    var inFlight = false;
    var stopped = false;
    var lastRoute = "";
    var referrer = safeReferrer(document.referrer);
    var identity = null;

    function cookieText() {
      try { return document.cookie; }
      catch (_) { return null; } // 无法读取排除偏好时停止采集，不绕过浏览器策略。
    }

    function excluded() {
      var cookies = cookieText();
      return navigator.doNotTrack === "1" || navigator.msDoNotTrack === "1" ||
        navigator.globalPrivacyControl === true || navigator.webdriver === true ||
        cookies === null || /(?:^|;\s*)px_traffic_exclude=1(?:;|$)/.test(cookies);
    }

    // 共享的随机 cookie 没有登录或授权含义；不可用时明确降为站点/单页标识。
    function visitor() {
      var cookies = cookieText();
      if (cookies === null) return null;
      var match = cookies.match(/(?:^|;\s*)px_traffic_id=([a-f0-9-]{36})(?:;|$)/i);
      if (match) return { id: match[1], scope: local ? "site" : "shared" };
      var id = randomId();
      if (!id) return null;
      try {
        document.cookie = "px_traffic_id=" + id + "; Path=/; Max-Age=31536000; SameSite=Lax" +
          (local ? "" : "; Domain=pingxingxian.space; Secure");
        if (document.cookie.indexOf("px_traffic_id=" + id) !== -1)
          return { id: id, scope: local ? "site" : "shared" };
      } catch (_) { /* 禁用 cookie 时不尝试绕过浏览器限制。 */ }
      try {
        var saved = localStorage.getItem("parallellines.traffic_id.v1");
        if (saved && /^[a-f0-9-]{36}$/i.test(saved)) return { id: saved, scope: "site" };
        localStorage.setItem("parallellines.traffic_id.v1", id);
        return { id: id, scope: "site" };
      } catch (_) { return { id: id, scope: "ephemeral" }; }
    }

    function route() {
      var path = location.pathname;
      if (/^\/(?:admin|auth|account|messages|invites|moderation|design-system|forbidden|oauth|reset-password|workspace|new-topic|me|email-preferences)(?:\/|$)/.test(path)) return null;
      var key = site;
      if (site === "games") {
        if (/^\/(?:forum|boards|b|topics|members)(?:\/|$)/.test(path)) key = "forum";
        else if (/^\/tools(?:\/|$)/.test(path)) key = "tools";
      }
      if (key === "chat") {
        if (/^\/c\//.test(path)) path = "/c/:chat";
        else if (/^\/s\//.test(path)) path = "/s/:share";
        else if (path !== "/") return null;
      } else if (key === "api") {
        path = /^\/(?:console|pricing|about|status|token|topup|log|data)(?:\/|$)/.test(path)
          ? "/" + path.split("/")[1] : "/";
      } else if (key === "forum") {
        if (/^\/(?:topics|t)\//.test(path)) path = "/topics/:topic";
        else if (/^\/(?:members|users)\//.test(path)) path = "/members/:member";
        else if (/^\/(?:b|boards)\//.test(path)) path = "/boards/:board";
        else if (/^\/(?:space|journal|circles)\//.test(path)) path = "/space/:space";
        else path = path === "/" || path === "/forum" ? path : "/other";
      } else if (!/^\/[A-Za-z0-9/_-]{0,180}$/.test(path)) return null;
      return { site_key: key, path: path.replace(/\/$/, "") || "/" };
    }

    function append(name, pathOverride) {
      if (stopped || excluded()) { queue.length = 0; return; }
      var current = route();
      if (!current || queue.length >= 40) return;
      identity = identity || visitor();
      if (!identity) return;
      var id = randomId();
      if (!id) return;
      var event = {
        event_id: id, site_key: current.site_key, event_name: name,
        path: pathOverride || current.path, referrer: referrer,
        occurred_at: new Date().toISOString()
      };
      if (name === "page_view") {
        var campaign = new URLSearchParams(location.search).get("utm_source") || "";
        if (/^[A-Za-z0-9_.-]{1,80}$/.test(campaign)) event.campaign_source = campaign;
      }
      queue.push(event);
      if (queue.length >= 20) idle(flush);
      if (!timer) timer = window.setTimeout(function () { timer = 0; flush(); }, 30000);
    }

    function page() {
      var current = route();
      var key = current ? current.site_key + location.pathname : "";
      if (key && key !== lastRoute) append("page_view");
      lastRoute = key;
      referrer = safeReferrer(location.origin);
    }

    // 只从规范化动作白名单取值；不读取 DOM 文本、表单值、文件名或对话内容。
    window.addEventListener("pl:traffic", function (event) {
      var detail = event.detail;
      if (!detail) return;
      var current = route();
      if (!current) return;
      if (detail.event_name === "game_open" && current.site_key === "games" && site === "games" &&
          typeof detail.path === "string" && /^\/games\/[A-Za-z0-9_-]{1,80}$/.test(detail.path)) {
        append("game_open", detail.path);
      } else if (site === "tools" && (detail.event_name === "tool_download" || detail.event_name === "tool_copy")) {
        append(detail.event_name); // 工具动作只能使用当前规范路由，忽略外部传入的路径。
      }
    });
    document.addEventListener("click", function (event) {
      if (site !== "tools" || !event.isTrusted || !(event.target instanceof Element)) return;
      var button = event.target.closest("[data-traffic-action]");
      if (!button || button.disabled) return;
      var name = button.getAttribute("data-traffic-action");
      if (name === "tool_download" || name === "tool_copy") append(name);
    });
    window.addEventListener("pl:traffic-preference", function () {
      queue.length = 0;
      if (timer) { clearTimeout(timer); timer = 0; }
      if (!excluded()) { lastRoute = ""; page(); }
    });

    function flush() {
      if (!queue.length || inFlight || stopped || excluded()) {
        if (excluded()) queue.length = 0;
        return;
      }
      var events = queue.splice(0, 20);
      var body = JSON.stringify({ visitor_id: identity.id, identity_scope: identity.scope, events: events });
      // 离页也使用 keepalive fetch，明确 omit 凭据；Beacon 不能保证不带会话 Cookie。
      inFlight = true;
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 3000);
      fetch(endpoint.href, {
        method: "POST", body: body, headers: { "Content-Type": "text/plain;charset=UTF-8" },
        mode: "cors", credentials: "omit", referrerPolicy: "no-referrer",
        keepalive: true, signal: controller.signal
      }).then(function (response) {
        if (!response.ok) { stopped = true; queue.length = 0; }
      }).catch(function () {
        // 遥测尽力而为：失败后本页停发，业务无失败态，也不重复提交丢失的一批。
        stopped = true;
        queue.length = 0;
      }).finally(function () {
        clearTimeout(timeout);
        inFlight = false;
        if (queue.length && !stopped && !timer)
          timer = setTimeout(function () { timer = 0; flush(); }, 30000);
      });
    }

    // 保留原 history 返回值、this 和异常；只在成功导航后排一个微小空闲任务。
    ["pushState", "replaceState"].forEach(function (name) {
      var original = history[name];
      history[name] = function () {
        var result = original.apply(this, arguments);
        idle(page);
        return result;
      };
    });
    window.addEventListener("popstate", function () { idle(page); });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") flush();
    });
    window.addEventListener("pagehide", flush);
    page();
  }

  function randomId() {
    if (!window.crypto || !crypto.getRandomValues) return null;
    if (crypto.randomUUID) return crypto.randomUUID();
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.prototype.map.call(bytes, function (value) { return value.toString(16).padStart(2, "0"); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  function safeReferrer(value) {
    try { var parsed = new URL(value); return /^(http|https):$/.test(parsed.protocol) ? parsed.origin : null; }
    catch (_) { return null; }
  }
})();

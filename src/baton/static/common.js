"use strict";

// Shared by both management pages: CSRF-bound requests, status text and the storage badge.
window.baton = (() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const message = document.getElementById("message");

  function showMessage(text, kind = "") {
    message.textContent = text;
    message.className = `message ${kind}`;
  }

  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (options.method && options.method !== "GET") {
      headers.set("Content-Type", "application/json");
      headers.set("X-Baton-CSRF", csrfToken);
    }
    let response;
    try {
      response = await fetch(path, {
        ...options, headers, credentials: "same-origin", cache: "no-store", redirect: "error",
      });
    } catch (_error) {
      throw new Error("로컬 보관함 서버에 연결할 수 없습니다.");
    }
    if (response.status === 204) return null;
    let result;
    try {
      result = await response.json();
    } catch (_error) {
      throw new Error("서버 응답을 확인할 수 없습니다.");
    }
    if (!response.ok) throw new Error(result.error || "요청을 처리할 수 없습니다.");
    return result;
  }

  function renderStorageBadge(state) {
    const badge = document.getElementById("secure-badge");
    const notice = document.getElementById("storage-notice");
    const ready = Boolean(state.secure_storage_ready);
    badge.textContent = ready ? "보안 저장소 사용 가능" : "안전한 저장소 확인 필요";
    badge.className = `badge ${ready ? "badge-ready" : "badge-error"}`;
    notice.hidden = ready;
    notice.textContent = state.secure_storage_message || "운영체제 자격 증명 저장소를 사용할 수 없어 키 저장과 복호화가 중단됩니다.";
    return ready;
  }

  return { showMessage, request, renderStorageBadge };
})();

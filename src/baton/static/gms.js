"use strict";

(() => {
  const { showMessage, request, renderStorageBadge } = window.baton;
  let state = { folders: [], credentials: [], secure_storage_ready: false };
  const gmsSwitch = document.getElementById("gms-switch");
  const gmsSelect = document.getElementById("gms-credential");
  const gmsButton = document.getElementById("gms-check");
  const gmsResult = document.getElementById("gms-result");
  let gmsPending = false;
  let gmsRevision = 0;
  let gmsBudget = { policy: { enabled: false }, accounted_credits: 0, accounted_tokens: 0, held_credits: 0 };
  let gmsQuote = null;
  let quoteRevision = 0;
  const policyFields = {
    reserve_credits: "gms-reserve", max_total_credits: "gms-total-credits", max_total_tokens: "gms-total-tokens",
    max_input_tokens: "gms-max-input", max_output_tokens: "gms-max-output",
    expected_output_tokens: "gms-expected-output", max_call_credits: "gms-call-credits",
    max_count_credits: "gms-count-credits",
  };

  function clearQuote() {
    quoteRevision += 1;
    gmsQuote = null;
    document.getElementById("gms-execute").disabled = true;
    document.getElementById("gms-quote-result").textContent = "새 견적을 요청하세요.";
    document.getElementById("gms-work-result").textContent = "";
  }

  function updateReserveMinimum() {
    document.getElementById("gms-reserve").min =
      document.getElementById("gms-budget-mode").value === "reserve_only" ? "1000" : "0";
  }

  function renderPolicy() {
    const cumulative = gmsBudget.policy.budget_mode !== "reserve_only";
    document.getElementById("gms-budget-mode").value = gmsBudget.policy.budget_mode || "cumulative";
    updateReserveMinimum();
    for (const id of ["gms-total-credits", "gms-total-tokens", "gms-call-credits"]) {
      document.getElementById(id).disabled = !cumulative;
    }
    const workLimit = document.getElementById("gms-work-limit");
    const maxOutput = Number(gmsBudget.policy.max_output_tokens || 64);
    workLimit.max = String(maxOutput);
    workLimit.value = String(Math.min(Number(workLimit.value) || maxOutput, maxOutput));
    for (const [field, id] of Object.entries(policyFields)) {
      document.getElementById(id).value = gmsBudget.policy[field] ?? 0;
    }
    renderSwitch();
    const ledgerLabel = cumulative ? "이 앱의 누적 사용·예약" : "사용 기록 · 누적 차단 기준 아님";
    document.getElementById("gms-ledger").textContent = `${ledgerLabel} ${gmsBudget.accounted_credits.toLocaleString("ko-KR")}크레딧 / ${gmsBudget.accounted_tokens.toLocaleString("ko-KR")}토큰 · 보류 ${gmsBudget.held_credits.toLocaleString("ko-KR")}크레딧`;
  }

  async function refreshBudget() {
    gmsBudget = await request("/api/gms/state");
    renderPolicy();
    renderGMS();
  }

  function showBalance(balance) {
    const output = document.getElementById("gms-balance-result");
    if (!balance) { output.textContent = "최신 잔액을 확인하지 못했습니다. 다시 조회하세요."; return; }
    output.textContent = `잔여 ${balance.remain_credit.toLocaleString("ko-KR")} · 사용 ${balance.used_credit.toLocaleString("ko-KR")} · 전체 ${balance.total_credit.toLocaleString("ko-KR")}크레딧 | 만료 ${new Date(balance.expired_date).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST${balance.expired ? " (만료됨)" : ""} | 조회 ${new Date(balance.checked_at).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })}`;
  }

  function clearGMSResult() {
    gmsRevision += 1;
    gmsResult.textContent = "아직 확인하지 않았습니다. 선택한 키로 연결을 확인하세요.";
    gmsResult.className = "message";
    document.getElementById("gms-balance-result").textContent = "잔액을 조회하지 않았습니다.";
    clearQuote();
  }

  function renderGMS() {
    const previous = gmsSelect.value;
    gmsSelect.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "GMS 키를 직접 선택하세요";
    gmsSelect.append(placeholder);
    for (const key of state.credentials) {
      const option = document.createElement("option");
      option.value = key.id;
      option.textContent = `${key.alias} · ${key.folder_name}`;
      gmsSelect.append(option);
    }
    const selected = previous || gmsBudget.policy.credential_id || "";
    gmsSelect.value = state.credentials.some((key) => key.id === selected) ? selected : "";
    gmsSelect.disabled = gmsPending || !state.secure_storage_ready;
    gmsButton.disabled = gmsPending || !state.secure_storage_ready || !gmsSelect.value ||
      !gmsBudget.policy.enabled || gmsSelect.value !== gmsBudget.policy.credential_id;
    document.getElementById("gms-balance").disabled = gmsPending || !state.secure_storage_ready || !gmsSelect.value;
    document.getElementById("gms-execute").disabled = gmsPending || !gmsQuote;
  }

  function renderSwitch() {
    const enabled = Boolean(gmsBudget.policy.enabled);
    gmsSwitch.checked = enabled;
    gmsSwitch.disabled = gmsPending;
    document.getElementById("gms-switch-state").textContent = enabled
      ? "켜짐 · 저장한 한도 안에서 BATON 작업이 GMS를 사용할 수 있습니다."
      : "꺼짐 · BATON 작업은 GMS를 호출하지 않습니다. 직접 지정과 fallback 모두 차단됩니다.";
  }

  async function refresh() {
    clearGMSResult();
    state = await request("/api/state");
    renderStorageBadge(state);
    await refreshBudget();
  }

  gmsSwitch.addEventListener("change", async () => {
    const enabled = gmsSwitch.checked;
    gmsPending = true;
    renderGMS();
    gmsSwitch.disabled = true;
    clearQuote();
    try {
      gmsBudget = await request("/api/gms/enabled", { method: "POST", body: JSON.stringify({ enabled }) });
      showMessage(enabled ? "GMS를 켰습니다." : "GMS를 껐습니다.", "success-text");
    } catch (error) {
      showMessage(error.message, "error-text");
    } finally {
      gmsPending = false;
      renderPolicy();
      renderGMS();
    }
  });

  gmsSelect.addEventListener("change", () => {
    clearGMSResult();
    renderGMS();
  });

  document.getElementById("gms-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (gmsPending || !gmsSelect.value) return;
    const credentialId = gmsSelect.value;
    const revision = gmsRevision;
    gmsPending = true;
    renderGMS();
    gmsResult.textContent = "GMS 연결 확인 중… 시험 요청은 자동 재시도하지 않습니다.";
    try {
      const result = await request("/api/gms/check", {
        method: "POST", body: JSON.stringify({ credential_id: credentialId, confirm: true }),
      });
      if (revision !== gmsRevision) return;
      let details = "";
      if (result.usage && result.estimated_credits !== null) {
        details = ` 입력 ${result.usage.input_tokens} / 출력 ${result.usage.output_tokens}토큰 · 예상 ${result.estimated_credits.toLocaleString("ko-KR")}크레딧 사용.`;
      } else {
        details = " 사용량·비용은 확인되지 않았습니다.";
      }
      gmsResult.textContent = result.message + details;
      gmsResult.className = `message ${result.status === "available" ? "success-text" : "error-text"}`;
      showBalance(result.balance);
      await refreshBudget();
    } catch (error) {
      if (revision === gmsRevision) {
        gmsResult.textContent = error.message;
        gmsResult.className = "message error-text";
      }
    } finally {
      gmsPending = false;
      renderGMS();
    }
  });

  document.getElementById("gms-balance").addEventListener("click", async () => {
    if (gmsPending || !gmsSelect.value) return;
    const revision = gmsRevision;
    const credentialId = gmsSelect.value;
    gmsPending = true;
    renderGMS();
    try {
      const result = await request("/api/gms/balance", { method: "POST", body: JSON.stringify({ credential_id: credentialId }) });
      if (revision === gmsRevision) showBalance(result);
    } catch (error) {
      if (revision === gmsRevision) document.getElementById("gms-balance-result").textContent = error.message;
    } finally {
      gmsPending = false;
      renderGMS();
    }
  });

  document.getElementById("gms-policy-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (gmsPending || !gmsSelect.value) return;
    const values = { credential_id: gmsSelect.value, enabled: Boolean(gmsBudget.policy.enabled),
      budget_mode: document.getElementById("gms-budget-mode").value };
    for (const [field, id] of Object.entries(policyFields)) values[field] = Number(document.getElementById(id).value);
    clearQuote();
    try {
      gmsBudget = await request("/api/gms/policy", { method: "POST", body: JSON.stringify(values) });
      renderPolicy();
      renderGMS();
      document.getElementById("gms-policy-result").textContent = "한도를 저장했습니다. 누적 사용량은 유지됩니다. 모델 생성은 하지 않았습니다.";
    } catch (error) {
      document.getElementById("gms-policy-result").textContent = error.message;
    }
  });

  document.getElementById("gms-work-form").addEventListener("input", clearQuote);
  document.getElementById("gms-policy-form").addEventListener("input", clearQuote);
  document.getElementById("gms-budget-mode").addEventListener("change", updateReserveMinimum);
  document.getElementById("gms-work-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (gmsPending) return;
    if (gmsSelect.value !== gmsBudget.policy.credential_id) {
      showMessage("작업에 사용할 키를 선택하고 그 키의 한도를 먼저 저장하세요.", "error-text"); return;
    }
    clearQuote();
    const revision = quoteRevision;
    gmsPending = true;
    renderGMS();
    document.getElementById("gms-quote-result").textContent = "실잔액과 전체 입력 토큰을 확인하는 중…";
    try {
      const quote = await request("/api/gms/quote", {
        method: "POST", body: JSON.stringify({task_id: document.getElementById("gms-task-id").value,
          objective: document.getElementById("gms-objective").value, context: document.getElementById("gms-context").value,
          difficulty: document.getElementById("gms-difficulty").value,
          max_output_tokens: Number(document.getElementById("gms-work-limit").value)}),
      });
      if (revision !== quoteRevision) return;
      gmsQuote = quote;
      document.getElementById("gms-quote-result").textContent = `${quote.model} · 입력/출력 ${quote.input_rate}/${quote.output_rate}크레딧/토큰 | 입력 ${quote.input_tokens} · 예상 출력 ${quote.expected_output_tokens} · 최대 출력 ${quote.max_output_tokens}토큰 | 카운트 조회 ${quote.count_credits}크레딧 | 조회 포함 예상 ${quote.estimated_credits} · 최대 ${quote.maximum_credits}크레딧 (생성 예약 ${quote.generation_maximum_credits}) | 120초 유효`;
      showBalance(quote.balance);
      await refreshBudget();
    } catch (error) {
      if (revision === quoteRevision) document.getElementById("gms-quote-result").textContent = error.message;
    } finally {
      gmsPending = false;
      renderGMS();
    }
  });

  document.getElementById("gms-execute").addEventListener("click", async () => {
    if (gmsPending || !gmsQuote) return;
    const quote = gmsQuote;
    const revision = quoteRevision;
    gmsQuote = null;
    gmsPending = true;
    renderGMS();
    try {
      const result = await request("/api/gms/execute", { method: "POST", body: JSON.stringify({quote_id: quote.quote_id, confirm: true}) });
      if (revision === quoteRevision) {
        document.getElementById("gms-work-result").textContent = result.text || result.message;
        document.getElementById("gms-quote-result").textContent = `${result.message} ${result.usage ? `실사용 입력 ${result.usage.input_tokens} / 출력 ${result.usage.output_tokens}토큰 · ${result.estimated_credits}크레딧` : "사용량 미확인 · 최대 비용 보류"}`;
        showBalance(result.balance);
      }
      await refreshBudget();
    } catch (error) {
      document.getElementById("gms-work-result").textContent = error.message;
    } finally {
      gmsPending = false;
      renderGMS();
    }
  });

  refresh().catch((error) => showMessage(error.message, "error-text"));
})();

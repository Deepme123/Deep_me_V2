    const THEME_STORAGE_KEY = "emotion-demo-theme";
    const CARD_LABELS = {
      summary: "요약",
      core_emotions: "핵심 감정",
      situation: "상황",
      emotion: "감정",
      thoughts: "생각",
      physical_reactions: "신체 반응",
      behaviors: "행동",
      coping_actions: "대처 행동",
      insight: "통찰",
      tags: "태그",
      risk_flag: "위험 신호",
      risk_level: "위험도",
      exportable: "내보내기 가능",
    };

    const EVENT_META = {
      open_ok: {
        title: "연결 준비 완료",
        describe: (payload) => payload.session_id
          ? `세션 ${payload.session_id}가 준비되었습니다. 바로 메시지를 보낼 수 있습니다.`
          : "대화 세션 연결이 준비되었습니다.",
      },
      message_start: {
        title: "응답 생성 시작",
        describe: () => "AI가 응답 생성을 시작했습니다.",
      },
      message_delta: {
        title: "응답 스트리밍 중",
        describe: (payload) => payload.delta
          ? `실시간으로 응답 조각을 수신했습니다.`
          : "실시간 응답 조각을 수신했습니다.",
      },
      message_end: {
        title: "응답 스트리밍 종료",
        describe: () => "스트리밍 응답 전송이 마무리되었습니다.",
      },
      message: {
        title: "AI 응답 완료",
        describe: (payload) => payload.message
          ? "한 턴의 AI 응답이 완성되어 대화 내역에 반영되었습니다."
          : "한 턴의 AI 응답이 완료되었습니다.",
      },
      suggest_close: {
        title: "세션 종료 제안 도착",
        describe: () => "대화를 마무리해도 좋다는 신호가 도착했습니다.",
      },
      close_ok: {
        title: "세션 종료 완료",
        describe: () => "세션 종료 요청이 정상적으로 처리되었습니다.",
      },
      cancel_close_ok: {
        title: "종료 취소 완료",
        describe: () => "종료 제안이 취소되어 대화를 이어갈 수 있습니다.",
      },
      analysis_card_status: {
        title: "분석 카드 생성 중",
        describe: () => "분석 카드를 준비하는 중입니다.",
      },
      analysis_card_ready: {
        title: "분석 카드 생성 완료",
        describe: () => "대화를 바탕으로 분석 카드가 생성되어 화면과 저장 영역을 갱신합니다.",
      },
      analysis_card_failed: {
        title: "분석 카드 생성 실패",
        describe: (payload) => payload.message
          ? `분석 카드 생성 중 문제가 발생했습니다: ${payload.message}`
          : "분석 카드 생성 중 문제가 발생했습니다.",
      },
      task_recommend_ok: {
        title: "추천 작업 생성 완료",
        describe: () => "후속 작업 추천 결과가 준비되었습니다.",
      },
      limit: {
        title: "세션 제한 도달",
        describe: (payload) => payload.message || "대화 제한에 도달했습니다.",
      },
      error: {
        title: "오류 응답",
        describe: (payload) => payload.message || "오류 메시지를 수신했습니다.",
      },
      raw: {
        title: "원본 메시지 수신",
        describe: () => "JSON으로 해석되지 않은 원본 메시지를 그대로 기록했습니다.",
      },
      send_failed: {
        title: "메시지 전송 실패",
        describe: (payload) => payload.message || "메시지 전송에 실패했습니다.",
      },
      copy_failed: {
        title: "대화 복사 실패",
        describe: (payload) => payload.message || "대화 복사 중 문제가 발생했습니다.",
      },
    };

    const state = {
      ws: null,
      sessionId: null,
      connected: false,
      conversationHistory: [],
      copyFeedbackTimer: null,
    };

    const $ = (id) => document.getElementById(id);
    const els = {
      wsUrl: $("wsUrl"),
      accessToken: $("accessToken"),
      connectBtn: $("connectBtn"),
      disconnectBtn: $("disconnectBtn"),
      resetBtn: $("resetBtn"),
      sendBtn: $("sendBtn"),
      closeOnlyBtn: $("closeOnlyBtn"),
      confirmCloseBtn: $("confirmCloseBtn"),
      loadCardsBtn: $("loadCardsBtn"),
      messageInput: $("messageInput"),
      copyConversationBtn: $("copyConversationBtn"),
      themeToggleBtn: $("themeToggleBtn"),
      connectionState: $("connectionState"),
      sessionIdLabel: $("sessionIdLabel"),
      conversationFeed: $("conversationFeed"),
      eventTimeline: $("eventTimeline"),
      analysisCard: $("analysisCard"),
      savedCards: $("savedCards"),
    };

    function defaultWsUrl() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      return `${proto}://${window.location.host}/ws/emotion`;
    }

    function nowStamp() {
      return new Date().toLocaleTimeString("ko-KR", { hour12: false });
    }

    function formatTimestamp(value) {
      if (!value) return "정보 없음";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return String(value);
      return parsed.toLocaleString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    function getStoredTheme() {
      try {
        const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
        return stored === "light" || stored === "dark" ? stored : null;
      } catch {
        return null;
      }
    }

    function getPreferredTheme() {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function updateThemeToggle(theme) {
      els.themeToggleBtn.textContent = theme === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환";
      els.themeToggleBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }

    function applyTheme(theme) {
      document.documentElement.dataset.theme = theme;
      updateThemeToggle(theme);
    }

    function initializeTheme() {
      applyTheme(getStoredTheme() || getPreferredTheme());
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
        if (getStoredTheme()) return;
        applyTheme(event.matches ? "dark" : "light");
      });
    }

    function toggleTheme() {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      } catch {
        // Ignore storage failures and still apply the chosen theme for this session.
      }
      applyTheme(nextTheme);
    }

    function conversationRoleLabel(role) {
      if (role === "user") return "사용자";
      if (role === "assistant") return "AI";
      return role;
    }

    function formatDisplayValue(value) {
      if (Array.isArray(value)) {
        return value.length ? value.join(", ") : "";
      }
      if (typeof value === "boolean") {
        return value ? "예" : "아니오";
      }
      if (value && typeof value === "object") {
        return JSON.stringify(value, null, 2);
      }
      return value == null ? "" : String(value);
    }

    function cardFieldLabel(key) {
      return CARD_LABELS[key] || key.replaceAll("_", " ");
    }

    function getCardEntries(card) {
      if (!card) return [];
      return Object.entries(card)
        .map(([key, value]) => [key, formatDisplayValue(value)])
        .filter(([, value]) => value && String(value).trim());
    }

    function buildMetricGrid(grid, entries) {
      entries.forEach(([key, value]) => {
        const metric = document.createElement("section");
        metric.className = "metric";
        metric.innerHTML = `
          <p class="metric-label">${cardFieldLabel(key)}</p>
          <p class="metric-value"></p>
        `;
        metric.querySelector(".metric-value").textContent = value;
        grid.appendChild(metric);
      });
    }

    function buildMetaPill(label, value) {
      const pill = document.createElement("span");
      pill.className = "meta-pill";
      pill.innerHTML = `<strong>${label}</strong><span></span>`;
      pill.querySelector("span").textContent = value;
      return pill;
    }

    function getRiskLevelLabel(level) {
      const riskLabels = {
        low: "낮음",
        medium: "보통",
        high: "높음",
      };
      return riskLabels[level] || (level ? String(level) : "정보 없음");
    }

    function getEventMeta(payload) {
      const meta = EVENT_META[payload.type] || {
        title: "기타 이벤트",
        describe: () => "정의되지 않은 이벤트를 수신했습니다.",
      };
      return {
        title: meta.title,
        description: meta.describe(payload),
      };
    }

    function setConnectionState(label, stateName) {
      els.connectionState.textContent = label;
      els.connectionState.dataset.state = stateName;
    }

    function setInteractiveState(connected) {
      state.connected = connected;
      els.connectBtn.disabled = connected;
      els.disconnectBtn.disabled = !connected;
      els.sendBtn.disabled = !connected;
      els.closeOnlyBtn.disabled = !connected;
      els.confirmCloseBtn.disabled = !connected;
      els.loadCardsBtn.disabled = !state.sessionId;
    }

    function clearNode(node, emptyHtml) {
      node.innerHTML = "";
      node.classList.remove("scroll-region");
      if (emptyHtml) {
        node.innerHTML = emptyHtml;
      }
    }

    function syncScrollRegion(node, itemSelector) {
      const count = node.querySelectorAll(itemSelector).length;
      node.classList.toggle("scroll-region", count > 5);
      if (count > 5) {
        node.scrollTop = node.scrollHeight;
      }
    }

    function appendConversation(role, text) {
      if (!text) return;
      const time = nowStamp();
      state.conversationHistory.push({ role, text, time });
      if (els.conversationFeed.querySelector(".empty")) {
        clearNode(els.conversationFeed);
      }
      const item = document.createElement("article");
      item.className = "bubble";
      item.innerHTML = `
        <div class="bubble-head">
          <span class="bubble-role">${conversationRoleLabel(role)}</span>
          <span class="bubble-time">${time}</span>
        </div>
        <p class="bubble-text"></p>
      `;
      item.querySelector(".bubble-text").textContent = text;
      els.conversationFeed.appendChild(item);
      syncScrollRegion(els.conversationFeed, ".bubble");
    }

    function appendEvent(payload) {
      if (els.eventTimeline.querySelector(".empty")) {
        clearNode(els.eventTimeline);
      }
      const eventMeta = getEventMeta(payload);
      const item = document.createElement("article");
      item.className = "event";
      item.innerHTML = `
        <div class="event-head">
          <div>
            <p class="event-title">${eventMeta.title}</p>
            <p class="event-sub">${payload.type || "unknown"}</p>
          </div>
          <span class="event-time">${nowStamp()}</span>
        </div>
        <p class="event-description"></p>
        <details class="event-details">
          <summary>원본 데이터 보기</summary>
          <pre></pre>
        </details>
      `;
      item.querySelector(".event-description").textContent = eventMeta.description;
      item.querySelector("pre").textContent = JSON.stringify(payload, null, 2);
      els.eventTimeline.appendChild(item);
      syncScrollRegion(els.eventTimeline, ".event");
    }

    function renderAnalysisCard(card) {
      if (!card) return;
      clearNode(els.analysisCard);
      const wrapper = document.createElement("div");
      wrapper.className = "saved-card";

      const sections = getCardEntries(card);

      const summary = card.summary || "요약이 비어 있습니다.";
      wrapper.innerHTML = `
        <div class="card-header">
          <div class="bubble-head">
            <span class="bubble-role">분석 카드 생성 완료</span>
            <span class="bubble-time">${nowStamp()}</span>
          </div>
          <div class="meta-row"></div>
        </div>
        <p class="card-summary"></p>
        <div class="card-grid"></div>
      `;
      wrapper.querySelector(".card-summary").textContent = summary;
      wrapper.querySelector(".meta-row").appendChild(buildMetaPill("상태", "분석 완료"));

      const grid = wrapper.querySelector(".card-grid");
      buildMetricGrid(grid, sections.filter(([label]) => label !== "summary"));
      els.analysisCard.appendChild(wrapper);
    }

    function renderSavedCards(cards) {
      clearNode(els.savedCards);
      if (!Array.isArray(cards) || cards.length === 0) {
        els.savedCards.innerHTML = '<div class="empty">저장된 카드가 아직 없습니다.</div>';
        return;
      }
      cards.forEach((card, index) => {
        const item = document.createElement("article");
        item.className = "saved-card";
        const sections = getCardEntries(card).filter(([key]) => !["summary", "created_at", "session_id", "card_id"].includes(key));
        const summary = formatDisplayValue(card.summary) || "저장된 카드 요약이 없습니다.";
        item.innerHTML = `
          <div class="card-header">
            <div class="bubble-head">
              <span class="bubble-role">저장 카드 ${index + 1}</span>
              <span class="bubble-time">${formatTimestamp(card.created_at)}</span>
            </div>
            <div class="meta-row"></div>
          </div>
          <p class="card-summary"></p>
          <div class="card-grid"></div>
          <details class="event-details">
            <summary>원본 JSON 보기</summary>
            <pre class="json"></pre>
          </details>
        `;
        item.querySelector(".card-summary").textContent = summary;
        const metaRow = item.querySelector(".meta-row");
        metaRow.appendChild(buildMetaPill("카드 ID", formatDisplayValue(card.card_id) || "정보 없음"));
        metaRow.appendChild(buildMetaPill("세션 ID", formatDisplayValue(card.session_id) || "정보 없음"));
        metaRow.appendChild(buildMetaPill("위험도", getRiskLevelLabel(card.risk_level)));
        metaRow.appendChild(buildMetaPill("내보내기", card.exportable === false ? "불가" : "가능"));
        buildMetricGrid(item.querySelector(".card-grid"), sections);
        item.querySelector(".json").textContent = JSON.stringify(card, null, 2);
        els.savedCards.appendChild(item);
      });
    }

    function rememberSession(sessionId) {
      if (!sessionId) return;
      state.sessionId = sessionId;
      els.sessionIdLabel.textContent = sessionId;
      els.loadCardsBtn.disabled = false;
    }

    function sendJson(payload) {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        throw new Error("WebSocket is not connected");
      }
      state.ws.send(JSON.stringify(payload));
    }

    async function copyToClipboard(text) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
      }

      const temp = document.createElement("textarea");
      temp.value = text;
      temp.setAttribute("readonly", "readonly");
      temp.style.position = "fixed";
      temp.style.opacity = "0";
      document.body.appendChild(temp);
      temp.select();
      document.execCommand("copy");
      document.body.removeChild(temp);
    }

    function formatConversationForCopy() {
      return state.conversationHistory
        .map(({ role, text, time }) => {
          return `[${conversationRoleLabel(role)}] ${time}\n${text}`;
        })
        .join("\n\n");
    }

    function updateCopyButtonLabel(label) {
      if (!els.copyConversationBtn) return;
      els.copyConversationBtn.textContent = label;
      if (state.copyFeedbackTimer) {
        window.clearTimeout(state.copyFeedbackTimer);
        state.copyFeedbackTimer = null;
      }
      if (label !== "대화 복사") {
        state.copyFeedbackTimer = window.setTimeout(() => {
          els.copyConversationBtn.textContent = "대화 복사";
          state.copyFeedbackTimer = null;
        }, 1800);
      }
    }

    async function copyConversation() {
      if (state.conversationHistory.length === 0) {
        updateCopyButtonLabel("복사할 대화 없음");
        return;
      }

      try {
        await copyToClipboard(formatConversationForCopy());
        updateCopyButtonLabel("복사 완료");
      } catch (error) {
        updateCopyButtonLabel("복사 실패");
        appendEvent({
          type: "copy_failed",
          message: String(error.message || error),
        });
      }
    }

    function handleEvent(payload) {
      appendEvent(payload);
      if (payload.type === "open_ok") {
        rememberSession(payload.session_id);
        setConnectionState("연결됨", "connected");
      }
      if (payload.type === "message") {
        appendConversation("assistant", payload.message || "");
      }
      if (payload.type === "close_ok") {
        setConnectionState("세션 종료", "closed");
      }
      if (payload.type === "analysis_card_ready") {
        renderAnalysisCard(payload.card || {});
        void loadCards();
      }
      if (payload.type === "analysis_card_failed") {
        clearNode(els.analysisCard, `<div class="empty">분석 카드 생성에 실패했습니다.\n${payload.message || ""}</div>`);
      }
    }

    async function loadCards() {
      if (!state.sessionId) return;
      try {
        const response = await fetch(`/analyze/api/sessions/${state.sessionId}/cards`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const cards = await response.json();
        renderSavedCards(cards);
      } catch (error) {
        clearNode(els.savedCards, `<div class="empty">카드 조회 실패: ${String(error.message || error)}</div>`);
      }
    }

    function connect() {
      if (state.ws) {
        state.ws.close();
      }
      const token = els.accessToken.value.trim();
      const url = new URL(els.wsUrl.value.trim() || defaultWsUrl(), window.location.href);
      if (token) {
        url.searchParams.set("access_token", token);
      }

      setConnectionState("연결 중", "working");
      const ws = new WebSocket(url.toString());
      state.ws = ws;

      ws.onopen = () => {
        setInteractiveState(true);
        setConnectionState("대기 중", "working");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleEvent(payload);
        } catch {
          appendEvent({ type: "raw", data: event.data });
        }
      };

      ws.onerror = () => {
        setConnectionState("오류 발생", "closed");
      };

      ws.onclose = (event) => {
        setInteractiveState(false);
        state.ws = null;
        if (!state.sessionId) {
          setConnectionState(`연결 종료 (${event.code})`, "closed");
        }
      };
    }

    function disconnect() {
      if (state.ws) {
        state.ws.close(1000, "manual_disconnect");
      }
      setInteractiveState(false);
      setConnectionState("연결 종료", "closed");
    }

    function resetScreen() {
      disconnect();
      state.sessionId = null;
      state.conversationHistory = [];
      els.sessionIdLabel.textContent = "없음";
      els.loadCardsBtn.disabled = true;
      updateCopyButtonLabel("대화 복사");
      clearNode(els.conversationFeed, '<div class="empty">아직 대화가 없습니다. 연결한 뒤 메시지를 보내 보세요.</div>');
      clearNode(els.eventTimeline, '<div class="empty">이벤트가 여기에 쌓입니다.</div>');
      clearNode(els.analysisCard, '<div class="empty">아직 분석 카드가 생성되지 않았습니다.</div>');
      clearNode(els.savedCards, '<div class="empty">세션이 끝나면 저장 카드 조회 버튼으로 결과를 확인할 수 있습니다.</div>');
    }

    function submitMessage() {
      const text = els.messageInput.value.trim();
      if (!text) return;
      try {
        sendJson({ type: "message", text });
        appendConversation("user", text);
        els.messageInput.value = "";
        els.messageInput.focus();
      } catch (error) {
        appendEvent({
          type: "send_failed",
          message: String(error.message || error),
          text,
        });
        els.messageInput.focus();
      }
    }

    els.connectBtn.addEventListener("click", connect);
    els.disconnectBtn.addEventListener("click", disconnect);
    els.resetBtn.addEventListener("click", resetScreen);
    els.sendBtn.addEventListener("click", submitMessage);
    els.copyConversationBtn.addEventListener("click", () => {
      void copyConversation();
    });
    els.themeToggleBtn.addEventListener("click", toggleTheme);
    els.messageInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey) return;
      event.preventDefault();
      submitMessage();
    });
    els.closeOnlyBtn.addEventListener("click", () => sendJson({ type: "close" }));
    els.confirmCloseBtn.addEventListener("click", () => sendJson({ type: "confirm_close" }));
    els.loadCardsBtn.addEventListener("click", loadCards);
    document.querySelectorAll(".preset-btn").forEach((button) => {
      button.addEventListener("click", () => {
        els.messageInput.value = button.dataset.text || "";
        els.messageInput.focus();
      });
    });

    els.wsUrl.value = defaultWsUrl();
    initializeTheme();
    setInteractiveState(false);

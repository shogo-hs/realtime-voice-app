const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusLabel = document.getElementById("statusLabel");
const logList = document.getElementById("logList");

let lastLogId = 0;
let pollingTimer = null;

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return await response.json();
}

function setStatusLabel(state) {
  const statusMap = {
    idle: "待機中",
    starting: "初期化中",
    connecting: "接続中...",
    completed: "完了",
    stopping: "停止中...",
    stopped: "停止",
    error: "エラー",
  };
  statusLabel.textContent = statusMap[state] || state;
}

function appendLog(entry) {
  const item = document.createElement("div");
  item.className = "log-entry";
  const time = new Date(entry.timestamp * 1000);
  const timeLabel = time.toLocaleTimeString([], { hour12: false });
  item.textContent = `[${timeLabel}] ${entry.message}`;
  logList.appendChild(item);
  logList.scrollTop = logList.scrollHeight;
}

function pushLocalLog(message) {
  appendLog({ timestamp: Date.now() / 1000, message });
}

async function pollLogs() {
  try {
    const data = await fetchJSON(`/api/logs?after=${lastLogId}`);
    data.logs.forEach((entry) => {
      lastLogId = Math.max(lastLogId, entry.id);
      appendLog(entry);
    });
  } catch (error) {
    console.warn("ログの取得に失敗しました", error);
  }
}

async function refreshStatus() {
  try {
    const data = await fetchJSON("/api/session/status");
    setStatusLabel(data.state);
    if (data.running) {
      startBtn.disabled = true;
      stopBtn.disabled = false;
    } else {
      startBtn.disabled = false;
      stopBtn.disabled = true;
    }
  } catch (error) {
    console.warn("ステータス取得エラー", error);
  }
}

async function startSession() {
  startBtn.disabled = true;
  pushLocalLog("🎤 接続を開始します...");
  try {
    const result = await fetchJSON("/api/session/start", { method: "POST" });
    if (!result.ok) {
      pushLocalLog("⚠️ 既にセッションが実行中です");
    }
    await refreshStatus();
  } catch (error) {
    pushLocalLog(`❌ 起動失敗: ${error.message}`);
    startBtn.disabled = false;
  }
}

async function stopSession() {
  stopBtn.disabled = true;
  pushLocalLog("🛑 停止要求を送信");
  try {
    await fetchJSON("/api/session/stop", { method: "POST" });
    await refreshStatus();
  } catch (error) {
    pushLocalLog(`⚠️ 停止エラー: ${error.message}`);
    stopBtn.disabled = false;
  }
}

function init() {
  startBtn.addEventListener("click", startSession);
  stopBtn.addEventListener("click", stopSession);

  pollingTimer = setInterval(() => {
    pollLogs();
    refreshStatus();
  }, 1200);

  pollLogs();
  refreshStatus();
}

window.addEventListener("DOMContentLoaded", init);

const DEFAULT_GATEWAY = "https://rivalradar-api-fl5j.onrender.com";

const form = document.getElementById("form");
const codeEl = document.getElementById("code");
const platformEl = document.getElementById("platform");
const gatewayEl = document.getElementById("gateway");
const statusEl = document.getElementById("status");
const goBtn = document.getElementById("go");

chrome.storage.local.get(["gatewayUrl", "lastPlatform"], (data) => {
  gatewayEl.value = data.gatewayUrl || DEFAULT_GATEWAY;
  if (data.lastPlatform) platformEl.value = data.lastPlatform;
});

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const code = codeEl.value.trim().toUpperCase();
  const platform = platformEl.value;
  const gatewayUrl = gatewayEl.value.trim().replace(/\/$/, "") || DEFAULT_GATEWAY;

  statusEl.className = "";
  statusEl.textContent = "Reading cookies…";
  goBtn.disabled = true;

  chrome.storage.local.set({ gatewayUrl, lastPlatform: platform });

  chrome.runtime.sendMessage(
    { type: "QUICK_CONNECT", platform, code, gatewayUrl, workspaceId: "default" },
    (res) => {
      goBtn.disabled = false;
      if (chrome.runtime.lastError) {
        statusEl.className = "err";
        statusEl.textContent = chrome.runtime.lastError.message;
        return;
      }
      if (!res?.ok) {
        statusEl.className = "err";
        statusEl.textContent = res?.error || "Connect failed";
        return;
      }
      statusEl.className = "ok";
      statusEl.textContent = `${platform} connected — return to RivalRadar.`;
    },
  );
});

// options.js — Settings page for server URL configuration and offline queue viewer

document.addEventListener("DOMContentLoaded", async () => {
  const serverUrlInput = document.getElementById("serverUrl",);
  const autoTagCheckbox = document.getElementById("autoTag",);
  const saveBtn = document.getElementById("save-btn",);
  const saveStatus = document.getElementById("save-status",);
  const queueList = document.getElementById("queue-list",);
  const failedSection = document.getElementById("failed-section",);
  const failedList = document.getElementById("failed-list",);
  const retryAllBtn = document.getElementById("retry-all-btn",);
  const pendingCount = document.getElementById("pending-count",);
  const failedCount = document.getElementById("failed-count",);

  // Load settings from background
  const { settings, } = await chrome.runtime.sendMessage({ action: "getSettings", },);
  serverUrlInput.value = settings?.serverUrl || "http://127.0.0.1:8765";
  autoTagCheckbox.checked = settings?.autoTag !== false; // Default true

  // Render queue with retry/remove controls
  async function renderQueue() {
    const { queue, } = await chrome.runtime.sendMessage({ action: "getQueue", },);
    if (!queue || queue.length === 0) {
      queueList.innerHTML = "<div class=\"queue-empty\">No pending bookmarks</div>";
      pendingCount.textContent = "0";
      return;
    }

    pendingCount.textContent = String(queue.length,);

    queueList.innerHTML = queue
      .map(
        (item, idx,) => `
      <div class="queue-item">
        <div class="url">${escapeHtml(item.url,)}</div>
        <div class="meta">
          <span>${escapeHtml(item.title || "Untitled",)}</span>
          <span>•</span>
          <span>${new Date(item.enqueuedAt || item.timestamp,).toLocaleString()}</span>
          <span>•</span>
          <span>Attempts: ${item.attempts || 0}</span>
          <div class="queue-actions">
            <button class="retry-btn" data-idx="${idx}">Retry</button>
            <button class="remove-btn" data-idx="${idx}">Remove</button>
          </div>
        </div>
      </div>
    `,
      )
      .join("",);

    queueList.querySelectorAll(".retry-btn",).forEach((btn,) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        await chrome.runtime.sendMessage({ action: "retryNow", },);
        await renderQueue();
      },);
    },);

    queueList.querySelectorAll(".remove-btn",).forEach((btn,) => {
      btn.addEventListener("click", async () => {
        const idx = Number(btn.dataset.idx,);
        await chrome.runtime.sendMessage({ action: "removeQueueItem", index: idx, },);
        await renderQueue();
      },);
    },);
  }

  // Render failed queue
  async function renderFailedQueue() {
    const { failedQueue, } = await chrome.runtime.sendMessage({ action: "getFailedQueue", },);
    if (!failedQueue || failedQueue.length === 0) {
      failedSection.style.display = "none";
      failedCount.textContent = "0";
      return;
    }

    failedSection.style.display = "block";
    failedCount.textContent = String(failedQueue.length,);

    failedList.innerHTML = failedQueue
      .map(
        (item, idx,) => `
      <div class="failed-item">
        <div class="url">${escapeHtml(item.url,)}</div>
        <div class="meta">
          <span>${escapeHtml(item.title || "Untitled",)}</span>
          <span>•</span>
          <span>Failed: ${new Date(item.failedAt,).toLocaleString()}</span>
          <span>•</span>
          <span>Attempts: ${item.attempts || 5}</span>
          <button class="remove-btn" data-idx="${idx}">Remove</button>
        </div>
      </div>
    `,
      )
      .join("",);

    failedList.querySelectorAll(".remove-btn",).forEach((btn,) => {
      btn.addEventListener("click", async () => {
        const idx = Number(btn.dataset.idx,);
        await chrome.runtime.sendMessage({ action: "removeFailedItem", index: idx, },);
        await renderFailedQueue();
      },);
    },);
  }

  function escapeHtml(str,) {
    const div = document.createElement("div",);
    div.textContent = str;
    return div.innerHTML;
  }

  await renderQueue();
  await renderFailedQueue();

  // Save settings
  saveBtn.addEventListener("click", async () => {
    const settings = {
      serverUrl: serverUrlInput.value.trim() || "http://127.0.0.1:8765",
      autoTag: autoTagCheckbox.checked,
    };

    try {
      await chrome.runtime.sendMessage({ action: "saveSettings", settings, },);
      saveStatus.textContent = "Settings saved!";
      saveStatus.className = "success";
    } catch (err) {
      saveStatus.textContent = `Error: ${err.message}`;
      saveStatus.className = "error";
    }

    setTimeout(() => {
      saveStatus.textContent = "";
      saveStatus.className = "";
    }, 3000,);
  },);

  // Retry all queued bookmarks
  retryAllBtn.addEventListener("click", async () => {
    retryAllBtn.disabled = true;
    retryAllBtn.textContent = "Retrying...";
    await chrome.runtime.sendMessage({ action: "retryNow", },);
    await renderQueue();
    await renderFailedQueue();
    retryAllBtn.disabled = false;
    retryAllBtn.textContent = "Retry All Now";
  },);
},);

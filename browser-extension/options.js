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
  /**
   * Shared renderer for the pending-queue and failed-queue sections.
   * @param {object} cfg - Section configuration.
   * @param {HTMLElement} cfg.listEl - List container element.
   * @param {HTMLElement} cfg.countEl - Element displaying the item count.
   * @param {HTMLElement|null} cfg.sectionEl - Section wrapper; hidden when empty.
   * @param {string} cfg.action - Background message action (e.g. "getQueue").
   * @param {string} cfg.responseKey - Key on the response holding the items array.
   * @param {string} cfg.emptyText - Text shown when the list is empty.
   * @param {string} cfg.itemClass - CSS class for each rendered item row.
   * @param {(item: object) => string} cfg.renderMeta - Returns the inner meta HTML for an item.
   * @param {Array<{className: string, label: string, messageAction: string}>} cfg.buttons - Buttons to attach to each item.
   */
  async function renderQueueSection(cfg,) {
    const {
      listEl,
      countEl,
      sectionEl,
      action,
      responseKey,
      emptyText,
      itemClass,
      renderMeta,
      buttons,
    } = cfg;
    const response = await chrome.runtime.sendMessage({ action, },);
    const items = response?.[responseKey] || [];

    if (items.length === 0) {
      if (sectionEl) sectionEl.style.display = "none";
      else listEl.innerHTML = `<div class="queue-empty">${emptyText}</div>`;
      countEl.textContent = "0";
      return;
    }

    if (sectionEl) sectionEl.style.display = "block";
    countEl.textContent = String(items.length,);

    listEl.innerHTML = items
      .map(
        (item, idx,) => `
      <div class="${itemClass}">
        <div class="url">${escapeHtml(item.url,)}</div>
        <div class="meta">
          ${renderMeta(item,)}
          <div class="queue-actions">
            ${buttons.map((b,) => `<button class="${b.className}" data-idx="${idx}">${b.label}</button>`).join("",)}
          </div>
        </div>
      </div>
    `,
      )
      .join("",);

    for (const b of buttons) {
      listEl.querySelectorAll(`.${b.className}`,).forEach((btn,) => {
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          const idx = Number(btn.dataset.idx,);
          await chrome.runtime.sendMessage({ action: b.messageAction, index: idx, },);
          await renderQueueSection(cfg,);
        },);
      },);
    }
  }

  const pendingCfg = {
    listEl: queueList,
    countEl: pendingCount,
    sectionEl: null,
    action: "getQueue",
    responseKey: "queue",
    emptyText: "No pending bookmarks",
    itemClass: "queue-item",
    renderMeta: (item,) => `
          <span>${escapeHtml(item.title || "Untitled",)}</span>
          <span>•</span>
          <span>${new Date(item.enqueuedAt || item.timestamp,).toLocaleString()}</span>
          <span>•</span>
          <span>Attempts: ${item.attempts || 0}</span>
        `,
    buttons: [
      { className: "retry-btn", label: "Retry", messageAction: "retryNow", },
      { className: "remove-btn", label: "Remove", messageAction: "removeQueueItem", },
    ],
  };

  const failedCfg = {
    listEl: failedList,
    countEl: failedCount,
    sectionEl: failedSection,
    action: "getFailedQueue",
    responseKey: "failedQueue",
    emptyText: "",
    itemClass: "failed-item",
    renderMeta: (item,) => `
          <span>${escapeHtml(item.title || "Untitled",)}</span>
          <span>•</span>
          <span>Failed: ${new Date(item.failedAt,).toLocaleString()}</span>
          <span>•</span>
          <span>Attempts: ${item.attempts || 5}</span>
        `,
    buttons: [
      { className: "remove-btn", label: "Remove", messageAction: "removeFailedItem", },
    ],
  };

  await renderQueueSection(pendingCfg,);
  await renderQueueSection(failedCfg,);

  function escapeHtml(str,) {
    const div = document.createElement("div",);
    div.textContent = str;
    return div.innerHTML;
  }

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
    await renderQueueSection(pendingCfg,);
    await renderQueueSection(failedCfg,);
    retryAllBtn.disabled = false;
    retryAllBtn.textContent = "Retry All Now";
  },);
},);

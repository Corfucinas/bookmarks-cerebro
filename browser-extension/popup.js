async function updateQueueCount(queueCountEl, queueResult,) {
  if (queueResult?.queue?.length > 0) {
    queueCountEl.textContent = `Queue: ${queueResult.queue.length} pending`;
    queueCountEl.style.display = "block";
  } else {
    queueCountEl.style.display = "none";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const urlEl = document.getElementById("url",);
  const btn = document.getElementById("cerebro-btn",);
  const status = document.getElementById("status",);
  const queueCountEl = document.getElementById("queue-count",);
  const dupWarningEl = document.getElementById("dup-warning",);
  const settingsLink = document.getElementById("settings-link",);

  const [tab,] = await chrome.tabs.query({ active: true, currentWindow: true, },);
  const tabUrl = tab?.url || "";
  const tabTitle = tab?.title || "";

  urlEl.textContent = tabUrl || "No active tab";

  // Check duplicate against local cache
  const dupResult = await chrome.runtime.sendMessage({
    action: "checkDuplicate",
    url: tabUrl,
    title: tabTitle,
  },);
  if (dupResult?.duplicate) {
    dupWarningEl.style.display = "block";
  }

  // Show offline queue count
  await updateQueueCount(queueCountEl, await chrome.runtime.sendMessage({ action: "getQueue", },),);

  // Extract metadata from content script (inject if not present)
  let metadata = {};
  try {
    const [response,] = await chrome.tabs.sendMessage(tab.id, { action: "extractMetadata", },);
    metadata = response || {};
  } catch (e) {
    console.error("Content script communication failed:", e,);
    await chrome.scripting.executeScript({
      target: { tabId: tab.id, },
      files: ["content.js",],
    },);
    const [response,] = await chrome.tabs.sendMessage(tab.id, { action: "extractMetadata", },);
    metadata = response || {};
  }

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    status.textContent = "Sending...";
    status.className = "";

    const payload = {
      url: tabUrl,
      title: tabTitle,
      description: metadata.description || "",
      selectedText: metadata.selectedText || "",
    };

    try {
      const result = await chrome.runtime.sendMessage({ action: "ingest", payload, },);

      if (result?.duplicate) {
        status.textContent = "⚠️ Already bookmarked (sent anyway)";
        status.className = "warning";
      } else if (result?.success) {
        status.textContent = `✅ Added to ${result.data?.category || "vault"}`;
        status.className = "success";
      } else {
        status.textContent = `⏳ Queued for retry (${result?.error || "offline"})`;
        status.className = "queued";
      }
    } catch (err) {
      status.textContent = `❌ ${err.message}`;
      status.className = "error";
    } finally {
      btn.disabled = false;
      // Refresh queue count
      await updateQueueCount(queueCountEl, await chrome.runtime.sendMessage({ action: "getQueue", },),);
    }
  },);

  settingsLink.addEventListener("click", (e,) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  },);
},);

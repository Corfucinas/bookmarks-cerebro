// background.js — Manifest V3 service worker for Bookmarks Cerebro
// Handles offline queue, exponential backoff retries, context menus,
// keyboard shortcuts, duplicate detection, settings, and message passing.

const DEFAULT_SETTINGS = { serverUrl: "http://127.0.0.1:8765", autoTag: true, };
const QUEUE_KEY = "pending_queue";
const FAILED_QUEUE_KEY = "failed_queue";
const BOOKMARKED_IDS_KEY = "bookmarkedIds";
const SETTINGS_KEY = "settings";
const MAX_ATTEMPTS = 5;

// ------------------------------------------------------------------
// Settings helpers
// ------------------------------------------------------------------
async function getSettings() {
  const result = await chrome.storage.local.get(SETTINGS_KEY,);
  return { ...DEFAULT_SETTINGS, ...(result[SETTINGS_KEY] || {}), };
}

async function saveSettings(settings,) {
  await chrome.storage.local.set({ [SETTINGS_KEY]: settings, },);
}

// ------------------------------------------------------------------
// ID generation (mirrors Python: sha256(f"{url}::{title}")[:16])
// ------------------------------------------------------------------
async function computeId(url, title,) {
  const encoder = new TextEncoder();
  const data = encoder.encode(`${url}::${title}`,);
  const buf = await crypto.subtle.digest("SHA-256", data,);
  const arr = Array.from(new Uint8Array(buf,),);
  return arr.map((b,) => b.toString(16,).padStart(2, "0",)).join("",).slice(0, 16,);
}

// ------------------------------------------------------------------
// Queue management (chrome.storage.local)
// ------------------------------------------------------------------
async function getQueue() {
  const result = await chrome.storage.local.get(QUEUE_KEY,);
  return result[QUEUE_KEY] || [];
}

async function setQueue(queue,) {
  await chrome.storage.local.set({ [QUEUE_KEY]: queue, },);
  await updateBadge();
}

async function getFailedQueue() {
  const result = await chrome.storage.local.get(FAILED_QUEUE_KEY,);
  return result[FAILED_QUEUE_KEY] || [];
}

async function setFailedQueue(queue,) {
  await chrome.storage.local.set({ [FAILED_QUEUE_KEY]: queue, },);
}

async function enqueueBookmark(bookmark,) {
  const queue = await getQueue();
  const item = {
    ...bookmark,
    enqueuedAt: Date.now(),
    attempts: 0,
    nextRetryAt: Date.now(),
  };
  queue.push(item,);
  await setQueue(queue,);
  return item;
}

async function removeFromQueue(index,) {
  const queue = await getQueue();
  if (index >= 0 && index < queue.length) {
    queue.splice(index, 1,);
    await setQueue(queue,);
  }
}

async function moveToFailedQueue(item,) {
  const failedQueue = await getFailedQueue();
  failedQueue.push({
    ...item,
    failedAt: Date.now(),
  },);
  await setFailedQueue(failedQueue,);
}

async function updateBadge() {
  const queue = await getQueue();
  const text = queue.length > 0 ? String(queue.length,) : "";
  await chrome.action.setBadgeText({ text, },);
  await chrome.action.setBadgeBackgroundColor({ color: "#dc2626", },);
}

// ------------------------------------------------------------------
// Exponential backoff calculation
// ------------------------------------------------------------------
function calculateBackoffDelay(attempts,) {
  // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 60s)
  const baseDelay = 1000;
  const maxDelay = 60000;
  return Math.min(baseDelay * Math.pow(2, attempts,), maxDelay,);
}

// ------------------------------------------------------------------
// Duplicate detection (local cache of successfully sent IDs)
// ------------------------------------------------------------------
async function isDuplicate(url, title,) {
  const id = await computeId(url, title,);
  const result = await chrome.storage.local.get(BOOKMARKED_IDS_KEY,);
  const ids = result[BOOKMARKED_IDS_KEY] || {};
  return ids[id] === true;
}

async function markAsBookmarked(url, title,) {
  const id = await computeId(url, title,);
  const result = await chrome.storage.local.get(BOOKMARKED_IDS_KEY,);
  const ids = result[BOOKMARKED_IDS_KEY] || {};
  ids[id] = true;
  await chrome.storage.local.set({ [BOOKMARKED_IDS_KEY]: ids, },);
}

// ------------------------------------------------------------------
// Server ingest (single bookmark POST)
// ------------------------------------------------------------------
async function ingestBookmark(payload,) {
  const settings = await getSettings();
  const url = `${settings.serverUrl}/api/ingest`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", },
      body: JSON.stringify(payload,),
    },);

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`,);
    const data = await resp.json();
    await markAsBookmarked(payload.url, payload.title,);
    return { success: true, data, };
  } catch (err) {
    return { success: false, error: err.message, };
  }
}

// ------------------------------------------------------------------
// Retry queue processing (called by alarm + online event)
// ------------------------------------------------------------------
async function drainQueue() {
  const queue = await getQueue();
  if (queue.length === 0) return;

  const now = Date.now();
  const remaining = [];

  for (const item of queue) {
    // Skip items not yet ready for retry
    if (item.nextRetryAt > now) {
      remaining.push(item,);
      continue;
    }

    // Check if max attempts exceeded
    if (item.attempts >= MAX_ATTEMPTS) {
      await moveToFailedQueue(item,);
      continue;
    }

    const result = await ingestBookmark(item,);
    if (result.success) {
      // Successfully sent, don't add to remaining
    } else {
      // Increment attempts and apply backoff
      const newAttempts = (item.attempts || 0) + 1;
      const delay = calculateBackoffDelay(newAttempts,);

      remaining.push({
        ...item,
        attempts: newAttempts,
        nextRetryAt: now + delay,
      },);
    }
  }

  await setQueue(remaining,);
}

// ------------------------------------------------------------------
// Context menus
// ------------------------------------------------------------------
chrome.runtime.onInstalled.addListener(() => {
  // Create context menus
  chrome.contextMenus.create({
    id: "cerebro-page",
    title: "Cerebro this page",
    contexts: ["page",],
  },);
  chrome.contextMenus.create({
    id: "cerebro-link",
    title: "Cerebro this link",
    contexts: ["link",],
  },);
  chrome.contextMenus.create({
    id: "cerebro-selection",
    title: "Cerebro this selection",
    contexts: ["selection",],
  },);

  // Retry alarm every 1 minute
  chrome.alarms.create("drainQueue", { periodInMinutes: 1, },);

  // Seed default settings
  chrome.storage.local.get(SETTINGS_KEY, (result,) => {
    if (!result[SETTINGS_KEY]) {
      chrome.storage.local.set({ [SETTINGS_KEY]: DEFAULT_SETTINGS, },);
    }
  },);
},);

chrome.contextMenus.onClicked.addListener(async (info, tab,) => {
  let payload = { url: "", title: "", };

  if (info.menuItemId === "cerebro-page") {
    payload = { url: tab.url, title: tab.title, };
  } else if (info.menuItemId === "cerebro-link") {
    payload = { url: info.linkUrl, title: info.linkUrl, };
  } else if (info.menuItemId === "cerebro-selection") {
    payload = {
      url: tab.url,
      title: tab.title,
      selectedText: info.selectionText,
    };
  }

  if (!payload.url) return;

  // Best-effort link-text extraction for link context menu
  if (info.menuItemId === "cerebro-link" && tab.id) {
    try {
      const [{ result, },] = await chrome.scripting.executeScript({
        target: { tabId: tab.id, },
        func: (linkUrl,) => {
          const links = Array.from(document.querySelectorAll("a",),);
          const match = links.find((a,) => a.href === linkUrl);
          return match ? match.textContent?.trim() || match.innerText?.trim() : "";
        },
        args: [info.linkUrl,],
      },);
      if (result) payload.title = result;
    } catch {
      // Ignore injection failures
    }
  }

  const dup = await isDuplicate(payload.url, payload.title,);
  const result = await ingestBookmark(payload,);
  if (!result.success) {
    await enqueueBookmark(payload,);
  }

  // Brief badge flash for duplicate warning on background actions
  if (dup) {
    await chrome.action.setBadgeText({ text: "DUP", },);
    await chrome.action.setBadgeBackgroundColor({ color: "#ca8a04", },);
    setTimeout(() => updateBadge(), 2000,);
  }
},);

// ------------------------------------------------------------------
// Keyboard shortcuts (chrome.commands)
// ------------------------------------------------------------------
chrome.commands.onCommand.addListener(async (command,) => {
  if (command !== "cerebro-page") return;

  const [tab,] = await chrome.tabs.query({ active: true, currentWindow: true, },);
  if (!tab?.id) return;

  let payload = { url: tab.url, title: tab.title, };

  // Extract metadata via injected function
  try {
    const [{ result: meta, },] = await chrome.scripting.executeScript({
      target: { tabId: tab.id, },
      func: () => {
        const desc = document.querySelector(
          "meta[name=\"description\"], meta[property=\"og:description\"]",
        );
        const sel = window.getSelection().toString();
        return {
          description: desc?.getAttribute("content",) || "",
          selectedText: sel ? sel.slice(0, 500,) : "",
        };
      },
    },);
    if (meta) {
      payload.description = meta.description;
      payload.selectedText = meta.selectedText;
    }
  } catch {
    // Ignore injection errors
  }

  const dup = await isDuplicate(payload.url, payload.title,);
  const result = await ingestBookmark(payload,);
  if (!result.success) {
    await enqueueBookmark(payload,);
  }

  if (dup) {
    await chrome.action.setBadgeText({ text: "DUP", },);
    await chrome.action.setBadgeBackgroundColor({ color: "#ca8a04", },);
    setTimeout(() => updateBadge(), 2000,);
  }
},);

// ------------------------------------------------------------------
// Retry alarm
// ------------------------------------------------------------------
chrome.alarms.onAlarm.addListener((alarm,) => {
  if (alarm.name === "drainQueue") {
    drainQueue();
  }
},);

// ------------------------------------------------------------------
// Online event — attempt immediate retry when connectivity returns
// ------------------------------------------------------------------
self.addEventListener("online", () => {
  drainQueue();
},);

// ------------------------------------------------------------------
// Message passing hub (popup ↔ background, options ↔ background)
// ------------------------------------------------------------------
chrome.runtime.onMessage.addListener((request, _sender, sendResponse,) => {
  (async () => {
    try {
      switch (request.action) {
        case "ingest": {
          const dup = await isDuplicate(request.payload.url, request.payload.title,);
          const result = await ingestBookmark(request.payload,);
          if (!result.success) {
            await enqueueBookmark(request.payload,);
          }
          sendResponse({ ...result, duplicate: dup, },);
          break;
        }
        case "getQueue": {
          const queue = await getQueue();
          sendResponse({ queue, },);
          break;
        }
        case "getFailedQueue": {
          const failedQueue = await getFailedQueue();
          sendResponse({ failedQueue, },);
          break;
        }
        case "removeQueueItem": {
          await removeFromQueue(request.index,);
          sendResponse({ success: true, },);
          break;
        }
        case "removeFailedItem": {
          const failedQueue = await getFailedQueue();
          if (request.index >= 0 && request.index < failedQueue.length) {
            failedQueue.splice(request.index, 1,);
            await setFailedQueue(failedQueue,);
          }
          sendResponse({ success: true, },);
          break;
        }
        case "getSettings": {
          const settings = await getSettings();
          sendResponse({ settings, },);
          break;
        }
        case "saveSettings": {
          await saveSettings(request.settings,);
          sendResponse({ success: true, },);
          break;
        }
        case "checkDuplicate": {
          const dup = await isDuplicate(request.url, request.title,);
          sendResponse({ duplicate: dup, },);
          break;
        }
        case "retryNow": {
          await drainQueue();
          sendResponse({ success: true, },);
          break;
        }
        case "getQueueStats": {
          const queue = await getQueue();
          const failedQueue = await getFailedQueue();
          sendResponse({
            pending: queue.length,
            failed: failedQueue.length,
          },);
          break;
        }
        default:
          sendResponse({ error: "Unknown action", },);
      }
    } catch (err) {
      sendResponse({ error: err.message, },);
    }
  })();
  return true; // Keep channel open for async
},);

// Initialize badge on startup
updateBadge();

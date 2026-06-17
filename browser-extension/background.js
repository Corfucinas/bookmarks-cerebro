// background.js — Manifest V3 service worker for Bookmarks Cerebro
// Handles offline queue, exponential backoff retries, context menus,
// keyboard shortcuts, duplicate detection, settings, and message passing.

/* global chrome, self, crypto, document, window */

function getChromeApi() {
  return typeof globalThis.chrome !== "undefined" ? globalThis.chrome : null;
}

const DEFAULT_SETTINGS = { serverUrl: "http://127.0.0.1:8765", autoTag: true, };
const QUEUE_KEY = "pending_queue";
const FAILED_QUEUE_KEY = "failed_queue";
const BOOKMARKED_IDS_KEY = "bookmarkedIds";
const SETTINGS_KEY = "settings";
const MAX_ATTEMPTS = 5;

// ------------------------------------------------------------------
// Settings helpers
// ------------------------------------------------------------------
export async function getSettings() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return { ...DEFAULT_SETTINGS, };
  const result = await chromeApi.storage.local.get(SETTINGS_KEY,);
  return { ...DEFAULT_SETTINGS, ...(result[SETTINGS_KEY] || {}), };
}

export async function saveSettings(settings,) {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  await chromeApi.storage.local.set({ [SETTINGS_KEY]: settings, },);
}

// ------------------------------------------------------------------
// ID generation (mirrors Python: sha256(f"{url}::{title}")[:16])
// ------------------------------------------------------------------
export async function computeId(url, title,) {
  const encoder = new TextEncoder();
  const data = encoder.encode(`${url}::${title}`,);
  const buf = await crypto.subtle.digest("SHA-256", data,);
  const arr = Array.from(new Uint8Array(buf,),);
  return arr.map((b,) => b.toString(16,).padStart(2, "0",)).join("",).slice(0, 16,);
}

// ------------------------------------------------------------------
// Queue management (chrome.storage.local)
// ------------------------------------------------------------------
export async function getQueue() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return [];
  const result = await chromeApi.storage.local.get(QUEUE_KEY,);
  return result[QUEUE_KEY] || [];
}

export async function setQueue(queue,) {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  await chromeApi.storage.local.set({ [QUEUE_KEY]: queue, },);
  await updateBadge();
}

export async function getFailedQueue() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return [];
  const result = await chromeApi.storage.local.get(FAILED_QUEUE_KEY,);
  return result[FAILED_QUEUE_KEY] || [];
}

export async function setFailedQueue(queue,) {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  await chromeApi.storage.local.set({ [FAILED_QUEUE_KEY]: queue, },);
}

export async function enqueueBookmark(bookmark,) {
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

export async function removeFromQueue(index,) {
  const queue = await getQueue();
  if (index >= 0 && index < queue.length) {
    queue.splice(index, 1,);
    await setQueue(queue,);
  }
}

export async function moveToFailedQueue(item,) {
  const failedQueue = await getFailedQueue();
  failedQueue.push({
    ...item,
    failedAt: Date.now(),
  },);
  await setFailedQueue(failedQueue,);
}

export async function updateBadge() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  const queue = await getQueue();
  const text = queue.length > 0 ? String(queue.length,) : "";
  await chromeApi.action.setBadgeText({ text, },);
  await chromeApi.action.setBadgeBackgroundColor({ color: "#dc2626", },);
}

// ------------------------------------------------------------------
// Exponential backoff calculation
// ------------------------------------------------------------------
export function calculateBackoffDelay(attempts,) {
  // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 60s)
  const baseDelay = 1000;
  const maxDelay = 60000;
  return Math.min(baseDelay * Math.pow(2, attempts,), maxDelay,);
}

// ------------------------------------------------------------------
// Duplicate detection (local cache of successfully sent IDs)
// ------------------------------------------------------------------
export async function isDuplicate(url, title,) {
  const chromeApi = getChromeApi();
  if (!chromeApi) return false;
  const id = await computeId(url, title,);
  const result = await chromeApi.storage.local.get(BOOKMARKED_IDS_KEY,);
  const ids = result[BOOKMARKED_IDS_KEY] || {};
  return ids[id] === true;
}

export async function markAsBookmarked(url, title,) {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  const id = await computeId(url, title,);
  const result = await chromeApi.storage.local.get(BOOKMARKED_IDS_KEY,);
  const ids = result[BOOKMARKED_IDS_KEY] || {};
  ids[id] = true;
  await chromeApi.storage.local.set({ [BOOKMARKED_IDS_KEY]: ids, },);
}

// ------------------------------------------------------------------
// Server ingest (single bookmark POST)
// ------------------------------------------------------------------
export async function ingestBookmark(payload,) {
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
// Ingest with offline-queue fallback (dedup → ingest → enqueue)
// ------------------------------------------------------------------
export async function ingestWithFallback(payload,) {
  const dup = await isDuplicate(payload.url, payload.title,);
  const result = await ingestBookmark(payload,);
  if (!result.success) {
    await enqueueBookmark(payload,);
  }
  return { result, dup, };
}

// ------------------------------------------------------------------
// Flash the badge amber to signal a duplicate was detected
// ------------------------------------------------------------------
export async function flashDuplicateBadge() {
  const api = getChromeApi();
  if (!api) return;
  await api.action.setBadgeText({ text: "DUP", },);
  await api.action.setBadgeBackgroundColor({ color: "#ca8a04", },);
  setTimeout(() => {
    updateBadge().catch((e,) => console.error("Badge reset failed:", e,));
  }, 2000,);
}

// ------------------------------------------------------------------
// Retry queue processing (called by alarm + online event)
// ------------------------------------------------------------------
export async function drainQueue() {
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
function setupContextMenus() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;
  // Create context menus
  chromeApi.contextMenus.create({
    id: "cerebro-page",
    title: "Cerebro this page",
    contexts: ["page",],
  },);
  chromeApi.contextMenus.create({
    id: "cerebro-link",
    title: "Cerebro this link",
    contexts: ["link",],
  },);
  chromeApi.contextMenus.create({
    id: "cerebro-selection",
    title: "Cerebro this selection",
    contexts: ["selection",],
  },);

  // Retry alarm every 1 minute
  chromeApi.alarms.create("drainQueue", { periodInMinutes: 1, },);

  // Seed default settings
  chromeApi.storage.local.get(SETTINGS_KEY, (result,) => {
    if (!result[SETTINGS_KEY]) {
      chromeApi.storage.local.set({ [SETTINGS_KEY]: DEFAULT_SETTINGS, },);
    }
  },);
}

async function handleContextMenuClick(info, tab,) {
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
  if (info.menuItemId === "cerebro-link" && tab.id && getChromeApi()) {
    try {
      const [{ result, },] = await getChromeApi().scripting.executeScript({
        target: { tabId: tab.id, },
        func: (linkUrl,) => {
          const links = Array.from(document.querySelectorAll("a",),);
          const match = links.find((a,) => a.href === linkUrl);
          return match ? match.textContent?.trim() || match.innerText?.trim() : "";
        },
        args: [info.linkUrl,],
      },);
      if (result) payload.title = result;
    } catch (e) {
      console.error("Script injection failed:", e,);
    }
  }

  const { dup, } = await ingestWithFallback(payload,);

  if (dup) await flashDuplicateBadge();
}

// ------------------------------------------------------------------
// Keyboard shortcuts (chrome.commands)
// ------------------------------------------------------------------
async function handleCommand(command,) {
  if (command !== "cerebro-page") return;

  const chromeApi = getChromeApi();
  const [tab,] = await chromeApi.tabs.query({ active: true, currentWindow: true, },);
  if (!tab?.id) return;

  let payload = { url: tab.url, title: tab.title, };

  // Extract metadata via injected function
  try {
    const [{ result: meta, },] = await chromeApi.scripting.executeScript({
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
  } catch (e) {
    console.error("Metadata extraction failed:", e,);
  }

  const { dup, } = await ingestWithFallback(payload,);

  if (dup) await flashDuplicateBadge();
}

// ------------------------------------------------------------------
// Message passing hub (popup ↔ background, options ↔ background)
// ------------------------------------------------------------------
async function handleMessage(request, _sender, sendResponse,) {
  try {
    switch (request.action) {
      case "ingest": {
        const { result, dup, } = await ingestWithFallback(request.payload,);
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
}

// ------------------------------------------------------------------
// Browser-only registration (guarded so tests can import this module)
// ------------------------------------------------------------------
if (getChromeApi()?.runtime?.onInstalled) {
  getChromeApi().runtime.onInstalled.addListener(() => {
    setupContextMenus();
  },);
}

export function registerBrowserListeners() {
  const chromeApi = getChromeApi();
  if (!chromeApi) return;

  if (chromeApi.runtime?.onInstalled) {
    chromeApi.runtime.onInstalled.addListener(() => {
      setupContextMenus();
    },);
  }

  if (chromeApi.contextMenus?.onClicked) {
    chromeApi.contextMenus.onClicked.addListener((info, tab,) => {
      handleContextMenuClick(info, tab,).catch((e,) => console.error("Context menu ingest failed:", e,));
    },);
  }

  if (chromeApi.commands?.onCommand) {
    chromeApi.commands.onCommand.addListener((command,) => {
      handleCommand(command,).catch((e,) => console.error("Command ingest failed:", e,));
    },);
  }

  if (chromeApi.alarms?.onAlarm) {
    chromeApi.alarms.onAlarm.addListener((alarm,) => {
      if (alarm.name === "drainQueue") {
        drainQueue().catch((e,) => console.error("Queue drain failed:", e,));
      }
    },);
  }

  if (chromeApi.runtime?.onMessage) {
    chromeApi.runtime.onMessage.addListener(async (request, sender, sendResponse,) => {
      try {
        await handleMessage(request, sender, sendResponse,);
      } catch (err) {
        sendResponse({ error: err.message, },);
      }
      return true; // Keep channel open for async
    },);
  }

  if (chromeApi.action) {
    updateBadge().catch((e,) => console.error("Badge update failed:", e,));
  }
}

// Auto-register in a real browser; tests set __CEREBRO_TEST__ and call registerBrowserListeners().
if (getChromeApi() && typeof globalThis.__CEREBRO_TEST__ === "undefined") {
  registerBrowserListeners();
}

if (typeof self !== "undefined") {
  self.addEventListener("online", () => {
    drainQueue().catch((e,) => console.error("Online drain failed:", e,));
  },);
}

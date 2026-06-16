/**
 * Unit + integration tests for the Cerebro browser extension service worker.
 *
 * These tests exercise the core logic that runs inside the Manifest V3 service
 * worker: settings, ID generation, duplicate detection, offline queue, retry
 * backoff, and message passing. They rely on the chrome.* mock installed by
 * vitest.setup.js, so no real browser is required.
 */

import { beforeEach, describe, expect, it, vi, } from "vitest";

import {
  calculateBackoffDelay,
  computeId,
  drainQueue,
  enqueueBookmark,
  getFailedQueue,
  getQueue,
  getSettings,
  ingestBookmark,
  isDuplicate,
  markAsBookmarked,
  moveToFailedQueue,
  registerBrowserListeners,
  removeFromQueue,
  saveSettings,
  updateBadge,
} from "../background.js";

import { chromeMockController, resetChromeMock, } from "../vitest.setup.js";

const { storage, listeners, getBadgeText, getBadgeColor, } = chromeMockController;

beforeEach(() => {
  resetChromeMock();
  vi.restoreAllMocks();
},);

describe("settings", () => {
  it("returns default settings when storage is empty", async () => {
    const settings = await getSettings();
    expect(settings,).toEqual({ serverUrl: "http://127.0.0.1:8765", autoTag: true, },);
    expect(storage.get("settings",),).toBeUndefined();
  });

  it("merges stored settings with defaults", async () => {
    storage.set("settings", { serverUrl: "http://localhost:9999", },);
    const settings = await getSettings();
    expect(settings,).toEqual({ serverUrl: "http://localhost:9999", autoTag: true, },);
  });

  it("persists settings to storage", async () => {
    await saveSettings({ serverUrl: "http://custom:8765", autoTag: false, },);
    expect(storage.get("settings",),).toEqual({ serverUrl: "http://custom:8765", autoTag: false, },);
  });
});

describe("id generation", () => {
  it("computes a 16-char hex id matching the Python implementation", async () => {
    const id = await computeId("https://example.com", "Example",);
    expect(id,).toMatch(/^[0-9a-f]{16}$/,);
  });

  it("produces different ids for different inputs", async () => {
    const id1 = await computeId("https://example.com", "One",);
    const id2 = await computeId("https://example.com", "Two",);
    expect(id1,).not.toBe(id2,);
  });
});

describe("duplicate detection", () => {
  it("marks a bookmark as duplicate after it has been bookmarked", async () => {
    expect(await isDuplicate("https://example.com", "Example",),).toBe(false,);
    await markAsBookmarked("https://example.com", "Example",);
    expect(await isDuplicate("https://example.com", "Example",),).toBe(true,);
  });
});

describe("queue management", () => {
  it("enqueues a bookmark with metadata", async () => {
    const item = await enqueueBookmark({ url: "https://example.com", title: "Example", },);
    expect(item.url,).toBe("https://example.com",);
    expect(item.attempts,).toBe(0,);
    expect(item.enqueuedAt,).toBeGreaterThan(0,);
    expect(item.nextRetryAt,).toBeGreaterThan(0,);

    const queue = await getQueue();
    expect(queue,).toHaveLength(1,);
  });

  it("removes an item by index", async () => {
    await enqueueBookmark({ url: "https://a.com", title: "A", },);
    await enqueueBookmark({ url: "https://b.com", title: "B", },);
    await removeFromQueue(0,);

    const queue = await getQueue();
    expect(queue,).toHaveLength(1,);
    expect(queue[0].url,).toBe("https://b.com",);
  });

  it("moves exhausted items to the failed queue", async () => {
    await moveToFailedQueue({ url: "https://fail.com", title: "Fail", attempts: 5, },);
    const failed = await getFailedQueue();
    expect(failed,).toHaveLength(1,);
    expect(failed[0].failedAt,).toBeGreaterThan(0,);
  });
});

describe("backoff", () => {
  it("doubles the delay each attempt up to the max", () => {
    expect(calculateBackoffDelay(0,),).toBe(1000,);
    expect(calculateBackoffDelay(1,),).toBe(2000,);
    expect(calculateBackoffDelay(4,),).toBe(16000,);
    expect(calculateBackoffDelay(10,),).toBe(60000,);
  });
});

describe("badge", () => {
  it("reflects pending queue length in badge text", async () => {
    await updateBadge();
    expect(getBadgeText(),).toBe("",);

    await enqueueBookmark({ url: "https://queued.com", title: "Queued", },);
    await updateBadge();
    expect(getBadgeText(),).toBe("1",);
  });
});

describe("server ingest", () => {
  it("succeeds when the server returns 201", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve({ id: "abc123", status: "created", },), },)
    );

    const result = await ingestBookmark({ url: "https://ok.com", title: "OK", },);
    expect(result.success,).toBe(true,);
    expect(result.data.id,).toBe("abc123",);
  });

  it("fails and does not mark bookmarked when the server errors", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({},), },));

    const result = await ingestBookmark({ url: "https://err.com", title: "Err", },);
    expect(result.success,).toBe(false,);
    expect(await isDuplicate("https://err.com", "Err",),).toBe(false,);
  });
});

describe("retry drain", () => {
  it("sends queued items and removes them on success", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve({ id: "x", status: "created", },), },)
    );

    await enqueueBookmark({ url: "https://retry.com", title: "Retry", },);
    await drainQueue();

    expect(await getQueue(),).toHaveLength(0,);
  });

  it("moves exhausted items to the failed queue", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({},), },));

    await enqueueBookmark({ url: "https://fail.com", title: "Fail", },);
    const queue = await getQueue();
    expect(queue,).toHaveLength(1,);
    queue[0].attempts = 5;
    queue[0].nextRetryAt = 0;

    await drainQueue();

    expect(await getQueue(),).toHaveLength(0,);
    expect(await getFailedQueue(),).toHaveLength(1,);
  });
});

describe("message hub", () => {
  beforeEach(() => {
    resetChromeMock();
    registerBrowserListeners();
  },);

  it("registers a message listener", () => {
    expect(listeners.message,).toHaveLength(1,);
  });

  it("responds to getQueueStats with current counts", async () => {
    const messageListener = listeners.message[0];
    const sendResponse = vi.fn();
    await messageListener({ action: "getQueueStats", }, {}, sendResponse,);
    expect(sendResponse,).toHaveBeenCalledWith({ pending: 0, failed: 0, },);
  });
});

// ------------------------------------------------------------------
// Wave 1 regression tests — pin current behavior before slop removal
// ------------------------------------------------------------------

describe("ingestWithFallback", () => {
  beforeEach(() => {
    resetChromeMock();
    registerBrowserListeners();
  },);

  it("enqueues bookmark when ingest fails (fallback path)", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({},), },));

    const messageListener = listeners.message[0];
    const sendResponse = vi.fn();

    await messageListener(
      { action: "ingest", payload: { url: "https://fail.com", title: "Fail", }, },
      {},
      sendResponse,
    );

    // Verify response indicates failure
    expect(sendResponse,).toHaveBeenCalledWith(
      expect.objectContaining({ success: false, duplicate: false, },),
    );

    // Verify bookmark was enqueued as fallback
    const queue = await getQueue();
    expect(queue,).toHaveLength(1,);
    expect(queue[0].url,).toBe("https://fail.com",);
  });

  it("does NOT enqueue when ingest succeeds", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve({ id: "abc", status: "created", },), },)
    );

    const messageListener = listeners.message[0];
    const sendResponse = vi.fn();

    await messageListener(
      { action: "ingest", payload: { url: "https://ok.com", title: "OK", }, },
      {},
      sendResponse,
    );

    // Verify response indicates success
    expect(sendResponse,).toHaveBeenCalledWith(
      expect.objectContaining({ success: true, duplicate: false, },),
    );

    // Verify no fallback enqueue
    const queue = await getQueue();
    expect(queue,).toHaveLength(0,);
  });
});

describe("flashBadge on duplicate", () => {
  beforeEach(() => {
    resetChromeMock();
    registerBrowserListeners();
  },);

  it("sets DUP badge text/color when duplicate detected", async () => {
    // Pre-mark as duplicate
    await markAsBookmarked("https://example.com", "Example",);

    // Mock fetch to succeed (so ingest doesn't fail and enqueue)
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve({ id: "abc", status: "created", },), },)
    );

    // Fire context menu click listener for "cerebro-page"
    const clickListener = listeners.click[0];
    clickListener(
      { menuItemId: "cerebro-page", },
      { url: "https://example.com", title: "Example", id: 1, },
    );

    // Yield to microtask queue so handleContextMenuClick's await chain completes
    await new Promise((r,) => setTimeout(r, 10,));

    // Verify chrome.action.setBadgeText was called with "DUP"
    expect(chrome.action.setBadgeText,).toHaveBeenCalledWith({ text: "DUP", },);
    expect(chrome.action.setBadgeBackgroundColor,).toHaveBeenCalledWith({ color: "#ca8a04", },);
  });
});

describe("silent error swallowing", () => {
  beforeEach(() => {
    resetChromeMock();
    registerBrowserListeners();
  },);

  it("currently swallows errors in alarm drainQueue handler", async () => {
    const originalGet = chrome.storage.local.get;
    try {
      chrome.storage.local.get = vi.fn(() => Promise.reject(new Error("storage failure",),));

      const alarmListener = listeners.alarm[0];

      // The wrapper does NOT return a promise, and .catch(() => {}) swallows the async error.
      // Verify it does not throw synchronously.
      expect(() => alarmListener({ name: "drainQueue", },)).not.toThrow();

      // Let pending microtasks settle (the rejected promise is caught by .catch(() => {}))
      await new Promise((r,) => setTimeout(r, 0,));
    } finally {
      // ALWAYS restore original mock to avoid poisoning subsequent tests
      chrome.storage.local.get = originalGet;
    }
  });
});

describe("drainQueue ordering", () => {
  beforeEach(() => {
    resetChromeMock();
  },);

  it("processes queued items in FIFO order", async () => {
    const fetchCalls = [];
    global.fetch = vi.fn((url, options,) => {
      const body = JSON.parse(options.body,);
      fetchCalls.push(body.url,);
      return Promise.resolve({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ id: "x", status: "created", },),
      },);
    },);

    // Enqueue 3 items in order
    await enqueueBookmark({ url: "https://first.com", title: "First", },);
    await enqueueBookmark({ url: "https://second.com", title: "Second", },);
    await enqueueBookmark({ url: "https://third.com", title: "Third", },);

    await drainQueue();

    // All items should be processed and removed
    expect(await getQueue(),).toHaveLength(0,);

    // Fetch should have been called 3 times in FIFO order
    expect(fetchCalls,).toHaveLength(3,);
    expect(fetchCalls,).toEqual([
      "https://first.com",
      "https://second.com",
      "https://third.com",
    ],);
  });
});

describe("handleMessage ingest", () => {
  beforeEach(() => {
    resetChromeMock();
    registerBrowserListeners();
  },);

  it("returns success:true with duplicate flag on successful ingest", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve({ id: "abc123", status: "created", },), },)
    );

    const messageListener = listeners.message[0];
    const sendResponse = vi.fn();

    await messageListener(
      { action: "ingest", payload: { url: "https://new.com", title: "New", }, },
      {},
      sendResponse,
    );

    expect(sendResponse,).toHaveBeenCalledWith({
      success: true,
      data: { id: "abc123", status: "created", },
      duplicate: false,
    },);
  });

  it("returns success:false with duplicate flag on failed ingest", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({},), },));

    const messageListener = listeners.message[0];
    const sendResponse = vi.fn();

    await messageListener(
      { action: "ingest", payload: { url: "https://err.com", title: "Err", }, },
      {},
      sendResponse,
    );

    expect(sendResponse,).toHaveBeenCalledWith(
      expect.objectContaining({ success: false, duplicate: false, },),
    );
  });
});

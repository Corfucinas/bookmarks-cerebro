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

import { chromeMockController, resetChromeMock, } from "../vitest.setup.js";

const { storage, listeners, getBadgeText, } = chromeMockController;

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

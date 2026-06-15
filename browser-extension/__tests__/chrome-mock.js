/**
 * Minimal chrome.* API mock for service-worker tests in a Node/jsdom harness.
 *
 * Simulates chrome.storage.local, chrome.tabs, chrome.scripting, chrome.alarms,
 * chrome.runtime, chrome.contextMenus, chrome.action, and chrome.commands just
 * enough to exercise background.js logic without a real browser.
 */

export function createChromeMock() {
  const storage = new Map();
  const alarms = new Map();
  const listeners = {
    install: [],
    click: [],
    command: [],
    alarm: [],
    message: [],
  };
  const menus = [];
  const sentMessages = [];
  let badgeText = "";
  let badgeColor = "";

  const mockGet = (keys,) => {
    const result = {};
    const keyList = Array.isArray(keys,) ? keys : [keys,];
    for (const key of keyList) {
      if (storage.has(key,)) {
        result[key] = storage.get(key,);
      }
    }
    return Promise.resolve(result,);
  };

  const mockSet = (items,) => {
    for (const [key, value,] of Object.entries(items,)) {
      storage.set(key, value,);
    }
    return Promise.resolve();
  };

  const mockRemove = (key,) => {
    storage.delete(key,);
    return Promise.resolve();
  };

  return {
    storage,
    alarms,
    menus,
    sentMessages,
    listeners,
    getBadgeText: () => badgeText,
    getBadgeColor: () => badgeColor,
    chrome: {
      storage: {
        local: {
          get: vi.fn(mockGet,),
          set: vi.fn(mockSet,),
          remove: vi.fn(mockRemove,),
        },
      },
      tabs: {
        query: vi.fn(() => Promise.resolve([{ id: 1, url: "https://example.com", title: "Example", },],)),
      },
      scripting: {
        executeScript: vi.fn(({ func, args, },) => {
          const result = func ? func(...(args || []),) : undefined;
          return Promise.resolve([{ result, },],);
        },),
      },
      alarms: {
        create: vi.fn((name, options,) => {
          alarms.set(name, options,);
        },),
        onAlarm: {
          addListener: vi.fn((cb,) => listeners.alarm.push(cb,)),
        },
      },
      runtime: {
        onInstalled: {
          addListener: vi.fn((cb,) => listeners.install.push(cb,)),
        },
        onMessage: {
          addListener: vi.fn((cb,) => listeners.message.push(cb,)),
        },
        openOptionsPage: vi.fn(),
        sendMessage: vi.fn((msg,) => {
          sentMessages.push(msg,);
          // Simulate simple message responses for known actions
          if (msg.action === "getQueue") {
            return Promise.resolve({ queue: storage.get("pending_queue",) || [], },);
          }
          if (msg.action === "getFailedQueue") {
            return Promise.resolve({ failedQueue: storage.get("failed_queue",) || [], },);
          }
          if (msg.action === "getQueueStats") {
            return Promise.resolve({
              pending: (storage.get("pending_queue",) || []).length,
              failed: (storage.get("failed_queue",) || []).length,
            },);
          }
          return Promise.resolve({ success: true, },);
        },),
      },
      contextMenus: {
        create: vi.fn((props,) => menus.push(props,)),
        onClicked: {
          addListener: vi.fn((cb,) => listeners.click.push(cb,)),
        },
      },
      commands: {
        onCommand: {
          addListener: vi.fn((cb,) => listeners.command.push(cb,)),
        },
      },
      action: {
        setBadgeText: vi.fn(({ text, },) => {
          badgeText = text;
          return Promise.resolve();
        },),
        setBadgeBackgroundColor: vi.fn(({ color, },) => {
          badgeColor = color;
          return Promise.resolve();
        },),
      },
    },
  };
}

import { vi, } from "vitest";

import { createChromeMock, } from "./__tests__/chrome-mock.js";
import { registerBrowserListeners, } from "./background.js";

const controller = createChromeMock();

globalThis.chrome = controller.chrome;
globalThis.self = { addEventListener: vi.fn(), };
globalThis.__CEREBRO_TEST__ = true;

registerBrowserListeners();

export const chromeMockController = controller;

export function resetChromeMock() {
  controller.storage.clear();
  controller.alarms.clear();
  controller.menus.length = 0;
  controller.sentMessages.length = 0;
  controller.listeners.install.length = 0;
  controller.listeners.click.length = 0;
  controller.listeners.command.length = 0;
  controller.listeners.alarm.length = 0;
  controller.listeners.message.length = 0;
}

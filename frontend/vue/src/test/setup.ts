import { afterEach, vi } from "vitest";
import { config } from "@vue/test-utils";

class MockEventSource {
  static instances: MockEventSource[] = [];

  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  readonly listeners = new Map<string, EventListenerOrEventListenerObject[]>();

  constructor(readonly url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(
      type,
      listeners.filter((item) => item !== listener),
    );
  }

  close() {}
}

Object.defineProperty(window, "EventSource", {
  configurable: true,
  writable: true,
  value: MockEventSource,
});

Object.defineProperty(globalThis, "EventSource", {
  configurable: true,
  writable: true,
  value: MockEventSource,
});

config.global.stubs = {
  transition: false,
};

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  MockEventSource.instances.length = 0;
});

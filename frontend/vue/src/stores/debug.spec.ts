import { beforeEach, describe, expect, it } from "vitest";
import { useDebugStore } from "./debug";
import { useEventsStore } from "./events";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useDebugStore", () => {
  beforeEach(resetStoreTest);

  it("loads raw MQTT, events and system info", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/debug/raw-mqtt?limit=20") return [{ topic: "device/status" }];
      if (path === "/events?limit=80") return [{ id: 1, source: "mqtt", type: "print.started", event_type: "print.started", severity: "info", message: "started", created_at: "2026-05-06T00:00:00Z" }];
      if (path === "/system/info") return { app_version: "0.1.0", uptime_seconds: 12, database_size_bytes: 1024, storage_size_bytes: 2048, memory: {}, configured_printers: 1, online_printers: 1 };
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useDebugStore();
    await store.loadDebug();

    expect(store.rawMqtt).toHaveLength(1);
    expect(store.systemInfo?.app_version).toBe("0.1.0");
    expect(useEventsStore().events).toHaveLength(1);
    expect(requestPaths(fetchMock)).toContain("/system/info");
  });
});

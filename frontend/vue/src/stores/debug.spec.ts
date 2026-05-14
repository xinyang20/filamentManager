import { beforeEach, describe, expect, it, vi } from "vitest";
import { useDebugStore } from "./debug";
import { useEventsStore } from "./events";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useDebugStore", () => {
  beforeEach(resetStoreTest);

  const retentionStatus = {
    raw_mqtt_db_limit: "5gb",
    limit_bytes: 5 * 1024 ** 3,
    trigger_threshold_bytes: Math.trunc(5 * 1024 ** 3 * 1.05),
    database_size_bytes: 1024,
    sqlite: true,
    enforcement_supported: true,
    is_over_threshold: false,
    raw_mqtt_row_count: 1,
    raw_mqtt_payload_bytes_estimate: 512,
    raw_mqtt_oldest_received_at: "2026-05-06T00:00:00Z",
    raw_mqtt_newest_received_at: "2026-05-06T00:01:00Z",
    retention_running: false,
    last_cleanup: null,
  };

  it("loads raw MQTT, events, system info and database retention", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/debug/raw-mqtt?limit=20") return [{ topic: "device/status" }];
      if (path === "/events?limit=80") return [{ id: 1, source: "mqtt", type: "print.started", event_type: "print.started", severity: "info", message: "started", created_at: "2026-05-06T00:00:00Z" }];
      if (path === "/system/info") return { app_version: "0.1.0", uptime_seconds: 12, database_size_bytes: 1024, storage_size_bytes: 2048, memory: {}, configured_printers: 1, online_printers: 1 };
      if (path === "/debug/database-retention") return retentionStatus;
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useDebugStore();
    await store.loadDebug();

    expect(store.rawMqtt).toHaveLength(1);
    expect(store.systemInfo?.app_version).toBe("0.1.0");
    expect(store.databaseRetention?.raw_mqtt_db_limit).toBe("5gb");
    expect(store.pendingRawMqttDbLimit).toBe("5gb");
    expect(useEventsStore().events).toHaveLength(1);
    expect(requestPaths(fetchMock)).toContain("/system/info");
    expect(requestPaths(fetchMock)).toContain("/debug/database-retention");
    expect(store.rawMqttDbLimitOptions.map((item) => item.value)).toEqual(["1gb", "5gb", "10gb", "20gb", "unlimited"]);
  });

  it("saves the selected database retention limit", async () => {
    const fetchMock = mockApi((path, init) => {
      if (path === "/debug/database-retention" && init.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({ raw_mqtt_db_limit: "10gb" });
        return { ...retentionStatus, raw_mqtt_db_limit: "10gb", limit_bytes: 10 * 1024 ** 3 };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useDebugStore();
    store.databaseRetention = retentionStatus as any;
    await store.saveRawMqttDbLimit("10gb");

    expect(store.databaseRetention?.raw_mqtt_db_limit).toBe("10gb");
    expect(requestPaths(fetchMock)).toEqual(["/debug/database-retention"]);
  });

  it("confirms before applying a smaller limit that will delete raw MQTT", async () => {
    const fetchMock = mockApi(() => {
      throw new Error("PATCH should not be sent");
    });
    vi.spyOn(window, "confirm").mockReturnValue(false);

    const store = useDebugStore();
    store.databaseRetention = {
      ...retentionStatus,
      raw_mqtt_db_limit: "5gb",
      database_size_bytes: Math.ceil(1 * 1024 ** 3 * 1.05),
      raw_mqtt_row_count: 10,
    } as any;
    store.pendingRawMqttDbLimit = "1gb";
    await store.saveRawMqttDbLimit("1gb");

    expect(window.confirm).toHaveBeenCalled();
    expect(store.pendingRawMqttDbLimit).toBe("5gb");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

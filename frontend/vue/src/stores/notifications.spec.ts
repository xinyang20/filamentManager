import { beforeEach, describe, expect, it } from "vitest";
import { useNotificationsStore } from "./notifications";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useNotificationsStore", () => {
  beforeEach(resetStoreTest);

  it("loads targets, rules and recent deliveries", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/notifications/targets") return [{ id: 1, channel: "webhook", name: "Ops", enabled: true, config: {}, display_config: { url: "https://example.test/hook" }, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/notifications/rules") return [{ id: 1, name: "Failures", enabled: true, event_types: ["print.failed"], printer_ids: [1], severities: ["error"], quiet_policy: {}, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/notifications/deliveries?limit=50") return [{ id: 1, target_id: 1, rule_id: 1, event_type: "print.failed", status: "sent", created_at: "2026-05-06T00:00:00Z" }];
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useNotificationsStore();
    await store.loadNotifications();

    expect(store.notificationTargets[0].name).toBe("Ops");
    expect(store.notificationRules[0].event_types).toEqual(["print.failed"]);
    expect(store.notificationDeliveries[0].status).toBe("sent");
    expect(requestPaths(fetchMock)).toContain("/notifications/deliveries?limit=50");
  });
});

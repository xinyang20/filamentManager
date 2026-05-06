import { beforeEach, describe, expect, it } from "vitest";
import { useEventsStore } from "./events";
import { usePrintersStore } from "./printers";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useEventsStore", () => {
  beforeEach(resetStoreTest);

  it("loads filtered events for the selected printer", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/events?limit=120&printer_id=1&severity=warning") return [{ id: 1, source: "mqtt", type: "hms.error.active", event_type: "hms.error.active", severity: "warning", active: true, message: "hotend warning", created_at: "2026-05-06T00:00:00Z" }];
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useEventsStore();
    store.eventFilters.severity = "warning";
    await store.loadEvents();

    expect(store.events).toHaveLength(1);
    expect(store.filteredEvents[0].severity).toBe("warning");
    expect(requestPaths(fetchMock)).toContain("/events?limit=120&printer_id=1&severity=warning");
  });
});

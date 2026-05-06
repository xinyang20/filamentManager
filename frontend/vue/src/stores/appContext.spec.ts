import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAppContextStore } from "./appContext";

function jsonResponse(data: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("useAppContextStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    window.localStorage.clear();
  });

  it("bootstraps printers and the current overview", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/api/printers")) return jsonResponse([{ id: 1, name: "P1", host: "127.0.0.1", port: 8883, serial: "S", tls_enabled: true, certificate_verify: false, enabled: true, connection_status: "connected" }]);
      if (url.endsWith("/api/dashboard/summary")) return jsonResponse([
        {
          printer: { id: 1, name: "P1", host: "127.0.0.1", port: 8883, serial: "S", tls_enabled: true, certificate_verify: false, enabled: true, connection_status: "connected" },
          state: { subtask_name: "Calibration cube", mc_percent: 42 },
          device_snapshot: { derived_status: { printing: true } },
        },
      ]);
      return jsonResponse(null);
    });
    const store = useAppContextStore();

    await store.bootstrap();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/dashboard/summary",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) }),
    );
    expect(store.viewContext.printers).toHaveLength(1);
    expect(store.viewContext.overviewStats[0].value).toBe(1);
    expect(store.viewContext.overviewItems[0].state.subtask_name).toBe("Calibration cube");
    expect(store.loading).toBe(false);
  });
});

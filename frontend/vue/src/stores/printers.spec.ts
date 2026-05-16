import { beforeEach, describe, expect, it, vi } from "vitest";
import { useNavigationStore } from "./navigation";
import { usePrintersStore } from "./printers";
import { mockApi, printerFixture, requestPaths, resetStoreTest } from "./testHelpers";

describe("usePrintersStore", () => {
  beforeEach(resetStoreTest);

  it("refreshes printers and selects the first printer", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/printers") return [printerFixture];
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintersStore();
    await store.refreshPrinters();

    expect(store.printers).toHaveLength(1);
    expect(store.selectedPrinterId).toBe(1);
    expect(store.editingPrinterId).toBeNull();
    expect(store.printerForm.host).toBe("");
    expect(requestPaths(fetchMock)).toContain("/printers");
  });

  it("creates a second printer without patching or switching the displayed printer", async () => {
    const secondPrinter = { ...printerFixture, id: 2, name: "P2", host: "192.0.2.20", serial: "SN002" };
    const fetchMock = mockApi((path, init) => {
      if (path === "/printers" && init.method === "POST") {
        expect(JSON.parse(String(init.body))).toMatchObject({ name: "P2", host: "192.0.2.20", serial: "SN002" });
        return secondPrinter;
      }
      if (path === "/printers" && !init.method) return [printerFixture, secondPrinter];
      if (path.startsWith("/printers/1")) throw new Error("PATCH should not update the selected printer");
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintersStore();
    store.printers = [printerFixture];
    store.selectedPrinterId = 1;
    store.startCreatePrinter();
    store.printerForm.name = "P2";
    store.printerForm.host = "192.0.2.20";
    store.printerForm.serial = "SN002";
    store.printerForm.access_code = "access-2";

    await store.savePrinter();

    expect(store.selectedPrinterId).toBe(1);
    expect(store.editingPrinterId).toBe(2);
    expect(requestPaths(fetchMock)).toEqual(["/printers", "/printers"]);
  });

  it("patches only the printer currently being edited", async () => {
    const secondPrinter = { ...printerFixture, id: 2, name: "P2", host: "192.0.2.20", serial: "SN002" };
    const updatedSecondPrinter = { ...secondPrinter, host: "192.0.2.21" };
    const fetchMock = mockApi((path, init) => {
      if (path === "/printers/2" && init.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toMatchObject({ host: "192.0.2.21" });
        return updatedSecondPrinter;
      }
      if (path === "/printers" && !init.method) return [printerFixture, updatedSecondPrinter];
      if (path === "/printers" && init.method === "POST") throw new Error("POST should not be used while editing");
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintersStore();
    store.printers = [printerFixture, secondPrinter];
    store.selectedPrinterId = 1;
    store.editPrinter(secondPrinter);
    store.printerForm.host = "192.0.2.21";

    await store.savePrinter();

    expect(store.selectedPrinterId).toBe(1);
    expect(store.editingPrinterId).toBe(2);
    expect(requestPaths(fetchMock)).toEqual(["/printers/2", "/printers"]);
  });

  it("puts scan candidates into create mode without overwriting an existing printer", async () => {
    const candidate = {
      host: "192.0.2.30",
      model: "P1S",
      device_name: "Scanned P1S",
      serial: "SN003",
      confidence: 95,
      reason: "validated",
    };
    const fetchMock = mockApi((path) => {
      if (path === "/discovery/scan") return [candidate];
      throw new Error(`Unexpected request: ${path}`);
    });
    const requestAnimationFrame = vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => 1);
    const cancelAnimationFrame = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
    const setTimeout = vi.spyOn(window, "setTimeout").mockImplementation((handler: TimerHandler) => {
      if (typeof handler === "function") handler();
      return 1;
    });

    try {
      const store = usePrintersStore();
      store.printers = [printerFixture];
      store.selectedPrinterId = 1;
      store.editPrinter(printerFixture);

      await store.scanDevices();

      expect(store.selectedPrinterId).toBe(1);
      expect(store.editingPrinterId).toBeNull();
      expect(store.printerForm.host).toBe("192.0.2.30");
      expect(store.printerForm.serial).toBe("SN003");
      expect(requestPaths(fetchMock)).toEqual(["/discovery/scan"]);
    } finally {
      requestAnimationFrame.mockRestore();
      cancelAnimationFrame.mockRestore();
      setTimeout.mockRestore();
    }
  });

  it("connects a row printer without switching the displayed printer", async () => {
    const secondPrinter = { ...printerFixture, id: 2, name: "P2", host: "192.0.2.20", serial: "SN002", connection_status: "connected" };
    const fetchMock = mockApi((path, init) => {
      if (path === "/printers/2/connect" && init.method === "POST") return secondPrinter;
      if (path === "/printers" && !init.method) return [printerFixture, secondPrinter];
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintersStore();
    useNavigationStore().activeView = "printers";
    store.printers = [printerFixture, { ...secondPrinter, connection_status: "disconnected" }];
    store.selectedPrinterId = 1;

    await store.connectPrinter(2);

    expect(store.selectedPrinterId).toBe(1);
    expect(requestPaths(fetchMock)).toEqual(["/printers/2/connect", "/printers"]);
  });
});

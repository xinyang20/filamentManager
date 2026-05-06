import { beforeEach, describe, expect, it } from "vitest";
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
    expect(store.printerForm.host).toBe("127.0.0.1");
    expect(requestPaths(fetchMock)).toContain("/printers");
  });
});

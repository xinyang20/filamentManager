import { beforeEach, describe, expect, it } from "vitest";
import { usePrintersStore } from "./printers";
import { useStorageStore } from "./storage";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useStorageStore", () => {
  beforeEach(resetStoreTest);

  it("loads storage files, summary and timelapse notes", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/printers/1/storage/files") return [{ id: 1, path: "/timelapse/a.mp4", name: "a.mp4", size: 2048, modified_at: "2026-05-06T00:00:00Z", type: "timelapse", source: "sdcard" }];
      if (path === "/printers/1/storage/summary") return { printer_id: 1, file_count: 1, total_size: 2048, by_type: { timelapse: 1 }, recent_files: [], timelapse_files: [] };
      if (path === "/printers/1/timelapse/notes") return [{ id: 1, printer_id: 1, path: "/timelapse/a.mp4", favorite: true, note: "good run", cached_metadata: {}, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useStorageStore();
    await store.loadStorage();

    expect(store.storageFiles).toHaveLength(1);
    expect(store.timelapseNotes["/timelapse/a.mp4"].note).toBe("good run");
    expect(store.storagePreviewFiles).toHaveLength(1);
    expect(requestPaths(fetchMock)).toContain("/printers/1/storage/files");
  });
});

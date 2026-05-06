import { beforeEach, describe, expect, it } from "vitest";
import { usePresentationStore } from "./presentation";
import { resetStoreTest } from "./testHelpers";

describe("usePresentationStore", () => {
  beforeEach(resetStoreTest);

  it("formats common presentation values", () => {
    const store = usePresentationStore();

    expect(store.formatBytes(1536)).toBe("1.5 KB");
    expect(store.percent(120)).toBe(100);
    expect(store.displayCell(null)).toBe("—");
    expect(store.splitCsv("print.failed, hms.error.active")).toEqual(["print.failed", "hms.error.active"]);
  });
});

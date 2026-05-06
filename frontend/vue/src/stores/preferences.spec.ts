import { beforeEach, describe, expect, it } from "vitest";
import { usePreferencesStore } from "./preferences";
import { resetStoreTest } from "./testHelpers";

describe("usePreferencesStore", () => {
  beforeEach(resetStoreTest);

  it("persists section layout preferences", () => {
    const store = usePreferencesStore();
    store.sectionLayouts = { overview: { stats: { hidden: true } } };

    store.saveSectionLayouts();

    expect(window.localStorage.getItem("filamentManager.sectionLayouts")).toBe(JSON.stringify({ overview: { stats: { hidden: true } } }));
  });
});

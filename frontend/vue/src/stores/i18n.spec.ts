import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useI18nStore } from "./i18n";

describe("useI18nStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("translates labels for the active locale", () => {
    const store = useI18nStore();

    expect(store.navLabel("printers")).toBe("打印机配置");

    store.locale = "en-US";

    expect(store.navLabel("printers")).toBe("Printer Config");
  });
});

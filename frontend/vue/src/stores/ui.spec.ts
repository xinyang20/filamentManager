import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useUiStore } from "./ui";

describe("useUiStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("clears loading after successful work", async () => {
    const store = useUiStore();

    await store.withLoading(async () => {
      expect(store.loading).toBe(true);
    });

    expect(store.loading).toBe(false);
    expect(store.error).toBe("");
  });

  it("captures errors without leaving loading active", async () => {
    const store = useUiStore();

    await store.withLoading(async () => {
      throw new Error("boom");
    });

    expect(store.loading).toBe(false);
    expect(store.error).toBe("boom");
  });
});

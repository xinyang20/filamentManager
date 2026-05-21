import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import { appViewRefs, composeViewContext } from "./viewContext";

describe("appViewRefs", () => {
  it("keeps actions callable while exposing state as refs", () => {
    const metricRange = ref("6h");
    const loadMetrics = vi.fn();
    const ctx = composeViewContext({ metricRange, loadMetrics });

    const refs = appViewRefs(ctx);

    refs.metricRange.value = "24h";
    refs.loadMetrics();

    expect(metricRange.value).toBe("24h");
    expect(loadMetrics).toHaveBeenCalledOnce();
  });
});

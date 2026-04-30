import { describe, expect, it } from "vitest";

import {
  filamentAmsRemainingLabel,
  filamentAmsRemainingWeight,
  filamentColor,
  filamentKg,
  filamentRemainPercent,
  filamentSpoolRemainingLabel,
  filamentSpoolRemainingWeight,
  filamentWeight,
  normalizeFilamentHex,
  remainLabel,
  remainPercent,
} from "./filamentMetrics";

describe("filamentMetrics", () => {
  it("normalizes Bambu-style color values", () => {
    expect(normalizeFilamentHex("#aabbcc")).toBe("AABBCC");
    expect(normalizeFilamentHex("AA_BB_CC_FF")).toBe("AABBCC");
    expect(normalizeFilamentHex("not-a-color")).toBeNull();
    expect(filamentColor("00ae42")).toBe("#00AE42");
  });

  it("formats spool weights without changing existing units", () => {
    expect(filamentWeight(999.6)).toBe("1000 g");
    expect(filamentKg(1250)).toBe("1.25 kg");
    expect(filamentKg(11000)).toBe("11.0 kg");
  });

  it("uses measured spool weight before percent fallback", () => {
    expect(filamentSpoolRemainingWeight({ actual_weight_g: 321, nominal_weight_g: 1000, last_ams_remain_percent: 50 })).toBe(321);
    expect(filamentSpoolRemainingWeight({ nominal_weight_g: 1000, last_ams_remain_percent: 42 })).toBe(420);
    expect(filamentRemainPercent({ current_remaining_g: 250, nominal_weight_g: 1000 })).toBe("25%");
    expect(filamentSpoolRemainingLabel({ nominal_weight_g: 1000, last_ams_remain_percent: 42 })).toBe("42% / 420 g");
  });

  it("prefers AMS reported weight over spool-derived estimates", () => {
    expect(filamentAmsRemainingWeight({ raw: { remain_weight: "123" }, remain: 80 }, { nominal_weight_g: 1000 })).toBe(123);
    expect(filamentAmsRemainingLabel({ remain: 80 }, { nominal_weight_g: 1000 })).toBe("80% / 800 g");
  });

  it("keeps remain labels bounded and readable", () => {
    expect(remainPercent(130)).toBe(100);
    expect(remainPercent(-1)).toBe(0);
    expect(remainLabel(null)).toBe("--");
    expect(remainLabel(34.5)).toBe("35%");
  });
});

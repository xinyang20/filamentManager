import { describe, expect, it } from "vitest";

import {
  defaultOverviewControls,
  isTransientCollapsedSection,
  isViewEnabled,
  loadExperimentalFeatureSettings,
  loadOverviewControls,
  loadSectionLayouts,
  resolveInitialInventoryPage,
  resolveInitialView,
} from "./preferences";

describe("preferences", () => {
  it("loads experimental feature settings with safe defaults", () => {
    window.localStorage.setItem(
      "filamentManager.experimentalFeatures",
      JSON.stringify({ maintenance: true, printLog: false, timelapse: "yes" }),
    );

    expect(loadExperimentalFeatureSettings()).toEqual({
      timelapse: false,
      maintenance: true,
      printLog: false,
      notifications: false,
    });
  });

  it("falls back to default overview controls for invalid storage", () => {
    window.localStorage.setItem("filamentManager.overviewControls", "{");

    expect(loadOverviewControls()).toEqual(defaultOverviewControls());
  });

  it("resolves legacy view keys without changing enabled view rules", () => {
    expect(resolveInitialView("filamentSkus", () => true)).toBe("inventory");
    expect(resolveInitialView("debug", () => false)).toBe("overview");
    expect(resolveInitialView("debug", () => true)).toBe("debug");
    expect(resolveInitialInventoryPage("filamentBrands")).toBe("brands");
  });

  it("keeps experimental views behind feature flags", () => {
    expect(isViewEnabled("maintenance", { timelapse: false, maintenance: false, printLog: false, notifications: false })).toBe(false);
    expect(isViewEnabled("inventory", { timelapse: false, maintenance: false, printLog: false, notifications: false })).toBe(true);
  });

  it("drops transient AMS layout entries loaded from older sessions", () => {
    window.localStorage.setItem(
      "filamentManager.sectionLayouts",
      JSON.stringify({
        ams: {
          "ams.unit.0": { collapsed: true },
          "ams.summary": { hidden: true },
        },
      }),
    );

    expect(loadSectionLayouts()).toEqual({ ams: { "ams.summary": { hidden: true } } });
    expect(isTransientCollapsedSection("ams", "ams.unit.0")).toBe(true);
  });
});

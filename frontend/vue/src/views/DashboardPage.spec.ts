import { mount } from "@vue/test-utils";
import { nextTick, reactive } from "vue";
import { describe, expect, it, vi } from "vitest";

import { composeViewContext } from "../app/viewContext";
import DashboardPage from "./DashboardPage.vue";

const translations: Record<string, string> = {
  "ams.emptySlot": "空",
  "ams.noSlots": "暂无槽位",
  "common.empty": "暂无数据",
  "layout.collapse": "折叠 / 展开",
};

function t(key: string) {
  return translations[key] || key;
}

function dashboardPageContext(overrides: Record<string, unknown> = {}) {
  return composeViewContext({
    activeDerivedStatuses: [],
    activeView: "dashboard",
    boolLabel: (value: unknown) => String(value),
    camera: {},
    cameraLightboxOpen: false,
    cameraLivePlaceholder: "",
    cameraStatusRows: [],
    cameraStreamError: false,
    cameraStreamSrc: "",
    canRequestFullRefresh: true,
    connectPrinter: vi.fn(),
    coverage: {},
    coverageStatusRows: [],
    dashboard: {},
    dashboardAmsCompactMode: true,
    dashboardAmsSummaryRows: [],
    dashboardAmsUnitRows: [],
    dashboardAmsUnitCollapsed: () => true,
    dashboardHmsRows: [],
    dashboardPrintStageLabel: () => "--",
    dashboardPrintStateLabel: () => "--",
    dashboardProgress: () => 0,
    dashboardRemainingTimeMetric: () => "--",
    dashboardTaskTitle: () => "No task",
    derivedStatusTone: () => "",
    detectionRows: [],
    displayCell: (value: unknown) => String(value ?? "--"),
    error: "",
    fanDisplayPercent: () => 0,
    fanRows: [],
    fieldLabel: (key: string) => key,
    formatCell: (value: unknown) => String(value ?? "--"),
    handleCameraStreamError: vi.fn(),
    handleCameraStreamLoaded: vi.fn(),
    hmsErrors: [],
    isSectionCollapsed: () => false,
    layerFraction: "",
    network: {},
    nozzleTemperatureRows: [{ key: "nozzle", label: "喷嘴", current: 0, target: 0 }],
    openCameraLightbox: vi.fn(),
    openHmsDetails: vi.fn(),
    readableNetworkHardware: [],
    remainingTimeLabel: "",
    restartCameraStream: vi.fn(),
    shouldShowChamberTemperature: false,
    statusTone: () => "",
    t,
    temperaturePercent: () => 0,
    temperatures: { bed: 0, bed_target: 0 },
    toggleDashboardAmsUnitCollapsed: vi.fn(),
    toggleSectionCollapsed: vi.fn(),
    ...overrides,
  });
}

function amsUnitRows() {
  return [
    {
      key: "0",
      title: "AMS 1",
      code: "#0",
      meta: "24°C / 2%",
      slots: [
        {
          key: "0-0",
          label: "A1",
          material: "PLA",
          remain: "32%",
          active: true,
          loaded: true,
          style: { "--filament-color": "#ff0000" },
        },
        {
          key: "0-1",
          label: "A2",
          material: "PETG",
          remain: "56%",
          active: false,
          loaded: true,
          style: { "--filament-color": "#00ff00" },
        },
        {
          key: "0-2",
          label: "A3",
          material: "--",
          remain: "--",
          active: false,
          loaded: false,
          style: { "--filament-color": "#d7dce2" },
        },
      ],
    },
  ];
}

describe("DashboardPage AMS overview", () => {
  it("renders compact AMS slots without full spool visuals", () => {
    const wrapper = mount(DashboardPage, {
      props: {
        ctx: dashboardPageContext({
          dashboardAmsUnitRows: amsUnitRows(),
          dashboardAmsUnitCollapsed: () => true,
        }),
      },
    });

    expect(wrapper.findAll(".ams-spool")).toHaveLength(0);
    expect(wrapper.findAll(".ams-compact-slot")).toHaveLength(3);
    expect(wrapper.get(".ams-compact-slot.active").text()).toContain("32%");
    expect(wrapper.get(".ams-compact-slot.active").text()).not.toContain("PLA");
    expect(wrapper.get(".ams-compact-slot.active").attributes("title")).toBe("PLA 32%");
    expect(wrapper.get(".ams-compact-slot.empty").text()).toContain("空");
    expect(wrapper.findAll(".ams-compact-slot strong")).toHaveLength(0);
    expect(wrapper.get(".ams-compact-slot").attributes("style")).toContain("--filament-color: #ff0000");

    wrapper.unmount();
  });

  it("restores full spool visuals after expanding one AMS unit", async () => {
    const collapsedByKey = reactive<Record<string, boolean>>({ "0": true });
    const wrapper = mount(DashboardPage, {
      props: {
        ctx: dashboardPageContext({
          dashboardAmsUnitRows: amsUnitRows(),
          dashboardAmsUnitCollapsed: (key: string) => collapsedByKey[key] ?? true,
          toggleDashboardAmsUnitCollapsed: (key: string) => {
            collapsedByKey[key] = !(collapsedByKey[key] ?? true);
          },
        }),
      },
    });

    expect(wrapper.findAll(".ams-spool")).toHaveLength(0);

    await wrapper.get(".ams-visual-unit .icon-button").trigger("click");
    await nextTick();

    expect(wrapper.findAll(".ams-compact-slot")).toHaveLength(0);
    expect(wrapper.findAll(".ams-spool")).toHaveLength(3);

    wrapper.unmount();
  });
});

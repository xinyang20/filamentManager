import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ViewKey } from "../app/navigation";
import AppSidebar from "./AppSidebar.vue";

const labels: Record<string, string> = {
  "app.name": "FilamentManager",
  "app.subtitle": "本地打印机运维",
  "app.api": "接口",
  "navGroup.monitoring": "监控",
  "navGroup.assets": "资产",
  "navGroup.system": "系统",
  "nav.overview": "总览",
  "nav.dashboard": "设备大屏",
  "nav.events": "事件中心",
  "nav.metrics": "历史趋势",
  "nav.printLog": "打印日志",
  "nav.maintenance": "维护",
  "nav.ams": "AMS",
  "nav.inventory": "耗材",
  "nav.storage": "延迟摄影",
  "nav.notifications": "通知",
  "nav.printers": "打印机配置",
  "nav.debug": "调试",
};

function mountSidebar(disabled: ViewKey[] = []) {
  return mount(AppSidebar, {
    props: {
      activeView: "overview",
      isViewEnabled: (view: ViewKey) => !disabled.includes(view),
      translate: (key: string) => labels[key] || key,
    },
  });
}

describe("AppSidebar", () => {
  it("groups enabled navigation items and hides disabled feature views", () => {
    const wrapper = mountSidebar(["printLog", "maintenance", "storage", "notifications"]);

    expect(wrapper.text()).toContain("监控");
    expect(wrapper.text()).toContain("资产");
    expect(wrapper.text()).toContain("系统");
    expect(wrapper.text()).toContain("总览");
    expect(wrapper.text()).toContain("耗材");
    expect(wrapper.text()).toContain("调试");
    expect(wrapper.text()).not.toContain("打印日志");
    expect(wrapper.text()).not.toContain("维护");
    expect(wrapper.text()).not.toContain("延迟摄影");
    expect(wrapper.text()).not.toContain("通知");
  });

  it("marks the active view and emits switch-view when a nav item is selected", async () => {
    const wrapper = mountSidebar();

    expect(wrapper.get(".nav-item.active").text()).toContain("总览");

    await wrapper.findAll(".nav-item").find((item) => item.text().includes("调试"))?.trigger("click");

    expect(wrapper.emitted("switch-view")).toEqual([["debug"]]);
  });
});

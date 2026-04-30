import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { MetricSample } from "../types";
import MetricPanel from "./MetricPanel.vue";

const headers = {
  time: "时间",
  metric: "指标",
  value: "数值",
  unit: "单位",
  details: "详情",
};

describe("MetricPanel", () => {
  it("renders an empty row when there are no samples", () => {
    const wrapper = mount(MetricPanel, {
      props: {
        title: "温度历史",
        items: [],
        metricLabel: (metric: string) => metric,
        emptyLabel: "暂无数据",
        headers,
      },
    });

    expect(wrapper.get("h3").text()).toBe("温度历史");
    expect(wrapper.get("td.empty").text()).toBe("暂无数据");
  });

  it("formats metric rows with labels, units and JSON details", () => {
    const items: MetricSample[] = [
      {
        id: 1,
        metric: "temperature.nozzle",
        value_float: 218,
        unit: "celsius",
        details: { source: "push_status" },
        sampled_at: "2026-04-30T10:00:00Z",
      },
      {
        id: 2,
        metric: "printer.state",
        value_text: "RUNNING",
        unit: "",
        details: {},
        sampled_at: "2026-04-30T10:01:00Z",
      },
    ];

    const wrapper = mount(MetricPanel, {
      props: {
        title: "指标",
        items,
        metricLabel: (metric: string) => (metric === "temperature.nozzle" ? "喷嘴" : "状态"),
        emptyLabel: "暂无数据",
        headers,
      },
    });

    expect(wrapper.text()).toContain("喷嘴");
    expect(wrapper.text()).toContain("218");
    expect(wrapper.text()).toContain("°C");
    expect(wrapper.text()).toContain(JSON.stringify({ source: "push_status" }));
    expect(wrapper.text()).toContain("RUNNING");
  });
});

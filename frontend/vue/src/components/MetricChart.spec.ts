import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { MetricSample } from "../types";
import MetricChart from "./MetricChart.vue";

const samples: MetricSample[] = [
  { id: 1, metric: "temperature.nozzle", value_float: 210, unit: "celsius", sampled_at: "2026-04-30T09:55:00Z" },
  { id: 2, metric: "temperature.nozzle", value_float: 218, unit: "celsius", sampled_at: "2026-04-30T10:00:00Z" },
  { id: 3, metric: "fan.cooling", value_float: 53, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
];

function mountChart(items: MetricSample[]) {
  return mount(MetricChart, {
    props: {
      title: "温度历史",
      subtitle: "最近 24 小时",
      items,
      metricLabel: (metric: string) => (metric === "temperature.nozzle" ? "喷嘴" : "风扇"),
      emptyLabel: "暂无曲线",
    },
  });
}

describe("MetricChart", () => {
  it("shows the empty state when samples are not numeric", () => {
    const wrapper = mountChart([{ id: 1, metric: "printer.state", value_text: "RUNNING", sampled_at: "2026-04-30T10:00:00Z" }]);

    expect(wrapper.text()).toContain("暂无曲线");
    expect(wrapper.find("svg.metric-chart").exists()).toBe(false);
  });

  it("renders numeric series and allows hiding all but one metric", async () => {
    const wrapper = mountChart(samples);

    expect(wrapper.text()).toContain("喷嘴");
    expect(wrapper.text()).toContain("风扇");
    expect(wrapper.findAll(".series-line")).toHaveLength(2);

    await wrapper.findAll(".chart-summary-item").find((item) => item.text().includes("风扇"))?.trigger("click");
    expect(wrapper.findAll(".series-line")).toHaveLength(1);

    await wrapper.findAll(".chart-summary-item").find((item) => item.text().includes("喷嘴"))?.trigger("click");
    expect(wrapper.findAll(".series-line")).toHaveLength(1);
  });
});

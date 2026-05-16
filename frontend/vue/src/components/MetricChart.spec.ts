import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import type { MetricSample } from "../types";
import MetricChart from "./MetricChart.vue";

const samples: MetricSample[] = [
  { id: 1, metric: "temperature.nozzle", value_float: 210, unit: "celsius", sampled_at: "2026-04-30T09:55:00Z" },
  { id: 2, metric: "temperature.nozzle", value_float: 218, unit: "celsius", sampled_at: "2026-04-30T10:00:00Z" },
  { id: 3, metric: "fan.cooling", value_float: 53, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
];

type MetricLabel = (metric: string) => string;

const defaultMetricLabel: MetricLabel = (metric) => (metric === "temperature.nozzle" ? "喷嘴" : "风扇");

function mountChart(items: MetricSample[], metricLabel: MetricLabel = defaultMetricLabel) {
  return mount(MetricChart, {
    props: {
      title: "温度历史",
      subtitle: "最近 24 小时",
      items,
      metricLabel,
      emptyLabel: "暂无曲线",
    },
  });
}

async function hoverChart(wrapper: ReturnType<typeof mountChart>, clientX = 360) {
  const svg = wrapper.find("svg.metric-chart").element as SVGSVGElement;
  vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 720,
    bottom: 240,
    width: 720,
    height: 240,
    toJSON: () => ({}),
  } as DOMRect);

  wrapper.find(".chart-axis-hit-area").element.dispatchEvent(
    new MouseEvent("pointermove", {
      bubbles: true,
      clientX,
    }),
  );
  await wrapper.vm.$nextTick();
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

  it("keeps a six-series tooltip inside the SVG viewBox", async () => {
    const wrapper = mountChart(
      Array.from({ length: 6 }, (_, index) => ({
        id: index + 1,
        metric: `temperature.tool${index}`,
        value_float: 200 + index,
        unit: "celsius",
        sampled_at: "2026-04-30T10:00:00Z",
      })),
    );
    await hoverChart(wrapper);

    const tooltipBackground = wrapper.find(".chart-tooltip-bg");
    expect(tooltipBackground.exists()).toBe(true);
    const transform = tooltipBackground.element.parentElement?.getAttribute("transform") || "";
    const tooltipY = Number(transform.match(/translate\([^,]+,\s*([^)]+)\)/)?.[1]);
    const tooltipHeight = Number(tooltipBackground.attributes("height"));
    expect(tooltipY + tooltipHeight).toBeLessThanOrEqual(240);
  });

  it("renders all AMS temperature and humidity series beyond six", async () => {
    const wrapper = mountChart(
      Array.from({ length: 10 }, (_, index) => ({
        id: index + 1,
        metric: `ams.${index}.temperature`,
        value_float: 20 + index,
        unit: "celsius",
        sampled_at: "2026-04-30T10:00:00Z",
      })),
      (metric) => metric.replace(".temperature", " · 温度"),
    );

    expect(wrapper.findAll(".chart-summary-item")).toHaveLength(10);
    expect(wrapper.findAll(".series-line")).toHaveLength(10);
    expect(wrapper.text()).toContain("ams.9 · 温度");
  });

  it("keeps a ten-series tooltip inside the dynamic SVG viewBox", async () => {
    const wrapper = mountChart(
      Array.from({ length: 10 }, (_, index) => ({
        id: index + 1,
        metric: `ams.${index}.humidity`,
        value_float: 20 + index,
        unit: "percent",
        sampled_at: "2026-04-30T10:00:00Z",
      })),
      (metric) => metric.replace(".humidity", " · 湿度"),
    );
    await hoverChart(wrapper);

    const tooltipBackground = wrapper.find(".chart-tooltip-bg");
    const transform = tooltipBackground.element.parentElement?.getAttribute("transform") || "";
    const tooltipY = Number(transform.match(/translate\([^,]+,\s*([^)]+)\)/)?.[1]);
    const tooltipHeight = Number(tooltipBackground.attributes("height"));
    const viewBox = wrapper.find("svg.metric-chart").attributes("viewBox");
    const viewBoxHeight = Number(viewBox?.split(" ")[3] || 0);
    expect(wrapper.findAll(".chart-tooltip-line")).toHaveLength(10);
    expect(tooltipY + tooltipHeight).toBeLessThanOrEqual(viewBoxHeight);
  });

  it("keeps AMS unit identifiers in tooltip labels", async () => {
    const wrapper = mountChart(
      [
        { id: 1, metric: "ams.0.humidity", value_float: 32, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 2, metric: "ams.1.humidity", value_float: 41, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
      ],
      (metric) => (metric === "ams.0.humidity" ? "AMS 0 · 湿度" : "AMS 1 · 湿度"),
    );

    await hoverChart(wrapper);

    const tooltipLines = wrapper.findAll(".chart-tooltip-line").map((item) => item.text());
    expect(tooltipLines).toEqual(
      expect.arrayContaining([expect.stringContaining("AMS 0 · 湿度"), expect.stringContaining("AMS 1 · 湿度")]),
    );
  });

  it("groups AMS temperature and humidity pairs by unit in the legend", () => {
    const wrapper = mountChart(
      [
        { id: 1, metric: "ams.1.temperature", value_float: 44, unit: "celsius", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 2, metric: "ams.128.humidity", value_float: 9, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 3, metric: "ams.0.humidity", value_float: 22, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 4, metric: "ams.1.humidity", value_float: 20, unit: "percent", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 5, metric: "ams.0.temperature", value_float: 45, unit: "celsius", sampled_at: "2026-04-30T10:00:00Z" },
        { id: 6, metric: "ams.128.temperature", value_float: 67, unit: "celsius", sampled_at: "2026-04-30T10:00:00Z" },
      ],
      (metric) => metric.replace(/^ams\.(\d+)\.temperature$/, "AMS $1 · 温度").replace(/^ams\.(\d+)\.humidity$/, "AMS $1 · 湿度"),
    );

    const labels = wrapper.findAll(".chart-summary-item").map((item) => item.text());
    expect(labels[0]).toContain("AMS 0 · 温度");
    expect(labels[1]).toContain("AMS 0 · 湿度");
    expect(labels[2]).toContain("AMS 1 · 温度");
    expect(labels[3]).toContain("AMS 1 · 湿度");
    expect(labels[4]).toContain("AMS 128 · 温度");
    expect(labels[5]).toContain("AMS 128 · 湿度");
  });

  it("shows the tooltip time once without repeating sample times in rows", async () => {
    const nozzleSampledAt = "2026-04-30T10:00:00Z";
    const fanSampledAt = "2026-04-30T10:10:00Z";
    const wrapper = mountChart([
      { id: 1, metric: "temperature.nozzle", value_float: 210, unit: "celsius", sampled_at: nozzleSampledAt },
      { id: 2, metric: "fan.cooling", value_float: 53, unit: "percent", sampled_at: fanSampledAt },
    ]);

    await hoverChart(wrapper);

    const tooltipLines = wrapper.findAll(".chart-tooltip-line").map((item) => item.text());
    expect(wrapper.find(".chart-tooltip-title").text()).toContain("Time:");
    expect(tooltipLines.find((line) => line.includes("喷嘴"))).not.toContain("2026-04-30");
    expect(tooltipLines.find((line) => line.includes("风扇"))).not.toContain("2026-04-30");
  });
});

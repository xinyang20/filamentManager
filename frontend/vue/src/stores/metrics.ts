import { computed, ref } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";
import { apiRequest } from "../api";
import type { MetricSample } from "../types";
import { useI18nStore } from "./i18n";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";

export const useMetricsStore = defineStore("metrics", () => {
  const { t } = useI18nStore();
  const printersStore = () => usePrintersStore();
  const presentationStore = () => usePresentationStore();

  const metrics = ref<MetricSample[]>([]);

  const metricRange = ref("6h");

  const metricRangeOptions = computed(() => [
    { label: t("metrics.range1h"), value: "1h" },
    { label: t("metrics.range6h"), value: "6h" },
    { label: t("metrics.range24h"), value: "24h" },
    { label: t("metrics.range7d"), value: "7d" },
    { label: t("metrics.range30d"), value: "30d" },
  ]);

  const metricGroups = computed(() => ({
    temperatures: metrics.value.filter((item) => item.metric.startsWith("temperature.")),
    fans: metrics.value.filter((item) => item.metric.startsWith("fan.") && item.metric !== "fan.fan_gear.percent"),
    ams: metrics.value.filter((item) => item.metric.startsWith("ams.")),
  }));

  const metricTooltipLabels = computed(() => ({
    time: t("table.time"),
    value: t("table.value"),
  }));


  async function loadMetrics() {
    if (!printersStore().selectedPrinterId) return;
    const since = metricSince();
    const bucket = metricBucket();
    const groups = ["temperature", "fan", "ams"];
    const results = await Promise.all(
      groups.map((group) =>
        apiRequest<MetricSample[]>(
          `/printers/${printersStore().selectedPrinterId}/metrics?limit=5000&bucket=${bucket}&group=${group}&since=${encodeURIComponent(since)}`,
        )
      ),
    );
    metrics.value = results.flat();
  }


  function metricBucket() {
    return metricRange.value === "1h" || metricRange.value === "6h" ? "minute" : "hour";
  }


  function metricSince() {
    const now = Date.now();
    const hours: Record<string, number> = { "1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7, "30d": 24 * 30 };
    return new Date(now - (hours[metricRange.value] || 6) * 60 * 60 * 1000).toISOString();
  }


  function metricLabel(metric: string) {
    const [group, ...rest] = metric.split(".");
    if (group === "ams" && rest.length > 1) {
      const field = rest.slice(1).join(".");
      return `${presentationStore().fieldLabel("ams")} ${rest[0]} · ${presentationStore().fieldLabel(field === "humidity" ? "humidity_raw" : field)}`;
    }
    if (group === "fan") {
      return fanMetricLabel(rest[0] || rest.join("."));
    }
    const field = rest.join(".");
    const groupLabel = presentationStore().fieldLabel(group);
    const fieldName = presentationStore().fieldLabel(field);
    return field ? `${groupLabel} · ${fieldName}` : groupLabel;
  }


  function fanMetricLabel(source: string) {
    const mapping: Record<string, string> = {
      cooling_fan_speed: "toolhead_fan",
      big_fan1_speed: "right_aux_fan",
      big_fan2_speed: "exhaust_fan",
      heatbreak_fan_speed: "heatbreak_fan",
      chamber_fan_speed: "chamber_fan",
      aux_part_fan_speed: "aux_part_fan",
      fan_gear: "fan_gear",
    };
    return presentationStore().fieldLabel(mapping[source] || source);
  }


  return {
    metrics,
    metricRange,
    metricRangeOptions,
    metricGroups,
    metricTooltipLabels,
    loadMetrics,
    metricBucket,
    metricSince,
    metricLabel,
    fanMetricLabel,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useMetricsStore, import.meta.hot));
}

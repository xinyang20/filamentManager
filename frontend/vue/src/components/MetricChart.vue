<script setup lang="ts">
import { computed } from "vue";
import { formatUnit } from "../api";
import type { MetricSample } from "../types";

const props = defineProps<{
  title: string;
  subtitle: string;
  items: MetricSample[];
  metricLabel: (metric: string) => string;
  emptyLabel: string;
}>();

const width = 720;
const height = 220;
const padding = { top: 16, right: 20, bottom: 24, left: 42 };
const colors = ["#00AE42", "#0033FF", "#00B1B7", "#C37A00", "#C53333", "#5E43B7"];

const numericItems = computed(() =>
  props.items
    .filter((item) => typeof item.value_float === "number" && Number.isFinite(item.value_float))
    .sort((a, b) => new Date(a.sampled_at).getTime() - new Date(b.sampled_at).getTime()),
);

const series = computed(() => {
  const grouped = new Map<string, MetricSample[]>();
  for (const item of numericItems.value) {
    const list = grouped.get(item.metric) || [];
    list.push(item);
    grouped.set(item.metric, list);
  }
  return Array.from(grouped.entries()).slice(0, 6).map(([metric, points], index) => ({
    metric,
    label: props.metricLabel(metric),
    points,
    color: colors[index % colors.length],
    latest: points[points.length - 1],
  }));
});

const domain = computed(() => {
  const values = numericItems.value.map((item) => item.value_float as number);
  if (!values.length) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  const pad = (max - min) * 0.12;
  return { min: min - pad, max: max + pad };
});

const timeDomain = computed(() => {
  const times = numericItems.value.map((item) => new Date(item.sampled_at).getTime());
  if (!times.length) {
    const now = Date.now();
    return { min: now - 1, max: now };
  }
  const min = Math.min(...times);
  const max = Math.max(...times);
  return min === max ? { min: min - 1, max: max + 1 } : { min, max };
});

const latestItems = computed(() =>
  series.value.map((item) => ({
    metric: item.metric,
    label: item.label,
    color: item.color,
    value: item.latest?.value_float ?? undefined,
    unit: item.latest?.unit || "",
  })),
);

function x(sample: MetricSample) {
  const time = new Date(sample.sampled_at).getTime();
  const span = timeDomain.value.max - timeDomain.value.min;
  return padding.left + ((time - timeDomain.value.min) / span) * (width - padding.left - padding.right);
}

function y(value: number) {
  const span = domain.value.max - domain.value.min;
  return padding.top + (1 - (value - domain.value.min) / span) * (height - padding.top - padding.bottom);
}

function linePath(points: MetricSample[]) {
  return points
    .map((point, index) => {
      const value = point.value_float as number;
      return `${index === 0 ? "M" : "L"} ${x(point).toFixed(2)} ${y(value).toFixed(2)}`;
    })
    .join(" ");
}

function areaPath(points: MetricSample[]) {
  if (!points.length) return "";
  const baseline = height - padding.bottom;
  const line = linePath(points);
  const first = points[0];
  const last = points[points.length - 1];
  return `${line} L ${x(last).toFixed(2)} ${baseline} L ${x(first).toFixed(2)} ${baseline} Z`;
}

function formatNumber(value: number | undefined) {
  if (value === undefined) return "—";
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

function unitLabel(value: string) {
  return value ? formatUnit(value) : "";
}
</script>

<template>
  <section class="panel chart-panel">
    <div class="panel-header">
      <div>
        <h3>{{ title }}</h3>
        <p class="panel-subtitle">{{ subtitle }}</p>
      </div>
    </div>

    <div v-if="!numericItems.length" class="chart-empty">{{ emptyLabel }}</div>
    <template v-else>
      <div class="chart-summary">
        <div v-for="item in latestItems" :key="item.metric" class="chart-summary-item">
          <span class="legend-dot" :style="{ background: item.color }"></span>
          <span class="summary-label">{{ item.label }}</span>
          <strong>{{ formatNumber(item.value) }} {{ unitLabel(item.unit) }}</strong>
        </div>
      </div>

      <svg class="metric-chart" :viewBox="`0 0 ${width} ${height}`" role="img">
        <line :x1="padding.left" :x2="width - padding.right" :y1="height - padding.bottom" :y2="height - padding.bottom" class="axis-line" />
        <line :x1="padding.left" :x2="padding.left" :y1="padding.top" :y2="height - padding.bottom" class="axis-line" />
        <text :x="padding.left - 8" :y="padding.top + 4" class="axis-label" text-anchor="end">{{ formatNumber(domain.max) }}</text>
        <text :x="padding.left - 8" :y="height - padding.bottom" class="axis-label" text-anchor="end">{{ formatNumber(domain.min) }}</text>
        <g v-for="item in series" :key="item.metric">
          <path :d="areaPath(item.points)" :fill="item.color" opacity="0.08" />
          <path :d="linePath(item.points)" :stroke="item.color" class="series-line" />
          <circle
            v-for="point in item.points.slice(-18)"
            :key="`${item.metric}-${point.id}`"
            :cx="x(point)"
            :cy="y(point.value_float as number)"
            r="2.5"
            :fill="item.color"
          />
        </g>
      </svg>

      <div class="chart-legend">
        <span v-for="item in series" :key="item.metric">
          <i :style="{ background: item.color }"></i>{{ item.label }}
        </span>
      </div>
    </template>
  </section>
</template>

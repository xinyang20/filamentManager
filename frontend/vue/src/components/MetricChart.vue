<script setup lang="ts">
import { computed, ref } from "vue";
import { formatUnit, parseApiDateTime } from "../api";
import type { MetricSample } from "../types";

const props = defineProps<{
  title: string;
  subtitle: string;
  items: MetricSample[];
  metricLabel: (metric: string) => string;
  emptyLabel: string;
  tooltipLabels?: {
    time: string;
    value: string;
  };
}>();

const width = 720;
const baseHeight = 240;
const padding = { top: 16, right: 20, bottom: 40, left: 42 };
const colors = [
  "#00AE42",
  "#0033FF",
  "#00B1B7",
  "#C37A00",
  "#C53333",
  "#5E43B7",
  "#FF6A13",
  "#0077B6",
  "#7A8A3A",
  "#8B4E2F",
  "#D43F8D",
  "#4D7CFE",
];
const hovered = ref<{
  x: number;
  time: number;
  rows: {
    metric: string;
    label: string;
    color: string;
    point: MetricSample;
    x: number;
    y: number;
  }[];
} | null>(null);
const hiddenMetrics = ref<Set<string>>(new Set());

const numericItems = computed(() =>
  props.items
    .filter((item) => typeof item.value_float === "number" && Number.isFinite(item.value_float))
    .sort((a, b) => sampleTime(a) - sampleTime(b)),
);

const series = computed(() => {
  const grouped = new Map<string, MetricSample[]>();
  for (const item of numericItems.value) {
    const list = grouped.get(item.metric) || [];
    list.push(item);
    grouped.set(item.metric, list);
  }
  return Array.from(grouped.entries())
    .map(([metric, points], index) => ({ metric, points, index }))
    .sort((left, right) => compareMetricOrder(left.metric, right.metric, left.index, right.index))
    .map(({ metric, points }, index) => ({
      metric,
      label: props.metricLabel(metric),
      points,
      color: colors[index % colors.length],
      latest: points[points.length - 1],
    }));
});

const visibleSeries = computed(() => series.value.filter((item) => !hiddenMetrics.value.has(item.metric)));
const visibleItems = computed(() => visibleSeries.value.flatMap((item) => item.points));
const height = computed(() => Math.max(baseHeight, 62 + visibleSeries.value.length * 30));

const domain = computed(() => {
  const values = visibleItems.value.map((item) => item.value_float as number);
  if (!values.length) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  const pad = (max - min) * 0.12;
  return { min: min - pad, max: max + pad };
});

const timeDomain = computed(() => {
  const times = numericItems.value.map(sampleTime);
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
    hidden: hiddenMetrics.value.has(item.metric),
  })),
);

const xTicks = computed(() => {
  if (!numericItems.value.length) return [];
  const span = timeDomain.value.max - timeDomain.value.min;
  return [0, 1 / 3, 2 / 3, 1].map((ratio, index) => {
    const value = timeDomain.value.min + span * ratio;
    return {
      key: `${index}-${Math.round(value)}`,
      x: padding.left + ratio * (width - padding.left - padding.right),
      value,
      label: formatAxisTime(value),
    };
  });
});

function x(sample: MetricSample) {
  const time = sampleTime(sample);
  return xAtTime(time);
}

function xAtTime(time: number) {
  const span = timeDomain.value.max - timeDomain.value.min;
  return padding.left + ((time - timeDomain.value.min) / span) * (width - padding.left - padding.right);
}

function y(value: number) {
  const span = domain.value.max - domain.value.min;
  return padding.top + (1 - (value - domain.value.min) / span) * (height.value - padding.top - padding.bottom);
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
  const baseline = height.value - padding.bottom;
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

function sampleTime(sample: MetricSample) {
  return parseApiDateTime(sample.sampled_at)?.getTime() ?? new Date(sample.sampled_at).getTime();
}

function compareMetricOrder(leftMetric: string, rightMetric: string, leftIndex: number, rightIndex: number) {
  const leftAms = parseAmsMetric(leftMetric);
  const rightAms = parseAmsMetric(rightMetric);
  if (leftAms && rightAms) {
    return (
      leftAms.unitOrder - rightAms.unitOrder ||
      leftAms.unitLabel.localeCompare(rightAms.unitLabel) ||
      leftAms.kindOrder - rightAms.kindOrder ||
      leftAms.kind.localeCompare(rightAms.kind) ||
      leftIndex - rightIndex
    );
  }
  return leftIndex - rightIndex;
}

function parseAmsMetric(metric: string) {
  const match = /^ams\.([^.]+)\.(.+)$/.exec(metric);
  if (!match) return null;
  const unitNumber = Number(match[1]);
  const kind = match[2];
  return {
    unitLabel: match[1],
    unitOrder: Number.isFinite(unitNumber) ? unitNumber : Number.MAX_SAFE_INTEGER,
    kind,
    kindOrder: kind === "temperature" ? 0 : kind === "humidity" ? 1 : 2,
  };
}

function unitLabel(value: string) {
  return value ? formatUnit(value) : "";
}

function hoverAxis(event: PointerEvent) {
  if (!visibleSeries.value.length) return;
  const svg = event.currentTarget instanceof SVGElement ? event.currentTarget.ownerSVGElement : null;
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  const pointerX = ((event.clientX - rect.left) / rect.width) * width;
  const plotLeft = padding.left;
  const plotRight = width - padding.right;
  const clampedX = Math.min(Math.max(pointerX, plotLeft), plotRight);
  const ratio = (clampedX - plotLeft) / (plotRight - plotLeft);
  const time = timeDomain.value.min + ratio * (timeDomain.value.max - timeDomain.value.min);
  const rows = visibleSeries.value
    .map((item) => {
      const point = nearestPoint(item.points, time);
      const value = point?.value_float;
      if (!point || typeof value !== "number") return null;
      return {
        metric: item.metric,
        label: item.label,
        color: item.color,
        point,
        x: x(point),
        y: y(value),
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);
  hovered.value = rows.length ? { x: clampedX, time, rows } : null;
}

function clearHover() {
  hovered.value = null;
}

function tooltipX(value: number) {
  return Math.min(Math.max(value + 12, padding.left), width - tooltipWidth.value - 10);
}

function tooltipY() {
  const margin = 4;
  const maxY = Math.max(0, height.value - tooltipHeight.value - margin);
  return Math.min(padding.top + 8, maxY);
}

function hoverValue(item: MetricSample) {
  return `${formatNumber(item.value_float ?? undefined)} ${unitLabel(item.unit || "")}`.trim();
}

function estimateTextWidth(text: string, fontSize: number) {
  let width = 0;
  for (const char of text) {
    const code = char.codePointAt(0) || 0;
    if (char === " ") {
      width += fontSize * 0.35;
    } else if (code > 255) {
      width += fontSize;
    } else {
      width += fontSize * 0.62;
    }
  }
  return width;
}

function nearestPoint(points: MetricSample[], time: number) {
  if (!points.length) return null;
  let best = points[0];
  let bestDistance = Math.abs(sampleTime(best) - time);
  for (let index = 1; index < points.length; index += 1) {
    const point = points[index];
    const distance = Math.abs(sampleTime(point) - time);
    if (distance < bestDistance) {
      best = point;
      bestDistance = distance;
    }
  }
  return best;
}

function toggleMetric(metric: string) {
  const next = new Set(hiddenMetrics.value);
  if (next.has(metric)) {
    next.delete(metric);
  } else {
    const visibleCount = series.value.filter((item) => !next.has(item.metric)).length;
    if (visibleCount <= 1) return;
    next.add(metric);
  }
  hiddenMetrics.value = next;
  clearHover();
}

function formatAxisTime(value: number) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

function tickAnchor(index: number) {
  if (index === 0) return "start";
  if (index === xTicks.value.length - 1) return "end";
  return "middle";
}

const tooltipHeight = computed(() => Math.max(104, 54 + (hovered.value?.rows.length || 0) * 30));
const tooltipTitle = computed(() => {
  if (!hovered.value) return "";
  return `${props.tooltipLabels?.time || "Time"}: ${formatAxisTime(hovered.value.time)}`;
});
const tooltipRows = computed(() =>
  (hovered.value?.rows || []).map((row) => {
    const value = hoverValue(row.point);
    return {
      ...row,
      label: row.label,
      value,
      text: `${row.label}: ${value}`,
    };
  }),
);
const tooltipWidth = computed(() => {
  const lineWidths = [
    estimateTextWidth(tooltipTitle.value, 20),
    ...tooltipRows.value.map((row) => estimateTextWidth(row.text, 18)),
  ];
  const contentWidth = Math.max(180, ...lineWidths);
  return Math.min(560, Math.ceil(contentWidth + 32));
});
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
        <button
          v-for="item in latestItems"
          :key="item.metric"
          class="chart-summary-item"
          :class="{ off: item.hidden }"
          type="button"
          @click="toggleMetric(item.metric)"
        >
          <span class="legend-dot" :style="{ background: item.color }"></span>
          <span class="summary-label">{{ item.label }}</span>
          <strong>{{ formatNumber(item.value) }} {{ unitLabel(item.unit) }}</strong>
        </button>
      </div>

      <svg class="metric-chart" :style="{ height: `${height}px` }" :viewBox="`0 0 ${width} ${height}`" role="img">
        <line :x1="padding.left" :x2="width - padding.right" :y1="height - padding.bottom" :y2="height - padding.bottom" class="axis-line" />
        <line :x1="padding.left" :x2="padding.left" :y1="padding.top" :y2="height - padding.bottom" class="axis-line" />
        <text :x="padding.left - 8" :y="padding.top + 4" class="axis-label" text-anchor="end">{{ formatNumber(domain.max) }}</text>
        <text :x="padding.left - 8" :y="height - padding.bottom" class="axis-label" text-anchor="end">{{ formatNumber(domain.min) }}</text>
        <g v-for="(tick, index) in xTicks" :key="tick.key">
          <line :x1="tick.x" :x2="tick.x" :y1="padding.top" :y2="height - padding.bottom" class="grid-line" />
          <line :x1="tick.x" :x2="tick.x" :y1="height - padding.bottom" :y2="height - padding.bottom + 5" class="axis-line" />
          <text :x="tick.x" :y="height - 14" class="axis-label" :text-anchor="tickAnchor(index)">{{ tick.label }}</text>
        </g>
        <g v-for="item in visibleSeries" :key="item.metric">
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
        <rect
          :x="padding.left"
          :y="padding.top"
          :width="width - padding.left - padding.right"
          :height="height - padding.top - padding.bottom"
          class="chart-axis-hit-area"
          @pointermove="hoverAxis"
          @pointerleave="clearHover"
        />
        <g v-if="hovered" class="chart-hover">
          <line :x1="hovered.x" :x2="hovered.x" :y1="padding.top" :y2="height - padding.bottom" class="hover-line" />
          <circle
            v-for="row in hovered.rows"
            :key="`hover-${row.metric}`"
            :cx="row.x"
            :cy="row.y"
            r="4.5"
            :fill="row.color"
            class="hover-dot"
          />
          <g :transform="`translate(${tooltipX(hovered.x)}, ${tooltipY()})`">
            <rect :width="tooltipWidth" :height="tooltipHeight" rx="8" class="chart-tooltip-bg" />
            <text x="16" y="30" class="chart-tooltip-title">{{ tooltipTitle }}</text>
            <text
              v-for="(row, index) in tooltipRows"
              :key="`tip-${row.metric}`"
              x="16"
              :y="68 + index * 30"
              class="chart-tooltip-line"
            >
              {{ row.text }}
            </text>
          </g>
        </g>
      </svg>

    </template>
  </section>
</template>

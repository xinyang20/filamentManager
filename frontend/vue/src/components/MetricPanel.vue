<script setup lang="ts">
import { LineChart } from "lucide-vue-next";
import { formatCell, formatUnit } from "../api";
import type { MetricSample } from "../types";

defineProps<{
  title: string;
  items: MetricSample[];
  metricLabel: (metric: string) => string;
  emptyLabel: string;
  headers: {
    time: string;
    metric: string;
    value: string;
    unit: string;
    details: string;
  };
}>();

function metricValue(item: MetricSample) {
  return item.value_float ?? item.value_text ?? "—";
}

function unitLabel(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  return formatUnit(value);
}

function detailText(item: MetricSample) {
  const details = item.details || {};
  return Object.keys(details).length ? JSON.stringify(details) : "—";
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h3>{{ title }}</h3>
      <LineChart :size="18" />
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ headers.time }}</th>
            <th>{{ headers.metric }}</th>
            <th>{{ headers.value }}</th>
            <th>{{ headers.unit }}</th>
            <th>{{ headers.details }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="5" class="empty">{{ emptyLabel }}</td>
          </tr>
          <tr v-for="item in items" :key="item.id">
            <td>{{ formatCell(item.sampled_at) }}</td>
            <td>{{ metricLabel(item.metric) }}</td>
            <td>{{ metricValue(item) }}</td>
            <td>{{ unitLabel(item.unit) }}</td>
            <td>{{ detailText(item) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

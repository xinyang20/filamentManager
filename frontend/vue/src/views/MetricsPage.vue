<script setup lang="ts">
import { appViewRefs, type AppViewContext } from "../app/viewContext";
import {
  Activity,
  AlertCircle,
  Archive,
  Bell,
  Boxes,
  Camera,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  Eye,
  EyeOff,
  FileDown,
  Gauge,
  LineChart,
  Loader2,
  Network,
  PencilLine,
  Plus,
  PlugZap,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings,
  ShieldAlert,
  Star,
  Thermometer,
  Trash2,
  Unplug,
  Upload,
  Wrench,
  X,
} from "lucide-vue-next";
import AppSelect from "../components/AppSelect.vue";
import MetricChart from "../components/MetricChart.vue";

const props = defineProps<{ ctx: AppViewContext }>();
const {
  activeView,
  fans,
  loadMetrics,
  metricGroups,
  metricLabel,
  metricRange,
  metricRangeOptions,
  metricTooltipLabels,
  metrics,
  t,
  temperatures,
  withLoading,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar filters">
          <AppSelect v-model="metricRange" :options="metricRangeOptions" @change="withLoading(loadMetrics)" />
        </div>
        <div class="metrics-chart-grid">
          <MetricChart
            :title="t('metrics.temperatureHistory')"
            :subtitle="t('metrics.temperatureSubtitle')"
            :items="metricGroups.temperatures"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
          <MetricChart
            :title="t('metrics.fanHistory')"
            :subtitle="t('metrics.fanSubtitle')"
            :items="metricGroups.fans"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
          <MetricChart
            :title="t('metrics.amsHistory')"
            :subtitle="t('metrics.amsSubtitle')"
            :items="metricGroups.ams"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
        </div>
      </section>
</template>

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
  compactHotendLabel,
  dashboard,
  formatCell,
  metrics,
  openPrinterDashboard,
  overviewControls,
  overviewDensityOptions,
  overviewFilterOptions,
  overviewItems,
  overviewSortOptions,
  overviewStats,
  printers,
  summaryActiveHmsCount,
  summaryCoveragePercent,
  summaryLayerFraction,
  summaryNozzleTemperatureRows,
  summaryProgress,
  summaryStage,
  summaryStatusLabel,
  summaryTaskName,
  summaryTemperature,
  summaryTone,
  summaryWifi,
  switchView,
  t,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar filters overview-toolbar">
          <label class="search-field">
            <Search :size="16" />
            <input v-model="overviewControls.search" :placeholder="t('overview.search')" />
          </label>
          <AppSelect v-model="overviewControls.filter" :options="overviewFilterOptions" />
          <AppSelect v-model="overviewControls.sort" :options="overviewSortOptions" />
          <AppSelect v-model="overviewControls.density" :options="overviewDensityOptions" />
        </div>
        <div class="metric-grid overview-metrics">
          <div v-for="item in overviewStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
            <div class="metric-foot">{{ item.foot }}</div>
          </div>
        </div>

        <section v-if="!overviewItems.length" class="panel empty-overview">
          <h3>{{ t("overview.noPrinters") }}</h3>
          <p>{{ t("overview.noPrintersHint") }}</p>
          <button class="primary" type="button" @click="switchView('printers')">
            <Settings :size="17" />
            {{ t("overview.configurePrinter") }}
          </button>
        </section>

        <div v-else class="fleet-grid" :class="`density-${overviewControls.density}`">
          <article
            v-for="item in overviewItems"
            :key="item.printer.id"
            class="fleet-card"
            :class="summaryTone(item)"
          >
            <div class="fleet-card-header">
              <div>
                <div class="fleet-name">{{ item.printer.name }}</div>
                <div class="fleet-host">{{ item.printer.host }}</div>
              </div>
              <span class="status-pill" :class="summaryTone(item)">
                <span class="dot"></span>
                {{ summaryStatusLabel(item) }}
              </span>
            </div>

            <div class="fleet-task">
              <div class="mini-label">{{ t("overview.currentTask") }}</div>
              <strong>{{ summaryTaskName(item) }}</strong>
              <span>{{ summaryStage(item) }}</span>
            </div>

            <div class="fleet-progress">
              <div>
                <span>{{ t("overview.progress") }}</span>
                <strong>{{ summaryProgress(item) }}%</strong>
              </div>
              <div class="progress-track">
                <span :style="{ width: `${summaryProgress(item)}%` }"></span>
              </div>
            </div>

            <div v-if="overviewControls.density !== 'compact'" class="fleet-metrics">
              <div>
                <span>{{ t("dashboard.nozzle") }}</span>
                <strong v-if="summaryNozzleTemperatureRows(item).length <= 1">{{ summaryNozzleTemperatureRows(item)[0]?.current !== undefined ? `${formatCell(summaryNozzleTemperatureRows(item)[0]?.current)}℃` : `${summaryTemperature(item, "nozzle")}℃` }}</strong>
                <strong v-else class="fleet-hotends">
                  <span v-for="hotend in summaryNozzleTemperatureRows(item)" :key="hotend.key">
                    <em>{{ compactHotendLabel(hotend.key, hotend.label) }}</em>
                    {{ formatCell(hotend.current) }}℃
                  </span>
                </strong>
              </div>
              <div>
                <span>{{ t("dashboard.bed") }}</span>
                <strong>{{ summaryTemperature(item, "bed") }}℃</strong>
              </div>
              <div>
                <span>WiFi</span>
                <strong>{{ summaryWifi(item) }}</strong>
              </div>
              <div>
                <span>{{ t("dashboard.dataCoverage") }}</span>
                <strong>{{ summaryCoveragePercent(item) }}%</strong>
              </div>
            </div>

            <div v-if="overviewControls.density === 'detailed'" class="fleet-detail-row">
              <span>{{ t("dashboard.layers") }} {{ summaryLayerFraction(item) }}</span>
              <span>HMS {{ summaryActiveHmsCount(item) }}</span>
              <span>{{ t("maintenance.due") }} {{ item.maintenance_due_count || 0 }}</span>
            </div>

            <div class="fleet-card-footer">
              <span>{{ t("overview.lastSync") }} {{ formatCell(item.printer.last_sync_at) }}</span>
              <div class="row-actions">
                <button class="secondary" type="button" @click="openPrinterDashboard(item.printer.id)">
                  <Gauge :size="17" />
                  {{ t("overview.openDashboard") }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
</template>

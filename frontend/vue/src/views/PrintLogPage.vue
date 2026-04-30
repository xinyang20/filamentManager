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
  applyPrintLogFilters,
  changePrintLogPage,
  dashboard,
  displayCell,
  formatCell,
  formatDurationSeconds,
  metrics,
  percent,
  percentageLabel,
  printLogAnalytics,
  printLogFilters,
  printLogPage,
  printLogPrinterOptions,
  printLogStatusOptions,
  printLogSummary,
  printLogTone,
  printLogTotal,
  printLogTotalPages,
  printLogs,
  softCell,
  t,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar filters">
          <AppSelect v-model="printLogFilters.printer_id" :options="printLogPrinterOptions" />
          <AppSelect v-model="printLogFilters.status" :options="printLogStatusOptions" />
          <input v-model="printLogFilters.search" :placeholder="t('printLog.search')" />
          <input v-model="printLogFilters.date_from" type="date" />
          <input v-model="printLogFilters.date_to" type="date" />
          <button class="primary" type="button" @click="applyPrintLogFilters">
            <Search :size="17" />
            {{ t("printLog.applyFilters") }}
          </button>
        </div>

        <div class="metric-grid overview-metrics">
          <div class="metric-card">
            <div class="metric-label">{{ t("printLog.total") }}</div>
            <div class="metric-value">{{ printLogSummary?.total || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("values.succeeded") }}</div>
            <div class="metric-value">{{ printLogSummary?.succeeded || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("values.failed") }}</div>
            <div class="metric-value">{{ printLogSummary?.failed || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("printLog.totalDuration") }}</div>
            <div class="metric-value compact-value">{{ formatDurationSeconds(printLogSummary?.total_duration_seconds) }}</div>
          </div>
        </div>

        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printLog.analytics") }}</h3><LineChart :size="18" /></div>
            <div class="analytics-strip">
              <div><span>{{ t("printLog.successRate") }}</span><strong>{{ percentageLabel(printLogAnalytics?.success_rate) }}</strong></div>
              <div><span>{{ t("printLog.failureRate") }}</span><strong>{{ percentageLabel(printLogAnalytics?.failure_rate) }}</strong></div>
              <div><span>{{ t("printLog.averageDuration") }}</span><strong>{{ formatDurationSeconds(printLogAnalytics?.average_duration_seconds) }}</strong></div>
              <div><span>{{ t("printLog.longestDuration") }}</span><strong>{{ formatDurationSeconds(printLogAnalytics?.longest_duration_seconds) }}</strong></div>
            </div>
            <div class="trend-bars">
              <div v-for="bucket in printLogAnalytics?.by_date || []" :key="bucket.bucket" class="trend-row">
                <span>{{ bucket.bucket }}</span>
                <div class="bar"><i :style="{ width: `${percent(bucket.total, 0)}%` }"></i></div>
                <strong>{{ bucket.total }}</strong>
              </div>
              <div v-if="!printLogAnalytics?.by_date?.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printLog.failureRanking") }}</h3><ShieldAlert :size="18" /></div>
            <div class="table-wrap compact-table">
              <table>
                <thead><tr><th>{{ t("printLog.failureReason") }}</th><th>{{ t("table.value") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!printLogAnalytics?.by_failure_reason?.length"><td colspan="2" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="item in printLogAnalytics?.by_failure_reason || []" :key="item.reason">
                    <td>{{ item.reason }}</td>
                    <td>{{ item.count }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <section class="panel">
          <div class="panel-header">
            <h3>{{ t("nav.printLog") }}</h3>
            <ClipboardList :size="18" />
          </div>
          <div class="table-wrap tall-table">
            <table>
              <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("table.printer") }}</th><th>{{ t("table.status") }}</th><th>{{ t("printLog.startedAt") }}</th><th>{{ t("printLog.duration") }}</th><th>{{ t("overview.progress") }}</th><th>{{ t("dashboard.layers") }}</th><th>{{ t("printLog.failureReason") }}</th></tr></thead>
              <tbody>
                <tr v-if="!printLogs.length"><td colspan="8" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="log in printLogs" :key="log.id">
                  <td>{{ formatCell(log.print_name || log.gcode_file) }}</td>
                  <td>{{ formatCell(log.printer_name_snapshot || log.printer_id) }}</td>
                  <td><span class="status-pill" :class="printLogTone(log.status)"><span class="dot"></span>{{ displayCell(log.status) }}</span></td>
                  <td>{{ formatCell(log.started_at) }}</td>
                  <td>{{ formatDurationSeconds(log.duration_seconds) }}</td>
                  <td>{{ formatCell(log.max_progress ?? log.final_progress) }}%</td>
                  <td>{{ softCell(log.layer_current) }} / {{ softCell(log.layer_total) }}</td>
                  <td>{{ softCell(log.failure_reason) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <button class="secondary" type="button" :disabled="printLogFilters.offset <= 0" @click="changePrintLogPage(-1)">{{ t("printLog.prev") }}</button>
            <span>{{ printLogPage }} / {{ printLogTotalPages }} · {{ printLogTotal }}</span>
            <button class="secondary" type="button" :disabled="printLogPage >= printLogTotalPages" @click="changePrintLogPage(1)">{{ t("printLog.next") }}</button>
          </div>
        </section>
      </section>
</template>

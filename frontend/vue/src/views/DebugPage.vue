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
  checkboxChecked,
  displayCell,
  downloadExport,
  downloadSupportBundle,
  enforceDatabaseRetention,
  eventMessage,
  eventTypeLabel,
  events,
  experimentalFeatureItems,
  experimentalFeatures,
  exportOptions,
  exportSectionItems,
  formatBytes,
  formatCell,
  formatDurationSeconds,
  importBackupFile,
  importFileInput,
  importModeOptions,
  importOptions,
  importResult,
  message,
  network,
  databaseRetention,
  databaseRetentionLastCleanupLabel,
  pendingRawMqttDbLimit,
  rawMqtt,
  rawMqttDbLimitOptions,
  recentEvents,
  saveRawMqttDbLimit,
  switchView,
  systemInfo,
  t,
  toggleExportSection,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <section class="panel">
          <div class="panel-header">
            <h3>{{ t("debug.systemInfo") }}</h3>
            <div class="widget-tools">
              <span class="retention-toolbar-label">{{ t("debug.databaseLimit") }}</span>
              <AppSelect v-model="pendingRawMqttDbLimit" class="retention-select" :options="rawMqttDbLimitOptions" @change="saveRawMqttDbLimit" />
              <button class="secondary retention-check-button" type="button" :disabled="databaseRetention?.retention_running" @click="enforceDatabaseRetention">
                <RefreshCw :size="17" />
                {{ t("debug.retentionEnforce") }}
              </button>
              <button v-if="experimentalFeatures.notifications" class="secondary" type="button" @click="switchView('notifications')">
                <Bell :size="17" />
                {{ t("nav.notifications") }}
              </button>
              <button class="secondary" type="button" @click="downloadSupportBundle">
                <Download :size="17" />
                {{ t("debug.supportBundle") }}
              </button>
              <Database :size="18" />
            </div>
          </div>
          <div class="network-info-grid system-info-grid">
            <div class="network-info-item"><span>{{ t("debug.appVersion") }}</span><strong>{{ systemInfo?.app_version || "--" }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.uptime") }}</span><strong>{{ formatDurationSeconds(systemInfo?.uptime_seconds) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.databaseSize") }}</span><strong>{{ formatBytes(systemInfo?.database_size_bytes || 0) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.storageSize") }}</span><strong>{{ formatBytes(systemInfo?.storage_size_bytes || 0) }}</strong></div>
            <div class="network-info-item"><span>CPU</span><strong>{{ formatCell(systemInfo?.cpu_percent) }}%</strong></div>
            <div class="network-info-item"><span>{{ t("debug.memory") }}</span><strong>{{ formatBytes(Number(systemInfo?.memory?.project_rss_bytes || systemInfo?.memory?.rss_bytes || 0)) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.configuredPrinters") }}</span><strong>{{ systemInfo?.configured_printers || 0 }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.onlinePrinters") }}</span><strong>{{ systemInfo?.online_printers || 0 }}</strong></div>
          </div>
          <div class="network-info-grid retention-info-grid">
            <div class="network-info-item">
              <span>{{ t("debug.retentionLimit") }}</span>
              <strong>{{ databaseRetention?.limit_bytes ? formatBytes(databaseRetention.limit_bytes) : t("debug.retentionLimitUnlimited") }}</strong>
            </div>
            <div class="network-info-item">
              <span>{{ t("debug.retentionThreshold") }}</span>
              <strong>{{ databaseRetention?.trigger_threshold_bytes ? formatBytes(databaseRetention.trigger_threshold_bytes) : "—" }}</strong>
            </div>
            <div class="network-info-item"><span>{{ t("debug.rawMqttRows") }}</span><strong>{{ databaseRetention?.raw_mqtt_row_count || 0 }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.rawPayloadSize") }}</span><strong>{{ formatBytes(databaseRetention?.raw_mqtt_payload_bytes_estimate || 0) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.rawMqttOldest") }}</span><strong>{{ formatCell(databaseRetention?.raw_mqtt_oldest_received_at) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.rawMqttNewest") }}</span><strong>{{ formatCell(databaseRetention?.raw_mqtt_newest_received_at) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.retentionSupported") }}</span><strong>{{ databaseRetention?.enforcement_supported ? t("common.yes") : t("common.no") }}</strong></div>
            <div class="network-info-item">
              <span>{{ t("debug.retentionLastCleanup") }}</span>
              <strong>{{ databaseRetention?.retention_running ? t("debug.retentionRunning") : databaseRetentionLastCleanupLabel }}</strong>
            </div>
          </div>
        </section>
        <section class="panel experimental-panel">
          <div class="panel-header"><h3>{{ t("debug.experimentalFeatures") }}</h3><ShieldAlert :size="18" /></div>
          <p class="panel-subtitle experimental-note">{{ t("debug.experimentalHint") }}</p>
          <div class="experimental-feature-grid">
            <label v-for="item in experimentalFeatureItems" :key="item.key" class="experimental-toggle-row">
              <span class="experimental-toggle-copy">
                <strong>{{ item.label }}</strong>
                <span>{{ item.description }}</span>
              </span>
              <input v-model="experimentalFeatures[item.key]" type="checkbox" />
              <span class="app-switch" :class="{ on: experimentalFeatures[item.key] }" aria-hidden="true"><i></i></span>
              <em>{{ experimentalFeatures[item.key] ? t("common.on") : t("common.off") }}</em>
            </label>
          </div>
        </section>
        <section class="panel export-panel">
          <div class="panel-header"><h3>{{ t("export.title") }}</h3><FileDown :size="18" /></div>
          <p class="panel-subtitle">{{ t("export.backupHint") }}</p>
          <div class="export-controls">
            <AppSelect v-model="exportOptions.type" :options="[{ label: 'JSON', value: 'json' }, { label: 'CSV ZIP', value: 'csv' }]" />
            <button class="primary" type="button" @click="downloadExport"><Download :size="17" />{{ t("export.download") }}</button>
          </div>
          <div class="export-section-grid">
            <label v-for="section in exportSectionItems" :key="section.key" class="checkbox export-section">
              <input
                type="checkbox"
                :checked="exportOptions.sections.includes(section.key)"
                @change="toggleExportSection(section.key, checkboxChecked($event))"
              />
              {{ section.label }}
            </label>
          </div>
        </section>
        <section class="panel export-panel">
          <div class="panel-header"><h3>{{ t("export.importTitle") }}</h3><Upload :size="18" /></div>
          <p class="panel-subtitle">{{ t("export.importHint") }}</p>
          <div class="export-controls">
            <AppSelect v-model="importOptions.mode" :options="importModeOptions" />
            <button class="primary" type="button" @click="importFileInput?.click()"><Upload :size="17" />{{ t("export.importJson") }}</button>
            <input ref="importFileInput" class="hidden-file-input" type="file" accept="application/json,.json" @change="importBackupFile" />
          </div>
          <pre v-if="importResult" class="json-block import-result">{{ JSON.stringify(importResult.counts || importResult, null, 2) }}</pre>
        </section>
        <div class="grid two wide debug-grid">
          <section class="panel debug-card">
            <div class="panel-header"><h3>{{ t("debug.events") }}</h3><Activity :size="18" /></div>
            <div class="table-wrap debug-scroll">
              <table>
                <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.message") }}</th></tr></thead>
                <tbody>
                  <tr v-for="item in recentEvents" :key="item.id">
                    <td>{{ formatCell(item.created_at) }}</td>
                    <td>{{ eventTypeLabel(item) }}</td>
                    <td>{{ displayCell(item.severity) }}</td>
                    <td>{{ eventMessage(item) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <section class="panel debug-card">
            <div class="panel-header"><h3>{{ t("debug.rawMqtt") }}</h3><Database :size="18" /></div>
            <pre class="json-block debug-scroll">{{ JSON.stringify(rawMqtt, null, 2) }}</pre>
          </section>
        </div>
      </section>
</template>

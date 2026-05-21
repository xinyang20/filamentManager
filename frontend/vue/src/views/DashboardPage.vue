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
  activeDerivedStatuses,
  activeView,
  boolLabel,
  camera,
  cameraLightboxOpen,
  cameraLivePlaceholder,
  cameraStatusRows,
  cameraStreamError,
  cameraStreamSrc,
  canRequestFullRefresh,
  connectPrinter,
  coverage,
  coverageStatusRows,
  dashboard,
  dashboardAmsCompactMode,
  dashboardAmsSummaryRows,
  dashboardAmsUnitRows,
  dashboardAmsUnitCollapsed,
  dashboardHmsRows,
  dashboardPrintStageLabel,
  dashboardPrintStateLabel,
  dashboardProgress,
  dashboardRemainingTimeMetric,
  dashboardTaskTitle,
  derivedStatusTone,
  detectionRows,
  displayCell,
  error,
  fanDisplayPercent,
  fanRows,
  fieldLabel,
  formatCell,
  handleCameraStreamError,
  handleCameraStreamLoaded,
  hmsErrors,
  isSectionCollapsed,
  layerFraction,
  network,
  nozzleTemperatureRows,
  openCameraLightbox,
  openHmsDetails,
  readableNetworkHardware,
  remainingTimeLabel,
  restartCameraStream,
  shouldShowChamberTemperature,
  statusTone,
  t,
  temperaturePercent,
  temperatures,
  toggleSectionCollapsed,
  toggleDashboardAmsUnitCollapsed,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="hero-strip">
          <div>
            <div class="mini-label">{{ t("dashboard.currentTask") }}</div>
            <h2>{{ dashboardTaskTitle() }}</h2>
            <div v-if="activeDerivedStatuses.length" class="task-status-chips">
              <span
                v-for="[key] in activeDerivedStatuses"
                :key="key"
                class="status-chip"
                :class="derivedStatusTone(key)"
              >
                {{ fieldLabel(key) }}
              </span>
            </div>
          </div>
          <div class="progress-block">
            <div class="progress-value">
              <span>{{ dashboardProgress() }}%</span>
              <div class="progress-meta">
                <small v-if="remainingTimeLabel">{{ t("dashboard.remainingTime") }} {{ remainingTimeLabel }}</small>
                <small v-if="layerFraction">{{ t("dashboard.layers") }} {{ layerFraction }}</small>
              </div>
            </div>
            <div class="progress-track">
              <span :style="{ width: `${dashboardProgress()}%` }"></span>
            </div>
          </div>
          <div v-if="!canRequestFullRefresh" class="strip-actions">
            <button class="secondary" type="button" @click="connectPrinter">
              <PlugZap :size="17" />
              {{ t("common.connectPrinter") }}
            </button>
          </div>
        </div>

        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.printState") }}</div>
            <div class="metric-value">{{ dashboardPrintStateLabel() }}</div>
            <div class="metric-foot">{{ dashboardPrintStageLabel() }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.remainingTime") }}</div>
            <div class="metric-value compact-value">{{ dashboardRemainingTimeMetric() }}</div>
            <div class="metric-foot">{{ t("dashboard.minutes") }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.nozzle") }}</div>
            <div v-if="nozzleTemperatureRows.length <= 1" class="metric-value">{{ formatCell(nozzleTemperatureRows[0]?.current) }}℃</div>
            <div v-if="nozzleTemperatureRows.length <= 1" class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(nozzleTemperatureRows[0]?.target) }}℃</div>
            <div v-else class="hotend-stack">
              <div v-for="item in nozzleTemperatureRows" :key="item.key" class="hotend-line">
                <span>{{ item.label }}</span>
                <strong>{{ formatCell(item.current) }}℃</strong>
                <small>{{ t("dashboard.target") }} {{ formatCell(item.target) }}℃</small>
              </div>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.bed") }}</div>
            <div class="metric-value">{{ formatCell(temperatures.bed) }}℃</div>
            <div class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(temperatures.bed_target) }}℃</div>
          </div>
          <div v-if="shouldShowChamberTemperature" class="metric-card">
            <div class="metric-label">{{ fieldLabel("chamber") }}</div>
            <div class="metric-value">{{ formatCell(temperatures.chamber) }}℃</div>
            <div class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(temperatures.chamber_target) }}℃</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">WiFi</div>
            <div class="metric-value">{{ formatCell(network.wifi_signal) }}</div>
            <div class="metric-foot">dBm</div>
          </div>
        </div>

        <div class="dashboard-card-flow">
          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.thermalFans") }}</h3>
              <div class="widget-tools">
                <Thermometer :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.thermal')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.thermal')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.thermal')" class="bar-list">
              <div v-for="item in nozzleTemperatureRows" :key="item.key" class="bar-row">
                <span>{{ item.label }}</span>
                <div class="bar"><i :style="{ width: `${temperaturePercent(item.current, item.target)}%` }"></i></div>
                <strong>{{ formatCell(item.current) }}℃</strong>
              </div>
              <div class="bar-row">
                <span>{{ fieldLabel("bed") }}</span>
                <div class="bar"><i :style="{ width: `${temperaturePercent(temperatures.bed, temperatures.bed_target)}%` }"></i></div>
                <strong>{{ formatCell(temperatures.bed) }}℃</strong>
              </div>
              <div v-for="[key, item] in fanRows" :key="key" class="bar-row">
                <span>{{ fieldLabel(key) }}</span>
                <div class="bar"><i :style="{ width: `${fanDisplayPercent(item)}%` }"></i></div>
                <strong>{{ formatCell(fanDisplayPercent(item)) }}%</strong>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.amsSummary") }}</h3>
              <div class="widget-tools">
                <Boxes :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.ams')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.ams')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.ams')" class="ams-status-grid">
              <div v-for="[label, value] in dashboardAmsSummaryRows" :key="label" class="ams-status-item">
                <span>{{ label }}</span>
                <strong>{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!dashboardAmsSummaryRows.length" class="empty">{{ t("common.empty") }}</div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.ams')" class="ams-visual-list" :class="{ compact: dashboardAmsCompactMode }">
              <article
                v-for="unit in dashboardAmsUnitRows"
                :key="unit.key"
                class="ams-visual-unit"
                :class="{ collapsed: dashboardAmsUnitCollapsed(unit.key) }"
              >
                <div class="ams-visual-head">
                  <div class="ams-visual-head-main">
                    <strong>{{ unit.title }}</strong>
                    <span>{{ unit.code }}</span>
                  </div>
                  <div class="ams-visual-head-actions">
                    <small>{{ unit.meta }}</small>
                    <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleDashboardAmsUnitCollapsed(unit.key)">
                      <ChevronDown v-if="dashboardAmsUnitCollapsed(unit.key)" :size="15" />
                      <ChevronUp v-else :size="15" />
                    </button>
                  </div>
                </div>
                <div v-if="dashboardAmsUnitCollapsed(unit.key)" class="ams-compact-slots">
                  <div
                    v-for="slot in unit.slots"
                    :key="slot.key"
                    class="ams-compact-slot"
                    :class="{ active: slot.active, empty: !slot.loaded }"
                    :style="slot.style"
                    :title="slot.loaded ? `${slot.material} ${slot.remain}` : t('ams.emptySlot')"
                  >
                    <span class="ams-compact-color"></span>
                    <span v-if="slot.loaded" class="ams-compact-remain">{{ slot.remain }}</span>
                    <span v-else class="ams-compact-material">{{ t("ams.emptySlot") }}</span>
                  </div>
                  <div v-if="!unit.slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                </div>
                <div v-else class="ams-visual-slots">
                  <div
                    v-for="slot in unit.slots"
                    :key="slot.key"
                    class="ams-visual-slot"
                    :class="{ active: slot.active, empty: !slot.loaded }"
                  >
                    <span class="ams-slot-material">{{ slot.material }}</span>
                    <div class="ams-spool" :style="slot.style"><i></i></div>
                    <strong>{{ slot.label }}</strong>
                    <small>{{ slot.remain }}</small>
                  </div>
                  <div v-if="!unit.slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                </div>
              </article>
            </div>
          </section>

          <section class="panel dashboard-live-panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.liveCamera") }}</h3>
              <div class="widget-tools">
                <Camera :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.liveCamera')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.liveCamera')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.liveCamera')" class="camera-live-card">
              <button class="camera-live-frame camera-live-trigger" type="button" :title="t('dashboard.openLiveCamera')" @click="openCameraLightbox">
                <img
                  v-if="cameraStreamSrc && !cameraStreamError && !cameraLightboxOpen"
                  :src="cameraStreamSrc"
                  :alt="t('dashboard.liveCamera')"
                  @error="handleCameraStreamError"
                  @load="handleCameraStreamLoaded"
                />
                <div v-else class="camera-live-placeholder">
                  <Camera :size="28" />
                  <strong>{{ cameraLivePlaceholder }}</strong>
                  <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
                </div>
              </button>
              <div class="camera-live-footer">
                <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
                <div class="camera-live-actions">
                  <button class="icon-button compact" type="button" :title="t('dashboard.openLiveCamera')" @click="openCameraLightbox">
                    <Eye :size="15" />
                  </button>
                  <button class="icon-button compact" type="button" :title="t('dashboard.restartCameraStream')" @click="restartCameraStream">
                    <RefreshCw :size="15" />
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.deviceDiagnostics") }}</h3>
              <div class="widget-tools">
                <Eye :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.detectionCoverage')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.detectionCoverage')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.detectionCoverage')" class="combined-status-sections">
              <div>
                <div class="section-label">{{ t("dashboard.detectionCapabilities") }}</div>
                <div class="capability-grid">
                  <div v-for="[key, value] in detectionRows" :key="key" class="capability-row">
                    <span>{{ fieldLabel(key) }}</span>
                    <strong :class="statusTone(value)">{{ boolLabel(value) }}</strong>
                  </div>
                  <div v-if="!detectionRows.length" class="empty">{{ t("common.empty") }}</div>
                </div>
              </div>
              <div>
                <div class="section-label">{{ t("dashboard.dataCoverage") }}</div>
                <div class="coverage-list">
                  <div v-for="item in coverageStatusRows" :key="item.key" class="coverage-row">
                    <span>{{ fieldLabel(item.key) }}</span>
                    <strong :class="{ on: item.received, off: !item.received }">
                      {{ item.received ? t("common.received") : t("common.missing") }}
                    </strong>
                  </div>
                  <div v-if="!coverageStatusRows.length" class="empty">{{ t("common.empty") }}</div>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.networkHardware") }}</h3>
              <div class="widget-tools">
                <Network :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.network')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.network')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.network')" class="combined-status-sections">
              <div class="network-info-grid">
                <div v-for="[key, value] in readableNetworkHardware" :key="key" class="network-info-item">
                  <span>{{ fieldLabel(key) }}</span>
                  <strong>{{ displayCell(value) }}</strong>
                </div>
                <div v-if="!readableNetworkHardware.length" class="empty">{{ t("common.empty") }}</div>
              </div>
              <div>
                <div class="section-label">{{ t("dashboard.hmsErrors") }}</div>
                <div class="dashboard-hms-list" :class="{ scrollable: dashboardHmsRows.length > 5 }">
                  <button v-if="!dashboardHmsRows.length" class="dashboard-hms-empty" type="button" disabled>
                    {{ t("dashboard.noHmsErrors") }}
                  </button>
                  <button
                    v-for="(item, index) in dashboardHmsRows"
                    :key="`${item.short_code || item.code}-${item.active}-${index}`"
                    class="dashboard-hms-row"
                    type="button"
                    @click="openHmsDetails(item)"
                  >
                    <span class="mono">{{ formatCell(item.short_code || item.code) }}</span>
                    <strong>{{ displayCell(item.severity_name) }}</strong>
                    <em>{{ item.active !== false && item.actionable !== false ? t("common.unresolved") : t("common.resolved") }}</em>
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.cameraStatus") }}</h3>
              <div class="widget-tools">
                <Camera :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.camera')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.camera')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.camera')" class="camera-info-grid camera-status-grid">
              <div v-for="[key, value] in cameraStatusRows" :key="key" class="camera-info-item">
                <span>{{ fieldLabel(key) }}</span>
                <strong :class="statusTone(value)">{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!cameraStatusRows.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>
        </div>
      </section>
</template>

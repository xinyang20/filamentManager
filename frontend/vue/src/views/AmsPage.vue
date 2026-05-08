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
  activeSlotDisplayLabel,
  activeView,
  amsHumidityLabel,
  amsLabelDrafts,
  amsLabelEditing,
  amsOverview,
  amsPageUnitVisual,
  amsSectionKey,
  amsIsDrying,
  amsSensorChartItems,
  amsSensorRange,
  amsSensorRangeOptions,
  amsStats,
  amsTitle,
  amsTone,
  clearAmsLabel,
  displayCell,
  filamentColor,
  formatCell,
  isSectionCollapsed,
  loadAmsSensorHistories,
  metricLabel,
  metricTooltipLabels,
  metrics,
  openSlotDetails,
  remainLabel,
  remainPercent,
  saveAmsLabel,
  slotDisplayLabel,
  slotKey,
  slotMaterialColorLabel,
  softCell,
  state,
  t,
  toggleAmsLabelEditor,
  toggleSectionCollapsed,
  withLoading,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar ams-toolbar">
          <span class="toolbar-field-label">{{ t("ams.historyRange") }}</span>
          <AppSelect v-model="amsSensorRange" :options="amsSensorRangeOptions" @change="withLoading(loadAmsSensorHistories)" />
        </div>
        <div class="metric-grid overview-metrics">
          <div v-for="item in amsStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
          </div>
        </div>
        <div class="ams-unit-grid">
        <section
          v-for="(unit, unitIndex) in amsOverview?.units || []"
          :key="unit.ams_id"
          class="panel ams-unit-card"
          :class="[amsTone(unit), { collapsed: isSectionCollapsed(amsSectionKey(unit)), drying: amsIsDrying(unit) }]"
        >
          <div class="ams-unit-header" :class="{ collapsed: isSectionCollapsed(amsSectionKey(unit)) }">
            <div class="ams-unit-title">
              <div class="badge-row">
                <span class="ams-badge">{{ unit.ams_type_name === "unknown" ? t("ams.unknownType") : unit.ams_type_name }}</span>
                <span class="ams-code mono">#{{ unit.ams_id }}</span>
              </div>
              <h3>{{ amsTitle(unit) }}</h3>
            </div>
            <div class="ams-unit-actions">
              <span v-if="isSectionCollapsed(amsSectionKey(unit))" class="ams-compact-sensor">{{ softCell(unit.temperature) }}℃ / {{ amsHumidityLabel(unit) }}</span>
              <button
                v-if="!isSectionCollapsed(amsSectionKey(unit))"
                class="icon-button compact subtle"
                type="button"
                :title="t('ams.editLabel')"
                @click="toggleAmsLabelEditor(unit)"
              >
                <PencilLine :size="14" />
              </button>
              <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed(amsSectionKey(unit))">
                <ChevronDown v-if="isSectionCollapsed(amsSectionKey(unit))" :size="15" />
                <ChevronUp v-else :size="15" />
              </button>
            </div>
            <div v-if="amsLabelEditing[unit.ams_id] && !isSectionCollapsed(amsSectionKey(unit))" class="ams-label-row">
              <input v-model="amsLabelDrafts[unit.ams_id]" :placeholder="t('ams.labelPlaceholder')" />
              <button class="secondary" type="button" @click="saveAmsLabel(unit)"><Save :size="15" />{{ t("common.save") }}</button>
              <button class="icon-button compact" type="button" :title="t('ams.clearLabel')" @click="clearAmsLabel(unit)"><X :size="15" /></button>
            </div>
            <div v-if="!isSectionCollapsed(amsSectionKey(unit))" class="ams-unit-meta">
              <span>{{ t("fields.temperature") }} {{ softCell(unit.temperature) }}℃</span>
              <span>{{ t("fields.humidity_raw") }} {{ amsHumidityLabel(unit) }}</span>
              <span>{{ t("ams.activeSlot") }} {{ activeSlotDisplayLabel(unit.active_slot) }}</span>
              <span>{{ t("ams.dryStatus") }} {{ displayCell(unit.dry_status_name || unit.dry_status) }}</span>
              <span class="quiet-meta">{{ t("fields.firmware") }} {{ softCell(unit.sw_ver) }}</span>
              <span>{{ t("overview.lastSync") }} {{ formatCell(unit.updated_at) }}</span>
            </div>
          </div>
          <div class="ams-fold-stack">
            <Transition name="ams-fold">
              <div v-if="isSectionCollapsed(amsSectionKey(unit))" :key="`${unit.ams_id}-collapsed`" class="ams-fold-region">
                <div class="ams-collapsed-preview">
                  <div
                    class="ams-visual-slots ams-page-preview-slots"
                    :class="{ 'single-slot': amsPageUnitVisual(unit, unitIndex).slots.length <= 1 }"
                  >
                    <div
                      v-for="slot in amsPageUnitVisual(unit, unitIndex).slots"
                      :key="slot.key"
                      class="ams-visual-slot"
                      :class="{ active: slot.active, empty: !slot.loaded }"
                    >
                      <span class="ams-slot-material">{{ slot.material }}</span>
                      <div class="ams-spool" :style="slot.style"><i></i></div>
                      <strong>{{ slot.label }}</strong>
                      <small>{{ slot.remain }}</small>
                    </div>
                    <div v-if="!amsPageUnitVisual(unit, unitIndex).slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                  </div>
                </div>
              </div>
              <div v-else :key="`${unit.ams_id}-expanded`" class="ams-fold-region">
                <div class="ams-sensor-row">
                  <MetricChart
                    :title="t('ams.sensorHistory')"
                    :subtitle="`${t('fields.temperature')} / ${t('fields.humidity_raw')}`"
                    :items="amsSensorChartItems(unit.ams_id)"
                    :metric-label="metricLabel"
                    :empty-label="t('common.empty')"
                    :tooltip-labels="metricTooltipLabels"
                  />
                </div>
                <div class="ams-slot-grid">
                  <div v-if="!unit.slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                  <article v-for="slot in unit.slots" :key="slotKey(slot)" class="ams-slot-card" :class="{ active: slot.is_active }">
                    <div class="ams-slot-topline">
                      <div>
                        <span class="mini-label">{{ slotDisplayLabel(slot) }}</span>
                        <strong><span class="swatch" :style="{ background: filamentColor(slot.color) }"></span>{{ slotMaterialColorLabel(slot) }}</strong>
                      </div>
                      <button class="icon-button compact" type="button" :title="t('table.details')" @click="openSlotDetails(slot)">
                        <Eye :size="15" />
                      </button>
                    </div>
                    <div class="ams-slot-remain">
                      <div class="progress-track">
                        <span :style="{ width: `${remainPercent(slot.remain)}%` }"></span>
                      </div>
                      <strong>{{ remainLabel(slot.remain) }}</strong>
                    </div>
                    <div class="ams-slot-facts">
                      <div><span>{{ t("table.state") }}</span><strong>{{ displayCell(slot.state_name || slot.slot_state) }}</strong></div>
                      <div><span>K</span><strong>{{ softCell(slot.k) }}</strong></div>
                      <div><span>{{ t("ams.caliIdx") }}</span><strong>{{ softCell(slot.cali_idx) }}</strong></div>
                      <div><span>{{ t("table.spool") }}</span><strong>{{ softCell(slot.spool_id) }}</strong></div>
                    </div>
                    <span v-if="slot.is_active" class="ams-active-ribbon">{{ t("common.currentInUse") }}</span>
                  </article>
                </div>
              </div>
            </Transition>
          </div>
        </section>
        </div>
      </section>
</template>

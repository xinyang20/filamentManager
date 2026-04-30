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
  formatCell,
  loadMaintenance,
  maintenanceHealthPercent,
  maintenanceItems,
  maintenanceNotes,
  maintenanceOverview,
  maintenanceProgress,
  maintenanceRemainingLabel,
  maintenanceStats,
  maintenanceStatusGroups,
  maintenanceTone,
  performMaintenance,
  printers,
  selectedPrinter,
  selectedPrinterId,
  selectedPrinterPrintHours,
  t,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <section class="maintenance-hero">
          <div>
            <div class="mini-label">{{ t("maintenance.titleKicker") }}</div>
            <h2>{{ selectedPrinter ? selectedPrinter.name : t("nav.maintenance") }}</h2>
            <p>{{ t("maintenance.subtitle") }}</p>
          </div>
          <div class="maintenance-hero-stats">
            <div>
              <span>{{ t("maintenance.currentHours") }}</span>
              <strong>{{ selectedPrinterPrintHours }}h</strong>
            </div>
            <div>
              <span>{{ t("maintenance.health") }}</span>
              <strong>{{ maintenanceHealthPercent }}%</strong>
            </div>
          </div>
        </section>

        <div class="maintenance-summary-grid">
          <div v-for="item in maintenanceStats" :key="item.label" class="maintenance-summary-card" :class="item.tone">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
          <div class="maintenance-summary-card neutral">
            <span>{{ t("maintenance.totalItems") }}</span>
            <strong>{{ maintenanceOverview?.total_items || 0 }}</strong>
          </div>
        </div>

        <div class="maintenance-layout">
          <section class="panel maintenance-fleet-panel">
            <div class="panel-header">
              <h3>{{ t("maintenance.fleet") }}</h3>
              <Wrench :size="18" />
            </div>
            <div class="maintenance-printer-list">
              <button
                v-for="printer in maintenanceOverview?.printers || []"
                :key="printer.printer_id"
                type="button"
                class="maintenance-printer-row"
                :class="{ selected: printer.printer_id === selectedPrinterId }"
                @click="selectedPrinterId = Number(printer.printer_id); loadMaintenance()"
              >
                <span>{{ printer.printer_name }}</span>
                <strong>{{ printer.due_count }} / {{ printer.soon_count }} / {{ printer.ok_count }}</strong>
              </button>
              <div v-if="!maintenanceOverview?.printers?.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>

          <section class="panel maintenance-worklist-panel">
            <div class="panel-header">
              <div>
                <h3>{{ t("maintenance.worklist") }}</h3>
                <p class="panel-subtitle">{{ t("maintenance.worklistSubtitle") }}</p>
              </div>
              <span class="status-pill" :class="maintenanceOverview?.due_count ? 'bad' : maintenanceOverview?.soon_count ? 'warn' : 'good'">
                <span class="dot"></span>
                {{ maintenanceOverview?.due_count ? t("maintenance.due") : maintenanceOverview?.soon_count ? t("maintenance.soon") : t("maintenance.ok") }}
              </span>
            </div>

            <div v-if="!maintenanceItems.length" class="maintenance-empty">
              <Wrench :size="24" />
              <strong>{{ t("common.empty") }}</strong>
            </div>

            <div v-else class="maintenance-group-list">
              <section v-for="group in maintenanceStatusGroups" :key="group.key" class="maintenance-group">
                <div class="maintenance-group-header">
                  <span class="status-pill" :class="group.tone"><span class="dot"></span>{{ group.label }}</span>
                  <small>{{ group.items.length }}</small>
                </div>

                <article
                  v-for="item in group.items"
                  :key="item.id"
                  class="maintenance-card"
                  :class="maintenanceTone(item.due_status)"
                >
                  <div class="maintenance-card-main">
                    <div class="maintenance-title-row">
                      <div class="maintenance-icon" :class="{ ams: item.target_type === 'ams' }">
                        <Boxes v-if="item.target_type === 'ams'" :size="16" />
                        <Wrench v-else :size="16" />
                      </div>
                      <div>
                        <h4>{{ item.maintenance_type.name }}</h4>
                        <div v-if="item.target_label" class="maintenance-target">{{ item.target_label }}</div>
                        <p>{{ item.maintenance_type.description }}</p>
                      </div>
                    </div>

                    <div class="maintenance-progress-row">
                      <div class="maintenance-progress-label">
                        <span>{{ t("maintenance.sinceLast") }} {{ item.hours_since_last }}h</span>
                        <strong>{{ maintenanceRemainingLabel(item) }}</strong>
                      </div>
                      <div class="maintenance-progress-track">
                        <i :style="{ width: `${maintenanceProgress(item)}%` }"></i>
                      </div>
                    </div>

                    <div class="maintenance-facts">
                      <div><span>{{ t("maintenance.interval") }}</span><strong>{{ item.interval }}h</strong></div>
                      <div><span>{{ t("maintenance.currentHours") }}</span><strong>{{ item.current_print_hours }}h</strong></div>
                      <div><span>{{ t("maintenance.lastDone") }}</span><strong>{{ formatCell(item.last_performed_at) }}</strong></div>
                    </div>
                  </div>

                  <div class="maintenance-actions">
                    <input v-model="maintenanceNotes[item.id]" :placeholder="t('maintenance.note')" />
                    <button class="primary" type="button" @click="performMaintenance(item)">
                      <CheckCircle2 :size="17" />
                      {{ t("maintenance.perform") }}
                    </button>
                  </div>
                </article>
              </section>
            </div>
          </section>
        </div>
      </section>
</template>

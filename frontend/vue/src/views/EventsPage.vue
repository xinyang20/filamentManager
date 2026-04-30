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
  displayCell,
  eventActiveOptions,
  eventCurrentLabel,
  eventFilters,
  eventMessage,
  eventSeverityOptions,
  eventTone,
  eventTypeLabel,
  events,
  filteredEvents,
  formatCell,
  message,
  openEventDetails,
  t,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar filters">
          <input v-model="eventFilters.type" :placeholder="t('events.typeFilter')" />
          <AppSelect v-model="eventFilters.severity" :options="eventSeverityOptions" />
          <AppSelect v-model="eventFilters.active" :options="eventActiveOptions" />
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("events.title") }}</h3><Bell :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.current") }}</th><th>{{ t("table.message") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
              <tbody>
                <tr v-if="!filteredEvents.length"><td colspan="6" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="item in filteredEvents" :key="`${item.source}-${item.id}`">
                  <td>{{ formatCell(item.created_at) }}</td>
                  <td>{{ eventTypeLabel(item) }}</td>
                  <td><span class="status-pill" :class="eventTone(item)"><span class="dot"></span>{{ displayCell(item.severity) }}</span></td>
                  <td>{{ eventCurrentLabel(item) }}</td>
                  <td>{{ eventMessage(item) }}</td>
                  <td><button class="text-action compact" type="button" @click="openEventDetails(item)">{{ t("table.details") }}</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>
</template>

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
  accessCodeRevealLoading,
  accessCodeVisible,
  activeView,
  connectPrinter,
  deletePrinterConfig,
  disconnectPrinter,
  discovery,
  displayCell,
  formatCell,
  printerForm,
  printers,
  savePrinter,
  scanDevices,
  scanPhase,
  scanProgressLabel,
  scanProgressWidth,
  scanning,
  selectedPrinterId,
  t,
  toggleAccessCodeVisibility,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printers.config") }}</h3><Settings :size="18" /></div>
            <div class="form-grid">
              <label>{{ t("form.name") }}<input v-model="printerForm.name" /></label>
              <label>{{ t("form.host") }}<input v-model="printerForm.host" /></label>
              <label>{{ t("form.port") }}<input v-model.number="printerForm.port" type="number" /></label>
              <label>{{ t("form.serial") }}<input v-model="printerForm.serial" /></label>
              <label class="access-code-field">
                {{ t("form.accessCode") }}
                <div class="input-with-action">
                  <input v-model="printerForm.access_code" :type="accessCodeVisible ? 'text' : 'password'" autocomplete="off" />
                  <button
                    class="icon-button compact"
                    type="button"
                    :disabled="accessCodeRevealLoading"
                    :title="accessCodeVisible ? t('form.hideAccessCode') : t('form.showAccessCode')"
                    @click="toggleAccessCodeVisibility"
                  >
                    <Loader2 v-if="accessCodeRevealLoading" class="spin" :size="15" />
                    <EyeOff v-else-if="accessCodeVisible" :size="15" />
                    <Eye v-else :size="15" />
                  </button>
                </div>
              </label>
              <div class="printer-security-options">
                <label class="checkbox"><input v-model="printerForm.tls_enabled" type="checkbox" /> TLS</label>
                <label class="checkbox"><input v-model="printerForm.certificate_verify" type="checkbox" /> {{ t("form.verifyCert") }}</label>
              </div>
            </div>
            <div class="toolbar printer-config-actions">
              <button class="primary" type="button" @click="savePrinter"><Save :size="17" />{{ t("common.save") }}</button>
              <button class="secondary" type="button" @click="connectPrinter"><PlugZap :size="17" />{{ t("common.connect") }}</button>
              <button class="secondary" type="button" @click="disconnectPrinter"><Unplug :size="17" />{{ t("common.disconnect") }}</button>
              <button class="secondary" type="button" :disabled="scanning" @click="scanDevices">
                <Loader2 v-if="scanning" class="spin" :size="17" />
                <Search v-else :size="17" />
                {{ scanning ? t("common.scanning") : t("common.scanLan") }}
              </button>
            </div>
            <div v-if="scanning || scanPhase" class="scan-progress">
              <div class="scan-progress-header">
                <span>{{ scanPhase }}</span>
                <strong>{{ scanProgressLabel }}%</strong>
              </div>
              <div class="progress-track">
                <span :style="{ width: `${scanProgressWidth}%` }"></span>
              </div>
            </div>
          </section>
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printers.list") }}</h3><Network :size="18" /></div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.id") }}</th><th>{{ t("table.name") }}</th><th>{{ t("table.host") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.lastSync") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-for="printer in printers" :key="printer.id" :class="{ selected: printer.id === selectedPrinterId }" @click="selectedPrinterId = printer.id">
                    <td>{{ printer.id }}</td>
                    <td>{{ printer.name }}</td>
                    <td>{{ printer.host }}</td>
                    <td>{{ displayCell(printer.connection_status) }}</td>
                    <td>{{ formatCell(printer.last_sync_at) }}</td>
                    <td>
                      <button class="icon-button danger" type="button" :title="t('printers.delete')" @click.stop="deletePrinterConfig(printer)">
                        <Trash2 :size="16" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("printers.discovery") }}</h3><Search :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.host") }}</th><th>{{ t("table.model") }}</th><th>{{ t("table.deviceName") }}</th><th>{{ t("table.serial") }}</th><th>{{ t("table.confidence") }}</th><th>{{ t("table.reason") }}</th></tr></thead>
              <tbody>
                <tr v-if="!discovery.length"><td colspan="6" class="empty">{{ t("printers.noDiscovery") }}</td></tr>
                <tr v-for="item in discovery" :key="item.host">
                  <td>{{ item.host }}</td>
                  <td>{{ formatCell(item.model) }}</td>
                  <td>{{ formatCell(item.device_name) }}</td>
                  <td>{{ formatCell(item.serial) }}</td>
                  <td>{{ item.confidence }}</td>
                  <td>{{ item.reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>
</template>

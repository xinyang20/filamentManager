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
  adjustSelectedFilamentQuantity,
  camera,
  cameraLightboxOpen,
  cameraLivePlaceholder,
  cameraStreamError,
  cameraStreamSrc,
  cancelFilamentSkuEdit,
  closeCameraLightbox,
  closeInventoryDialog,
  confirmFilamentSpoolSku,
  createFilamentSpool,
  dashboard,
  displayCell,
  editSkuFromConfirmDialog,
  editingFilamentBrandId,
  editingFilamentColorMappingId,
  editingFilamentSkuId,
  editingFilamentTypeSeriesId,
  error,
  eventCurrentLabel,
  eventMessage,
  eventRawMessage,
  eventTypeLabel,
  events,
  filamentBrandForm,
  filamentColor,
  filamentColorDisplay,
  filamentColorMappingForm,
  filamentColorMappingTypeSeriesOptions,
  filamentRemainPercent,
  filamentRequiredBrandOptions,
  filamentSkuForm,
  filamentSkuReviewDescription,
  filamentSkuTypeSeriesOptions,
  filamentSpoolBrandOptions,
  filamentSpoolForm,
  filamentSpoolLabel,
  filamentSpoolLocation,
  filamentSpoolNeedsUidConflictResolution,
  filamentSpoolRemainingLabel,
  filamentSpoolRemainingWeight,
  filamentSpoolSkuOptions,
  filamentSpoolStatusLabel,
  filamentSpoolStatusOptions,
  filamentSpoolTypeSeriesOptions,
  filamentTypeSeriesForm,
  filamentWeight,
  formatCell,
  handleCameraStreamError,
  handleCameraStreamLoaded,
  hmsMessage,
  hmsSuggestion,
  inventoryDialog,
  inventoryDialogSkuLabel,
  inventoryDialogSpoolLabel,
  isFilamentSpoolPendingConfirm,
  loading,
  locationAdjustForm,
  locationPrinterOptions,
  message,
  openConfirmFilamentSpoolSku,
  prettyJson,
  printerDisplayName,
  quantityAdjustForm,
  quantityAdjustSourceOptions,
  remainLabel,
  remainPercent,
  resolveFilamentUidConflict,
  restartCameraStream,
  saveFilamentBrand,
  saveFilamentColorMapping,
  saveFilamentSku,
  saveFilamentTypeSeries,
  saveSealedStockAdjust,
  sealedStockAdjustForm,
  selectedEvent,
  selectedFilamentSpool,
  selectedHms,
  selectedHmsStats,
  selectedPrinter,
  selectedSlot,
  selectedSlotHistory,
  slotChangeKinds,
  slotColorLabel,
  slotDisplayLabel,
  slotHistoryChanges,
  softCell,
  state,
  t,
  updateFilamentSpoolStatus,
  updateSelectedFilamentLocation,
} = appViewRefs(props.ctx);
</script>

<template>
<div v-if="cameraLightboxOpen" class="modal-backdrop camera-lightbox-backdrop" @click.self="closeCameraLightbox">
      <section class="modal-panel camera-lightbox-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("dashboard.liveCamera") }}</h3>
            <p>{{ selectedPrinter?.name || t("dashboard.cameraStreamForwarding") }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeCameraLightbox"><X :size="17" /></button>
        </div>
        <div class="camera-lightbox-frame">
          <img
            v-if="cameraStreamSrc && !cameraStreamError"
            :src="cameraStreamSrc"
            :alt="t('dashboard.liveCamera')"
            @error="handleCameraStreamError"
            @load="handleCameraStreamLoaded"
          />
          <div v-else class="camera-live-placeholder">
            <Camera :size="34" />
            <strong>{{ cameraLivePlaceholder }}</strong>
            <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
          </div>
        </div>
        <div class="camera-lightbox-footer">
          <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
          <div class="camera-live-actions">
            <button class="secondary" type="button" @click="restartCameraStream"><RefreshCw :size="16" />{{ t("dashboard.restartCameraStream") }}</button>
            <button class="primary" type="button" @click="closeCameraLightbox">{{ t("common.close") }}</button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="inventoryDialog.key" class="modal-backdrop" @click.self="closeInventoryDialog">
      <section v-if="inventoryDialog.key === 'brand'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentBrandId ? t("inventory.editBrand") : t("inventory.addBrand") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentBrand">
          <label class="field-label"><span>{{ t("form.brand") }}</span><input v-model="filamentBrandForm.name" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("inventory.aliases") }}</span><input v-model="filamentBrandForm.aliases" :placeholder="t('inventory.aliases')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentBrandForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'typeSeries'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentTypeSeriesId ? t("inventory.editTypeSeries") : t("inventory.addTypeSeries") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentTypeSeries">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentTypeSeriesForm.brand_id" :options="filamentRequiredBrandOptions" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("form.material") }}</span><input v-model="filamentTypeSeriesForm.material_type" :placeholder="t('form.material')" /></label>
          <label class="field-label"><span>{{ t("form.series") }}</span><input v-model="filamentTypeSeriesForm.series_name" :placeholder="t('form.series')" /></label>
          <label class="field-label"><span>{{ t("inventory.emptySpoolWeight") }}</span><input v-model.number="filamentTypeSeriesForm.empty_spool_weight_g" type="number" min="0" :placeholder="t('inventory.emptySpoolWeight')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentTypeSeriesForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'sku'" class="modal-panel sku-modal">
        <div class="modal-header">
          <h3>{{ editingFilamentSkuId ? t("inventory.editSku") : t("inventory.addSku") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form sku-modal-form" @submit.prevent="saveFilamentSku">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentSkuForm.brand_id" :options="filamentRequiredBrandOptions" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentSkuForm.type_series_id" :options="filamentSkuTypeSeriesOptions" :placeholder="t('inventory.typeSeries')" /></label>
          <label class="field-label"><span>{{ t("inventory.officialColorName") }}</span><input v-model="filamentSkuForm.color_name" :placeholder="t('inventory.officialColorName')" /></label>
          <label class="field-label"><span>{{ t("inventory.hexValue") }}</span><input v-model="filamentSkuForm.color_value" :placeholder="t('inventory.hexValue')" /></label>
          <label class="field-label"><span>{{ t("inventory.nominalWeight") }}</span><input v-model.number="filamentSkuForm.nominal_weight_g" type="number" min="0" :placeholder="t('inventory.nominalWeight')" /></label>
          <label class="field-label"><span>{{ t("inventory.diameter") }}</span><input v-model.number="filamentSkuForm.filament_diameter_mm" type="number" min="0.1" step="0.01" :placeholder="t('inventory.diameter')" /></label>
          <label class="field-label"><span>{{ t("inventory.trayInfoIdx") }}</span><input v-model="filamentSkuForm.tray_info_idx" :placeholder="t('inventory.trayInfoIdx')" /></label>
          <label class="field-label"><span>{{ t("form.sealedQty") }}</span><input v-model.number="filamentSkuForm.sealed_quantity" type="number" min="0" :placeholder="t('form.sealedQty')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentSkuForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="cancelFilamentSkuEdit">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'colorMapping'" class="modal-panel color-mapping-modal">
        <div class="modal-header">
          <h3>{{ editingFilamentColorMappingId ? t("inventory.editColorMapping") : t("inventory.addColorMapping") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentColorMapping">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentColorMappingForm.brand_id" :options="filamentRequiredBrandOptions" /></label>
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentColorMappingForm.type_series_id" :options="filamentColorMappingTypeSeriesOptions" /></label>
          <label class="field-label"><span>{{ t("inventory.hexValue") }}</span><input v-model="filamentColorMappingForm.hex_value" :placeholder="t('inventory.hexValue')" /></label>
          <label class="field-label"><span>{{ t("inventory.officialColorName") }}</span><input v-model="filamentColorMappingForm.official_name" :placeholder="t('inventory.officialColorName')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentColorMappingForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'stockAdjust'" class="modal-panel">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.adjustStock") }}</h3>
            <p>{{ inventoryDialogSkuLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveSealedStockAdjust">
          <label class="field-label"><span>{{ t("inventory.currentSealedQty") }}</span><input :value="sealedStockAdjustForm.current_quantity" disabled :placeholder="t('inventory.currentSealedQty')" /></label>
          <label class="field-label"><span>{{ t("inventory.targetSealedQty") }}</span><input v-model.number="sealedStockAdjustForm.target_quantity" type="number" min="0" :placeholder="t('inventory.targetSealedQty')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="sealedStockAdjustForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'spoolCreate'" class="modal-panel wide-modal">
        <div class="modal-header">
          <h3>{{ t("inventory.addSpool") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="createFilamentSpool">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentSpoolForm.brand_id" :options="filamentSpoolBrandOptions" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentSpoolForm.type_series_id" :options="filamentSpoolTypeSeriesOptions" :placeholder="t('inventory.typeSeries')" /></label>
          <label class="field-label"><span>{{ t("inventory.skus") }}</span><AppSelect v-model="filamentSpoolForm.sku_id" :options="filamentSpoolSkuOptions" :placeholder="t('inventory.skus')" /></label>
          <label class="field-label"><span>{{ t("table.status") }}</span><AppSelect v-model="filamentSpoolForm.status" :options="filamentSpoolStatusOptions" /></label>
          <label class="field-label"><span>{{ t("fields.tray_uuid") }}</span><input v-model="filamentSpoolForm.tray_uuid" :placeholder="t('fields.tray_uuid')" /></label>
          <label class="field-label"><span>{{ t("fields.tag_uid") }}</span><input v-model="filamentSpoolForm.tag_uid" :placeholder="t('fields.tag_uid')" /></label>
          <label class="field-label"><span>{{ t("inventory.remainingWeight") }}</span><input v-model.number="filamentSpoolForm.current_remaining_g" type="number" min="0" :placeholder="t('inventory.remainingWeight')" /></label>
          <label class="field-label"><span>{{ t("inventory.manualLocation") }}</span><input v-model="filamentSpoolForm.manual_location" :placeholder="t('inventory.manualLocation')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentSpoolForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'spoolDetail' && selectedFilamentSpool" class="modal-panel wide-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.spoolDetail") }}</h3>
            <p>{{ inventoryDialogSpoolLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <div class="metric-grid small">
          <div class="metric-card"><div class="metric-label">{{ t("table.spool") }}</div><div class="metric-value compact-value">{{ filamentSpoolLabel(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.remaining") }}</div><div class="metric-value compact-value">{{ filamentWeight(filamentSpoolRemainingWeight(selectedFilamentSpool)) }}</div><div class="metric-foot">{{ filamentRemainPercent(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("table.location") }}</div><div class="metric-value compact-value">{{ filamentSpoolLocation(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("table.status") }}</div><div class="metric-value compact-value">{{ filamentSpoolStatusLabel(selectedFilamentSpool.status) }}</div></div>
        </div>
        <div v-if="isFilamentSpoolPendingConfirm(selectedFilamentSpool)" class="modal-note">
          <span>{{ t("inventory.confirmSkuTitle") }}</span>
          <button class="secondary" type="button" @click="openConfirmFilamentSpoolSku(selectedFilamentSpool)">{{ t("inventory.confirmSku") }}</button>
        </div>
        <div class="spool-status-actions">
          <button
            v-if="selectedFilamentSpool.status !== 'empty' && selectedFilamentSpool.status !== 'archived'"
            class="secondary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'empty')"
          >
            {{ t("inventory.markEmpty") }}
          </button>
          <button
            v-if="selectedFilamentSpool.status !== 'archived'"
            class="secondary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'archived')"
          >
            {{ t("inventory.archiveSpool") }}
          </button>
          <button
            v-if="selectedFilamentSpool.status === 'empty' || selectedFilamentSpool.status === 'archived'"
            class="primary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'opened_in_storage')"
          >
            <CheckCircle2 :size="17" />{{ t("inventory.restoreOpened") }}
          </button>
        </div>
        <div class="spool-dialog-forms">
          <form class="modal-subform" @submit.prevent="adjustSelectedFilamentQuantity">
            <h4>{{ t("inventory.quantityAdjust") }}</h4>
            <div class="spool-adjust-grid">
              <label class="field-label"><span>{{ t("inventory.remainingWeight") }}</span><input v-model.number="quantityAdjustForm.current_remaining_g" type="number" min="0" :placeholder="t('inventory.remainingWeight')" /></label>
              <label class="field-label"><span>{{ t("inventory.remainPercent") }}</span><input v-model.number="quantityAdjustForm.remain_percent" type="number" min="0" max="100" :placeholder="t('inventory.remainPercent')" /></label>
              <label class="field-label"><span>{{ t("inventory.source") }}</span><AppSelect v-model="quantityAdjustForm.source" :options="quantityAdjustSourceOptions" /></label>
              <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="quantityAdjustForm.note" :placeholder="t('form.note')" /></label>
            </div>
            <div class="modal-actions"><button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button></div>
          </form>
          <form class="modal-subform" @submit.prevent="updateSelectedFilamentLocation">
            <h4>{{ t("inventory.locationAdjust") }}</h4>
            <div class="spool-adjust-grid">
              <label class="field-label"><span>{{ t("table.printer") }}</span><AppSelect v-model="locationAdjustForm.printer_id" :options="locationPrinterOptions" :placeholder="t('table.printer')" /></label>
              <label class="field-label"><span>{{ t("fields.ams_id") }}</span><input v-model="locationAdjustForm.ams_id" :placeholder="t('fields.ams_id')" /></label>
              <label class="field-label"><span>{{ t("form.slotId") }}</span><input v-model="locationAdjustForm.tray_id" :placeholder="t('form.slotId')" /></label>
              <label class="field-label"><span>{{ t("inventory.manualLocation") }}</span><input v-model="locationAdjustForm.manual_location" :placeholder="t('inventory.manualLocation')" /></label>
              <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="locationAdjustForm.note" :placeholder="t('form.note')" /></label>
            </div>
            <div class="modal-actions"><button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button></div>
          </form>
        </div>
      </section>

      <section v-else-if="inventoryDialog.key === 'skuConfirm'" class="modal-panel">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.confirmSku") }}</h3>
            <p>{{ inventoryDialogSpoolLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <dl class="kv compact">
          <dt>{{ t("table.spool") }}</dt><dd>{{ inventoryDialogSpoolLabel() }}</dd>
          <dt>{{ t("inventory.identity") }}</dt><dd class="mono">{{ formatCell(inventoryDialog.context?.official_spool_uid || inventoryDialog.context?.identity_key) }}</dd>
          <dt>{{ t("inventory.remaining") }}</dt><dd>{{ filamentSpoolRemainingLabel(inventoryDialog.context) }}</dd>
        </dl>
        <div class="modal-note">{{ filamentSkuReviewDescription(inventoryDialog.context) }}</div>
        <div v-if="inventoryDialog.context && filamentSpoolNeedsUidConflictResolution(inventoryDialog.context)" class="modal-actions">
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'restore_old')">{{ t("inventory.restoreHistoricalSpool") }}</button>
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'create_new')">{{ t("inventory.createNewSpool") }}</button>
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'ignore')">{{ t("inventory.ignoreRecognition") }}</button>
        </div>
        <div v-else class="modal-actions">
          <button class="secondary" type="button" @click="editSkuFromConfirmDialog">{{ t("inventory.editSku") }}</button>
          <button class="primary" type="button" @click="inventoryDialog.context && confirmFilamentSpoolSku(inventoryDialog.context)"><CheckCircle2 :size="17" />{{ t("inventory.confirmSku") }}</button>
        </div>
      </section>
    </div>

    <div v-if="selectedEvent" class="modal-backdrop" @click.self="selectedEvent = null">
      <section class="modal-panel event-detail-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("events.details") }} · {{ eventTypeLabel(selectedEvent) }}</h3>
            <p>{{ formatCell(selectedEvent.created_at) }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedEvent = null"><X :size="17" /></button>
        </div>
        <dl class="kv compact">
          <dt>{{ t("table.type") }}</dt><dd>{{ eventTypeLabel(selectedEvent) }}</dd>
          <dt>{{ t("table.severity") }}</dt><dd>{{ displayCell(selectedEvent.severity) }}</dd>
          <dt>{{ t("table.current") }}</dt><dd>{{ eventCurrentLabel(selectedEvent) }}</dd>
          <dt>{{ t("table.message") }}</dt><dd>{{ eventMessage(selectedEvent) }}</dd>
          <dt>{{ t("events.rawMessage") }}</dt><dd>{{ eventRawMessage(selectedEvent) }}</dd>
          <dt>{{ t("table.printer") }}</dt><dd>{{ printerDisplayName(selectedEvent.printer_id) }}</dd>
          <dt>{{ t("table.spool") }}</dt><dd>{{ formatCell(selectedEvent.spool_id) }}</dd>
          <dt>{{ t("events.source") }}</dt><dd>{{ displayCell(selectedEvent.source) }}</dd>
        </dl>
        <div class="event-raw-block">
          <h4>{{ t("events.rawData") }}</h4>
          <pre>{{ prettyJson(selectedEvent.data) }}</pre>
        </div>
      </section>
    </div>

    <div v-if="selectedHms" class="modal-backdrop" @click.self="selectedHms = null">
      <section class="modal-panel">
        <div class="modal-header">
          <h3>{{ t("hms.details") }} · {{ formatCell(selectedHms.short_code || selectedHms.code) }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedHms = null"><X :size="17" /></button>
        </div>
        <dl class="kv">
          <dt>{{ t("table.description") }}</dt><dd>{{ hmsMessage(selectedHms) }}</dd>
          <dt>{{ t("hms.suggestion") }}</dt><dd>{{ hmsSuggestion(selectedHms) || "--" }}</dd>
          <dt>{{ t("table.current") }}</dt><dd>{{ selectedHms.active ? t("common.unresolved") : t("common.resolved") }}</dd>
          <dt>{{ t("table.module") }}</dt><dd>{{ formatCell(selectedHms.module_name) }}</dd>
          <dt>{{ t("hms.known") }}</dt><dd>{{ selectedHms.known === false ? t("common.off") : t("common.on") }}</dd>
          <dt>{{ t("hms.actionable") }}</dt><dd>{{ selectedHms.actionable === false ? t("common.off") : t("common.on") }}</dd>
          <dt>{{ t("hms.recentCount") }}</dt><dd>{{ selectedHmsStats?.recent_count ?? "--" }}</dd>
          <dt>{{ t("hms.lastRecovered") }}</dt><dd>{{ formatCell(selectedHmsStats?.last_recovered_at) }}</dd>
          <dt>{{ t("hms.highFrequency") }}</dt><dd>{{ selectedHmsStats?.high_frequency ? t("common.on") : t("common.off") }}</dd>
          <dt>attr / code / source</dt><dd class="mono">{{ formatCell(selectedHms.attr) }} / {{ formatCell(selectedHms.code) }} / {{ formatCell(selectedHms.source) }}</dd>
          <dt>Wiki</dt><dd><a v-if="selectedHms.wiki_url" :href="selectedHms.wiki_url" target="_blank" rel="noreferrer">{{ selectedHms.wiki_url }}</a><span v-else>--</span></dd>
        </dl>
      </section>
    </div>

    <div v-if="selectedSlot" class="modal-backdrop" @click.self="selectedSlot = null">
      <section class="modal-panel wide-modal slot-detail-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("ams.slotDetails") }}</h3>
            <p>AMS {{ selectedSlot.ams_id }} / {{ slotDisplayLabel(selectedSlot) }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedSlot = null"><X :size="17" /></button>
        </div>

        <div class="slot-detail-hero">
          <div class="slot-detail-spool">
            <div class="ams-spool" :style="{ '--filament-color': filamentColor(selectedSlot.color || selectedSlot.tray_color) }"><i></i></div>
            <div>
              <span>{{ t("table.material") }}</span>
              <strong>{{ softCell(selectedSlot.material) }}</strong>
              <small>{{ slotColorLabel(selectedSlot) }}</small>
            </div>
          </div>
          <div class="slot-detail-facts">
            <div><span>{{ t("table.state") }}</span><strong>{{ displayCell(selectedSlot.state_name || selectedSlot.slot_state) }}</strong></div>
            <div><span>{{ t("table.remain") }}</span><strong>{{ remainLabel(selectedSlot.remain) }}</strong></div>
            <div><span>K</span><strong>{{ softCell(selectedSlot.k) }}</strong></div>
            <div><span>{{ t("ams.caliIdx") }}</span><strong>{{ softCell(selectedSlot.cali_idx) }}</strong></div>
            <div><span>RFID</span><strong>{{ softCell(selectedSlot.rfid_status_name || selectedSlot.rfid_status || selectedSlot.tray_info_idx) }}</strong></div>
            <div><span>{{ t("table.spool") }}</span><strong>{{ softCell(selectedSlot.spool_id) }}</strong></div>
          </div>
        </div>

        <section class="slot-detail-section">
          <div class="slot-section-title">
            <h4>{{ t("ams.changeSummary") }}</h4>
            <span>{{ t("ams.historySamples") }} {{ selectedSlotHistory.length }}</span>
          </div>
          <div class="slot-change-grid">
            <section v-for="kind in slotChangeKinds" :key="kind" class="slot-change-card">
              <div class="slot-change-card-head">
                <h4>{{ t(`ams.change.${kind}`) }}</h4>
                <span>{{ slotHistoryChanges(kind).length }}</span>
              </div>
              <div v-if="!slotHistoryChanges(kind).length" class="slot-empty-state">{{ t("ams.noChanges") }}</div>
              <div v-for="change in slotHistoryChanges(kind)" :key="`${kind}-${change.time}`" class="slot-change-row">
                <time>{{ formatCell(change.time) }}</time>
                <div class="slot-change-flow">
                  <span>{{ change.before }}</span>
                  <i>→</i>
                  <strong>{{ change.after }}</strong>
                </div>
              </div>
            </section>
          </div>
        </section>

        <section class="slot-detail-section">
          <div class="slot-section-title">
            <h4>{{ t("ams.historySamples") }}</h4>
            <span>{{ selectedSlotHistory.length }}</span>
          </div>
          <div class="table-wrap slot-history-table">
          <table>
            <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.state") }}</th><th>{{ t("table.material") }}</th><th>{{ t("form.color") }}</th><th>{{ t("table.remain") }}</th><th>K</th><th>{{ t("ams.caliIdx") }}</th><th>RFID</th></tr></thead>
            <tbody>
              <tr v-if="!selectedSlotHistory.length"><td colspan="8" class="empty">{{ t("common.empty") }}</td></tr>
              <tr v-for="sample in selectedSlotHistory" :key="sample.id">
                <td>{{ formatCell(sample.sampled_at) }}</td>
                <td>{{ displayCell(sample.state_name) }}</td>
                <td>{{ softCell(sample.material) }}</td>
                <td><span class="swatch" :style="{ background: filamentColor(sample.color) }"></span>{{ filamentColorDisplay(sample.color) }}</td>
                <td>{{ softCell(sample.remain) }}</td>
                <td>{{ softCell(sample.k) }}</td>
                <td>{{ softCell(sample.cali_idx) }}</td>
                <td>{{ softCell(sample.rfid_status) }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </section>
      </section>
    </div>

    <div v-if="loading" class="loading-mask" :title="displayCell('loading')">
      <Loader2 class="spin" :size="24" />
    </div>
</template>

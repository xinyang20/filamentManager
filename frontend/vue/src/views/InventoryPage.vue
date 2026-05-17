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
  colorNeedsMapping,
  deleteFilamentBrand,
  deleteFilamentColorMapping,
  deleteFilamentSku,
  deleteFilamentTypeSeries,
  editFilamentBrand,
  editFilamentColorMapping,
  editFilamentSku,
  editFilamentTypeSeries,
  filamentAmsFilamentLabel,
  filamentAmsRemainingLabel,
  filamentAmsSlotLocationLabel,
  filamentAmsState,
  filamentBrandDisplay,
  filamentColor,
  filamentColorDisplay,
  filamentInventoryKg,
  filamentInventorySummary,
  filamentSkuColorStateOptions,
  filamentSkuFilterBrandOptions,
  filamentSkuFilterMaterialOptions,
  filamentSkuFilterSeriesOptions,
  filamentSkuFilters,
  filamentSkuLabel,
  filamentSkuWeightOptions,
  filamentSpoolCurrentPlace,
  filamentSpoolHistoryTime,
  filamentSpoolLabel,
  filamentSpoolLastLocation,
  filamentSpoolLocation,
  filamentSpoolRemainingLabel,
  filamentSpoolStatusLabel,
  filamentTypeSeriesDisplay,
  filamentTypeSeriesLabel,
  filamentWeight,
  formatCell,
  inventoryChartColors,
  inventoryHistorySearch,
  inventoryMaxTypeWeightG,
  inventoryPage,
  inventoryPageOptions,
  inventoryPendingConfirmCount,
  inventoryRealSpoolWeightG,
  inventoryRealSpools,
  inventorySealedWeightG,
  inventorySortIndicator,
  inventoryTotalRolls,
  inventoryTotalWeightG,
  inventoryTypeBreakdown,
  inventoryTypePieStyle,
  isFilamentSpoolPendingConfirm,
  isFilamentSpoolSkuReviewDeferred,
  jumpToInventorySection,
  openConfirmFilamentSpoolSku,
  openCreateFilamentSpoolDialog,
  openFilamentBrandCreate,
  openFilamentColorMappingCreate,
  openFilamentSkuCreate,
  openFilamentSpoolDialog,
  openFilamentTypeSeriesCreate,
  openSealedStockAdjust,
  officialColorPalette,
  officialColorTypeLabel,
  printerDisplayName,
  resetFilamentSkuFilters,
  selectedFilamentSpoolId,
  skuOpenedWeight,
  skuSealedWeight,
  sortedFilamentAmsRows,
  sortedFilamentBrands,
  sortedFilamentColorMappingGaps,
  sortedFilamentColorMappings,
  sortedBambuOfficialColorMappings,
  sortedFilamentOpenedUnusedSpools,
  sortedFilamentStockSkus,
  sortedFilamentTypeSeries,
  sortedFilteredFilamentSkus,
  sortedHistoricalFilamentSpools,
  sortedNeedsLocationSpools,
  sortedPendingConfirmSpools,
  spools,
  startFilamentColorMapping,
  state,
  t,
  toggleInventorySort,
  updateFilamentSpoolStatus,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="inventory-tabs" role="tablist">
          <button
            v-for="item in inventoryPageOptions"
            :key="item.key"
            type="button"
            :class="{ active: inventoryPage === item.key }"
            @click="inventoryPage = item.key"
          >
            {{ item.label }}
          </button>
        </div>

        <template v-if="inventoryPage === 'stock'">
        <div class="metric-grid small">
          <div class="metric-card"><div class="metric-label">{{ t("inventory.totalStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventoryTotalWeightG) }}</div><div class="metric-foot">{{ inventoryTotalRolls }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.skus") }}</div><div class="metric-value">{{ filamentInventorySummary?.totals.sku_count || 0 }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.sealedStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventorySealedWeightG) }}</div><div class="metric-foot">{{ filamentInventorySummary?.totals.sealed_quantity || 0 }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.openedStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventoryRealSpoolWeightG) }}</div><div class="metric-foot">{{ inventoryRealSpools.length }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.amsLoaded") }}</div><div class="metric-value">{{ filamentInventorySummary?.totals.ams_spool_count || 0 }}</div></div>
          <button class="metric-card metric-button" type="button" @click="jumpToInventorySection('inventory-pending-confirm')"><div class="metric-label">{{ t("inventory.pendingConfirm") }}</div><div class="metric-value">{{ inventoryPendingConfirmCount }}</div><div class="metric-foot">{{ t("inventory.jumpToPending") }}</div></button>
        </div>
        <div class="inventory-split-grid inventory-main-grid">
        <section class="panel inventory-panel">
          <div class="panel-header">
            <h3>{{ t("inventory.stockAnalysis") }}</h3>
            <button class="icon-button compact" type="button" :title="t('inventory.addSpool')" @click="openCreateFilamentSpoolDialog"><Plus :size="16" /></button>
          </div>
          <div class="inventory-visual-grid">
            <div class="inventory-pie" :style="inventoryTypePieStyle"><span>{{ filamentInventoryKg(inventoryTotalWeightG) }}</span></div>
            <div class="inventory-breakdown">
              <div class="slot-section-title">
                <h4>{{ t("inventory.typeBreakdown") }}</h4>
                <span>{{ filamentInventoryKg(inventoryTotalWeightG) }}</span>
              </div>
              <div v-if="!inventoryTypeBreakdown.length" class="slot-empty-state">{{ t("inventory.noStockData") }}</div>
              <div v-for="(row, index) in inventoryTypeBreakdown" :key="row.key" class="inventory-breakdown-row">
                <div class="inventory-breakdown-label"><strong>{{ row.label }}</strong><span>{{ filamentInventoryKg(row.grams) }} / {{ row.rolls }} {{ t("inventory.rolls") }}</span></div>
                <div class="inventory-bar"><span :style="{ width: `${Math.max(4, Math.round((Number(row.grams || 0) / Number(inventoryMaxTypeWeightG || 1)) * 100))}%`, background: inventoryChartColors[Number(index) % inventoryChartColors.length] }"></span></div>
              </div>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.sealedStock") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("sealedStock", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'filament')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("sealedStock", "filament") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'sealed')">{{ t("form.sealedQty") }} <span>{{ inventorySortIndicator("sealedStock", "sealed") }}</span></button></th>
                <th>{{ t("inventory.sealedWeight") }}</th>
                <th>{{ t("inventory.openedWeight") }}</th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentStockSkus.length"><td colspan="6" class="empty">{{ t("inventory.noSealedStock") }}</td></tr>
                <tr v-for="sku in sortedFilamentStockSkus" :key="sku.id">
                  <td>{{ sku.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(sku.color_hex || sku.color_value) }"></span>{{ filamentSkuLabel(sku) }}</td>
                  <td>{{ sku.sealed_quantity }}</td>
                  <td>{{ filamentWeight(skuSealedWeight(sku)) }}</td>
                  <td>{{ filamentWeight(skuOpenedWeight(sku)) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('inventory.adjustStock')" @click="openSealedStockAdjust(sku)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </div>
        <section id="inventory-ams-loaded" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.amsLoaded") }}</h3><Boxes :size="18" /></div>
          <div class="table-wrap">
            <table class="inventory-ams-table">
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'printer')">{{ t("table.printer") }} <span>{{ inventorySortIndicator("amsLoaded", "printer") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'slot')">{{ t("ams.slots") }} <span>{{ inventorySortIndicator("amsLoaded", "slot") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'filament')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("amsLoaded", "filament") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("amsLoaded", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("amsLoaded", "status") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentAmsRows.length"><td colspan="6" class="empty">{{ t("ams.noSlots") }}</td></tr>
                <tr v-for="row in sortedFilamentAmsRows" :key="row.slot.id" :class="{ 'pending-row': row.spool && isFilamentSpoolPendingConfirm(row.spool) && !isFilamentSpoolSkuReviewDeferred(row.spool) }">
                  <td>{{ row.slot.printer_name || printerDisplayName(row.slot.printer_id) }}</td>
                  <td>{{ filamentAmsSlotLocationLabel(row.slot) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(row.spool?.color_hex || row.spool?.color_value || row.slot.color || row.slot.tray_color) }"></span>{{ filamentAmsFilamentLabel(row.slot, row.spool) }}</td>
                  <td>{{ filamentAmsRemainingLabel(row.slot, row.spool) }}</td>
                  <td class="inventory-inline-action">
                    <span>{{ filamentAmsState(row.slot, row.spool) }}</span>
                    <span v-if="row.spool && isFilamentSpoolSkuReviewDeferred(row.spool)" class="muted small-text">{{ t("inventory.waitingRfidReviewShort") }}</span>
                    <button
                      v-else-if="row.spool && isFilamentSpoolPendingConfirm(row.spool)"
                      class="text-action compact"
                      type="button"
                      :title="t('inventory.confirmSkuTitle')"
                      @click.stop="openConfirmFilamentSpoolSku(row.spool)"
                    >
                      {{ t("inventory.confirmSku") }}
                    </button>
                  </td>
                  <td class="inventory-inline-action">
                    <button v-if="row.spool" class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(row.spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.openedUnused") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("openedUnused", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("openedUnused", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("openedUnused", "status") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("openedUnused", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("openedUnused", "location") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentOpenedUnusedSpools.length"><td colspan="6" class="empty">{{ t("inventory.noOpenedUnused") }}</td></tr>
                <tr v-for="spool in sortedFilamentOpenedUnusedSpools" :key="spool.id" :class="{ selected: selectedFilamentSpoolId === spool.id }">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolLocation(spool) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section v-if="inventoryPendingConfirmCount" id="inventory-pending-confirm" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.pendingConfirm") }}</h3><AlertCircle :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("pendingConfirm", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("pendingConfirm", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("pendingConfirm", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("pendingConfirm", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("pendingConfirm", "status") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedPendingConfirmSpools.length"><td colspan="6" class="empty">{{ t("inventory.noPendingConfirm") }}</td></tr>
                <tr v-for="spool in sortedPendingConfirmSpools" :key="spool.id" class="pending-row">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolCurrentPlace(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td class="inventory-inline-action">
                    <button class="text-action compact" type="button" :title="t('inventory.confirmSkuTitle')" @click="openConfirmFilamentSpoolSku(spool)">{{ t("inventory.confirmSku") }}</button>
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section v-if="sortedNeedsLocationSpools.length" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.needsLocation") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("needsLocation", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("needsLocation", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("needsLocation", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'identity')">{{ t("inventory.identity") }} <span>{{ inventorySortIndicator("needsLocation", "identity") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="spool in sortedNeedsLocationSpools" :key="spool.id">
                  <td>{{ spool.id }}</td>
                  <td>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolLocation(spool) }}</td>
                  <td class="mono">{{ formatCell(spool.official_spool_uid || spool.identity_key) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'history'">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h3>{{ t("inventory.historySpools") }}</h3>
              <p class="panel-subtitle">{{ t("inventory.historySpoolsSubtitle") }}</p>
            </div>
            <Archive :size="18" />
          </div>
          <div class="toolbar filters sku-filter-toolbar">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="inventoryHistorySearch" :placeholder="t('inventory.searchHistorySpools')" />
            </label>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("history", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'spool')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("history", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("history", "status") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'location')">{{ t("inventory.lastLocation") }} <span>{{ inventorySortIndicator("history", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("history", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'time')">{{ t("inventory.historyTime") }} <span>{{ inventorySortIndicator("history", "time") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("history", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedHistoricalFilamentSpools.length"><td colspan="8" class="empty">{{ t("inventory.noHistorySpools") }}</td></tr>
                <tr v-for="spool in sortedHistoricalFilamentSpools" :key="spool.id">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td>{{ filamentSpoolLastLocation(spool) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolHistoryTime(spool) }}</td>
                  <td>{{ formatCell(spool.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                    <button class="text-action compact" type="button" @click="updateFilamentSpoolStatus(spool, 'opened_in_storage')">{{ t("inventory.restoreOpened") }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'brands'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.brands") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addBrand')" @click="openFilamentBrandCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("brands", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("brands", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'aliases')">{{ t("inventory.aliases") }} <span>{{ inventorySortIndicator("brands", "aliases") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'typeSeries')">{{ t("inventory.typeSeries") }} <span>{{ inventorySortIndicator("brands", "typeSeries") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'skus')">{{ t("inventory.skus") }} <span>{{ inventorySortIndicator("brands", "skus") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'spools')">{{ t("inventory.spools") }} <span>{{ inventorySortIndicator("brands", "spools") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("brands", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentBrands.length"><td colspan="8" class="empty">{{ t("inventory.noBrands") }}</td></tr>
                <tr v-for="brand in sortedFilamentBrands" :key="brand.id">
                  <td>{{ brand.id }}</td>
                  <td>{{ brand.name }}</td>
                  <td>{{ (brand.aliases || []).join(", ") || "—" }}</td>
                  <td>{{ brand.type_series_count || 0 }}</td>
                  <td>{{ brand.sku_count || 0 }}</td>
                  <td>{{ brand.spool_count || 0 }}</td>
                  <td>{{ formatCell(brand.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentBrand(brand)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentBrand(brand)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'types'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.typeSeries") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addTypeSeries')" @click="openFilamentTypeSeriesCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("typeSeries", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("typeSeries", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("typeSeries", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'emptyWeight')">{{ t("inventory.emptySpoolWeight") }} <span>{{ inventorySortIndicator("typeSeries", "emptyWeight") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'skus')">{{ t("inventory.skus") }} <span>{{ inventorySortIndicator("typeSeries", "skus") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'spools')">{{ t("inventory.spools") }} <span>{{ inventorySortIndicator("typeSeries", "spools") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentTypeSeries.length"><td colspan="7" class="empty">{{ t("inventory.noTypeSeries") }}</td></tr>
                <tr v-for="row in sortedFilamentTypeSeries" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ filamentBrandDisplay(row.brands) }}</td>
                  <td>{{ filamentTypeSeriesLabel(row) }}</td>
                  <td>{{ filamentWeight(row.empty_spool_weight_g) }}</td>
                  <td>{{ row.sku_count }}</td>
                  <td>{{ row.spool_count }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentTypeSeries(row)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentTypeSeries(row)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'skus'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.skus") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addSku')" @click="openFilamentSkuCreate"><Plus :size="16" /></button></div>
          <div class="toolbar filters sku-filter-toolbar">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="filamentSkuFilters.search" :placeholder="t('inventory.searchSku')" />
            </label>
            <AppSelect v-model="filamentSkuFilters.brand_id" :options="filamentSkuFilterBrandOptions" />
            <AppSelect v-model="filamentSkuFilters.material_type" :options="filamentSkuFilterMaterialOptions" />
            <AppSelect v-model="filamentSkuFilters.series_name" :options="filamentSkuFilterSeriesOptions" />
            <AppSelect v-model="filamentSkuFilters.nominal_weight_g" :options="filamentSkuWeightOptions" />
            <AppSelect v-model="filamentSkuFilters.color_state" :options="filamentSkuColorStateOptions" />
            <button class="secondary" type="button" @click="resetFilamentSkuFilters">{{ t("common.clear") }}</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("skus", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("skus", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("skus", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("skus", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'weight')">{{ t("inventory.nominalWeight") }} <span>{{ inventorySortIndicator("skus", "weight") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'sealed')">{{ t("form.sealedQty") }} <span>{{ inventorySortIndicator("skus", "sealed") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilteredFilamentSkus.length"><td colspan="7" class="empty">{{ t("inventory.noSkuMatches") }}</td></tr>
                <tr v-for="sku in sortedFilteredFilamentSkus" :key="sku.id">
                  <td>{{ sku.id }}</td>
                  <td>{{ filamentBrandDisplay(sku.brands) }}</td>
                  <td>{{ filamentTypeSeriesDisplay(sku.type_series) }}</td>
                  <td>
                    <span class="swatch" :style="{ background: filamentColor(sku.color_hex || sku.color_value) }"></span>{{ filamentColorDisplay(sku.color_hex || sku.color_value, sku.color_name, sku) }}
                    <button v-if="colorNeedsMapping(sku.color_hex || sku.color_value, sku)" class="text-action compact" type="button" @click="startFilamentColorMapping(sku.color_hex || sku.color_value, sku)">{{ t("inventory.addOfficialName") }}</button>
                  </td>
                  <td>{{ filamentWeight(sku.nominal_weight_g) }}</td>
                  <td>{{ sku.sealed_quantity }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentSku(sku)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentSku(sku)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'colors'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.colorMappings") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addColorMapping')" @click="openFilamentColorMappingCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("colorMappings", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("colorMappings", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("colorMappings", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'hex')">{{ t("inventory.hexValue") }} <span>{{ inventorySortIndicator("colorMappings", "hex") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("colorMappings", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("colorMappings", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentColorMappings.length"><td colspan="7" class="empty">{{ t("inventory.noColorMappings") }}</td></tr>
                <tr v-for="mapping in sortedFilamentColorMappings" :key="mapping.id">
                  <td>{{ mapping.id }}</td>
                  <td>{{ formatCell(mapping.brand_name) }}</td>
                  <td>{{ filamentTypeSeriesLabel(mapping) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(mapping.color_hex || mapping.hex_value) }"></span><span class="mono">{{ mapping.color_hex || mapping.hex_value }}</span></td>
                  <td>{{ mapping.color_name || mapping.official_name }}</td>
                  <td>{{ formatCell(mapping.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentColorMapping(mapping)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentColorMapping(mapping)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.incompleteSkuColors") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("colorGaps", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("colorGaps", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("colorGaps", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("colorGaps", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'hex')">{{ t("inventory.hexValue") }} <span>{{ inventorySortIndicator("colorGaps", "hex") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'source')">{{ t("inventory.source") }} <span>{{ inventorySortIndicator("colorGaps", "source") }}</span></button></th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentColorMappingGaps.length"><td colspan="6" class="empty">{{ t("inventory.noColorGaps") }}</td></tr>
                <tr v-for="row in sortedFilamentColorMappingGaps" :key="row.sku_id">
                  <td>{{ row.sku_id }}</td>
                  <td>{{ filamentBrandDisplay(row.brands) }}</td>
                  <td>{{ filamentTypeSeriesDisplay(row.type_series) }}</td>
                  <td>{{ formatCell(row.color_name) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(row.color_hex) }"></span><span class="mono">{{ formatCell(row.color_hex) }}</span></td>
                  <td>{{ row.missing.join(", ") }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'officialColors'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.officialColorMappings") }}</h3><Database :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'id')">{{ t("inventory.officialColorCode") }} <span>{{ inventorySortIndicator("officialColorMappings", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("officialColorMappings", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'tray')">{{ t("inventory.trayInfoIdx") }} <span>{{ inventorySortIndicator("officialColorMappings", "tray") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'type')">{{ t("inventory.officialColorType") }} <span>{{ inventorySortIndicator("officialColorMappings", "type") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("officialColorMappings", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'en')">{{ t("inventory.officialColorNameEn") }} <span>{{ inventorySortIndicator("officialColorMappings", "en") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('officialColorMappings', 'hex')">{{ t("inventory.hexValue") }} <span>{{ inventorySortIndicator("officialColorMappings", "hex") }}</span></button></th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedBambuOfficialColorMappings.length"><td colspan="7" class="empty">{{ t("inventory.noOfficialColorMappings") }}</td></tr>
                <tr v-for="mapping in sortedBambuOfficialColorMappings" :key="mapping.id">
                  <td class="mono">{{ formatCell(mapping.official_color_code) }}</td>
                  <td>{{ filamentTypeSeriesLabel(mapping) }}</td>
                  <td class="mono">{{ formatCell(mapping.tray_info_idx) }}</td>
                  <td>{{ officialColorTypeLabel(mapping.official_color_type) }}</td>
                  <td>{{ filamentColorDisplay(mapping.color_hex || mapping.hex_value, mapping.color_name || mapping.official_name, mapping) }}</td>
                  <td>{{ formatCell(mapping.official_color_names?.en) }}</td>
                  <td>
                    <span class="swatch-row">
                      <span
                        v-for="color in officialColorPalette(mapping)"
                        :key="`${mapping.id}-${color}`"
                        class="swatch"
                        :style="{ background: filamentColor(color) }"
                      ></span>
                    </span>
                    <span class="mono">{{ officialColorPalette(mapping).join(", ") }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

      </section>
</template>

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
  changeStoragePage,
  error,
  filteredTimelapseFiles,
  formatBytes,
  formatCell,
  groupedTimelapseFiles,
  inputValue,
  resetVideoPlayback,
  saveTimelapseNote,
  seekVideoPreviewToEnd,
  setTimelapseDraft,
  softCell,
  storageFileUrl,
  storagePage,
  storagePreviewFiles,
  storageResult,
  storageSearch,
  storageSort,
  storageSortOptions,
  storageStats,
  storageTotalPages,
  t,
  timelapseNote,
  timelapseNoteText,
  toggleTimelapseFavorite,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="toolbar storage-toolbar">
          <div class="toolbar filters storage-filters">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="storageSearch" :placeholder="t('storage.search')" />
            </label>
            <AppSelect v-model="storageSort" :options="storageSortOptions" />
          </div>
        </div>
        <div class="metric-grid small spool-detail-summary">
          <div v-for="item in storageStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
            <div v-if="item.foot" class="metric-foot">{{ item.foot }}</div>
          </div>
        </div>
        <section class="panel">
          <div class="panel-header">
            <div>
              <h3>{{ t("storage.preview") }}</h3>
              <p class="panel-subtitle">{{ t("storage.previewSubtitle", { count: filteredTimelapseFiles.length }) }}</p>
            </div>
            <Camera :size="18" />
          </div>
          <div v-if="storageResult?.error" class="inline-error">{{ storageResult.error }}</div>
          <div class="storage-preview-grid">
            <article v-for="file in storagePreviewFiles" :key="file.path" class="storage-preview-card">
              <video
                :src="storageFileUrl(file, true)"
                muted
                controls
                preload="metadata"
                playsinline
                @loadedmetadata="seekVideoPreviewToEnd"
                @play="resetVideoPlayback"
              ></video>
              <div class="storage-preview-meta">
                <div class="storage-title-row">
                  <strong>{{ file.name }}</strong>
                  <button class="icon-button compact" type="button" :title="t('storage.favorite')" @click="toggleTimelapseFavorite(file)">
                    <Star :size="15" :fill="timelapseNote(file)?.favorite ? 'currentColor' : 'none'" />
                  </button>
                </div>
                <span>{{ formatBytes(file.size || 0) }} · {{ formatCell(file.modified_at) }}</span>
                <span>{{ t("fields.resolution") }} {{ softCell(timelapseNote(file)?.cached_metadata?.resolution) }} · {{ t("storage.coverCache") }} {{ softCell(timelapseNote(file)?.cached_metadata?.cover_cache) }}</span>
              </div>
              <div class="timelapse-note-row">
                <input
                  :value="timelapseNoteText(file)"
                  :placeholder="t('storage.note')"
                  @input="setTimelapseDraft(file.path, inputValue($event))"
                />
                <button class="secondary" type="button" @click="saveTimelapseNote(file)">{{ t("common.save") }}</button>
              </div>
              <a class="secondary storage-download-link" :href="storageFileUrl(file)" :download="file.name">
                <Download :size="15" />
                {{ t("storage.download") }}
              </a>
            </article>
            <div v-if="!storagePreviewFiles.length" class="empty">{{ t("storage.noPreview") }}</div>
          </div>
          <div v-if="filteredTimelapseFiles.length" class="pager">
            <button class="secondary" type="button" :disabled="storagePage <= 1" @click="changeStoragePage(-1)">{{ t("printLog.prev") }}</button>
            <span>{{ t("storage.pageInfo", { page: storagePage, total: storageTotalPages, count: filteredTimelapseFiles.length }) }}</span>
            <button class="secondary" type="button" :disabled="storagePage >= storageTotalPages" @click="changeStoragePage(1)">{{ t("printLog.next") }}</button>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("storage.groupByDate") }}</h3><Camera :size="18" /></div>
          <div class="date-group-list">
            <div v-for="group in groupedTimelapseFiles" :key="group.date" class="date-group-row">
              <strong>{{ group.date }}</strong>
              <span>{{ group.files.length }}</span>
            </div>
            <div v-if="!groupedTimelapseFiles.length" class="empty">{{ t("common.empty") }}</div>
          </div>
        </section>
      </section>
</template>

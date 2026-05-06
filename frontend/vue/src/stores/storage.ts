import { computed, reactive, ref, watch } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { API_BASE, apiRequest, numeric } from "../api";
import type { StorageFile, StorageSummary, TimelapseNote } from "../types";
import { useI18nStore } from "./i18n";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useStorageStore = defineStore("storage", () => {
  const i18nStore = useI18nStore();
  const { locale } = storeToRefs(i18nStore);
  const { t } = i18nStore;
  const { withLoading } = useUiStore();
  const printersStore = () => usePrintersStore();
  const presentationStore = () => usePresentationStore();

  const storageFiles = ref<StorageFile[]>([]);

  const storageSummary = ref<StorageSummary | null>(null);

  const storageSearch = ref("");

  const storageSort = ref("modified_desc");

  const storagePage = ref(1);

  const storagePageSize = ref(12);

  const timelapseNotes = ref<Record<string, TimelapseNote>>({});

  const timelapseNoteDrafts = reactive<Record<string, string>>({});

  const storageResult = ref<Record<string, any> | null>(null);

  const storageSortOptions = computed(() => [
    { label: t("storage.sortModifiedDesc"), value: "modified_desc" },
    { label: t("storage.sortModifiedAsc"), value: "modified_asc" },
    { label: t("storage.sortSizeDesc"), value: "size_desc" },
    { label: t("storage.sortSizeAsc"), value: "size_asc" },
    { label: t("storage.sortNameAsc"), value: "name_asc" },
    { label: t("storage.sortNameDesc"), value: "name_desc" },
  ]);

  const storageStats = computed(() => {
    const files = timelapseFiles.value;
    const totalSize = files.reduce((sum, item) => sum + (item.size || 0), 0);
    const usage = storageSummary.value?.storage_usage || {};
    const cards: { label: string; value: string | number; foot?: string }[] = [
      { label: t("storage.fileCount"), value: storageFiles.value.length },
      { label: t("storage.totalSize"), value: presentationStore().formatBytes(totalSize) },
      { label: t("storage.timelapseCount"), value: files.length },
    ];
    cards.push(storageUsageCard("internal", usage.internal));
    cards.push(storageUsageCard("external", usage.external));
    if (usage.current_target) {
      cards.push({ label: t("storage.currentTarget"), value: storageTargetLabel(usage.current_target) });
    }
    return cards;
  });

  const timelapseFiles = computed(() => storageFiles.value.filter((item) => isTimelapseStorageFile(item)));

  const filteredTimelapseFiles = computed(() => {
    const query = storageSearch.value.trim().toLowerCase();
    const items = query
      ? timelapseFiles.value.filter((item) => `${item.name} ${item.path}`.toLowerCase().includes(query))
      : timelapseFiles.value;
    return [...items].sort((a, b) => compareStorageFiles(a, b, storageSort.value));
  });

  const storageTotalPages = computed(() => Math.max(1, Math.ceil(filteredTimelapseFiles.value.length / storagePageSize.value)));

  const storagePreviewFiles = computed(() => {
    const start = (storagePage.value - 1) * storagePageSize.value;
    return filteredTimelapseFiles.value.slice(start, start + storagePageSize.value);
  });

  const groupedTimelapseFiles = computed(() => {
    const groups: Record<string, StorageFile[]> = {};
    for (const file of filteredTimelapseFiles.value) {
      const key = String(file.modified_at || "").slice(0, 10) || t("common.none");
      groups[key] = groups[key] || [];
      groups[key].push(file);
    }
    return Object.entries(groups).map(([date, files]) => ({ date, files }));
  });

  watch([storageSearch, storageSort, () => storageFiles.value.length], () => {
    storagePage.value = 1;
  });


  watch(storageTotalPages, (pages) => {
    if (storagePage.value > pages) storagePage.value = pages;
  });


  async function loadStorage() {
    if (!printersStore().selectedPrinterId) return;
    const [filesResult, summaryResult, notesResult] = await Promise.all([
      apiRequest<StorageFile[]>(`/printers/${printersStore().selectedPrinterId}/storage/files`),
      apiRequest<StorageSummary>(`/printers/${printersStore().selectedPrinterId}/storage/summary`),
      apiRequest<TimelapseNote[]>(`/printers/${printersStore().selectedPrinterId}/timelapse/notes`),
    ]);
    storageFiles.value = filesResult;
    storageSummary.value = summaryResult;
    timelapseNotes.value = Object.fromEntries(notesResult.map((note) => [note.path, note]));
    for (const note of notesResult) timelapseNoteDrafts[note.path] = note.note || "";
  }


  async function scanStorage() {
    if (!printersStore().selectedPrinterId) return;
    await withLoading(async () => {
      storageResult.value = await apiRequest<Record<string, any>>(`/printers/${printersStore().selectedPrinterId}/storage/scan`, {
        method: "POST",
      });
      await loadStorage();
    });
  }


  function storageUsageCard(kind: "internal" | "external", usage: Record<string, any> | undefined) {
    const label = kind === "internal" ? t("storage.internalStorage") : t("storage.externalStorage");
    if (!usage || !usage.total_bytes) return { label, value: "--", foot: t("storage.usageUnknown") };
    const used = numeric(usage.used_bytes) || 0;
    const total = numeric(usage.total_bytes) || 0;
    return {
      label,
      value: `${presentationStore().formatBytes(used)} / ${presentationStore().formatBytes(total)}`,
      foot: t("storage.freeSpace", { value: presentationStore().formatBytes(numeric(usage.free_bytes) || 0), percent: usage.used_percent ?? "--" }),
    };
  }


  function storageTargetLabel(value: unknown) {
    const key = String(value || "");
    if (key === "internal") return t("storage.internalStorage");
    if (key === "external") return t("storage.externalStorage");
    return presentationStore().displayCell(value);
  }


  function storageFileUrl(file: StorageFile, inline = false) {
    if (!printersStore().selectedPrinterId) return "#";
    const params = new URLSearchParams({ path: file.path });
    if (inline) params.set("inline", "true");
    return `${API_BASE}/printers/${printersStore().selectedPrinterId}/storage/files/download?${params.toString()}`;
  }


  function timelapseNote(file: StorageFile) {
    return timelapseNotes.value[file.path] || null;
  }


  function timelapseNoteText(file: StorageFile) {
    return timelapseNoteDrafts[file.path] ?? timelapseNote(file)?.note ?? "";
  }


  function setTimelapseDraft(path: string, value: string) {
    timelapseNoteDrafts[path] = value;
  }


  async function toggleTimelapseFavorite(file: StorageFile) {
    if (!printersStore().selectedPrinterId) return;
    const current = timelapseNote(file);
    await withLoading(async () => {
      const note = await apiRequest<TimelapseNote>(`/printers/${printersStore().selectedPrinterId}/timelapse/notes`, {
        method: "PATCH",
        body: JSON.stringify({
          path: file.path,
          favorite: !(current?.favorite === true),
          cached_metadata: timelapseMetadata(file),
        }),
      });
      timelapseNotes.value = { ...timelapseNotes.value, [file.path]: note };
    });
  }


  async function saveTimelapseNote(file: StorageFile) {
    if (!printersStore().selectedPrinterId) return;
    await withLoading(async () => {
      const note = await apiRequest<TimelapseNote>(`/printers/${printersStore().selectedPrinterId}/timelapse/notes`, {
        method: "PATCH",
        body: JSON.stringify({
          path: file.path,
          note: timelapseNoteText(file),
          cached_metadata: timelapseMetadata(file),
        }),
      });
      timelapseNotes.value = { ...timelapseNotes.value, [file.path]: note };
      timelapseNoteDrafts[file.path] = note.note || "";
    });
  }


  function timelapseMetadata(file: StorageFile) {
    return {
      name: file.name,
      size: file.size,
      modified_at: file.modified_at,
      type: file.type,
      cover_cache: "browser-metadata",
    };
  }


  function isTimelapseStorageFile(file: StorageFile) {
    const type = String(file.type || "").toLowerCase();
    const name = String(file.name || file.path || "").toLowerCase();
    return type === "timelapse" || file.path.includes("/timelapse/") || /\.(mp4|mov|avi|mkv)$/i.test(name);
  }


  function compareStorageFiles(a: StorageFile, b: StorageFile, sortKey: string) {
    const nameCompare = (a.name || a.path).localeCompare(b.name || b.path, locale.value);
    if (sortKey === "modified_asc") return storageTime(a) - storageTime(b) || nameCompare;
    if (sortKey === "size_desc") return (b.size || 0) - (a.size || 0) || nameCompare;
    if (sortKey === "size_asc") return (a.size || 0) - (b.size || 0) || nameCompare;
    if (sortKey === "name_desc") return -nameCompare;
    if (sortKey === "name_asc") return nameCompare;
    return storageTime(b) - storageTime(a) || nameCompare;
  }


  function storageTime(file: StorageFile) {
    const value = Date.parse(String(file.modified_at || ""));
    return Number.isFinite(value) ? value : 0;
  }


  function changeStoragePage(delta: number) {
    storagePage.value = Math.max(1, Math.min(storageTotalPages.value, storagePage.value + delta));
  }


  function seekVideoPreviewToEnd(event: Event) {
    const video = event.currentTarget as HTMLVideoElement | null;
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;
    try {
      video.currentTime = Math.max(0, video.duration - 0.08);
    } catch {
      // Some browsers defer seeking until enough metadata has loaded.
    }
  }


  function resetVideoPlayback(event: Event) {
    const video = event.currentTarget as HTMLVideoElement | null;
    if (!video || !Number.isFinite(video.duration)) return;
    if (video.currentTime >= Math.max(0, video.duration - 0.12)) {
      video.currentTime = 0;
    }
  }


  return {
    storageFiles,
    storageSummary,
    storageSearch,
    storageSort,
    storagePage,
    storagePageSize,
    timelapseNotes,
    timelapseNoteDrafts,
    storageResult,
    storageSortOptions,
    storageStats,
    timelapseFiles,
    filteredTimelapseFiles,
    storageTotalPages,
    storagePreviewFiles,
    groupedTimelapseFiles,
    loadStorage,
    scanStorage,
    storageUsageCard,
    storageTargetLabel,
    storageFileUrl,
    timelapseNote,
    timelapseNoteText,
    setTimelapseDraft,
    toggleTimelapseFavorite,
    saveTimelapseNote,
    timelapseMetadata,
    isTimelapseStorageFile,
    compareStorageFiles,
    storageTime,
    changeStoragePage,
    seekVideoPreviewToEnd,
    resetVideoPlayback,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useStorageStore, import.meta.hot));
}

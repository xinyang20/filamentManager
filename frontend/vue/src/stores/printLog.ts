import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";
import { apiRequest } from "../api";
import type { PrintLogAnalytics, PrintLogEntry, PrintLogList, PrintLogSummary } from "../types";
import { useI18nStore } from "./i18n";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const usePrintLogStore = defineStore("printLog", () => {
  const { t } = useI18nStore();
  const { withLoading } = useUiStore();
  const printersStore = () => usePrintersStore();

  const printLogs = ref<PrintLogEntry[]>([]);

  const printLogSummary = ref<PrintLogSummary | null>(null);

  const printLogAnalytics = ref<PrintLogAnalytics | null>(null);

  const printLogTotal = ref(0);

  const printLogFilters = reactive({
    printer_id: "",
    status: "",
    search: "",
    date_from: "",
    date_to: "",
    limit: 25,
    offset: 0,
  });

  const printLogPrinterOptions = computed(() => [
    { label: t("printLog.allPrinters"), value: "" },
    ...printersStore().printers.map((printer) => ({ label: printer.name, value: String(printer.id) })),
  ]);

  const printLogStatusOptions = computed(() => [
    { label: t("printLog.allStatuses"), value: "" },
    { label: t("values.running"), value: "running" },
    { label: t("values.paused"), value: "paused" },
    { label: t("values.succeeded"), value: "succeeded" },
    { label: t("values.failed"), value: "failed" },
    { label: t("values.cancelled"), value: "cancelled" },
  ]);

  const printLogPage = computed(() => Math.floor(printLogFilters.offset / printLogFilters.limit) + 1);

  const printLogTotalPages = computed(() => Math.max(1, Math.ceil(printLogTotal.value / printLogFilters.limit)));

  async function loadPrintLog() {
    const params = new URLSearchParams({
      limit: String(printLogFilters.limit),
      offset: String(printLogFilters.offset),
    });
    if (printLogFilters.printer_id) params.set("printer_id", printLogFilters.printer_id);
    if (printLogFilters.status) params.set("status", printLogFilters.status);
    if (printLogFilters.search) params.set("search", printLogFilters.search);
    if (printLogFilters.date_from) params.set("date_from", new Date(printLogFilters.date_from).toISOString());
    if (printLogFilters.date_to) params.set("date_to", new Date(printLogFilters.date_to).toISOString());
    const analyticsParams = new URLSearchParams();
    if (printLogFilters.printer_id) analyticsParams.set("printer_id", printLogFilters.printer_id);
    if (printLogFilters.date_from) analyticsParams.set("from", new Date(printLogFilters.date_from).toISOString());
    if (printLogFilters.date_to) analyticsParams.set("to", new Date(printLogFilters.date_to).toISOString());
    const [listResult, summaryResult, analyticsResult] = await Promise.all([
      apiRequest<PrintLogList>(`/print-log?${params.toString()}`),
      apiRequest<PrintLogSummary>("/print-log/summary"),
      apiRequest<PrintLogAnalytics>(`/print-log/analytics?${analyticsParams.toString()}`),
    ]);
    printLogs.value = listResult.items;
    printLogTotal.value = listResult.total;
    printLogSummary.value = summaryResult;
    printLogAnalytics.value = analyticsResult;
  }


  async function applyPrintLogFilters() {
    printLogFilters.offset = 0;
    await withLoading(loadPrintLog);
  }


  async function changePrintLogPage(delta: number) {
    const next = printLogFilters.offset + delta * printLogFilters.limit;
    printLogFilters.offset = Math.max(0, Math.min(next, Math.max(0, printLogTotal.value - 1)));
    await withLoading(loadPrintLog);
  }


  function printLogTone(statusValue: string) {
    if (statusValue === "succeeded") return "good";
    if (statusValue === "failed") return "bad";
    if (statusValue === "cancelled" || statusValue === "paused") return "warn";
    return "muted";
  }


  return {
    printLogs,
    printLogSummary,
    printLogAnalytics,
    printLogTotal,
    printLogFilters,
    printLogPrinterOptions,
    printLogStatusOptions,
    printLogPage,
    printLogTotalPages,
    loadPrintLog,
    applyPrintLogFilters,
    changePrintLogPage,
    printLogTone,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePrintLogStore, import.meta.hot));
}

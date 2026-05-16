import { computed, reactive, ref, watch } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { apiRequest } from "../api";
import type { DiscoveryCandidate, Printer } from "../types";
import { useDashboardStore } from "./dashboard";
import { useI18nStore } from "./i18n";
import { useNavigationStore } from "./navigation";
import { useUiStore } from "./ui";

export const usePrintersStore = defineStore("printers", () => {
  const uiStore = useUiStore();
  const { error, message } = storeToRefs(uiStore);
  const { t } = useI18nStore();
  const { withLoading } = uiStore;
  const navigationStore = () => useNavigationStore();
  const dashboardStore = () => useDashboardStore();

  const printers = ref<Printer[]>([]);

  const selectedPrinterId = ref<number | null>(null);

  const editingPrinterId = ref<number | null>(null);

  const discovery = ref<DiscoveryCandidate[]>([]);

  const scanning = ref(false);

  const scanProgress = ref(0);

  const scanPhase = ref("");

  const printerForm = reactive({
    name: "Printer",
    host: "",
    port: 8883,
    serial: "",
    access_code: "",
    tls_enabled: true,
    certificate_verify: false,
  });

  const accessCodeVisible = ref(false);

  const accessCodeRevealLoading = ref(false);

  const selectedPrinter = computed(() => printers.value.find((item) => item.id === selectedPrinterId.value) || null);

  const editingPrinter = computed(() => printers.value.find((item) => item.id === editingPrinterId.value) || null);

  const printerSelectOptions = computed(() =>
    printers.value.length
      ? printers.value.map((printer) => ({ label: `${printer.name} · ${printer.host}`, value: printer.id }))
      : [{ label: t("common.noPrinter"), value: null, disabled: true }],
  );

  const locationPrinterOptions = computed(() => [
    { label: t("common.noPrinter"), value: null },
    ...printers.value.map((printer) => ({ label: `${printer.name} · ${printer.host}`, value: printer.id })),
  ]);

  const scanProgressLabel = computed(() => Math.round(scanProgress.value));

  const scanProgressWidth = computed(() => Math.max(0, Math.min(100, scanProgress.value)));


  const printerStatusTone = computed(() => {
    const status = selectedPrinter.value?.connection_status;
    if (status === "connected") return "good";
    if (status === "error") return "bad";
    if (status === "connecting") return "warn";
    return "muted";
  });

  watch(selectedPrinter, () => {
    dashboardStore().cameraCapabilities = null;
    dashboardStore().cameraLightboxOpen = false;
    dashboardStore().restartCameraStream();
  });


  async function refreshPrinters() {
    printers.value = await apiRequest<Printer[]>("/printers");
    if (!selectedPrinterId.value && printers.value.length) {
      selectedPrinterId.value = printers.value[0].id;
    }
    if (selectedPrinterId.value && !printers.value.some((printer) => printer.id === selectedPrinterId.value)) {
      selectedPrinterId.value = printers.value[0]?.id ?? null;
    }
    if (editingPrinterId.value && !printers.value.some((printer) => printer.id === editingPrinterId.value)) {
      editingPrinterId.value = null;
      resetPrinterForm();
    }
  }


  async function savePrinter() {
    await withLoading(async () => {
      const editingId = editingPrinterId.value;
      const payload: Record<string, unknown> = {
        name: printerForm.name,
        host: printerForm.host,
        port: Number(printerForm.port),
        serial: printerForm.serial,
        access_code: printerForm.access_code,
        tls_enabled: printerForm.tls_enabled,
        certificate_verify: printerForm.certificate_verify,
      };
      const printer = editingId
        ? await apiRequest<Printer>(`/printers/${editingId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        })
        : await apiRequest<Printer>("/printers", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      editingPrinterId.value = printer.id;
      if (!selectedPrinterId.value) selectedPrinterId.value = printer.id;
      await refreshPrinters();
      populatePrinterForm(printer);
      message.value = editingId ? t("message.printerUpdated") : t("message.printerSaved");
    });
  }


  async function handlePrinterSelectionChanged() {
    await navigationStore().loadCurrent();
  }


  function populatePrinterForm(printer: Printer) {
    printerForm.name = printer.name;
    printerForm.host = printer.host;
    printerForm.port = printer.port;
    printerForm.serial = printer.serial;
    printerForm.access_code = printer.access_code || "";
    printerForm.tls_enabled = printer.tls_enabled;
    printerForm.certificate_verify = printer.certificate_verify;
    accessCodeVisible.value = false;
    accessCodeRevealLoading.value = false;
  }


  function resetPrinterForm() {
    printerForm.name = "Printer";
    printerForm.host = "";
    printerForm.port = 8883;
    printerForm.serial = "";
    printerForm.access_code = "";
    printerForm.tls_enabled = true;
    printerForm.certificate_verify = false;
    accessCodeVisible.value = false;
    accessCodeRevealLoading.value = false;
  }


  function startCreatePrinter(candidate?: DiscoveryCandidate | null) {
    editingPrinterId.value = null;
    resetPrinterForm();
    if (!candidate) return;
    printerForm.name = candidate.device_name || "Bambu Printer";
    printerForm.host = candidate.host;
    printerForm.serial = candidate.serial || "";
    printerForm.port = 8883;
  }


  function editPrinter(printer: Printer) {
    editingPrinterId.value = printer.id;
    populatePrinterForm(printer);
  }


  function isMaskedAccessCode(value: string) {
    return value.startsWith("****");
  }


  async function toggleAccessCodeVisibility() {
    if (accessCodeVisible.value) {
      accessCodeVisible.value = false;
      return;
    }
    if (editingPrinterId.value && isMaskedAccessCode(printerForm.access_code)) {
      accessCodeRevealLoading.value = true;
      error.value = "";
      try {
        const result = await apiRequest<{ access_code: string }>(`/printers/${editingPrinterId.value}/access-code`);
        printerForm.access_code = result.access_code || "";
      } catch (err) {
        error.value = err instanceof Error ? err.message : String(err);
        return;
      } finally {
        accessCodeRevealLoading.value = false;
      }
    }
    accessCodeVisible.value = true;
  }


  async function scanDevices() {
    scanning.value = true;
    scanProgress.value = 2;
    scanPhase.value = t("scan.phaseStart");
    let animationFrame = 0;
    let animating = true;
    const startedAt = window.performance.now();
    const animate = () => {
      if (!animating) return;
      const elapsedSeconds = (window.performance.now() - startedAt) / 1000;
      const easedTarget = Math.min(98, 4 + 94 * (1 - Math.exp(-elapsedSeconds / 4.8)));
      scanProgress.value = Math.max(scanProgress.value, easedTarget);
      if (scanProgress.value < 34) {
        scanPhase.value = t("scan.phasePorts");
      } else if (scanProgress.value < 72) {
        scanPhase.value = t("scan.phaseVerify");
      } else {
        scanPhase.value = t("scan.phaseCollect");
      }
      animationFrame = window.requestAnimationFrame(animate);
    };
    animationFrame = window.requestAnimationFrame(animate);
    await withLoading(async () => {
      try {
        discovery.value = await apiRequest<DiscoveryCandidate[]>("/discovery/scan");
        animating = false;
        window.cancelAnimationFrame(animationFrame);
        scanProgress.value = 100;
        scanPhase.value = discovery.value.length
          ? t("scan.found", { count: discovery.value.length })
          : t("scan.notFound");
        if (discovery.value.length) {
          startCreatePrinter(discovery.value[0]);
        }
      } finally {
        animating = false;
        window.cancelAnimationFrame(animationFrame);
        window.setTimeout(() => {
          scanning.value = false;
        }, 800);
      }
    });
  }


  async function connectPrinter(printerId?: number | null) {
    const targetPrinterId = printerId ?? selectedPrinterId.value;
    if (!targetPrinterId) return;
    await withLoading(async () => {
      await apiRequest<Printer>(`/printers/${targetPrinterId}/connect`, { method: "POST" });
      await refreshPrinters();
      if (targetPrinterId === selectedPrinterId.value) await navigationStore().loadCurrent();
      message.value = t("message.connectSent");
    });
  }


  async function disconnectPrinter(printerId?: number | null) {
    const targetPrinterId = printerId ?? selectedPrinterId.value;
    if (!targetPrinterId) return;
    await withLoading(async () => {
      await apiRequest<Printer>(`/printers/${targetPrinterId}/disconnect`, { method: "POST" });
      await refreshPrinters();
      if (targetPrinterId === selectedPrinterId.value) await navigationStore().loadCurrent();
      message.value = t("message.disconnected");
    });
  }


  async function deletePrinterConfig(printer: Printer) {
    const confirmed = window.confirm(t("printers.deleteConfirm", { name: printer.name }));
    if (!confirmed) return;
    await withLoading(async () => {
      await apiRequest(`/printers/${printer.id}`, { method: "DELETE" });
      if (selectedPrinterId.value === printer.id) {
        selectedPrinterId.value = null;
      }
      if (editingPrinterId.value === printer.id) {
        editingPrinterId.value = null;
      }
      await refreshPrinters();
      if (!selectedPrinterId.value && printers.value.length) {
        selectedPrinterId.value = printers.value[0].id;
      }
      if (editingPrinter.value) {
        populatePrinterForm(editingPrinter.value);
      } else if (!editingPrinterId.value) {
        resetPrinterForm();
      }
      await navigationStore().loadCurrent();
      message.value = t("message.printerDeleted");
    });
  }


  async function openPrinterDashboard(printerId: number) {
    selectedPrinterId.value = printerId;
    await navigationStore().switchView("dashboard");
  }


  return {
    printers,
    selectedPrinterId,
    editingPrinterId,
    discovery,
    scanning,
    scanProgress,
    scanPhase,
    printerForm,
    accessCodeVisible,
    accessCodeRevealLoading,
    selectedPrinter,
    editingPrinter,
    printerSelectOptions,
    locationPrinterOptions,
    scanProgressLabel,
    scanProgressWidth,
    printerStatusTone,
    refreshPrinters,
    savePrinter,
    handlePrinterSelectionChanged,
    populatePrinterForm,
    resetPrinterForm,
    startCreatePrinter,
    editPrinter,
    isMaskedAccessCode,
    toggleAccessCodeVisibility,
    scanDevices,
    connectPrinter,
    disconnectPrinter,
    deletePrinterConfig,
    openPrinterDashboard,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePrintersStore, import.meta.hot));
}

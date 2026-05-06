import { computed } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { formatCell, formatUnit, numeric } from "../api";
import { slotChangeKinds } from "../app/navigation";
import {
  filamentAmsRemainingLabel,
  filamentAmsRemainingWeight,
  filamentColor,
  filamentInventoryKg,
  filamentKg,
  filamentRemainPercent,
  filamentSpoolRemainingLabel,
  filamentSpoolRemainingWeight,
  filamentWeight,
  normalizeFilamentHex,
  remainLabel,
  remainPercent,
} from "../app/filamentMetrics";
import { useI18nStore } from "./i18n";

export const usePresentationStore = defineStore("presentation", () => {
  const i18nStore = useI18nStore();
  const { locale } = storeToRefs(i18nStore);
  const { t } = i18nStore;

  const localeOptions = computed(() => [
    { label: "简体中文", value: "zh-CN" },
    { label: "English", value: "en-US" },
  ]);

  function firstText(...values: unknown[]): string {
    for (const value of values) {
      if (value === null || value === undefined) continue;
      const text = String(value).trim();
      if (text) return text;
    }
    return "";
  }


  function record(value: unknown): Record<string, any> {
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, any>) : {};
  }


  function arrayOfRecord(value: unknown): Record<string, any>[] {
    return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
  }


  function entries(value: Record<string, any>) {
    return Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== "");
  }


  function fieldLabel(key: string) {
    const normalized = key.split(".").pop() || key;
    return t(`fields.${key}`) !== `fields.${key}`
      ? t(`fields.${key}`)
      : t(`fields.${normalized}`) !== `fields.${normalized}`
        ? t(`fields.${normalized}`)
        : key;
  }


  function valueLabel(value: unknown) {
    if (typeof value !== "string") return formatCell(value);
    return t(`values.${value}`) !== `values.${value}` ? t(`values.${value}`) : value;
  }


  function displayCell(value: unknown): string {
    if (typeof value === "boolean") return boolLabel(value);
    if (typeof value === "string") return valueLabel(value);
    return formatCell(value);
  }


  function optionalNumber(value: unknown): number | null {
    return numeric(value);
  }


  function softCell(value: unknown): string {
    const text = formatCell(value);
    return text === "—" ? "--" : text;
  }


  function maskSerial(value: unknown) {
    const text = String(value || "");
    if (!text) return "--";
    if (text.length <= 6) return "****";
    return `${text.slice(0, 3)}****${text.slice(-3)}`;
  }


  function boolLabel(value: unknown): string {
    if (value === true) return t("common.on");
    if (value === false) return t("common.off");
    if (typeof value === "string") return valueLabel(value);
    return formatCell(value);
  }


  function statusTone(value: unknown) {
    if (value === true) return "on";
    if (value === false) return "off";
    const text = String(value ?? "").trim().toLowerCase();
    if (!text) return "";
    if (["enable", "enabled", "on", "open", "opened", "true", "yes", "received", "开启", "打开", "已收到"].includes(text)) return "on";
    if (["disable", "disabled", "off", "closed", "close", "false", "no", "missing", "关闭", "缺失"].includes(text)) return "off";
    return "";
  }


  function percent(value: unknown, fallback = 0) {
    const parsed = numeric(value);
    if (parsed === null) return fallback;
    return Math.max(0, Math.min(100, parsed));
  }


  function temperaturePercent(current: unknown, target: unknown) {
    const currentValue = numeric(current) || 0;
    const targetValue = numeric(target) || 280;
    return percent((currentValue / Math.max(targetValue, 1)) * 100);
  }


  function formatBytes(value: number) {
    if (!value) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let size = value;
    let index = 0;
    while (size >= 1024 && index < units.length - 1) {
      size /= 1024;
      index += 1;
    }
    return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }


  function formatDurationMinutes(value: unknown) {
    const minutes = numeric(value);
    if (minutes === null || minutes < 0) return "";
    const rounded = Math.round(minutes);
    const hours = Math.floor(rounded / 60);
    const rest = rounded % 60;
    if (locale.value === "zh-CN") {
      if (hours > 0 && rest > 0) return `${hours}小时 ${rest}分钟`;
      if (hours > 0) return `${hours}小时`;
      return `${rest}分钟`;
    }
    if (hours > 0 && rest > 0) return `${hours}h ${rest}m`;
    if (hours > 0) return `${hours}h`;
    return `${rest}m`;
  }


  function formatDurationSeconds(value: unknown) {
    const seconds = numeric(value);
    if (seconds === null) return "--";
    const rounded = Math.max(0, Math.round(seconds));
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    if (locale.value === "zh-CN") {
      if (hours) return `${hours}小时 ${minutes}分钟`;
      return `${minutes}分钟`;
    }
    if (hours) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  }


  function unitLabel(value: unknown) {
    if (value === null || value === undefined || value === "") return "";
    return formatUnit(value);
  }


  function splitCsv(value: string) {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }


  function inputValue(event: Event) {
    return event.target instanceof HTMLInputElement ? event.target.value : "";
  }


  function checkboxChecked(event: Event) {
    return event.target instanceof HTMLInputElement ? event.target.checked : false;
  }


  function percentageLabel(value: unknown) {
    const parsed = numeric(value);
    if (parsed === null) return "--";
    return `${Math.round(parsed * 100)}%`;
  }


  function delay(ms: number) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }


  return {
    filamentAmsRemainingLabel,
    filamentAmsRemainingWeight,
    filamentColor,
    filamentInventoryKg,
    filamentKg,
    filamentRemainPercent,
    filamentSpoolRemainingLabel,
    filamentSpoolRemainingWeight,
    filamentWeight,
    formatCell,
    formatUnit,
    localeOptions,
    numeric,
    normalizeFilamentHex,
    remainLabel,
    remainPercent,
    slotChangeKinds,
    firstText,
    record,
    arrayOfRecord,
    entries,
    fieldLabel,
    valueLabel,
    displayCell,
    optionalNumber,
    softCell,
    maskSerial,
    boolLabel,
    statusTone,
    percent,
    temperaturePercent,
    formatBytes,
    formatDurationMinutes,
    formatDurationSeconds,
    unitLabel,
    splitCsv,
    inputValue,
    checkboxChecked,
    percentageLabel,
    delay,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePresentationStore, import.meta.hot));
}

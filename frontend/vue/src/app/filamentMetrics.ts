import { numeric } from "../api";

type FilamentRecord = Record<string, any>;

export function normalizeFilamentHex(value: unknown): string | null {
  const text = String(value || "")
    .trim()
    .replace(/^#/, "")
    .replace(/[\s_-]/g, "")
    .toUpperCase();
  const compact = text.length === 8 ? text.slice(0, 6) : text;
  return /^[0-9A-F]{6}$/.test(compact) ? compact : null;
}

export function filamentWeight(value: unknown): string {
  const parsed = numeric(value);
  return parsed === null ? "—" : `${Math.round(parsed)} g`;
}

export function filamentKg(value: unknown): string {
  const parsed = numeric(value);
  if (parsed === null) return "—";
  return `${(parsed / 1000).toFixed(parsed >= 10000 ? 1 : 2)} kg`;
}

export function filamentInventoryKg(value: unknown): string {
  const parsed = numeric(value);
  if (parsed === null) return "—";
  return `${(parsed / 1000).toFixed(2)} kg`;
}

export function filamentRemainPercent(spool: FilamentRecord | null | undefined): string {
  if (!spool) return "—";
  if (spool.last_ams_remain_percent !== null && spool.last_ams_remain_percent !== undefined) {
    return `${spool.last_ams_remain_percent}%`;
  }
  const remaining = numeric(spool.actual_weight_g ?? spool.current_remaining_g);
  const initial = numeric(spool.nominal_weight_g ?? spool.initial_net_weight_g);
  if (remaining === null || initial === null || initial <= 0) return "—";
  return `${Math.round((remaining / initial) * 100)}%`;
}

export function filamentSpoolRemainingWeight(spool: FilamentRecord | null | undefined): number | null {
  if (!spool) return null;
  const measured = numeric(spool.actual_weight_g ?? spool.current_remaining_g);
  if (measured !== null && measured >= 0) return measured;
  const remain = numeric(spool.last_ams_remain_percent);
  const nominal = numeric(spool.nominal_weight_g ?? spool.initial_net_weight_g);
  if (remain === null || remain < 0 || nominal === null || nominal <= 0) return null;
  return (nominal * remain) / 100;
}

export function filamentSpoolRemainingLabel(spool: FilamentRecord | null | undefined): string {
  const percent = filamentRemainPercent(spool);
  const weight = filamentSpoolRemainingWeight(spool);
  if (weight === null) return percent;
  return `${percent} / ${Math.round(weight)} g`;
}

export function filamentAmsRemainingWeight(
  slot: FilamentRecord,
  spool: FilamentRecord | null | undefined,
): number | null {
  const reported = [
    slot.remaining_weight_g,
    slot.remain_weight_g,
    slot.remain_g,
    slot.tray_remaining_weight_g,
    slot.raw?.remaining_weight_g,
    slot.raw?.remain_weight_g,
    slot.raw?.remain_g,
    slot.raw?.tray_remaining_weight_g,
    slot.raw?.remaining_weight,
    slot.raw?.remain_weight,
    slot.raw?.tray_remaining_weight,
  ].map((value) => numeric(value)).find((value) => value !== null && value >= 0);
  if (reported !== undefined) return reported;
  const remain = numeric(slot.remain);
  const nominal = numeric(spool?.nominal_weight_g ?? spool?.initial_net_weight_g);
  if (remain === null || remain < 0 || nominal === null || nominal <= 0) return null;
  return (nominal * remain) / 100;
}

export function filamentAmsRemainingLabel(
  slot: FilamentRecord,
  spool: FilamentRecord | null | undefined,
): string {
  const remain = numeric(slot.remain);
  const percent = remain !== null && remain >= 0 ? `${Math.round(remain)}%` : "—";
  const weight = filamentAmsRemainingWeight(slot, spool);
  if (weight === null) return percent;
  return `${percent} / ${Math.round(weight)} g`;
}

export function remainPercent(value: unknown) {
  const parsed = numeric(value);
  if (parsed === null || parsed < 0) return 0;
  return Math.max(0, Math.min(100, parsed));
}

export function remainLabel(value: unknown) {
  const parsed = numeric(value);
  if (parsed === null || parsed < 0) return "--";
  return `${Math.round(parsed)}%`;
}

export function filamentColor(value: unknown) {
  const hex = normalizeFilamentHex(value);
  return hex ? `#${hex}` : "#d7dce2";
}

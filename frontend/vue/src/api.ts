export const API_BASE =
  (import.meta.env.VITE_FILAMENT_MANAGER_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";

export type ApiRecord = Record<string, unknown>;

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const body = parseApiBody(text, response.headers.get("content-type"));
  if (!response.ok) {
    const detail = extractApiError(body, text);
    throw new Error(`HTTP ${response.status}: ${detail || response.statusText}`);
  }
  return body as T;
}

function parseApiBody(text: string, contentType: string | null): unknown {
  if (!text) return null;
  if (!contentType?.toLowerCase().includes("json")) return text;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractApiError(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object") {
      const data = detail as Record<string, any>;
      if (data.code === "duplicate_filament_sku") {
        const existing = data.existing_sku || {};
        const label = existing.label || [existing.brand_name, existing.material, existing.series, existing.color_name || existing.color_hex]
          .filter(Boolean)
          .join(" · ");
        return `重复的耗材 SKU：已存在 SKU #${existing.id || "?"}${label ? `（${label}）` : ""}。请编辑已有 SKU 或调整它的未开封库存，或修改颜色、克重、线径等信息后再保存。`;
      }
      if (typeof data.message === "string") return data.message;
    }
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  if (typeof body === "string") return body;
  if (body !== null && body !== undefined) return JSON.stringify(body);
  return fallback;
}

const ISO_DATE_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$/;

export function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "string") {
    const formattedDate = formatDateTime(value);
    if (formattedDate) return formattedDate;
  }
  return String(value);
}

export function formatUnit(value: unknown): string {
  if (value === "celsius") return "°C";
  if (value === "percent") return "%";
  return formatCell(value);
}

function formatDateTime(value: string): string | null {
  const parsed = parseApiDateTime(value);
  if (parsed) return formatDate(parsed);
  return null;
}

export function parseApiDateTime(value: string): Date | null {
  const match = ISO_DATE_TIME_RE.exec(value);
  if (!match) return null;
  const [, year, month, day, hour, minute, second = "00", timezone] = match;
  const zone = timezone || "Z";
  const parsed = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}${zone}`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDate(value: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: localTimeZone(),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  const part = (type: string) => parts.find((item) => item.type === type)?.value || "00";
  const year = part("year");
  const month = part("month");
  const day = part("day");
  const hour = part("hour");
  const minute = part("minute");
  const second = part("second");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

export function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

export function numeric(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function boolLabel(value: unknown): string {
  if (value === true) return "开启";
  if (value === false) return "关闭";
  return formatCell(value);
}

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
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = body?.detail ? JSON.stringify(body.detail) : text;
    throw new Error(`HTTP ${response.status}: ${detail || response.statusText}`);
  }
  return body as T;
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

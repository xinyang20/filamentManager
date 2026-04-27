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
  const match = ISO_DATE_TIME_RE.exec(value);
  if (!match) return null;
  const [, year, month, day, hour, minute, second = "00", timezone] = match;
  if (timezone) {
    const parsed = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}${timezone}`);
    if (!Number.isNaN(parsed.getTime())) return formatDate(parsed);
  }
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function formatDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  const second = String(value.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
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

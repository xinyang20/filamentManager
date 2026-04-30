import { describe, expect, it, vi } from "vitest";

import { apiRequest, boolLabel, formatCell, formatUnit, numeric, parseApiDateTime } from "./api";

function response(body: unknown, init: ResponseInit = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return Promise.resolve(
    new Response(text, {
      status: 200,
      headers: { "Content-Type": typeof body === "string" ? "text/plain" : "application/json" },
      ...init,
    }),
  );
}

describe("api utilities", () => {
  it("sends JSON requests through the configured API base", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(await response({ ok: true }));

    await expect(apiRequest("/status", { method: "POST", headers: { "X-Test": "1" }, body: "{}" })).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/status",
      expect.objectContaining({
        method: "POST",
        body: "{}",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-Test": "1",
        }),
      }),
    );
  });

  it("preserves plain text responses and reports structured API errors", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(await response("ok"))
      .mockResolvedValueOnce(
        await response(
          {
            detail: {
              code: "duplicate_filament_sku",
              existing_sku: {
                id: 7,
                brand_name: "Bambu",
                material: "PLA",
                series: "Matte",
                color_name: "Green",
              },
            },
          },
          { status: 409, statusText: "Conflict" },
        ),
      );

    await expect(apiRequest("/plain")).resolves.toBe("ok");
    await expect(apiRequest("/filament/skus")).rejects.toThrow("重复的耗材 SKU：已存在 SKU #7");
  });

  it("formats cells, units, booleans and numbers defensively", () => {
    expect(formatCell(null)).toBe("—");
    expect(formatCell({ a: 1 })).toBe(JSON.stringify({ a: 1 }));
    expect(formatUnit("celsius")).toBe("°C");
    expect(formatUnit("percent")).toBe("%");
    expect(boolLabel(true)).toBe("开启");
    expect(boolLabel(false)).toBe("关闭");
    expect(numeric("12.5")).toBe(12.5);
    expect(numeric("")).toBeNull();
  });

  it("parses API date-times without accepting unrelated strings", () => {
    expect(parseApiDateTime("2026-04-30T10:00:00Z")?.toISOString()).toBe("2026-04-30T10:00:00.000Z");
    expect(parseApiDateTime("not-a-date")).toBeNull();
  });
});

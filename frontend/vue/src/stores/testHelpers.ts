import { createPinia, setActivePinia } from "pinia";
import { vi } from "vitest";

export function resetStoreTest() {
  vi.restoreAllMocks();
  setActivePinia(createPinia());
  window.localStorage.clear();
}

export function jsonResponse(data: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

export function mockApi(handler: (path: string, init: RequestInit) => unknown | Promise<unknown>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const path = String(input).replace(/^\/api/, "");
    const result = await handler(path, init);
    return jsonResponse(result);
  });
}

export function requestPaths(fetchMock: { mock: { calls: Array<[RequestInfo | URL, RequestInit?]> } }) {
  return fetchMock.mock.calls.map(([input]) => String(input).replace(/^\/api/, ""));
}

export const printerFixture = {
  id: 1,
  name: "P1",
  host: "127.0.0.1",
  port: 8883,
  serial: "SN001",
  access_code: "12345678",
  tls_enabled: true,
  certificate_verify: false,
  enabled: true,
  connection_status: "connected",
};

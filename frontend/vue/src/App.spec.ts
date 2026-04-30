import { mount, flushPromises } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import App from "./App.vue";

function jsonResponse(data: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function mockApi() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/printers")) return jsonResponse([]);
    if (url.endsWith("/api/dashboard/summary")) return jsonResponse([]);
    return jsonResponse(null);
  });
}

describe("App", () => {
  it("bootstraps the overview without a real backend", async () => {
    const fetchMock = mockApi();
    const wrapper = mount(App);

    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/dashboard/summary",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) }),
    );
    expect(wrapper.text()).toContain("FilamentManager");
    expect(wrapper.text()).toContain("还没有打印机");

    wrapper.unmount();
  });

  it("switches views through the sidebar", async () => {
    mockApi();
    const wrapper = mount(App);

    await flushPromises();
    await wrapper.findAll(".nav-item").find((item) => item.text().includes("打印机配置"))?.trigger("click");
    await flushPromises();

    expect(window.localStorage.getItem("filamentManager.activeView")).toBe("printers");
    expect(wrapper.get("h1").text()).toBe("打印机配置");

    wrapper.unmount();
  });
});

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppSelect from "./AppSelect.vue";

const options = [
  { label: "总览", value: "overview" },
  { label: "设备大屏", value: "dashboard" },
  { label: "禁用项", value: "disabled", disabled: true },
];

describe("AppSelect", () => {
  it("renders a placeholder and opens the option list", async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: null,
        options,
        placeholder: "请选择",
      },
      attachTo: document.body,
    });

    expect(wrapper.get(".app-select-button").text()).toContain("请选择");

    await wrapper.get(".app-select-button").trigger("click");
    expect(wrapper.find(".app-select-menu").exists()).toBe(true);
    wrapper.unmount();
  });

  it("renders the selected option and emits updates when an option is clicked", async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: "overview",
        options,
      },
    });

    expect(wrapper.get(".app-select-button").text()).toContain("总览");

    await wrapper.get(".app-select-button").trigger("click");
    await wrapper.findAll(".app-select-option")[1].trigger("click");

    expect(wrapper.emitted("update:modelValue")).toEqual([["dashboard"]]);
    expect(wrapper.emitted("change")).toEqual([["dashboard"]]);
    expect(wrapper.get(".app-select-button").attributes("aria-expanded")).toBe("false");
  });

  it("keeps disabled options from being selected", async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: "overview",
        options,
      },
    });

    await wrapper.get(".app-select-button").trigger("click");
    await wrapper.findAll(".app-select-option")[2].trigger("click");

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    expect(wrapper.find(".app-select-menu").exists()).toBe(true);
  });

  it("supports keyboard selection", async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: "overview",
        options,
      },
      attachTo: document.body,
    });

    const button = wrapper.get(".app-select-button");
    await button.trigger("keydown", { key: "ArrowDown" });
    await button.trigger("keydown", { key: "ArrowDown" });
    await button.trigger("keydown", { key: "Enter" });

    expect(wrapper.emitted("update:modelValue")).toEqual([["dashboard"]]);
  });

  it("does not open or emit when disabled", async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: "overview",
        options,
        disabled: true,
      },
    });

    await wrapper.get(".app-select-button").trigger("click");
    await wrapper.get(".app-select-button").trigger("keydown", { key: "ArrowDown" });

    expect(wrapper.find(".app-select-menu").exists()).toBe(false);
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });
});

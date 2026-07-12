// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { Check, Save } from "lucide-vue-next";
import { afterEach, describe, expect, it, vi } from "vitest";
import { h, nextTick } from "vue";
import UiButton from "./UiButton.vue";
import UiIconButton from "./UiIconButton.vue";

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("UiButton", () => {
  it("renders stable state layers and exposes busy semantics", async () => {
    const wrapper = mount(UiButton, {
      props: { variant: "primary", loadingLabel: "保存中", successLabel: "已保存" },
      slots: { default: () => "保存 Workflow", icon: () => h(Save) },
    });

    expect(wrapper.classes()).toContain("is-primary");
    expect(wrapper.attributes("aria-busy")).toBeUndefined();
    expect(wrapper.text()).toContain("保存 Workflow");
    expect(wrapper.text()).toContain("保存中");
    expect(wrapper.text()).toContain("已保存");

    await wrapper.setProps({ state: "loading" });
    expect(wrapper.attributes("aria-busy")).toBe("true");
    expect(wrapper.attributes("disabled")).toBeDefined();

    await wrapper.setProps({ state: "success" });
    expect(wrapper.attributes("data-state")).toBe("success");
    expect(wrapper.find(".ui-button-check").exists()).toBe(true);
  });

  it("does not emit clicks while disabled or reporting progress", async () => {
    const wrapper = mount(UiButton, { props: { state: "loading" }, slots: { default: "保存" } });
    await wrapper.trigger("click");
    expect(wrapper.emitted("click")).toBeUndefined();

    await wrapper.setProps({ state: "idle", disabled: false });
    await wrapper.trigger("click");
    expect(wrapper.emitted("click")).toHaveLength(1);
  });

  it("keeps a disabled button focusable when it has an explanation", async () => {
    const wrapper = mount(UiButton, {
      props: { disabled: true, disabledReason: "请先保存 Workflow" },
      slots: { default: "同步" },
    });

    expect(wrapper.attributes("disabled")).toBeUndefined();
    expect(wrapper.attributes("aria-disabled")).toBe("true");
    expect(wrapper.attributes("title")).toBe("请先保存 Workflow");
    await wrapper.trigger("click");
    expect(wrapper.emitted("click")).toBeUndefined();
  });
});

describe("UiIconButton", () => {
  it("uses its label for accessibility and shows a delayed tooltip", async () => {
    vi.useFakeTimers();
    const wrapper = mount(UiIconButton, {
      attachTo: document.body,
      props: { label: "保存 Workflow" },
      slots: { default: () => h(Check) },
    });

    expect(wrapper.get("button").attributes("aria-label")).toBe("保存 Workflow");
    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("click")).toHaveLength(1);
    await wrapper.get(".ui-tooltip-trigger").trigger("mouseenter");
    await vi.advanceTimersByTimeAsync(349);
    expect(document.body.querySelector("[role=tooltip]")).toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    await nextTick();
    expect(document.body.querySelector("[role=tooltip]")?.textContent).toBe("保存 Workflow");

    await wrapper.get(".ui-tooltip-trigger").trigger("keydown", { key: "Escape" });
    await nextTick();
    expect(document.body.querySelector("[role=tooltip]")).toBeNull();
  });

  it("explains a disabled icon button from keyboard focus", async () => {
    vi.useFakeTimers();
    const wrapper = mount(UiIconButton, {
      attachTo: document.body,
      props: { label: "同步", disabled: true, disabledReason: "请先保存 Workflow" },
      slots: { default: () => h(Check) },
    });

    await wrapper.get("button").trigger("focusin");
    await vi.advanceTimersByTimeAsync(350);
    await nextTick();
    expect(document.body.querySelector("[role=tooltip]")?.textContent).toBe("请先保存 Workflow");
  });
});

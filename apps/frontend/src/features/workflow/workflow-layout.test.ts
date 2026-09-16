// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { describe, expect, it } from "vitest";
import { useWorkflowLayout, workflowInitialLeftWidth, workflowInitialRightWidth } from "./useWorkflowLayout";

describe("Workflow desktop layout", () => {
  it("collapses tracks without changing remembered panel widths", () => {
    const { wrapper, layout } = mountLayout();
    const expanded = layout.gridStyle.value.gridTemplateColumns;

    layout.toggle("left");
    expect(layout.gridStyle.value.gridTemplateColumns).toContain("0px 20px");
    layout.toggle("left");
    expect(layout.gridStyle.value.gridTemplateColumns).toBe(expanded);

    layout.setGraphExpanded(true);
    expect(layout.graphExpanded.value).toBe(true);
    expect(layout.leftCollapsed.value).toBe(false);
    expect(layout.gridStyle.value.gridTemplateColumns).toBe(expanded);
    layout.setGraphExpanded(false);
    expect(layout.graphExpanded.value).toBe(false);
    wrapper.unmount();
  });

  it("clamps resized panels and removes global listeners when unmounted", () => {
    const { wrapper, layout } = mountLayout();
    layout.startResize("left", pointerEvent("pointerdown", 100));
    expect(document.body.classList.contains("workflow-resizing")).toBe(true);

    window.dispatchEvent(pointerEvent("pointermove", 1000));
    expect(layout.gridStyle.value.gridTemplateColumns).toContain("360px 6px");
    const finalColumns = layout.gridStyle.value.gridTemplateColumns;

    wrapper.unmount();
    expect(document.body.classList.contains("workflow-resizing")).toBe(false);
    window.dispatchEvent(pointerEvent("pointermove", -1000));
    expect(layout.gridStyle.value.gridTemplateColumns).toBe(finalColumns);
  });

  it("在 1179/1180 切换面板并恢复桌面状态", () => {
    const { wrapper, layout } = mountLayout();
    layout.toggle("left");
    const desktop = layout.gridStyle.value.gridTemplateColumns;
    window.innerWidth = 1179;
    window.dispatchEvent(new Event("resize"));
    expect(layout.compact.value).toBe(true);
    expect(layout.activePanel.value).toBe("editor");
    layout.showPanel("preview");
    expect(layout.activePanel.value).toBe("preview");
    expect(layout.gridStyle.value.gridTemplateColumns).toBe("minmax(0, 1fr)");
    window.innerWidth = 1180;
    window.dispatchEvent(new Event("resize"));
    expect(layout.compact.value).toBe(false);
    expect(layout.gridStyle.value.gridTemplateColumns).toBe(desktop);
    expect(layout.leftCollapsed.value).toBe(true);
    wrapper.unmount();
  });

  it("gives the editor more room on compact desktop workbenches", () => {
    expect(workflowInitialRightWidth(1280)).toBe(360);
    expect(workflowInitialRightWidth(1600)).toBe(440);
    expect(workflowInitialLeftWidth(1280)).toBe(232);
    expect(workflowInitialLeftWidth(1600)).toBe(252);
  });
});

function mountLayout() {
  Object.defineProperty(window, "innerWidth", { value: 1600, configurable: true, writable: true });
  let layout: ReturnType<typeof useWorkflowLayout> | undefined;
  const Host = defineComponent({
    setup() {
      layout = useWorkflowLayout();
      return () => h("div");
    },
  });
  const wrapper = mount(Host);
  return { wrapper, layout: layout! };
}

function pointerEvent(type: string, clientX: number): PointerEvent {
  return new MouseEvent(type, { clientX }) as PointerEvent;
}

// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { PublishRecord, PublishRecordStatus } from "../../types";
import AdminPublishTab from "./AdminPublishTab.vue";

function record(id: string, status: PublishRecordStatus, metadata: Record<string, unknown> = {}): PublishRecord {
  return {
    id,
    skill_id: "skill-1",
    skill_version_id: "version-1",
    review_request_id: "review-1",
    publish_target_id: "target-1",
    status,
    check_snapshot: [],
    metadata,
    created_by: "owner",
    skill: { id: "skill-1", slug: "demo" } as PublishRecord["skill"],
    skill_version: { id: "version-1", version: "0.0.2" } as PublishRecord["skill_version"],
    publish_target: { id: "target-1", name: "云析" } as PublishRecord["publish_target"],
  };
}

describe("AdminPublishTab", () => {
  it("renders queued, releasing and uncertain failure states with valid actions", async () => {
    const wrapper = mount(AdminPublishTab, {
      props: {
        records: [
          record("pending", "pending_confirmation"),
          record("queued", "queued"),
          record("releasing", "releasing"),
          record("failed", "failed", { external_state: "unknown", release_error: "lease expired" }),
        ],
      },
    });

    await wrapper.get(".admin-publish-group-toggle").trigger("click");

    expect(wrapper.text()).toContain("排队中");
    expect(wrapper.text()).toContain("发布中");
    expect(wrapper.text()).toContain("外部状态未知，请核对发布目标后再重试。");
    expect(wrapper.findAll("button").filter((button) => button.text() === "取消")).toHaveLength(2);
    expect(wrapper.findAll("button").some((button) => button.text() === "核对后重试")).toBe(true);
    expect(wrapper.findAll("button").some((button) => button.text() === "确认发布")).toBe(true);
  });

  it("emits retry only from a failed record", async () => {
    const failed = record("failed", "failed", { external_state: "unknown" });
    const wrapper = mount(AdminPublishTab, { props: { records: [failed] } });
    await wrapper.get(".admin-publish-group-toggle").trigger("click");
    await wrapper.findAll("button").find((button) => button.text() === "核对后重试")?.trigger("click");

    expect(wrapper.emitted("retryRecord")).toEqual([[failed]]);
  });
});

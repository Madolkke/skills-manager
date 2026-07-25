// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import Tabs from "../components/Tabs.vue";
import { api } from "../lib/api";
import type { SkillDetail, SkillRecord, SkillSummary, SkillVersion } from "../types";
import OverviewPage from "./OverviewPage.vue";
import HubSkillCard from "./hub/HubSkillCard.vue";

describe("Skill display copy", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the current Skill description instead of the version change summary", async () => {
    const detail = skillDetail("Review authorization boundaries.");
    mockOverviewApi(detail.skill);

    const card = mount(HubSkillCard, { props: { item: skillSummary(detail) } });
    const overview = mount(OverviewPage, { props: { skill: detail } });
    await flushPromises();

    expect(card.get(".card-body > p").text()).toBe("Review authorization boundaries.");
    expect(overview.get(".skill-title-copy > p").text()).toBe("Review authorization boundaries.");

    card.unmount();
    overview.unmount();
  });

  it("shows an explicit fallback when the current version has no description", async () => {
    const detail = skillDetail(null);
    mockOverviewApi(detail.skill);
    const card = mount(HubSkillCard, { props: { item: skillSummary(detail) } });
    const overview = mount(OverviewPage, { props: { skill: detail } });
    await flushPromises();

    expect(card.get(".card-body > p").text()).toBe("尚未填写 Skill 描述。");
    expect(overview.get(".skill-title-copy > p").text()).toBe("尚未填写 Skill 描述。");

    card.unmount();
    overview.unmount();
  });

  it("labels the history tab as evaluation history", () => {
    const tabs = mount(Tabs, { props: { active: "history" } });

    expect(tabs.get('[role="tab"][aria-selected="true"]').text()).toBe("测评历史");
  });
});

function skillDetail(description: string | null): SkillDetail {
  const skill: SkillRecord = {
    id: "skill-1",
    slug: "access-reviewer",
    owner_ref: "owner",
    current_version_id: "version-1",
    lifecycle_status: "active",
    tags: [],
  };
  const version: SkillVersion = {
    id: "version-1",
    skill_id: skill.id,
    version_number: 1,
    version: "0.0.1",
    content_ref: { kind: "artifact", locator: "artifact:artifact-1", digest: "digest-1" },
    content_digest: "digest-1",
    description,
    change_summary: "Internal version change summary.",
    created_by: "owner",
    bundle_files: [],
  };
  return {
    skill,
    summary: { skill, current_version: version, primary_eval_set: null, latest_accepted_eval_run: null },
    versions: [version],
    eval_sets: [],
    latest_eval_runs: [],
    role_assignments: [],
    audit_events: [],
    capabilities: null,
    workflow: null,
  };
}

function skillSummary(detail: SkillDetail): SkillSummary {
  return { skill: detail.skill, summary: detail.summary, workflow: detail.workflow };
}

function mockOverviewApi(skill: SkillRecord): void {
  vi.spyOn(api, "listSkillReviews").mockResolvedValue([]);
  vi.spyOn(api, "getSkillPublishOverview").mockResolvedValue({
    skill,
    versions: [],
    publish_targets: [],
    publish_records: [],
  });
}

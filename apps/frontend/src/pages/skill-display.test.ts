// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import DropdownSelect from "../components/DropdownSelect.vue";
import TaskCenterPanel from "../components/TaskCenterPanel.vue";
import Tabs from "../components/Tabs.vue";
import { api } from "../lib/api";
import { readRoute, replaceRoute, reviewShareUrl } from "../lib/navigation";
import type { SkillDetail, SkillRecord, SkillSummary, SkillVersion } from "../types";
import HubPage from "./HubPage.vue";
import OverviewPage from "./OverviewPage.vue";
import HubSkillCard from "./hub/HubSkillCard.vue";
import { filterSkills } from "./hub/hubFilters";

describe("Skill display copy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
  });

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
    expect(card.get(".card-tag-list").text()).toBe("未设置 Tag");
    expect(overview.get(".skill-title-copy > p").text()).toBe("尚未填写 Skill 描述。");

    card.unmount();
    overview.unmount();
  });

  it("keeps the slug primary and uses the Chinese name as secondary searchable text", async () => {
    const detail = skillDetail("Review authorization boundaries.");
    detail.skill.display_name = "访问权限评审";
    mockOverviewApi(detail.skill);

    const card = mount(HubSkillCard, { props: { item: skillSummary(detail) } });
    const overview = mount(OverviewPage, { props: { skill: detail } });
    await flushPromises();

    expect(card.get("h3").text()).toBe("access-reviewer");
    expect(card.get(".skill-card-title-copy small").text()).toBe("访问权限评审");
    expect(overview.get("h1").text()).toBe("access-reviewer");
    expect(overview.get(".skill-display-name").text()).toBe("访问权限评审");
    expect(filterSkills([skillSummary(detail)], {
      query: "权限评审",
      filter: "all",
      actor: "owner",
      selectedTags: [],
      tagGroups: [],
    })).toHaveLength(1);

    card.unmount();
    overview.unmount();
  });

  it("shows current-version review and publish status badges", () => {
    const detail = skillDetail("Review authorization boundaries.");
    const item = skillSummary(detail);
    item.summary.review_status = "open";
    item.summary.publish_status = "released";

    const card = mount(HubSkillCard, { props: { item } });

    expect(card.text()).toContain("评审中");
    expect(card.text()).toContain("已发布");
    expect(card.get('[aria-label="评审状态：评审中"]').text()).toBe("评审中");
    expect(card.get('[aria-label="发布状态：已发布"]').text()).toBe("已发布");
  });

  it("preserves a selected review in share links and routes", () => {
    window.history.replaceState({}, "", "/skills?section=skills&skill=skill-1&tab=reviews&review=review-9");

    expect(readRoute()).toMatchObject({ tab: "reviews", selectedReviewId: "review-9" });
    expect(reviewShareUrl("skill-1", "review-9")).toContain("section=skills&skill=skill-1&tab=reviews&review=review-9");
  });

  it("labels the history tab as evaluation history", () => {
    const tabs = mount(Tabs, { props: { active: "history" } });

    expect(tabs.get('[role="tab"][aria-selected="true"]').text()).toBe("测评历史");
  });

  it("replaces evaluation metrics with the first three valid Skill tags", () => {
    const detail = skillDetail("Review authorization boundaries.");
    detail.skill.tags = [
      skillTag("domain", "领域", "network", "网络"),
      skillTag("vendor", "厂商", "cisco", "Cisco"),
      skillTag("stale", "失效分组", "legacy", "旧值", false),
      skillTag("level", "难度", "advanced", "高级"),
      skillTag("protocol", "协议", "bgp", "BGP"),
      skillTag("region", "区域", "global", "全球"),
    ];
    const item = skillSummary(detail);
    item.workflow = { id: "workflow-1" } as never;

    const card = mount(HubSkillCard, { props: { item } });
    const labels = card.findAll(".card-tag-list .tag-chip-label").map((chip) => chip.text());
    const overflow = card.get(".tag-overflow");

    expect(labels).toEqual(["领域: 网络", "厂商: Cisco", "难度: 高级"]);
    expect(overflow.text()).toBe("+2");
    expect(overflow.attributes("title")).toBe("协议: BGP、区域: 全球");
    expect(overflow.attributes("aria-label")).toBe("还有 2 个 Tag：协议: BGP、区域: 全球");
    expect(card.text()).not.toContain("失效分组");
    expect(card.text()).not.toContain("验证分数");
    expect(card.text()).not.toContain("测评集");
    expect(card.text()).not.toContain("未测");
    expect(card.find(".score-chip").exists()).toBe(false);
    expect(card.find(".status-ring").exists()).toBe(false);
    expect(card.text()).toContain("当前版本0.0.1");
    expect(card.text()).toContain("Workflow");
  });

  it("keeps evaluation filters and score sorting in the enabled Hub toolbar", async () => {
    const detail = skillDetail("Review authorization boundaries.");
    vi.spyOn(api, "listTagGroups").mockResolvedValue([]);
    const hub = mount(HubPage, {
      props: { skills: [skillSummary(detail)], actor: "owner", loading: false, evaluationsVisible: true },
    });
    await flushPromises();

    expect(hub.text()).toContain("已验证");
    expect(hub.text()).toContain("未测");
    expect(hub.findComponent(DropdownSelect).props("options")).toContainEqual({ value: "score", label: "验证得分" });
  });

  it("hides evaluation-only content while preserving the rest of the Skill UI", async () => {
    const detail = skillDetail("Review authorization boundaries.");
    mockOverviewApi(detail.skill);
    vi.spyOn(api, "listTagGroups").mockResolvedValue([]);
    const tabs = mount(Tabs, { props: { active: "overview", evaluationsVisible: false } });
    const card = mount(HubSkillCard, { props: { item: skillSummary(detail) } });
    const overview = mount(OverviewPage, { props: { skill: detail, evaluationsVisible: false } });
    const hub = mount(HubPage, {
      props: { skills: [skillSummary(detail)], actor: "owner", loading: false, evaluationsVisible: false },
    });
    const taskCenter = mount(TaskCenterPanel, {
      props: { groups: [], badgeCount: 0, loading: false, error: "", evaluationsVisible: false },
    });
    await flushPromises();

    const visibleText = [tabs.text(), card.text(), overview.text(), hub.text(), taskCenter.text()].join(" ");
    for (const hiddenText of ["测评集", "测评历史", "验证分数", "已验证", "未测", "运行中测评"]) {
      expect(visibleText).not.toContain(hiddenText);
    }
    expect(visibleText).toContain("当前版本");
    expect(visibleText).toContain("Tag 过滤");
    expect(visibleText).toContain("评审");
    expect(visibleText).toContain("发布");

    tabs.unmount();
    card.unmount();
    overview.unmount();
    hub.unmount();
    taskCenter.unmount();
  });

  it("canonicalizes direct evaluation URLs to the Skill overview", () => {
    window.history.replaceState({}, "", "/skills?section=skills&skill=skill-1&tab=history&evalSet=set-1&case=case-1&run=run-1");

    const route = readRoute(false);
    expect(route).toMatchObject({
      section: "skills",
      skillId: "skill-1",
      tab: "overview",
      selectedEvalSetId: null,
      selectedCaseId: null,
      selectedRunId: null,
    });

    replaceRoute(route, false);
    expect(window.location.pathname).toBe("/skills");
    expect(window.location.search).toBe("?section=skills&skill=skill-1");
  });
});

function skillDetail(description: string | null): SkillDetail {
  const skill: SkillRecord = {
    id: "skill-1",
    slug: "access-reviewer",
    display_name: null,
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

function skillTag(groupId: string, groupName: string, value: string, valueName: string, pathValid = true) {
  return {
    group_id: groupId,
    group_display_name: groupName,
    value,
    value_display_name: valueName,
    path_valid: pathValid,
  };
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

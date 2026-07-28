// @vitest-environment jsdom

import { flushPromises, shallowMount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import type { SkillDetail } from "../types";
import VersionsPage from "./VersionsPage.vue";

const wrappers: VueWrapper[] = [];

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.restoreAllMocks();
});

describe("VersionsPage bundle actions", () => {
  it("下载当前版本并释放临时 URL", async () => {
    const bundle = new Blob(["bundle"], { type: "application/zip" });
    vi.spyOn(api, "downloadSkillBundle").mockResolvedValue(bundle);
    const createObjectURL = vi.fn(() => "blob:skill-bundle");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    let downloadedFilename = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function recordDownload(this: HTMLAnchorElement) {
      downloadedFilename = this.download;
    });
    const wrapper = mountPage();

    await button(wrapper, "下载 Skill").trigger("click");
    await flushPromises();

    expect(api.downloadSkillBundle).toHaveBeenCalledWith("version-2");
    expect(createObjectURL).toHaveBeenCalledWith(bundle);
    expect(downloadedFilename).toBe("router-check-0.2.0.zip");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:skill-bundle");
    expect(lastToast(wrapper)).toEqual({ tone: "success", message: "Skill 压缩包已开始下载。" });
  });

  it("显示下载错误并恢复按钮", async () => {
    vi.spyOn(api, "downloadSkillBundle").mockRejectedValue(new Error("下载连接已断开。"));
    const wrapper = mountPage();

    await button(wrapper, "下载 Skill").trigger("click");
    await flushPromises();

    expect(lastToast(wrapper)).toEqual({ tone: "danger", message: "下载连接已断开。" });
    expect(button(wrapper, "下载 Skill").attributes("disabled")).toBeUndefined();
  });

  it("快速发布当前版本并显示目标目录", async () => {
    vi.spyOn(api, "quickPublishSkillBundle").mockResolvedValue({ destination: "D:\\published\\router-check", file_count: 3 });
    const wrapper = mountPage();

    await button(wrapper, "快速发布").trigger("click");
    await flushPromises();

    expect(api.quickPublishSkillBundle).toHaveBeenCalledWith("version-2");
    expect(lastToast(wrapper)).toEqual({ tone: "success", message: "Skill 已发布至 D:\\published\\router-check。" });
  });

  it("显示快速发布错误并恢复按钮", async () => {
    vi.spyOn(api, "quickPublishSkillBundle").mockRejectedValue(new Error("目标目录不可写。"));
    const wrapper = mountPage();

    await button(wrapper, "快速发布").trigger("click");
    await flushPromises();

    expect(lastToast(wrapper)).toEqual({ tone: "danger", message: "目标目录不可写。" });
    expect(button(wrapper, "快速发布").attributes("disabled")).toBeUndefined();
  });
});

function mountPage(): VueWrapper {
  const wrapper = shallowMount(VersionsPage, {
    props: { skill: skillDetail(), selectedVersionId: "version-2", uploadOpen: false },
  });
  wrappers.push(wrapper);
  return wrapper;
}

function button(wrapper: VueWrapper, label: string) {
  const match = wrapper.findAll("button").find((item) => item.text().includes(label));
  if (!match) throw new Error(`找不到按钮：${label}`);
  return match;
}

function lastToast(wrapper: VueWrapper): unknown {
  return wrapper.emitted("toast")?.at(-1)?.[0];
}

function skillDetail(): SkillDetail {
  const versions = [
    {
      id: "version-1",
      skill_id: "skill-1",
      version_number: 1,
      version: "0.1.0",
      content_ref: { kind: "artifact" as const, locator: "artifact-1", digest: "digest-1" },
      content_digest: "digest-1",
      change_summary: "Initial",
      created_at: "2026-07-27T00:00:00Z",
      created_by: "owner",
      bundle_files: [],
    },
    {
      id: "version-2",
      skill_id: "skill-1",
      version_number: 2,
      version: "0.2.0",
      content_ref: { kind: "artifact" as const, locator: "artifact-2", digest: "digest-2" },
      content_digest: "digest-2",
      change_summary: "Current",
      created_at: "2026-07-28T00:00:00Z",
      created_by: "owner",
      bundle_files: [],
    },
  ];
  const skill = {
    id: "skill-1",
    slug: "router-check",
    display_name: null,
    owner_ref: "owner",
    current_version_id: "version-2",
    lifecycle_status: "active",
    tags: [],
  };
  return {
    skill,
    summary: { skill, current_version: versions[1]!, primary_eval_set: null, latest_accepted_eval_run: null },
    versions,
    eval_sets: [],
    latest_eval_runs: [],
    role_assignments: [],
    audit_events: [],
    capabilities: null,
    workflow: null,
  };
}

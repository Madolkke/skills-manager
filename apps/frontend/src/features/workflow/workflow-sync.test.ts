// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type {
  SkillDetail,
  WorkflowSkillGenerator,
  WorkflowSkillGeneratorCatalog,
  WorkflowSyncPreview,
  WorkflowSyncPreviewAction,
} from "../../types";
import WorkflowSyncModal from "./components/WorkflowSyncModal.vue";

const generators: WorkflowSkillGenerator[] = [
  { id: "builtin.single-file", version: "workflow-skill-v4", label: "单文件（兼容模式）", default: false, options_schema: {} },
  { id: "builtin.three-file", version: "2.0.0", label: "固定三文件", default: true, options_schema: {} },
  { id: "builtin.node-split", version: "2.0.0", label: "按节点拆分", default: false, options_schema: {} },
];

const wrappers: VueWrapper[] = [];

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.restoreAllMocks();
});

describe("Workflow sync preview", () => {
  it("uses the default Generator declared by the server", async () => {
    const previewSpy = installApiMocks(preview());
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get(".workflow-generator-segment.active").text()).toContain("固定三文件");
    expect(previewSpy).toHaveBeenCalledWith("skill-1", {
      expected_workflow_revision: 7,
      generator_id: "builtin.three-file",
      generator_options: {},
    });
    expect(wrapper.get(".workflow-skill-preview").text()).toContain("Workflow revision 7");
  });

  it("discards the old preview immediately when the Generator changes", async () => {
    const previewSpy = installApiMocks(preview());
    const wrapper = mountModal();
    await flushPromises();

    let resolveNodePreview!: (value: WorkflowSyncPreview) => void;
    previewSpy.mockReturnValueOnce(new Promise((resolve) => { resolveNodePreview = resolve; }));
    await wrapper.findAll(".workflow-generator-segment").find((button) => button.text().includes("按节点拆分"))!.trigger("click");

    expect(wrapper.find(".workflow-skill-preview").exists()).toBe(false);
    expect(wrapper.text()).toContain("正在生成 Skill Bundle 预览");
    resolveNodePreview(preview({ generator: generators[2], path: "references/index.md", digest: "node-preview" }));
    await flushPromises();

    expect(previewSpy).toHaveBeenLastCalledWith("skill-1", expect.objectContaining({ generator_id: "builtin.node-split" }));
    expect(wrapper.get(".workflow-skill-preview").text()).toContain("references/index.md");
  });

  it("submits Generator evidence only after explicit confirmation", async () => {
    installApiMocks(preview({ options: { normalized: true } }));
    const wrapper = mountModal();
    await flushPromises();

    const submit = wrapper.findAll("button").find((button) => button.text().includes("确认同步"))!;
    expect(submit.attributes("data-disabled")).toBe("true");
    await wrapper.get<HTMLInputElement>('.workflow-sync-confirmation input[type="checkbox"]').setValue(true);
    await submit.trigger("click");

    expect(wrapper.emitted("submit")?.at(-1)).toEqual([{
      version: "0.2.0",
      display_name: undefined,
      change_summary: "从 Workflow revision 7 同步。",
      expected_workflow_revision: 7,
      generator_id: "builtin.three-file",
      generator_version: "2.0.0",
      generator_options: { normalized: true },
      preview_digest: "preview-digest",
    }]);
  });

  it("shows a reactivate action with immutable version metadata", async () => {
    installApiMocks(preview({
      action: action({ mode: "reactivate", skill_version_id: "version-1", version: "0.1.0", version_number: 1, display_name: "已生成版本", next_version: null }),
    }));
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.text()).toContain("重新激活既有版本");
    expect(wrapper.findComponent({ name: "VersionSelector" }).exists()).toBe(false);
    const fields = wrapper.findAll<HTMLInputElement | HTMLTextAreaElement>(".workflow-sync-version-fields input, .workflow-sync-version-fields textarea");
    expect(fields).toHaveLength(3);
    expect(fields.every((field) => field.attributes("disabled") !== undefined)).toBe(true);
  });

  it("shows an explicit empty diff state for an already-current result", async () => {
    const current = preview({
      action: action({ mode: "already_current", skill_version_id: "version-1", version: "0.1.0", version_number: 1, next_version: null }),
    });
    current.diff = {
      summary: { added: 0, changed: 0, removed: 0, unchanged: 1, binary: 0 },
      files: [],
    };
    installApiMocks(current);
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.findAll(".workflow-preview-tabs button").find((button) => button.text().includes("差异"))!.trigger("click");

    expect(wrapper.text()).toContain("文件内容无变化");
  });

  it("reloads the registry and preview while clearing confirmation on recovery", async () => {
    const previewSpy = installApiMocks(preview());
    const wrapper = mountModal();
    await flushPromises();
    const confirmation = wrapper.get<HTMLInputElement>('.workflow-sync-confirmation input[type="checkbox"]');
    await confirmation.setValue(true);
    expect(confirmation.element.checked).toBe(true);

    previewSpy.mockResolvedValueOnce(preview({ revision: 8, digest: "recovered-preview" }));
    await wrapper.setProps({ revision: 8, recoveryKey: 1 });
    await flushPromises();

    expect(api.listWorkflowSkillGenerators).toHaveBeenCalledTimes(2);
    expect(previewSpy).toHaveBeenCalledTimes(2);
    expect(previewSpy).toHaveBeenLastCalledWith("skill-1", expect.objectContaining({ expected_workflow_revision: 8 }));
    expect(wrapper.get<HTMLInputElement>('.workflow-sync-confirmation input[type="checkbox"]').element.checked).toBe(false);
    expect(wrapper.text()).toContain("Workflow revision 8");
  });

  it("defines a single-column mobile layout for the preview and actions", () => {
    const css = readFileSync(resolve(process.cwd(), "src/styles/features/workflow/sync-responsive.css"), "utf8");
    const mobile = css.slice(css.indexOf("@media (max-width: 760px)"));
    expect(mobile).toContain(".workflow-skill-preview .bundle-browser");
    expect(mobile).toContain("grid-template-columns: 1fr");
    expect(mobile).toContain(".workflow-sync-sidebar .modal-actions");
  });
});

function installApiMocks(result: WorkflowSyncPreview) {
  vi.spyOn(api, "listWorkflowSkillGenerators").mockResolvedValue(catalog());
  return vi.spyOn(api, "previewWorkflowSync").mockResolvedValue(result);
}

function mountModal(): VueWrapper {
  const wrapper = mount(WorkflowSyncModal, {
    props: { skill: skillDetail(), revision: 7, recoveryKey: 0, busy: false, open: true },
    global: { stubs: { Teleport: true } },
  });
  wrappers.push(wrapper);
  return wrapper;
}

function catalog(): WorkflowSkillGeneratorCatalog {
  return { generators, default_generator_id: "builtin.three-file" };
}

function action(overrides: Partial<WorkflowSyncPreviewAction> = {}): WorkflowSyncPreviewAction {
  return {
    mode: "create",
    skill_version_id: null,
    version: null,
    version_number: null,
    display_name: null,
    next_version: "0.2.0",
    ...overrides,
  };
}

function preview(input: {
  revision?: number;
  generator?: WorkflowSkillGenerator;
  path?: string;
  digest?: string;
  options?: Record<string, unknown>;
  action?: WorkflowSyncPreviewAction;
} = {}): WorkflowSyncPreview {
  const generator = input.generator ?? generators[1]!;
  const path = input.path ?? "SKILL.md";
  return {
    workflow_id: "workflow-1",
    workflow_revision: input.revision ?? 7,
    generator,
    generator_options: input.options ?? {},
    generator_options_digest: "options-digest",
    preview_digest: input.digest ?? "preview-digest",
    bundle_digest: "bundle-digest",
    files: [{ path, sha256: "file-digest", size_bytes: 8, content_text: "# Skill\n" }],
    diff: {
      summary: { added: 1, changed: 0, removed: 0, unchanged: 0, binary: 0 },
      files: [{ path, status: "added", binary: false, left_digest: null, right_digest: "file-digest", left_size_bytes: null, right_size_bytes: 8, hunks: [] }],
    },
    warnings: [],
    action: input.action ?? action(),
  };
}

function skillDetail(): SkillDetail {
  return {
    skill: { id: "skill-1", slug: "router-check", display_name: null, owner_ref: "owner", current_version_id: "version-1", lifecycle_status: "active", tags: [] },
    summary: { skill: {} as never, current_version: null, primary_eval_set: null, latest_accepted_eval_run: null },
    versions: [{ id: "version-1", skill_id: "skill-1", version_number: 1, version: "0.1.0", content_ref: { kind: "artifact", locator: "artifact-1", digest: "old" }, content_digest: "old", change_summary: "Initial", created_by: "owner" }],
    eval_sets: [],
    latest_eval_runs: [],
    role_assignments: [],
    audit_events: [],
    capabilities: null,
    workflow: null,
  };
}

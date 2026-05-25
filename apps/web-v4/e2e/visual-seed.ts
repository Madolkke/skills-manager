import { expect, type APIRequestContext } from "@playwright/test";
import type { EvalSetVersionDetail, SkillDetail } from "../src/types";

const apiPort = Number(process.env.SKILLHUB_VISUAL_API_PORT ?? process.env.SKILLHUB_E2E_API_PORT ?? 18110);
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;
const actor = "product-operator";

type BundleSource = {
  kind: "files";
  name: string;
  files: Array<{ path: string; content_text: string }>;
};

type ImportResult = {
  skill_id: string;
};

type VariantResult = {
  variant_id: string;
};

type EvalCaseResult = {
  eval_case_id: string;
};

export type VisualDataset = {
  primarySkillId: string;
};

export class VisualSeed {
  constructor(private readonly request: APIRequestContext) {}

  async createProductDataset(): Promise<VisualDataset> {
    await this.createAuxiliarySkills();
    const primary = await this.importSkill("code-reviewer", "自动化代码审查，指出高风险问题并给出可执行建议。", ["codex", "gpt5.4"], 3);
    let detail = await this.getSkill(primary.skill_id);

    await this.createVariant(detail.skill.id, ["codex"], "轻量代码审查，适合快速预检。", 2);
    await this.createVariant(detail.skill.id, ["codex", "minimax2.7"], "强调上下文整理和变更摘要。", 2);
    await this.createVariant(detail.skill.id, ["opencode", "minimax2.7"], "适合开源项目维护场景。", 3);
    await this.createVariant(detail.skill.id, ["opencode"], "以兼容性和低成本为优先。", 2);
    await this.createVariant(detail.skill.id, ["opencode", "gpt5.4"], "用于高风险安全审查候选。", 1);

    const first = await this.createCase(detail.skill.id, {
      title: "PR: missing owner filter",
      inputText: "diff --git a/api/projects.py b/api/projects.py\n+return Project.query.all()",
      expectedOutput: "应指出缺少 owner_id 或 tenant 过滤条件，提示存在越权读取风险。",
      notes: "确保审查器能识别多租户场景下缺失的访问控制条件。",
    });
    await this.updateCase(first.eval_case_id, {
      title: "PR: missing owner filter",
      inputText: "diff --git a/api/projects.py b/api/projects.py\n-return Project.objects.all()\n+return Project.objects.filter(tenant_id=user.tenant_id)",
      expectedOutput: "应确认新增 tenant filter，并保留对 owner_id 缺失场景的提醒。",
      notes: "case v2：补充多租户访问控制说明。",
    });

    for (const item of [
      "PR: tenant scope not enforced",
      "PR: unsafe eval usage",
      "PR: hardcoded secret",
      "PR: missing input validation",
      "PR: sensitive data in logs",
      "PR: weak error handling",
      "PR: missing rate limit",
    ]) {
      await this.createCase(detail.skill.id, {
        title: item,
        inputText: `diff fixture for ${item}`,
        expectedOutput: "Should produce an actionable risk finding with severity and remediation.",
        notes: "manual verification flow",
      });
    }

    detail = await this.getSkill(primary.skill_id);
    const evalSetVersionId = detail.summary.primary_eval_set?.current_version_id ?? "";
    const evalSetVersion = await this.getEvalSetVersion(evalSetVersionId);
    await this.recordRun(detail.summary.default_variant?.current_version_id ?? "", evalSetVersion, (index) => index !== 1);
    return { primarySkillId: primary.skill_id };
  }

  private async createAuxiliarySkills(): Promise<void> {
    await this.createSkillWithRun("security-reviewer", "识别安全漏洞和风险，提供修复建议和最佳实践指导。", ["codex", "gpt5.4"], true);
    await this.createSkillWithRun("pr-assistant", "生成 PR 描述、总结变更、跟踪讨论并管理合并流程。", ["opencode", "minimax2.7"], false);
    await this.createSkillWithRun("documentation-writer", "根据代码和需求自动生成清晰的技术文档和使用指南。", ["gpt5.4", "claude-3.7"], true);
    await this.createSkillWithRun("test-generator", "自动生成单元测试和集成测试，提高代码覆盖率和质量。", ["codex", "gpt5.4"], true);
    await this.createSkillWithRun("bug-analyzer", "分析错误日志和堆栈跟踪，定位根本原因并提供修复建议。", ["claude-3.7", "gpt5.4"], false);
    await this.importSkill("refactor-helper", "智能重构建议，提升代码质量和可维护性。", ["codex", "gpt5.4"], 1);
    await this.createSkillWithRun("api-designer", "设计 RESTful API 接口，生成文档和示例代码。", ["opencode", "gpt5.4"], true);
    await this.importSkill("database-optimizer", "优化数据库查询性能，提供索引建议和结构优化方案。", ["codex", "postgres"], 1);
  }

  private async createSkillWithRun(slug: string, description: string, tags: string[], passed: boolean): Promise<void> {
    const imported = await this.importSkill(slug, description, tags, 1);
    const detail = await this.getSkill(imported.skill_id);
    await this.createCase(detail.skill.id, {
      title: `${displayName(slug)} smoke case`,
      inputText: `input fixture for ${slug}`,
      expectedOutput: `expected output for ${slug}`,
      notes: "recent evaluation seed",
    });
    const next = await this.getSkill(imported.skill_id);
    const evalSetVersion = await this.getEvalSetVersion(next.summary.primary_eval_set?.current_version_id ?? "");
    await this.recordRun(next.summary.default_variant?.current_version_id ?? "", evalSetVersion, () => passed);
  }

  private async importSkill(slug: string, description: string, tags: string[], versions: number): Promise<ImportResult> {
    const imported = await this.post<ImportResult>("/api/skill-imports", {
      owner_ref: "product-operator",
      tags,
      source: bundleSource(slug, description, tags, 1),
    });
    const detail = await this.getSkill(imported.skill_id);
    for (let version = 2; version <= versions; version += 1) {
      await this.post("/api/variant-versions", {
        variant_id: detail.summary.default_variant?.id,
        source: bundleSource(slug, description, tags, version),
        make_current: true,
      });
    }
    return imported;
  }

  private async createVariant(skillId: string, tags: string[], description: string, versions: number): Promise<void> {
    const slug = `code-reviewer-${tags.join("-").replaceAll(".", "-")}`;
    const created = await this.post<VariantResult>("/api/variants", {
      skill_id: skillId,
      tags,
      source: bundleSource(slug, description, tags, 1),
      make_default: false,
    });
    for (let version = 2; version <= versions; version += 1) {
      await this.post("/api/variant-versions", {
        variant_id: created.variant_id,
        source: bundleSource(slug, description, tags, version),
        make_current: true,
      });
    }
  }

  private async createCase(skillId: string, input: CaseInput): Promise<EvalCaseResult> {
    return this.post<EvalCaseResult>("/api/eval-cases", {
      skill_id: skillId,
      title: input.title,
      input_text: input.inputText,
      expected_output: input.expectedOutput,
      notes: input.notes,
    });
  }

  private async updateCase(caseId: string, input: CaseInput): Promise<void> {
    await this.post(`/api/eval-cases/${caseId}`, {
      case_id: caseId,
      title: input.title,
      input_text: input.inputText,
      expected_output: input.expectedOutput,
      notes: input.notes,
      make_current: true,
    }, "PATCH");
  }

  private async recordRun(
    variantVersionId: string,
    evalSetVersion: EvalSetVersionDetail,
    verdict: (index: number) => boolean,
  ): Promise<void> {
    const results = Object.fromEntries(evalSetVersion.cases.map((item, index) => [item.case_version.id, verdict(index)]));
    await this.post("/api/eval-runs", {
      variant_version_id: variantVersionId,
      eval_set_version_id: evalSetVersion.eval_set_version.id,
      strategy: "manual_pass_fail",
      results,
    });
  }

  private async getSkill(skillId: string): Promise<SkillDetail> {
    return this.get<SkillDetail>(`/api/skills/${skillId}`);
  }

  private async getEvalSetVersion(versionId: string): Promise<EvalSetVersionDetail> {
    return this.get<EvalSetVersionDetail>(`/api/eval-set-versions/${versionId}`);
  }

  private async get<T>(path: string): Promise<T> {
    const response = await this.request.get(`${apiBaseUrl}${path}`, { headers: { "X-SkillHub-Actor": actor } });
    expect(response.ok()).toBeTruthy();
    return response.json() as Promise<T>;
  }

  private async post<T = unknown>(path: string, data: unknown, method: "POST" | "PATCH" = "POST"): Promise<T> {
    const response = method === "POST"
      ? await this.request.post(`${apiBaseUrl}${path}`, { data, headers: { "X-SkillHub-Actor": actor } })
      : await this.request.patch(`${apiBaseUrl}${path}`, { data, headers: { "X-SkillHub-Actor": actor } });
    expect(response.ok(), `${method} ${path} failed: ${response.status()} ${await response.text()}`).toBeTruthy();
    return response.json() as Promise<T>;
  }
}

type CaseInput = {
  title: string;
  inputText: string;
  expectedOutput: string;
  notes: string;
};

function bundleSource(slug: string, description: string, tags: string[], version: number): BundleSource {
  return {
    kind: "files",
    name: slug,
    files: [
      {
        path: `${slug}/SKILL.md`,
        content_text: [
          "---",
          `name: ${slug}`,
          `description: ${description}`,
          "---",
          "",
          `# ${displayName(slug)}`,
          "",
          "## 目标",
          "对 Pull Request 提供高质量审查，聚焦正确性、安全性、可维护性和性能。",
          "",
          "## 审查流程",
          "1. 理解变更范围与上下文",
          "2. 识别高风险问题",
          "3. 给出可执行的修改建议",
          "4. 提供总结与风险评级",
          "",
          `version: v${version}`,
          `tags: ${tags.join(", ")}`,
          "",
        ].join("\n"),
      },
      {
        path: `${slug}/examples/pr.diff`,
        content_text: "diff --git a/api/projects.py b/api/projects.py\n+return Project.query.all()\n",
      },
      {
        path: `${slug}/tests/cases.md`,
        content_text: "- owner filter\n- tenant scope\n- secret handling\n",
      },
      {
        path: `${slug}/references/checklist.md`,
        content_text: "Check owner filters, tenant isolation, secret logging, and unsafe eval usage.\n",
      },
    ],
  };
}

function displayName(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

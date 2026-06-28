import type { EvalAssertionTemplate, EvalCaseStep, EvalRunnerConfig, EvalSetCase, EvalStepAssertion } from "../../../types";

export type EvalCaseFormData = {
  title: string;
  steps: EvalCaseStep[];
  workspace_name?: string;
  workspace_base64?: string;
  runner_config: EvalRunnerConfig;
  notes: string;
};

export type StepValidation = {
  complete: boolean;
  message: string;
};

export function createEvalCaseForm(caseItem?: EvalSetCase | null): EvalCaseFormData {
  return {
    title: caseItem?.case.title ?? "",
    steps: caseItem?.case_version.steps.length ? caseItem.case_version.steps.map(cloneStep) : [defaultStep()],
    workspace_name: undefined,
    workspace_base64: undefined,
    runner_config: cleanRunnerConfig(caseItem?.case_version.runner_config),
    notes: caseItem?.case_version.notes ?? "",
  };
}

export function defaultStep(index = 0): EvalCaseStep {
  return {
    id: "",
    title: `步骤 ${index + 1}`,
    input: "",
    assertions: [defaultAssertion()],
  };
}

export function defaultAssertion(index = 0): EvalStepAssertion {
  return {
    id: `assertion-${index + 1}`,
    assertion_template_id: "agent_output_semantic",
    assertion_params: { expected: "", threshold: 0.85 },
  };
}

export function cloneStep(step: EvalCaseStep): EvalCaseStep {
  return {
    ...step,
    assertions: stepAssertions(step).map((assertion) => ({ ...assertion, assertion_params: { ...assertion.assertion_params } })),
  };
}

export function validateStep(step: EvalCaseStep, templateFor: (id: string) => EvalAssertionTemplate | undefined): StepValidation {
  if (!step.input.trim()) return { complete: false, message: "缺少输入" };
  const assertions = stepAssertions(step);
  if (assertions.length === 0) return { complete: false, message: "缺少判断条件" };
  for (const [index, assertion] of assertions.entries()) {
    const template = templateFor(assertion.assertion_template_id);
    if (!template) return { complete: false, message: `判断条件 ${index + 1} 模板无效` };
    for (const param of template.params_schema) {
      if (!param.required) continue;
      const value = assertion.assertion_params[param.name];
      if (value === null || value === undefined || (typeof value === "string" && !value.trim())) {
        return { complete: false, message: `判断条件 ${index + 1} 缺少${param.label}` };
      }
    }
  }
  return { complete: true, message: "完整" };
}

export function stepAssertions(step: EvalCaseStep): EvalStepAssertion[] {
  return Array.isArray(step.assertions) ? step.assertions : [];
}

export function nextAssertionIndex(assertions: EvalStepAssertion[]): number {
  const maxExisting = assertions.reduce((max, assertion) => {
    const match = /^assertion-(\d+)$/.exec(assertion.id);
    const value = match ? Number(match[1]) : 0;
    return Number.isFinite(value) ? Math.max(max, value) : max;
  }, 0);
  return maxExisting;
}

export function artifactFileName(locator: string): string {
  return locator.split(":").at(-1) || "workspace.zip";
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function cleanRunnerConfig(value?: EvalRunnerConfig | null): EvalRunnerConfig {
  return {
    timeout_seconds: value?.timeout_seconds ?? null,
  };
}

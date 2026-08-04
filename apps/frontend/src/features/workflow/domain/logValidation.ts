import type { CollectionDefinition, WorkflowJsonSchema } from "../../../types";

export type LogValidationIssue = { code: string; message: string; field: string; itemId?: string };

const scalarTypes = new Set(["string", "integer", "number", "boolean"]);

export function logCollectionIssues(definition: CollectionDefinition): LogValidationIssue[] {
  if (definition.spec.collectionType !== "log") return [];
  const issues: LogValidationIssue[] = [];
  const queryIds = new Set<string>();
  const assigned = new Map<string, string>();
  definition.spec.queries.forEach((query) => {
    const queryField = `spec.queries.${query.id || "_"}`;
    if (!query.id.trim()) issues.push({ code: "MISSING_LOG_QUERY_ID", message: "日志聚合查询 ID 不能为空。", field: `${queryField}.id`, itemId: query.id });
    else if (queryIds.has(query.id.trim())) issues.push({ code: "DUPLICATE_LOG_QUERY_ID", message: `日志聚合查询 ID“${query.id}”重复。`, field: `${queryField}.id`, itemId: query.id });
    queryIds.add(query.id.trim());
    if (!query.sql.trim()) issues.push({ code: "LOG_QUERY_SQL_INVALID", message: "日志聚合 SQL 不能为空。", field: `${queryField}.sql`, itemId: query.id });
    if (query.outputIds.length === 0) issues.push({ code: "LOG_QUERY_OUTPUT_NOT_ASSIGNED", message: "日志聚合查询至少需要一个输出字段。", field: `${queryField}.outputIds`, itemId: query.id });
    query.outputIds.forEach((outputId) => {
      const previous = assigned.get(outputId);
      if (previous) issues.push({ code: "LOG_QUERY_OUTPUT_NOT_UNIQUE", message: "一个输出字段只能归属一条日志聚合查询。", field: `${queryField}.outputIds`, itemId: query.id });
      else assigned.set(outputId, query.id);
    });
  });
  const outputIds = new Set(definition.outputs.map((item) => item.id));
  definition.outputs.forEach((output) => {
    if (!scalarTypes.has(output.schema.type ?? "")) issues.push({ code: "LOG_OUTPUT_SCHEMA_NOT_SCALAR", message: "日志聚合输出只支持四种标量 Schema。", field: `outputs.${output.id}.schema`, itemId: output.id });
    if (!assigned.has(output.id)) issues.push({ code: "LOG_QUERY_OUTPUT_NOT_ASSIGNED", message: "日志聚合输出必须归属一条查询。", field: `outputs.${output.id}`, itemId: output.id });
  });
  definition.inputs.forEach((input) => {
    if (!scalarTypes.has(input.schema.type ?? "")) issues.push({ code: "LOG_INPUT_SCHEMA_NOT_SCALAR", message: "日志聚合输入只支持四种标量 Schema。", field: `inputs.${input.id}.schema`, itemId: input.id });
  });
  definition.spec.queries.forEach((query) => query.outputIds.forEach((outputId) => {
    if (!outputIds.has(outputId)) issues.push({ code: "LOG_QUERY_OUTPUT_NOT_ASSIGNED", message: "日志聚合查询引用了不存在的输出字段。", field: `spec.queries.${query.id}.outputIds`, itemId: query.id });
  }));
  const sampleIds = new Set<string>();
  definition.spec.outputSamples.forEach((sample) => {
    if (!sample.id.trim()) issues.push({ code: "MISSING_COLLECTION_SAMPLE_ID", message: "日志样例 ID 不能为空。", field: `spec.outputSamples.${sample.id}.id` });
    else if (sampleIds.has(sample.id.trim())) issues.push({ code: "DUPLICATE_COLLECTION_SAMPLE_ID", message: `日志样例 ID“${sample.id}”重复。`, field: `spec.outputSamples.${sample.id}.id` });
    sampleIds.add(sample.id.trim());
  });
  return issues;
}
export function isLogScalarSchema(schema: WorkflowJsonSchema): boolean {
  return Boolean(schema.type && scalarTypes.has(schema.type));
}

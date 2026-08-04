import type { WorkflowLogSchemaCatalog } from "../../../types";

export const fallbackWorkflowLogSchema: WorkflowLogSchemaCatalog = {
  document_schema_version: 5,
  dialect: "duckdb",
  logs_table: "logs",
  params_table: "params",
  columns: [
    { name: "event_time", duckdb_type: "TIMESTAMP", nullable: true, title: "时间", description: "日志事件时间（无时区）" },
    { name: "device", duckdb_type: "VARCHAR", nullable: true, title: "设备", description: "日志来源设备" },
    { name: "module", duckdb_type: "VARCHAR", nullable: true, title: "模块", description: "产生日志的模块" },
    { name: "severity", duckdb_type: "VARCHAR", nullable: true, title: "严重等级", description: "日志严重等级" },
    { name: "brief", duckdb_type: "VARCHAR", nullable: true, title: "简述", description: "日志摘要" },
    { name: "body", duckdb_type: "VARCHAR", nullable: true, title: "日志体", description: "原始日志正文" },
  ],
};

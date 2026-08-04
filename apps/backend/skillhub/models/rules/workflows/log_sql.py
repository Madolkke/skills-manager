from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlglot import exp, parse
from sqlglot.errors import ParseError, TokenError
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.tokens import Tokenizer, TokenType

from .log_schema import LOG_COLUMN_NAMES


@dataclass(frozen=True)
class LogSqlDiagnostic:
    code: str
    message: str


_ALLOWED_TABLES = {"logs", "params"}
_FORBIDDEN_FUNCTIONS = {
    "arrow_scan",
    "csv_scan",
    "delta_scan",
    "glob",
    "http_get",
    "iceberg_scan",
    "install",
    "json_scan",
    "load",
    "load_extension",
    "mysql_scan",
    "query_table",
    "parquet_scan",
    "postgres_scan",
    "read_blob",
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_ndjson_auto",
    "read_parquet",
    "read_text",
    "read_xlsx",
    "sqlite_scan",
}
_FORBIDDEN_SOURCE_EXPRESSIONS = (exp.GenerateSeries, exp.Unnest, exp.Values)


def validate_log_query(
    sql: str,
    output_keys: Iterable[str],
    input_keys: Iterable[str] = (),
) -> list[LogSqlDiagnostic]:
    """Statically validate one DuckDB query without executing user SQL."""
    text = sql.strip()
    if not text:
        return [LogSqlDiagnostic("LOG_QUERY_SQL_INVALID", "日志聚合 SQL 不能为空。")]
    try:
        statements = parse(text, read="duckdb")
    except (ParseError, TokenError) as exc:
        description = exc.errors[0].get("description", str(exc)) if isinstance(exc, ParseError) and exc.errors else str(exc)
        return [LogSqlDiagnostic("LOG_QUERY_SQL_INVALID", f"日志聚合 SQL 语法无效：{description}")]
    if len(statements) != 1:
        return [LogSqlDiagnostic("LOG_QUERY_MULTIPLE_STATEMENTS", "日志聚合 SQL 只能包含一条语句。")]
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return [LogSqlDiagnostic("LOG_QUERY_SQL_INVALID", "日志聚合 SQL 只允许 SELECT 或 WITH ... SELECT 查询。")]

    diagnostics: list[LogSqlDiagnostic] = []
    scopes = list(traverse_scope(statement))
    _validate_sources(statement, scopes, diagnostics)
    _validate_columns(scopes, set(input_keys), diagnostics)
    _validate_output_aliases(text, statement, list(output_keys), diagnostics)
    return _unique_diagnostics(diagnostics)


def _validate_sources(
    statement: exp.Select,
    scopes: list[Scope],
    diagnostics: list[LogSqlDiagnostic],
) -> None:
    for table in statement.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier) or table.db or table.catalog:
            diagnostics.append(LogSqlDiagnostic("LOG_QUERY_FORBIDDEN_SOURCE", "日志聚合 SQL 不允许文件、表函数或外部表来源。"))
    for expression_type in _FORBIDDEN_SOURCE_EXPRESSIONS:
        if statement.find(expression_type) is not None:
            diagnostics.append(LogSqlDiagnostic("LOG_QUERY_FORBIDDEN_SOURCE", "日志聚合 SQL 只能读取 logs、params 或本地查询结果。"))
    for function in statement.find_all(exp.Func):
        if function.sql_name().lower() in _FORBIDDEN_FUNCTIONS:
            diagnostics.append(LogSqlDiagnostic("LOG_QUERY_FORBIDDEN_SOURCE", f"日志聚合 SQL 不允许外部读取函数“{function.sql_name()}”。"))
    for scope in scopes:
        for source in scope.sources.values():
            if isinstance(source, Scope):
                continue
            if not isinstance(source, exp.Table) or not isinstance(source.this, exp.Identifier):
                diagnostics.append(LogSqlDiagnostic("LOG_QUERY_FORBIDDEN_SOURCE", "日志聚合 SQL 只能读取 logs、params 或本地查询结果。"))
                continue
            if source.name.lower() not in _ALLOWED_TABLES:
                diagnostics.append(LogSqlDiagnostic("LOG_QUERY_FORBIDDEN_SOURCE", f"日志聚合 SQL 不能读取数据源“{source.name}”。"))


def _validate_columns(
    scopes: list[Scope],
    input_keys: set[str],
    diagnostics: list[LogSqlDiagnostic],
) -> None:
    for scope in scopes:
        for column in scope.columns:
            if column.name == "*" or _is_output_alias_reference(column, scope):
                continue
            if not _column_is_known(scope, column, input_keys):
                diagnostics.append(LogSqlDiagnostic("LOG_QUERY_UNKNOWN_COLUMN", f"日志聚合 SQL 引用了未知列“{column.sql()}”。"))


def _column_is_known(scope: Scope, column: exp.Column, input_keys: set[str]) -> bool:
    if column.table:
        return _column_in_source(_find_source(scope, column.table), column.name, input_keys)
    current: Scope | None = scope
    while current is not None:
        for source in current.sources.values():
            if _column_in_source(source, column.name, input_keys):
                return True
        current = current.parent
    return False


def _is_output_alias_reference(column: exp.Column, scope: Scope) -> bool:
    aliases = {projection.alias_or_name for projection in scope.expression.selects if projection.alias_or_name}
    if column.name not in aliases:
        return False
    current = column.parent
    while current is not None and current is not scope.expression:
        if isinstance(current, (exp.Group, exp.Having, exp.Order, exp.Qualify)):
            return True
        current = current.parent
    return False


def _find_source(scope: Scope, alias: str) -> exp.Table | Scope | None:
    current: Scope | None = scope
    while current is not None:
        source = current.sources.get(alias)
        if isinstance(source, (exp.Table, Scope)):
            return source
        current = current.parent
    return None


def _source_columns(source: exp.Table | Scope | None, input_keys: set[str]) -> set[str]:
    if isinstance(source, Scope):
        return {projection.alias_or_name for projection in source.expression.selects if projection.alias_or_name}
    if not isinstance(source, exp.Table):
        return set()
    if source.name.lower() == "logs":
        return set(LOG_COLUMN_NAMES)
    if source.name.lower() == "params":
        return input_keys
    return set()


def _column_in_source(source: exp.Table | Scope | None, name: str, input_keys: set[str]) -> bool:
    if isinstance(source, Scope):
        return name in _source_columns(source, input_keys)
    if not isinstance(source, exp.Table):
        return False
    if source.name.lower() == "logs":
        return name.lower() in LOG_COLUMN_NAMES
    if source.name.lower() == "params":
        return name in input_keys
    return False


def _validate_output_aliases(
    sql: str,
    statement: exp.Select,
    output_keys: list[str],
    diagnostics: list[LogSqlDiagnostic],
) -> None:
    aliases: list[str] = []
    explicit = True
    for projection in statement.expressions:
        if not isinstance(projection, exp.Alias):
            explicit = False
            continue
        if isinstance(projection.this, exp.Star) or (isinstance(projection.this, exp.Column) and projection.this.name == "*"):
            explicit = False
        aliases.append(projection.alias)
    if explicit and not _top_level_aliases_are_explicit(sql):
        explicit = False
    if not explicit or aliases != output_keys:
        expected = "、".join(output_keys) or "无"
        diagnostics.append(LogSqlDiagnostic("LOG_QUERY_OUTPUT_ALIAS_MISMATCH", f"SQL 顶层输出必须使用 AS，并按声明顺序映射为：{expected}。"))


def _top_level_aliases_are_explicit(sql: str) -> bool:
    """Check the original query tokens because SQLGlot normalizes implicit aliases."""
    tokens = Tokenizer().tokenize(sql)
    depth = 0
    select_start: int | None = None
    projection_tokens: list[list[tuple[TokenType, int]]] = []
    current: list[tuple[TokenType, int]] = []
    for token in tokens:
        if token.token_type == TokenType.L_PAREN:
            depth += 1
        if select_start is None and token.token_type == TokenType.SELECT and depth == 0:
            select_start = depth
            continue
        if select_start is None:
            if token.token_type == TokenType.R_PAREN:
                depth -= 1
            continue
        if token.token_type == TokenType.FROM and depth == select_start:
            break
        if token.token_type == TokenType.COMMA and depth == select_start:
            projection_tokens.append(current)
            current = []
            continue
        current.append((token.token_type, depth))
        if token.token_type == TokenType.R_PAREN:
            depth -= 1
    if current:
        projection_tokens.append(current)
    return bool(projection_tokens) and all(
        any(token_type == TokenType.ALIAS and token_depth == select_start for token_type, token_depth in projection)
        for projection in projection_tokens
    )


def _unique_diagnostics(items: list[LogSqlDiagnostic]) -> list[LogSqlDiagnostic]:
    seen: set[tuple[str, str]] = set()
    source_error_seen = False
    result: list[LogSqlDiagnostic] = []
    for item in items:
        if item.code == "LOG_QUERY_FORBIDDEN_SOURCE":
            if source_error_seen:
                continue
            source_error_seen = True
        key = (item.code, item.message)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


__all__ = ["LogSqlDiagnostic", "validate_log_query"]

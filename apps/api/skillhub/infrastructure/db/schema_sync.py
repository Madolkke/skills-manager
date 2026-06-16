from __future__ import annotations

from sqlalchemy import Engine, text


SCHEMA_PATCHES = (
    "alter table eval_case_versions add column if not exists prompt_template_id text not null default 'standard_pass_fail'",
    "alter table eval_case_versions add column if not exists prompt_text text not null default ''",
    "alter table eval_case_versions add column if not exists model_provider_id text",
    "alter table eval_case_versions add column if not exists model_id text",
    "alter table jobs add column if not exists attempts integer not null default 0",
    "alter table jobs add column if not exists locked_by text",
    "alter table jobs add column if not exists last_heartbeat_at timestamptz",
    "alter table eval_case_runs add column if not exists runner_metadata jsonb not null default '{}'::jsonb",
    """
    update jobs
    set payload = (payload - 'strategy') || '{"runner":"opencode"}'::jsonb
    where type = 'eval_case_run'
      and payload->>'strategy' = 'opencode_server_structured'
    """,
    """
    update jobs
    set payload = (payload - 'strategy') || '{"runner":"opencode"}'::jsonb
    where type = 'eval_case_run'
      and payload ? 'strategy'
      and not payload ? 'runner'
      and payload->>'strategy' <> 'manual_pass_fail'
    """,
    """
    do $$
    begin
      if exists (
        select 1 from information_schema.columns
        where table_name = 'eval_runs' and column_name = 'strategy'
      ) then
        execute '
          with manual_eval_runs as (
            select id from eval_runs where strategy = ''manual_pass_fail''
          )
          delete from accepted_verifications
          where eval_run_id in (select id from manual_eval_runs)
        ';
        execute '
          with manual_eval_runs as (
            select id from eval_runs where strategy = ''manual_pass_fail''
          )
          delete from case_results
          where run_id in (select id from manual_eval_runs)
        ';
        execute 'delete from eval_runs where strategy = ''manual_pass_fail''';
      end if;

      if exists (
        select 1 from information_schema.columns
        where table_name = 'eval_case_runs' and column_name = 'strategy'
      ) then
        execute '
          with deleted_case_runs as (
            delete from eval_case_runs
            where strategy = ''manual_pass_fail''
            returning job_id
          )
          delete from jobs
          where id in (select job_id from deleted_case_runs where job_id is not null)
        ';
      end if;
    end $$;
    """,
    """
    delete from artifacts
    where kind = 'actual_output'
      and namespace like 'eval_case_run:%'
      and not exists (
        select 1 from eval_case_runs where eval_case_runs.result_artifact_id = artifacts.id
      )
      and not exists (
        select 1 from case_results where case_results.result_artifact_id = artifacts.id
      )
    """,
    "alter table eval_case_runs drop column if exists strategy",
    "alter table eval_runs drop column if exists strategy",
)


def ensure_current_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in SCHEMA_PATCHES:
            connection.execute(text(statement))

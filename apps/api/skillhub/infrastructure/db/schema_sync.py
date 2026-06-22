from __future__ import annotations

from sqlalchemy import Engine, text


CLEANUP_PATCHES = (
    """
    delete from accepted_verifications
    where eval_run_id in (select id from eval_runs)
    """,
    "delete from case_results",
    "delete from eval_runs",
    "delete from eval_case_runs",
    "delete from jobs where type = 'eval_case_run'",
    "delete from eval_set_cases",
    "update eval_cases set current_version_id = null",
    "delete from eval_case_versions",
    "delete from eval_cases",
    """
    delete from artifacts
    where kind in ('eval_input', 'expected_output', 'eval_case_attachment', 'eval_case_workspace', 'actual_output')
       or namespace like 'eval_case_run:%'
    """,
)

SCHEMA_PATCHES = (
    "alter table eval_case_versions add column if not exists workspace_artifact_id text references artifacts(id)",
    "alter table eval_case_versions add column if not exists steps jsonb not null default '[]'::jsonb",
    "alter table eval_case_versions add column if not exists runner_config jsonb not null default '{}'::jsonb",
    """
    update eval_case_versions ecv
    set steps = migrated.steps
    from (
      select
        ecv_inner.id,
        coalesce(
          jsonb_agg(
            case
              when jsonb_typeof(step_item.step -> 'assertions') = 'array'
                   and jsonb_array_length(step_item.step -> 'assertions') > 0
                then step_item.step - 'assertion_template_id' - 'assertion_params'
              else
                (step_item.step - 'assertion_template_id' - 'assertion_params')
                || jsonb_build_object(
                  'assertions',
                  jsonb_build_array(
                    jsonb_build_object(
                      'id', 'assertion-1',
                      'assertion_template_id', coalesce(nullif(step_item.step ->> 'assertion_template_id', ''), 'agent_output_semantic'),
                      'assertion_params',
                        case
                          when jsonb_typeof(step_item.step -> 'assertion_params') = 'object'
                            then step_item.step -> 'assertion_params'
                          else '{}'::jsonb
                        end
                    )
                  )
                )
            end
            order by step_item.ordinality
          ),
          '[]'::jsonb
        ) as steps
      from eval_case_versions ecv_inner
      cross join lateral jsonb_array_elements(ecv_inner.steps) with ordinality as step_item(step, ordinality)
      where exists (
        select 1
        from jsonb_array_elements(ecv_inner.steps) existing_step
        where existing_step ? 'assertion_template_id'
           or existing_step ? 'assertion_params'
      )
      group by ecv_inner.id
    ) migrated
    where ecv.id = migrated.id
    """,
    "alter table jobs add column if not exists attempts integer not null default 0",
    "alter table jobs add column if not exists locked_by text",
    "alter table jobs add column if not exists last_heartbeat_at timestamptz",
    "alter table eval_case_runs add column if not exists runner_metadata jsonb not null default '{}'::jsonb",
    "alter table eval_case_versions drop column if exists input_artifact_id",
    "alter table eval_case_versions drop column if exists expected_output_artifact_id",
    "alter table eval_case_versions drop column if exists attachment_artifact_id",
    "alter table eval_case_versions drop column if exists prompt_template_id",
    "alter table eval_case_versions drop column if exists prompt_text",
    "alter table eval_case_versions drop column if exists model_provider_id",
    "alter table eval_case_versions drop column if exists model_id",
    "alter table eval_case_runs drop column if exists strategy",
    "alter table eval_runs drop column if exists strategy",
    "alter table eval_sets drop column if exists lifecycle_status",
    "alter table eval_cases drop column if exists lifecycle_status",
    "alter table eval_set_cases add column if not exists case_id text",
    "alter table eval_set_cases drop constraint if exists eval_set_cases_pkey",
    """
    do $$
    begin
      if exists (
        select 1
        from information_schema.columns
        where table_schema = current_schema()
          and table_name = 'eval_set_cases'
          and column_name = 'case_version_id'
      ) then
        update eval_set_cases esc
        set case_id = ecv.case_id
        from eval_case_versions ecv
        where esc.case_id is null
          and esc.case_version_id = ecv.id;
      end if;
    end $$;
    """,
    """
    delete from eval_set_cases esc
    using eval_set_cases duplicate
    where esc.case_id is not null
      and duplicate.case_id is not null
      and esc.eval_set_id = duplicate.eval_set_id
      and esc.case_id = duplicate.case_id
      and (
        esc.position > duplicate.position
        or (esc.position = duplicate.position and esc.ctid > duplicate.ctid)
      )
    """,
    """
    update eval_set_cases esc
    set position = ranked.next_position
    from (
      select ctid, row_number() over (partition by eval_set_id order by position, case_id) - 1 as next_position
      from eval_set_cases
    ) ranked
    where esc.ctid = ranked.ctid
    """,
    "alter table eval_set_cases alter column case_id set not null",
    "drop index if exists eval_set_cases_case_version_id_idx",
    "alter table eval_set_cases drop constraint if exists eval_set_cases_case_unique",
    "alter table eval_set_cases drop constraint if exists eval_set_cases_case_skill_fkey",
    "alter table eval_set_cases drop constraint if exists eval_set_cases_case_version_skill_fkey",
    "alter table eval_set_cases drop constraint if exists eval_set_cases_case_version_fkey",
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'eval_set_cases'::regclass
          and conname = 'eval_set_cases_pkey'
      ) then
        alter table eval_set_cases add constraint eval_set_cases_pkey primary key (eval_set_id, position);
      end if;
    end $$;
    """,
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'eval_set_cases'::regclass
          and conname = 'eval_set_cases_case_unique'
      ) then
        alter table eval_set_cases add constraint eval_set_cases_case_unique unique (eval_set_id, case_id);
      end if;
    end $$;
    """,
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'eval_set_cases'::regclass
          and conname = 'eval_set_cases_case_skill_fkey'
      ) then
        alter table eval_set_cases add constraint eval_set_cases_case_skill_fkey foreign key (case_id, skill_id) references eval_cases(id, skill_id);
      end if;
    end $$;
    """,
    "alter table eval_set_cases drop column if exists case_version_id",
)


def ensure_current_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        if _has_legacy_eval_schema(connection):
            for statement in CLEANUP_PATCHES:
                connection.execute(text(statement))
        for statement in SCHEMA_PATCHES:
            connection.execute(text(statement))


def _has_legacy_eval_schema(connection) -> bool:
    rows = (
        connection.execute(
            text(
                """
                select table_name, column_name
                from information_schema.columns
                where table_schema = current_schema()
                  and (
                    (table_name = 'eval_case_versions' and column_name in (
                      'input_artifact_id',
                      'expected_output_artifact_id',
                      'attachment_artifact_id',
                      'prompt_template_id',
                      'prompt_text',
                      'model_provider_id',
                      'model_id'
                    ))
                    or (table_name in ('eval_case_runs', 'eval_runs') and column_name = 'strategy')
                  )
                """
            )
        )
        .mappings()
        .all()
    )
    return bool(rows)

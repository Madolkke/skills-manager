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
    "alter table skill_versions add column if not exists version text",
    "alter table skill_versions add column if not exists display_name text",
    """
    update skill_versions
    set version = '0.0.' || version_number::text
    where version is null
    """,
    "alter table skill_versions alter column version set not null",
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'skill_versions'::regclass
          and conname = 'skill_versions_version_semver_check'
      ) then
        alter table skill_versions
          add constraint skill_versions_version_semver_check
          check (version ~ '^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?$');
      end if;
    end $$;
    """,
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'skill_versions'::regclass
          and conname = 'skill_versions_skill_semver_unique'
      ) then
        alter table skill_versions add constraint skill_versions_skill_semver_unique unique (skill_id, version);
      end if;
    end $$;
    """,
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
    "alter table skills drop column if exists visibility",
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
    """
    create table if not exists groups (
      id text primary key,
      name text not null unique,
      description text not null default '',
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null
    )
    """,
    """
    create table if not exists group_memberships (
      group_id text not null references groups(id),
      subject_type text not null,
      subject_id text not null,
      created_at timestamptz not null default now(),
      created_by text not null,
      primary key (group_id, subject_type, subject_id),
      constraint group_memberships_subject_type_check check (subject_type in ('user'))
    )
    """,
    """
    create table if not exists tag_groups (
      id text primary key,
      display_name text not null,
      description text not null default '',
      sort_order integer not null default 0,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null,
      constraint tag_groups_id_format_check check (id ~ '^[A-Za-z0-9_-]+$'),
      constraint tag_groups_display_name_non_empty check (length(btrim(display_name)) > 0)
    )
    """,
    """
    create table if not exists tag_values (
      tag_group_id text not null references tag_groups(id),
      value text not null,
      display_name text,
      description text not null default '',
      sort_order integer not null default 0,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null,
      primary key (tag_group_id, value),
      constraint tag_values_value_non_empty check (length(btrim(value)) > 0)
    )
    """,
    """
    do $$
    begin
      if exists (
        select 1 from information_schema.columns
        where table_schema = current_schema()
          and table_name = 'skill_tags'
          and column_name = 'tag'
      ) then
        delete from role_assignments where resource_type = 'skill_tag';
        drop table skill_tags;
      end if;
    end $$;
    """,
    """
    create table if not exists skill_tags (
      skill_id text not null references skills(id),
      tag_group_id text not null,
      tag_value text not null,
      created_at timestamptz not null default now(),
      created_by text not null,
      primary key (skill_id, tag_group_id, tag_value),
      constraint skill_tags_tag_value_fkey foreign key (tag_group_id, tag_value) references tag_values(tag_group_id, value)
    )
    """,
    "alter table role_assignments drop constraint if exists role_assignments_subject_type_check",
    "alter table role_assignments drop constraint if exists role_assignments_resource_type_check",
    "alter table role_assignments drop constraint if exists role_assignments_role_check",
    """
    alter table role_assignments
      add constraint role_assignments_subject_type_check
      check (subject_type in ('user', 'group'))
    """,
    """
    alter table role_assignments
      add constraint role_assignments_resource_type_check
      check (resource_type in ('skill', 'skill_tag'))
    """,
    """
    alter table role_assignments
      add constraint role_assignments_role_check
      check (role in ('admin', 'owner', 'maintainer', 'evaluator', 'viewer'))
    """,
    "drop index if exists skill_tags_tag_idx",
    "create index if not exists skill_tags_group_value_idx on skill_tags (tag_group_id, tag_value)",
    "create index if not exists tag_groups_sort_idx on tag_groups (sort_order, id)",
    "create index if not exists tag_values_group_sort_idx on tag_values (tag_group_id, sort_order, value)",
    "create index if not exists group_memberships_subject_idx on group_memberships (subject_type, subject_id)",
    "create index if not exists role_assignments_subject_idx on role_assignments (subject_type, subject_id)",
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

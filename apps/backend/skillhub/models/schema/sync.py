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
    "alter table skills drop constraint if exists skills_slug_key",
    "alter table skills drop constraint if exists skills_owner_slug_unique",
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'skills'::regclass
          and conname = 'skills_slug_unique'
      ) then
        alter table skills add constraint skills_slug_unique unique (slug);
      end if;
    end $$;
    """,
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
    "update eval_case_versions set runner_config = runner_config - 'model_provider_id' - 'model_id' where runner_config ?| array['model_provider_id', 'model_id']",
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
      scope_type text not null default 'global',
      scope_id text not null default 'default',
      name text not null,
      description text not null default '',
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null,
      constraint groups_scope_type_check check (scope_type in ('global', 'skill')),
      constraint groups_scope_name_unique unique (scope_type, scope_id, name)
    )
    """,
    "alter table groups add column if not exists scope_type text not null default 'global'",
    "alter table groups add column if not exists scope_id text not null default 'default'",
    "update groups set scope_type = 'global' where scope_type is null",
    "update groups set scope_id = 'default' where scope_id is null",
    "alter table groups alter column scope_type set not null",
    "alter table groups alter column scope_id set not null",
    "alter table groups drop constraint if exists groups_name_key",
    "alter table groups drop constraint if exists groups_scope_type_check",
    """
    alter table groups
      add constraint groups_scope_type_check
      check (scope_type in ('global', 'skill'))
    """,
    """
    do $$
    begin
      if not exists (
        select 1 from pg_constraint
        where conrelid = 'groups'::regclass
          and conname = 'groups_scope_name_unique'
      ) then
        alter table groups add constraint groups_scope_name_unique unique (scope_type, scope_id, name);
      end if;
    end $$;
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
      check (role in ('admin', 'owner', 'maintainer', 'evaluator', 'reviewer', 'viewer'))
    """,
    """
    create table if not exists publish_targets (
      id text primary key,
      target_key text not null,
      name text not null,
      description text not null default '',
      enabled boolean not null default true,
      auto_publish_enabled boolean not null default false,
      gate_expression jsonb not null default '{}'::jsonb,
      config jsonb not null default '{}'::jsonb,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null,
      constraint publish_targets_key_unique unique (target_key),
      constraint publish_targets_key_non_empty check (length(btrim(target_key)) > 0),
      constraint publish_targets_gate_expression_object check (jsonb_typeof(gate_expression) = 'object'),
      constraint publish_targets_config_object check (jsonb_typeof(config) = 'object')
    )
    """,
    "alter table publish_targets add column if not exists auto_publish_enabled boolean not null default false",
    "alter table publish_targets add column if not exists gate_expression jsonb not null default '{}'::jsonb",
    "alter table publish_targets add column if not exists config jsonb not null default '{}'::jsonb",
    "alter table publish_targets drop constraint if exists publish_targets_required_checks_array",
    "alter table publish_targets drop constraint if exists publish_targets_gate_expression_object",
    "alter table publish_targets drop column if exists required_checks",
    """
    alter table publish_targets
      add constraint publish_targets_gate_expression_object
      check (jsonb_typeof(gate_expression) = 'object')
    """,
    """
    do $$
    begin
      if to_regclass('publish_records') is not null then
        delete from publish_records
        where publish_target_id in (
          select id from publish_targets
          where target_key not in ('yunxi', 'agentcenter', 'custom1', 'custom2')
        );
      end if;
    end $$;
    """,
    """
    do $$
    begin
      if to_regclass('review_request_publish_targets') is not null then
        delete from review_request_publish_targets
        where publish_target_id in (
          select id from publish_targets
          where target_key not in ('yunxi', 'agentcenter', 'custom1', 'custom2')
        );
      end if;
    end $$;
    """,
    "delete from publish_targets where target_key not in ('yunxi', 'agentcenter', 'custom1', 'custom2')",
    """
    insert into publish_targets (
      id,
      target_key,
      name,
      description,
      enabled,
      auto_publish_enabled,
      gate_expression,
      config,
      created_at,
      updated_at,
      created_by
    )
    values
      (
        'target_yunxi',
        'yunxi',
        '云析',
        '云析发布源',
        true,
        false,
        jsonb_build_object(
          'type', 'group',
          'op', 'and',
          'children', jsonb_build_array(
            jsonb_build_object('type', 'check', 'check_id', 'min_responses', 'params', jsonb_build_object('min', 1)),
            jsonb_build_object('type', 'check', 'check_id', 'no_negative_score', 'params', jsonb_build_object())
          )
        ),
        '{}'::jsonb,
        now(),
        now(),
        'system'
      ),
      (
        'target_agentcenter',
        'agentcenter',
        'AgentCenter',
        'AgentCenter 发布源',
        true,
        false,
        jsonb_build_object(
          'type', 'group',
          'op', 'and',
          'children', jsonb_build_array(
            jsonb_build_object('type', 'check', 'check_id', 'min_responses', 'params', jsonb_build_object('min', 1)),
            jsonb_build_object('type', 'check', 'check_id', 'no_negative_score', 'params', jsonb_build_object())
          )
        ),
        '{}'::jsonb,
        now(),
        now(),
        'system'
      ),
      (
        'target_custom1',
        'custom1',
        '自定义1',
        '预留自定义发布源 1',
        true,
        false,
        jsonb_build_object(
          'type', 'group',
          'op', 'and',
          'children', jsonb_build_array(
            jsonb_build_object('type', 'check', 'check_id', 'min_responses', 'params', jsonb_build_object('min', 1)),
            jsonb_build_object('type', 'check', 'check_id', 'no_negative_score', 'params', jsonb_build_object())
          )
        ),
        '{}'::jsonb,
        now(),
        now(),
        'system'
      ),
      (
        'target_custom2',
        'custom2',
        '自定义2',
        '预留自定义发布源 2',
        true,
        false,
        jsonb_build_object(
          'type', 'group',
          'op', 'and',
          'children', jsonb_build_array(
            jsonb_build_object('type', 'check', 'check_id', 'min_responses', 'params', jsonb_build_object('min', 1)),
            jsonb_build_object('type', 'check', 'check_id', 'no_negative_score', 'params', jsonb_build_object())
          )
        ),
        '{}'::jsonb,
        now(),
        now(),
        'system'
      )
    on conflict (target_key) do update
    set
      name = excluded.name,
      description = excluded.description,
      config = '{}'::jsonb,
      gate_expression = case
        when publish_targets.gate_expression = '{}'::jsonb then excluded.gate_expression
        else publish_targets.gate_expression
      end,
      updated_at = now()
    """,
    """
    create table if not exists review_requests (
      id text primary key,
      skill_id text not null,
      skill_version_id text not null,
      status text not null,
      summary jsonb not null default '{}'::jsonb,
      closed_at timestamptz,
      closed_by text,
      created_at timestamptz not null default now(),
      created_by text not null,
      constraint review_requests_status_check check (status in ('open', 'closed', 'cancelled')),
      constraint review_requests_id_skill_unique unique (id, skill_id),
      constraint review_requests_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id)
    )
    """,
    "alter table review_requests drop constraint if exists review_requests_skill_version_unique",
    """
    create table if not exists review_request_reviewers (
      review_request_id text not null,
      skill_id text not null,
      reviewer_actor text not null,
      source_subject_type text not null,
      source_subject_id text not null,
      created_at timestamptz not null default now(),
      primary key (review_request_id, reviewer_actor),
      constraint review_request_reviewers_source_type_check check (source_subject_type in ('user', 'group')),
      constraint review_request_reviewers_review_skill_fkey foreign key (review_request_id, skill_id) references review_requests(id, skill_id)
    )
    """,
    """
    create table if not exists review_responses (
      review_request_id text not null,
      skill_id text not null,
      reviewer_actor text not null,
      score integer not null,
      comment text not null default '',
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      primary key (review_request_id, reviewer_actor),
      constraint review_responses_score_check check (score in (-1, 0, 1)),
      constraint review_responses_review_skill_fkey foreign key (review_request_id, skill_id) references review_requests(id, skill_id),
      constraint review_responses_reviewer_fkey foreign key (review_request_id, reviewer_actor) references review_request_reviewers(review_request_id, reviewer_actor)
    )
    """,
    """
    create table if not exists review_request_publish_targets (
      review_request_id text not null,
      skill_id text not null,
      publish_target_id text not null references publish_targets(id),
      auto_submit_on_pass boolean not null default true,
      created_at timestamptz not null default now(),
      primary key (review_request_id, publish_target_id),
      constraint review_request_publish_targets_review_skill_fkey foreign key (review_request_id, skill_id) references review_requests(id, skill_id)
    )
    """,
    """
    create table if not exists review_check_results (
      review_request_id text not null,
      skill_id text not null,
      check_id text not null,
      passed boolean not null,
      details jsonb not null default '{}'::jsonb,
      created_at timestamptz not null default now(),
      primary key (review_request_id, check_id),
      constraint review_check_results_review_skill_fkey foreign key (review_request_id, skill_id) references review_requests(id, skill_id)
    )
    """,
    """
    create table if not exists publish_records (
      id text primary key,
      skill_id text not null,
      skill_version_id text not null,
      review_request_id text not null,
      publish_target_id text not null references publish_targets(id),
      status text not null,
      check_snapshot jsonb not null default '[]'::jsonb,
      metadata jsonb not null default '{}'::jsonb,
      confirmed_at timestamptz,
      confirmed_by text,
      created_at timestamptz not null default now(),
      created_by text not null,
      constraint publish_records_status_check check (status in ('pending_confirmation', 'released', 'cancelled', 'failed')),
      constraint publish_records_version_target_unique unique (skill_version_id, publish_target_id),
      constraint publish_records_id_skill_unique unique (id, skill_id),
      constraint publish_records_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
      constraint publish_records_review_skill_fkey foreign key (review_request_id, skill_id) references review_requests(id, skill_id)
    )
    """,
    """
    create table if not exists notifications (
      id text primary key,
      recipient_actor_id text not null,
      type text not null,
      title text not null,
      body text not null default '',
      resource_type text not null,
      resource_id text not null,
      read_at timestamptz,
      created_at timestamptz not null default now(),
      created_by text not null
    )
    """,
    """
    create table if not exists opencode_agents (
      id text primary key,
      name text not null,
      description text not null default '',
      prompt text not null,
      enabled boolean not null default true,
      deleted_at timestamptz,
      permission jsonb not null default '{}'::jsonb,
      provider_id text,
      model_id text,
      temperature text,
      steps jsonb not null default '[]'::jsonb,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      created_by text not null,
      updated_by text not null,
      constraint opencode_agents_id_format_check check (id ~ '^[A-Za-z0-9_-]+$'),
      constraint opencode_agents_name_non_empty check (length(btrim(name)) > 0),
      constraint opencode_agents_prompt_non_empty check (length(btrim(prompt)) > 0),
      constraint opencode_agents_permission_object check (jsonb_typeof(permission) = 'object'),
      constraint opencode_agents_steps_array check (jsonb_typeof(steps) = 'array')
    )
    """,
    "alter table opencode_agents add column if not exists enabled boolean not null default true",
    "alter table opencode_agents add column if not exists deleted_at timestamptz",
    "alter table opencode_agents add column if not exists permission jsonb not null default '{}'::jsonb",
    "alter table opencode_agents add column if not exists provider_id text",
    "alter table opencode_agents add column if not exists model_id text",
    "alter table opencode_agents add column if not exists temperature text",
    "alter table opencode_agents add column if not exists steps jsonb not null default '[]'::jsonb",
    "alter table opencode_agents add column if not exists updated_at timestamptz not null default now()",
    "alter table opencode_agents add column if not exists updated_by text not null default 'system'",
    "alter table opencode_agents drop constraint if exists opencode_agents_id_format_check",
    "alter table opencode_agents drop constraint if exists opencode_agents_name_non_empty",
    "alter table opencode_agents drop constraint if exists opencode_agents_prompt_non_empty",
    "alter table opencode_agents drop constraint if exists opencode_agents_permission_object",
    "alter table opencode_agents drop constraint if exists opencode_agents_steps_array",
    "alter table opencode_agents add constraint opencode_agents_id_format_check check (id ~ '^[A-Za-z0-9_-]+$')",
    "alter table opencode_agents add constraint opencode_agents_name_non_empty check (length(btrim(name)) > 0)",
    "alter table opencode_agents add constraint opencode_agents_prompt_non_empty check (length(btrim(prompt)) > 0)",
    "alter table opencode_agents add constraint opencode_agents_permission_object check (jsonb_typeof(permission) = 'object')",
    "alter table opencode_agents add constraint opencode_agents_steps_array check (jsonb_typeof(steps) = 'array')",
    "drop index if exists skill_tags_tag_idx",
    "create index if not exists skill_tags_group_value_idx on skill_tags (tag_group_id, tag_value)",
    "create index if not exists tag_groups_sort_idx on tag_groups (sort_order, id)",
    "create index if not exists tag_values_group_sort_idx on tag_values (tag_group_id, sort_order, value)",
    "create index if not exists groups_scope_idx on groups (scope_type, scope_id, name)",
    "create index if not exists group_memberships_subject_idx on group_memberships (subject_type, subject_id)",
    "create index if not exists role_assignments_subject_idx on role_assignments (subject_type, subject_id)",
    "create index if not exists review_requests_skill_version_idx on review_requests (skill_version_id)",
    "create index if not exists review_request_reviewers_actor_idx on review_request_reviewers (reviewer_actor)",
    "create index if not exists review_responses_reviewer_idx on review_responses (reviewer_actor)",
    "create index if not exists review_request_publish_targets_target_idx on review_request_publish_targets (publish_target_id)",
    "create index if not exists review_check_results_check_idx on review_check_results (check_id)",
    "create index if not exists publish_targets_enabled_idx on publish_targets (enabled, target_key)",
    "create index if not exists publish_records_skill_version_idx on publish_records (skill_version_id)",
    "create index if not exists publish_records_target_status_idx on publish_records (publish_target_id, status)",
    "create index if not exists notifications_recipient_idx on notifications (recipient_actor_id, created_at desc)",
    "create index if not exists opencode_agents_enabled_idx on opencode_agents (enabled, deleted_at, name)",
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

create table artifacts (
  id text primary key,
  kind text not null,
  namespace text not null,
  locator text not null,
  digest text not null,
  media_type text not null,
  size_bytes bigint not null default 0,
  content_text text,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint artifacts_size_bytes_non_negative check (size_bytes >= 0),
  constraint artifacts_locator_digest_unique unique (locator, digest)
);

create table skills (
  id text primary key,
  slug text not null unique,
  owner_ref text not null,
  current_version_id text,
  lifecycle_status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint skills_lifecycle_status_check check (lifecycle_status in ('active', 'archived'))
);

create table skill_versions (
  id text primary key,
  skill_id text not null references skills(id),
  version_number integer not null,
  version text not null,
  display_name text,
  content_ref jsonb not null,
  content_digest text not null,
  change_summary text not null,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint skill_versions_version_number_positive check (version_number > 0),
  constraint skill_versions_version_semver_check check (version ~ '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'),
  constraint skill_versions_skill_version_unique unique (skill_id, version_number),
  constraint skill_versions_skill_semver_unique unique (skill_id, version),
  constraint skill_versions_id_skill_unique unique (id, skill_id)
);

alter table skills
  add constraint skills_current_version_fkey
  foreign key (current_version_id, id) references skill_versions(id, skill_id);

create table eval_sets (
  id text primary key,
  skill_id text not null references skills(id),
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint eval_sets_id_skill_unique unique (id, skill_id),
  constraint eval_sets_skill_name_unique unique (skill_id, name)
);

create table eval_cases (
  id text primary key,
  skill_id text not null references skills(id),
  title text not null,
  current_version_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint eval_cases_id_skill_unique unique (id, skill_id)
);

create table eval_case_versions (
  id text primary key,
  skill_id text not null,
  case_id text not null,
  version_number integer not null,
  workspace_artifact_id text references artifacts(id),
  steps jsonb not null default '[]'::jsonb,
  runner_config jsonb not null default '{}'::jsonb,
  notes text,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint eval_case_versions_steps_array check (jsonb_typeof(steps) = 'array'),
  constraint eval_case_versions_runner_config_object check (jsonb_typeof(runner_config) = 'object'),
  constraint eval_case_versions_version_number_positive check (version_number > 0),
  constraint eval_case_versions_case_version_unique unique (case_id, version_number),
  constraint eval_case_versions_id_skill_unique unique (id, skill_id),
  constraint eval_case_versions_case_skill_fkey foreign key (case_id, skill_id) references eval_cases(id, skill_id)
);

alter table eval_cases
  add constraint eval_cases_current_version_fkey
  foreign key (current_version_id, skill_id) references eval_case_versions(id, skill_id);

create table eval_set_cases (
  eval_set_id text not null,
  skill_id text not null,
  case_id text not null,
  position integer not null,
  primary key (eval_set_id, position),
  constraint eval_set_cases_position_non_negative check (position >= 0),
  constraint eval_set_cases_case_unique unique (eval_set_id, case_id),
  constraint eval_set_cases_set_skill_fkey foreign key (eval_set_id, skill_id) references eval_sets(id, skill_id),
  constraint eval_set_cases_case_skill_fkey foreign key (case_id, skill_id) references eval_cases(id, skill_id)
);

create table eval_runs (
  id text primary key,
  skill_id text not null,
  skill_version_id text not null,
  eval_set_id text not null,
  status text not null,
  environment_tags text[] not null default '{}',
  run_context jsonb not null default '{}'::jsonb,
  run_context_hash text not null,
  summary jsonb not null default '{}'::jsonb,
  result_artifact_id text references artifacts(id),
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint eval_runs_status_check check (status in ('queued', 'running', 'finished', 'failed')),
  constraint eval_runs_id_skill_unique unique (id, skill_id),
  constraint eval_runs_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
  constraint eval_runs_eval_set_skill_fkey foreign key (eval_set_id, skill_id) references eval_sets(id, skill_id)
);

create table case_results (
  run_id text not null,
  skill_id text not null,
  case_version_id text not null,
  passed boolean not null,
  score integer not null,
  result_artifact_id text references artifacts(id),
  created_at timestamptz not null default now(),
  primary key (run_id, case_version_id),
  constraint case_results_score_pass_fail check (score in (0, 1)),
  constraint case_results_run_skill_fkey foreign key (run_id, skill_id) references eval_runs(id, skill_id),
  constraint case_results_case_skill_fkey foreign key (case_version_id, skill_id) references eval_case_versions(id, skill_id)
);

create table jobs (
  id text primary key,
  type text not null,
  status text not null default 'queued',
  payload jsonb not null,
  result_ref text,
  attempts integer not null default 0,
  locked_by text,
  last_heartbeat_at timestamptz,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  created_by text not null,
  error text,
  constraint jobs_status_check check (status in ('queued', 'running', 'succeeded', 'failed', 'canceled'))
);

create table eval_case_runs (
  id text primary key,
  job_id text references jobs(id),
  skill_id text not null,
  skill_version_id text not null,
  eval_set_id text not null,
  case_version_id text not null,
  status text not null,
  environment_tags text[] not null default '{}',
  run_context jsonb not null default '{}'::jsonb,
  run_context_hash text not null,
  passed boolean,
  score integer,
  result_artifact_id text references artifacts(id),
  runner_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  created_by text not null,
  error text,
  constraint eval_case_runs_status_check check (status in ('queued', 'running', 'succeeded', 'failed', 'canceled')),
  constraint eval_case_runs_score_pass_fail check (score is null or score in (0, 1)),
  constraint eval_case_runs_id_skill_unique unique (id, skill_id),
  constraint eval_case_runs_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
  constraint eval_case_runs_eval_set_skill_fkey foreign key (eval_set_id, skill_id) references eval_sets(id, skill_id),
  constraint eval_case_runs_case_skill_fkey foreign key (case_version_id, skill_id) references eval_case_versions(id, skill_id)
);

create table accepted_verifications (
  id text primary key,
  skill_id text not null,
  skill_version_id text not null,
  eval_set_id text not null,
  run_context_hash text not null,
  eval_run_id text not null,
  note text not null default '',
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint accepted_verifications_id_skill_unique unique (id, skill_id),
  constraint accepted_verifications_context_unique unique (skill_id, skill_version_id, eval_set_id, run_context_hash),
  constraint accepted_verifications_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
  constraint accepted_verifications_eval_set_skill_fkey foreign key (eval_set_id, skill_id) references eval_sets(id, skill_id),
  constraint accepted_verifications_eval_run_skill_fkey foreign key (eval_run_id, skill_id) references eval_runs(id, skill_id)
);

create table saved_views (
  id text primary key,
  skill_id text not null references skills(id),
  name text not null,
  view_type text not null,
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint saved_views_type_check check (view_type in ('run_history')),
  constraint saved_views_skill_type_name_unique unique (skill_id, view_type, name)
);

create table groups (
  id text primary key,
  name text not null unique,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by text not null
);

create table group_memberships (
  group_id text not null references groups(id),
  subject_type text not null,
  subject_id text not null,
  created_at timestamptz not null default now(),
  created_by text not null,
  primary key (group_id, subject_type, subject_id),
  constraint group_memberships_subject_type_check check (subject_type in ('user'))
);

create table tag_groups (
  id text primary key,
  display_name text not null,
  description text not null default '',
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by text not null,
  constraint tag_groups_id_format_check check (id ~ '^[A-Za-z0-9_-]+$'),
  constraint tag_groups_display_name_non_empty check (length(btrim(display_name)) > 0)
);

create table tag_values (
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
);

create table skill_tags (
  skill_id text not null references skills(id),
  tag_group_id text not null,
  tag_value text not null,
  created_at timestamptz not null default now(),
  created_by text not null,
  primary key (skill_id, tag_group_id, tag_value),
  constraint skill_tags_tag_value_fkey foreign key (tag_group_id, tag_value) references tag_values(tag_group_id, value)
);

create table role_assignments (
  id text primary key,
  subject_type text not null,
  subject_id text not null,
  resource_type text not null,
  resource_id text not null,
  role text not null,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint role_assignments_subject_type_check check (subject_type in ('user', 'group')),
  constraint role_assignments_resource_type_check check (resource_type in ('skill', 'skill_tag')),
  constraint role_assignments_role_check check (role in ('admin', 'owner', 'maintainer', 'evaluator', 'viewer')),
  constraint role_assignments_scope_unique unique (subject_type, subject_id, resource_type, resource_id, role)
);

create table audit_events (
  id text primary key,
  actor_ref text not null,
  action text not null,
  resource_type text not null,
  resource_id text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index artifacts_namespace_idx on artifacts (namespace);
create index skill_versions_skill_id_idx on skill_versions (skill_id);
create index eval_sets_skill_id_idx on eval_sets (skill_id);
create index eval_cases_skill_id_idx on eval_cases (skill_id);
create index eval_case_versions_skill_id_idx on eval_case_versions (skill_id);
create index eval_case_versions_case_id_idx on eval_case_versions (case_id);
create index eval_set_cases_skill_id_idx on eval_set_cases (skill_id);
create index eval_set_cases_case_id_idx on eval_set_cases (case_id);
create index eval_runs_skill_id_created_at_idx on eval_runs (skill_id, created_at desc);
create index eval_runs_skill_version_id_idx on eval_runs (skill_version_id);
create index eval_runs_eval_set_id_idx on eval_runs (eval_set_id);
create index eval_runs_context_hash_idx on eval_runs (run_context_hash);
create index case_results_skill_id_idx on case_results (skill_id);
create index case_results_case_version_id_idx on case_results (case_version_id);
create index eval_case_runs_skill_id_created_at_idx on eval_case_runs (skill_id, created_at desc);
create index eval_case_runs_skill_version_id_idx on eval_case_runs (skill_version_id);
create index eval_case_runs_eval_set_id_idx on eval_case_runs (eval_set_id);
create index eval_case_runs_case_version_id_idx on eval_case_runs (case_version_id);
create index eval_case_runs_job_id_idx on eval_case_runs (job_id);
create index eval_case_runs_context_hash_idx on eval_case_runs (run_context_hash);
create index accepted_verifications_context_idx on accepted_verifications (skill_id, skill_version_id, eval_set_id, run_context_hash);
create index accepted_verifications_eval_run_id_idx on accepted_verifications (eval_run_id);
create index saved_views_skill_type_idx on saved_views (skill_id, view_type);
create index skill_tags_group_value_idx on skill_tags (tag_group_id, tag_value);
create index tag_groups_sort_idx on tag_groups (sort_order, id);
create index tag_values_group_sort_idx on tag_values (tag_group_id, sort_order, value);
create index group_memberships_subject_idx on group_memberships (subject_type, subject_id);
create index jobs_status_created_at_idx on jobs (status, created_at);
create index role_assignments_subject_idx on role_assignments (subject_type, subject_id);
create index role_assignments_resource_idx on role_assignments (resource_type, resource_id);
create index audit_events_resource_idx on audit_events (resource_type, resource_id, created_at desc);

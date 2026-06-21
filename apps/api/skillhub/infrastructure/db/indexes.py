from __future__ import annotations

from sqlalchemy import Index

from skillhub.infrastructure.db.tables import (
    accepted_verifications,
    artifacts,
    audit_events,
    case_results,
    eval_case_runs,
    eval_case_versions,
    eval_cases,
    eval_runs,
    eval_set_cases,
    eval_sets,
    jobs,
    role_assignments,
    saved_views,
    skill_versions,
)


Index("artifacts_namespace_idx", artifacts.c.namespace)
Index("skill_versions_skill_id_idx", skill_versions.c.skill_id)
Index("eval_sets_skill_id_idx", eval_sets.c.skill_id)
Index("eval_cases_skill_id_idx", eval_cases.c.skill_id)
Index("eval_case_versions_skill_id_idx", eval_case_versions.c.skill_id)
Index("eval_case_versions_case_id_idx", eval_case_versions.c.case_id)
Index("eval_set_cases_skill_id_idx", eval_set_cases.c.skill_id)
Index("eval_set_cases_case_id_idx", eval_set_cases.c.case_id)
Index("eval_runs_skill_id_created_at_idx", eval_runs.c.skill_id, eval_runs.c.created_at.desc())
Index("eval_runs_skill_version_id_idx", eval_runs.c.skill_version_id)
Index("eval_runs_eval_set_id_idx", eval_runs.c.eval_set_id)
Index("eval_runs_context_hash_idx", eval_runs.c.run_context_hash)
Index("case_results_skill_id_idx", case_results.c.skill_id)
Index("case_results_case_version_id_idx", case_results.c.case_version_id)
Index("eval_case_runs_skill_id_created_at_idx", eval_case_runs.c.skill_id, eval_case_runs.c.created_at.desc())
Index("eval_case_runs_skill_version_id_idx", eval_case_runs.c.skill_version_id)
Index("eval_case_runs_eval_set_id_idx", eval_case_runs.c.eval_set_id)
Index("eval_case_runs_case_version_id_idx", eval_case_runs.c.case_version_id)
Index("eval_case_runs_job_id_idx", eval_case_runs.c.job_id)
Index("eval_case_runs_context_hash_idx", eval_case_runs.c.run_context_hash)
Index(
    "accepted_verifications_context_idx",
    accepted_verifications.c.skill_id,
    accepted_verifications.c.skill_version_id,
    accepted_verifications.c.eval_set_id,
    accepted_verifications.c.run_context_hash,
)
Index("accepted_verifications_eval_run_id_idx", accepted_verifications.c.eval_run_id)
Index("saved_views_skill_type_idx", saved_views.c.skill_id, saved_views.c.view_type)
Index("jobs_status_created_at_idx", jobs.c.status, jobs.c.created_at)
Index("role_assignments_resource_idx", role_assignments.c.resource_type, role_assignments.c.resource_id)
Index("audit_events_resource_idx", audit_events.c.resource_type, audit_events.c.resource_id, audit_events.c.created_at.desc())

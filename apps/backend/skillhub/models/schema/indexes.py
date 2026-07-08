from __future__ import annotations

from sqlalchemy import Index

from skillhub.models.schema.tables import (
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
    group_memberships,
    groups,
    jobs,
    notifications,
    publish_records,
    publish_targets,
    review_check_results,
    review_request_publish_targets,
    review_request_reviewers,
    review_requests,
    review_responses,
    role_assignments,
    saved_views,
    skill_builder_messages,
    skill_builder_sessions,
    skill_tags,
    skill_versions,
    tag_groups,
    tag_values,
    worker_heartbeats,
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
Index("review_requests_skill_version_idx", review_requests.c.skill_version_id)
Index("review_request_reviewers_actor_idx", review_request_reviewers.c.reviewer_actor)
Index("review_responses_reviewer_idx", review_responses.c.reviewer_actor)
Index("review_request_publish_targets_target_idx", review_request_publish_targets.c.publish_target_id)
Index("review_check_results_check_idx", review_check_results.c.check_id)
Index("publish_targets_enabled_idx", publish_targets.c.enabled, publish_targets.c.target_key)
Index("publish_records_skill_version_idx", publish_records.c.skill_version_id)
Index("publish_records_target_status_idx", publish_records.c.publish_target_id, publish_records.c.status)
Index("notifications_recipient_idx", notifications.c.recipient_actor_id, notifications.c.created_at.desc())
Index("skill_builder_sessions_actor_idx", skill_builder_sessions.c.actor_ref, skill_builder_sessions.c.created_at.desc())
Index("skill_builder_sessions_status_idx", skill_builder_sessions.c.status, skill_builder_sessions.c.updated_at.desc())
Index("skill_builder_messages_session_idx", skill_builder_messages.c.session_id, skill_builder_messages.c.created_at)
Index("skill_builder_messages_job_id_idx", skill_builder_messages.c.job_id)
Index("worker_heartbeats_last_seen_idx", worker_heartbeats.c.last_seen_at.desc())
Index("saved_views_skill_type_idx", saved_views.c.skill_id, saved_views.c.view_type)
Index("skill_tags_group_value_idx", skill_tags.c.tag_group_id, skill_tags.c.tag_value)
Index("tag_groups_sort_idx", tag_groups.c.sort_order, tag_groups.c.id)
Index("tag_values_group_sort_idx", tag_values.c.tag_group_id, tag_values.c.sort_order, tag_values.c.value)
Index("groups_scope_idx", groups.c.scope_type, groups.c.scope_id, groups.c.name)
Index("group_memberships_subject_idx", group_memberships.c.subject_type, group_memberships.c.subject_id)
Index("jobs_status_created_at_idx", jobs.c.status, jobs.c.created_at)
Index("role_assignments_subject_idx", role_assignments.c.subject_type, role_assignments.c.subject_id)
Index("role_assignments_resource_idx", role_assignments.c.resource_type, role_assignments.c.resource_id)
Index("audit_events_resource_idx", audit_events.c.resource_type, audit_events.c.resource_id, audit_events.c.created_at.desc())

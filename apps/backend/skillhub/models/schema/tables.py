"""Declarative ORM table compatibility exports.

Existing Core operations import this module during the staged Session migration.
New data access code must query the mapped classes from the domain schema modules.
"""

from skillhub.models.schema.access import (
    AuditEvent,
    Group,
    GroupMembership,
    Notification,
    RoleAssignment,
    TagGroup,
    TagGroupCascade,
    TagValue,
)
from skillhub.models.schema.artifacts import Artifact, SavedView
from skillhub.models.schema.base import Base
from skillhub.models.schema.evaluations import (
    AcceptedVerification,
    CaseResult,
    EvalCase,
    EvalCaseRun,
    EvalCaseVersion,
    EvalRun,
    EvalSet,
    EvalSetCase,
)
from skillhub.models.schema.reviews import (
    PublishRecord,
    PublishTarget,
    ReviewCheckResult,
    ReviewRequest,
    ReviewRequestPublishTarget,
    ReviewRequestReviewer,
    ReviewResponse,
)
from skillhub.models.schema.runtime import Job, OpencodeAgent, SkillBuilderMessage, SkillBuilderSession, WorkerHeartbeat
from skillhub.models.schema.skills import Skill, SkillTag, SkillVersion
from skillhub.models.schema.workflows import Workflow, WorkflowCollectionDefinition, WorkflowCollectionRevision, WorkflowSync

metadata = Base.metadata

artifacts = Artifact.__table__
skills = Skill.__table__
skill_versions = SkillVersion.__table__
workflows = Workflow.__table__
workflow_collection_definitions = WorkflowCollectionDefinition.__table__
workflow_collection_revisions = WorkflowCollectionRevision.__table__
workflow_syncs = WorkflowSync.__table__
eval_sets = EvalSet.__table__
eval_cases = EvalCase.__table__
eval_case_versions = EvalCaseVersion.__table__
eval_set_cases = EvalSetCase.__table__
eval_runs = EvalRun.__table__
case_results = CaseResult.__table__
eval_case_runs = EvalCaseRun.__table__
accepted_verifications = AcceptedVerification.__table__
review_requests = ReviewRequest.__table__
review_request_reviewers = ReviewRequestReviewer.__table__
review_responses = ReviewResponse.__table__
publish_targets = PublishTarget.__table__
review_request_publish_targets = ReviewRequestPublishTarget.__table__
review_check_results = ReviewCheckResult.__table__
publish_records = PublishRecord.__table__
notifications = Notification.__table__
opencode_agents = OpencodeAgent.__table__
skill_builder_sessions = SkillBuilderSession.__table__
skill_builder_messages = SkillBuilderMessage.__table__
saved_views = SavedView.__table__
jobs = Job.__table__
worker_heartbeats = WorkerHeartbeat.__table__
skill_tags = SkillTag.__table__
tag_groups = TagGroup.__table__
tag_values = TagValue.__table__
tag_group_cascades = TagGroupCascade.__table__
groups = Group.__table__
group_memberships = GroupMembership.__table__
role_assignments = RoleAssignment.__table__
audit_events = AuditEvent.__table__

from skillhub.models.schema import indexes as _indexes  # noqa: E402,F401

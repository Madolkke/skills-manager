from __future__ import annotations

from dataclasses import dataclass

import pytest

from skillhub.models.errors import FieldInvariantError, InvariantError, PermissionDeniedError
from skillhub.models.entities import ContentRef
from skillhub.models.operations.shared.results import CreateSkillResult, CreateSkillVersionResult
from skillhub.services import AdminService, EvaluationService, ExternalSkillService, ReviewService, SavedViewService, SkillService, VersionService, WorkflowService
from skillhub.services.opencode import sanitize_opencode_providers


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def create_text_artifact(self, **kwargs):
        self.calls.append(("create_text_artifact", kwargs))
        return {"id": "artifact_1", "digest": "digest-bundle"}

    def create_skill(self, **kwargs):
        self.calls.append(("create_skill", kwargs))
        return CreateSkillResult(
            skill_id="skill_1",
            skill_version_id="skill_version_1",
            eval_set_id="eval_set_1",
            version_number=1,
            version="0.0.1",
        )

    def insert_skill_with_initial_version(self, **kwargs):
        self.calls.append(("insert_skill_with_initial_version", kwargs))
        return CreateSkillResult(
            skill_id="skill_1",
            skill_version_id="skill_version_1",
            eval_set_id="eval_set_1",
            version_number=1,
            version=kwargs["version"],
        )

    def skill_update_snapshot(self, **kwargs):
        self.calls.append(("skill_update_snapshot", kwargs))
        return {"id": kwargs["skill_id"], "slug": "old-slug", "owner_ref": "old-owner"}

    def apply_skill_update(self, **kwargs):
        self.calls.append(("apply_skill_update", kwargs))
        return {"id": kwargs["skill_id"], "slug": kwargs["slug"], "owner_ref": kwargs["owner_ref"], "tags": kwargs["tags"] or []}

    def create_skill_version(self, **kwargs):
        self.calls.append(("create_skill_version", kwargs))
        return CreateSkillVersionResult(skill_id=kwargs["skill_id"], skill_version_id="skill_version_2", version_number=2, version="0.0.2")

    def skill_version_create_snapshot(self, **kwargs):
        self.calls.append(("skill_version_create_snapshot", kwargs))
        return {"skill_id": kwargs["skill_id"], "next_version_number": 2, "next_version": "0.0.2"}

    def insert_skill_version(self, **kwargs):
        self.calls.append(("insert_skill_version", kwargs))
        return CreateSkillVersionResult(
            skill_id=kwargs["skill_id"],
            skill_version_id="skill_version_2",
            version_number=kwargs["version_number"],
            version=kwargs["version"],
        )

    def upsert_skill_bundle_for_owner(self, **kwargs):
        self.calls.append(("upsert_skill_bundle_for_owner", kwargs))
        return {"operation": "created", "slug": kwargs["slug"], "bundle_digest": kwargs["bundle_digest"]}

    def external_skill_upsert_snapshot(self, **kwargs):
        self.calls.append(("external_skill_upsert_snapshot", kwargs))
        return {
            "operation": "created",
            "skill_id": "skill_1",
            "eval_set_id": "eval_set_1",
            "current_version_id": None,
            "next_version_number": 1,
            "next_version": "0.0.1",
        }

    def apply_external_skill_upsert(self, **kwargs):
        self.calls.append(("apply_external_skill_upsert", kwargs))
        return {"operation": kwargs["operation"], "slug": kwargs["slug"], "bundle_digest": kwargs["bundle_digest"], "version": kwargs["version"]}

    def create_review_request(self, **kwargs):
        self.calls.append(("create_review_request", kwargs))
        return {"id": "review_1"}

    def open_review_request(self, **kwargs):
        self.calls.append(("open_review_request", kwargs))
        return {"review_id": "review_1", "skill_slug": "skill-one", "reviewers": ["alice", "bob"]}

    def attach_review_publish_targets(self, **kwargs):
        self.calls.append(("attach_review_publish_targets", kwargs))

    def create_review_notifications(self, **kwargs):
        self.calls.append(("create_review_notifications", kwargs))

    def record_review_created_audit(self, **kwargs):
        self.calls.append(("record_review_created_audit", kwargs))

    def review_detail(self, **kwargs):
        self.calls.append(("review_detail", kwargs))
        return {"id": kwargs["review_id"]}

    def reviewer_candidates(self, **kwargs):
        self.calls.append(("reviewer_candidates", kwargs))
        return {"skill_id": kwargs["skill_id"], "groups": []}

    def review_closure_snapshot(self, **kwargs):
        self.calls.append(("review_closure_snapshot", kwargs))
        return {
            "reviewer_count": 2,
            "responses": [{"score": 1}, {"score": 1}],
            "publish_targets": [
                {"publish_target_id": "target_auto", "auto_submit_on_pass": True},
                {"publish_target_id": "target_manual", "auto_submit_on_pass": False},
            ],
        }

    def apply_review_closure(self, **kwargs):
        self.calls.append(("apply_review_closure", kwargs))
        return {
            "id": kwargs["review_id"],
            "status": "closed",
            "auto_publish_target_ids": kwargs["auto_publish_target_ids"],
            "publish_records": [
                {
                    "id": "publish_auto",
                    "status": "pending_confirmation",
                    "publish_target": {"auto_publish_enabled": True},
                }
            ],
        }

    def create_publish_record(self, **kwargs):
        self.calls.append(("create_publish_record", kwargs))
        return {"id": "publish_record_1", **kwargs}

    def publish_request_snapshot(self, **kwargs):
        self.calls.append(("publish_request_snapshot", kwargs))
        return {
            "target": {
                "enabled": True,
                "gate_expression": {"type": "group", "op": "and", "children": [{"type": "check", "check_id": "min_responses", "params": {"min": 1}}]},
            },
            "reviewer_count": 1,
            "responses": [{"score": 1}],
            "stored_checks": [],
        }

    def apply_publish_request(self, **kwargs):
        self.calls.append(("apply_publish_request", kwargs))
        return {"id": "publish_record_1", "check_snapshot": kwargs["check_snapshot"]}

    def review_response_snapshot(self, **kwargs):
        self.calls.append(("review_response_snapshot", kwargs))
        return {
            "review": {"id": kwargs["review_id"], "skill_id": "skill_1", "status": "open"},
            "is_reviewer": True,
            "response_exists": False,
        }

    def apply_review_response(self, **kwargs):
        self.calls.append(("apply_review_response", kwargs))
        return {"id": kwargs["review_id"], "responses": [{"reviewer_actor": kwargs["actor"], "score": kwargs["score"]}]}

    def publish_confirmation_snapshot(self, **kwargs):
        self.calls.append(("publish_confirmation_snapshot", kwargs))
        return {
            "record": {"id": kwargs["publish_record_id"], "status": "pending_confirmation"},
            "release_payload": {
                "publish_record_id": kwargs["publish_record_id"],
                "publish_target_id": "target_1",
                "publish_target_key": "yunxi",
                "publish_target_name": "云析",
                "publish_target_config": {},
                "skill_id": "skill_1",
                "skill_slug": "demo",
                "skill_version_id": "version_1",
                "version": "0.0.1",
                "content_digest": "digest",
                "bundle_artifact_id": None,
                "content_ref": {},
                "review_request_id": "review_1",
                "review_check_results": [],
                "requested_by": "maintainer",
                "confirmed_by": kwargs["actor"],
            },
        }

    def apply_publish_confirmation(self, **kwargs):
        self.calls.append(("apply_publish_confirmation", kwargs))
        return {"id": kwargs["publish_record_id"], "status": "released", "metadata": {"release_result": kwargs["release_result"]}}

    def apply_publish_failure(self, **kwargs):
        self.calls.append(("apply_publish_failure", kwargs))
        return {"id": kwargs["publish_record_id"], "status": "failed", "metadata": {"release_error": kwargs["error_message"]}}

    def publish_cancellation_snapshot(self, **kwargs):
        self.calls.append(("publish_cancellation_snapshot", kwargs))
        return {"record": {"id": kwargs["publish_record_id"], "status": "pending_confirmation"}}

    def apply_publish_cancellation(self, **kwargs):
        self.calls.append(("apply_publish_cancellation", kwargs))
        return {"id": kwargs["publish_record_id"], "status": "cancelled"}

    def list_saved_views(self, **kwargs):
        self.calls.append(("list_saved_views", kwargs))
        return []

    def insert_saved_view(self, **kwargs):
        self.calls.append(("insert_saved_view", kwargs))
        return {"id": "view_1", **kwargs}

    def delete_saved_view_record(self, **kwargs):
        self.calls.append(("delete_saved_view_record", kwargs))
        return {"ok": True}

    def insert_eval_set(self, **kwargs):
        self.calls.append(("insert_eval_set", kwargs))
        return {"id": "eval_set_1", **kwargs}

    def rename_eval_set(self, **kwargs):
        self.calls.append(("rename_eval_set", kwargs))
        return {"id": kwargs["eval_set_id"], **kwargs}

    def create_eval_case(self, **kwargs):
        self.calls.append(("create_eval_case", kwargs))
        return {"eval_case_id": "case_1", **kwargs}

    def eval_case_create_snapshot(self, **kwargs):
        self.calls.append(("eval_case_create_snapshot", kwargs))
        return {"skill_id": kwargs["skill_id"], "eval_set_id": kwargs["eval_set_id"] or "eval_set_primary"}

    def insert_eval_case(self, **kwargs):
        self.calls.append(("insert_eval_case", kwargs))
        return {"eval_case_id": "case_1", **kwargs}

    def create_eval_cases_batch(self, **kwargs):
        self.calls.append(("create_eval_cases_batch", kwargs))
        return {"created": len(kwargs["cases"]), **kwargs}

    def insert_eval_cases_batch(self, **kwargs):
        self.calls.append(("insert_eval_cases_batch", kwargs))
        return {"created": len(kwargs["cases"]), **kwargs}

    def create_eval_case_version(self, **kwargs):
        self.calls.append(("create_eval_case_version", kwargs))
        return {"eval_case_version_id": "casever_1", **kwargs}

    def eval_case_version_create_snapshot(self, **kwargs):
        self.calls.append(("eval_case_version_create_snapshot", kwargs))
        return {"case_id": kwargs["case_id"], "skill_id": "skill_1", "eval_set_id": kwargs["eval_set_id"] or "eval_set_primary", "next_version_number": 2}

    def insert_eval_case_version(self, **kwargs):
        self.calls.append(("insert_eval_case_version", kwargs))
        return {"eval_case_version_id": "casever_1", **kwargs}

    def enqueue_eval_case_run(self, **kwargs):
        self.calls.append(("enqueue_eval_case_run", kwargs))
        return {"eval_case_run_id": "run_1", **kwargs}

    def eval_case_run_enqueue_snapshot(self, **kwargs):
        self.calls.append(("eval_case_run_enqueue_snapshot", kwargs))
        return {"skill_id": "skill_1", "run_context_hash": "hash"}

    def insert_eval_case_run(self, **kwargs):
        self.calls.append(("insert_eval_case_run", kwargs))
        return {"eval_case_run_id": "run_1", **kwargs}

    def aggregate_eval_run(self, **kwargs):
        self.calls.append(("aggregate_eval_run", kwargs))
        return {"eval_run_id": "evalrun_1", **kwargs}

    def eval_run_aggregation_snapshot(self, **kwargs):
        self.calls.append(("eval_run_aggregation_snapshot", kwargs))
        return {
            "case_version_ids": ["casever_1", "casever_2"],
            "latest_case_runs": {
                "casever_1": {"passed": True, "score": 1, "result_artifact_id": "artifact_1"},
                "casever_2": {"passed": False, "score": 0, "result_artifact_id": None},
            },
        }

    def insert_aggregated_eval_run(self, **kwargs):
        self.calls.append(("insert_aggregated_eval_run", kwargs))
        return {"eval_run_id": "evalrun_1", **kwargs}


@dataclass
class FakeBundle:
    slug: str = "reviewer"
    manifest_text: str = "{}"
    entry_path: str = "reviewer/SKILL.md"
    description: str = "Review code."
    file_count: int = 2
    digest: str = "digest-input"


def skill_zip_bytes(slug: str = "external-test", body: str = "Use carefully.") -> bytes:
    from io import BytesIO
    from zipfile import ZipFile

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("SKILL.md", f"---\nname: {slug}\ndescription: External test skill.\n---\n{body}\n")
    return buffer.getvalue()


def test_skill_service_import_skill_stores_bundle_then_creates_skill() -> None:
    store = FakeStore()
    service = SkillService(store)

    result = service.import_skill(
        bundle=FakeBundle(),
        owner_ref="owner",
        version="1.0.0",
        tags=[{"group_id": "domain", "value": "api"}],
        actor="actor",
    )

    assert [name for name, _ in store.calls] == ["create_text_artifact", "insert_skill_with_initial_version"]
    assert store.calls[0][1]["namespace"] == "skill-import:reviewer"
    create_args = store.calls[1][1]
    assert create_args["content_ref"] == ContentRef(kind="artifact", locator="artifact:artifact_1", digest="digest-bundle", path="reviewer/SKILL.md")
    assert create_args["change_summary"] == "Imported standard skill bundle with 2 files."
    assert result["skill_id"] == "skill_1"
    assert result["bundle_artifact_id"] == "artifact_1"


def test_skill_service_import_skill_parses_source_before_creating_skill() -> None:
    store = FakeStore()
    service = SkillService(store)

    result = service.import_skill(
        source={
            "kind": "files",
            "files": [
                {
                    "path": "SKILL.md",
                    "content_text": "---\nname: parsed-skill\ndescription: Parsed skill.\n---\nBody\n",
                }
            ],
        },
        owner_ref="owner",
        version=None,
        tags=[],
        actor="actor",
    )

    assert result["slug"] == "parsed-skill"
    assert [name for name, _ in store.calls] == ["create_text_artifact", "insert_skill_with_initial_version"]


def test_skill_service_creates_initial_skill_version_with_defaults() -> None:
    store = FakeStore()
    service = SkillService(store)
    content_ref = ContentRef(kind="skill_bundle", locator="memory:bundle", digest="digest")

    result = service.create_skill(
        slug="created-skill",
        owner_ref="owner",
        content_ref=content_ref,
        change_summary=None,
        version=None,
        tags=[],
        actor="actor",
    )

    assert result.version == "0.0.1"
    assert [name for name, _ in store.calls] == ["insert_skill_with_initial_version"]
    args = store.calls[0][1]
    assert args["change_summary"] == "Initial version."
    assert args["version"] == "0.0.1"
    assert args["creator_role_reason"] == "skill.creator"


def test_skill_service_updates_skill_after_snapshot() -> None:
    store = FakeStore()
    service = SkillService(store)

    result = service.update_skill(skill_id="skill_1", slug=None, owner_ref="new-owner", tags=None, actor="actor")

    assert result["slug"] == "old-slug"
    assert result["owner_ref"] == "new-owner"
    assert [name for name, _ in store.calls] == ["skill_update_snapshot", "apply_skill_update"]
    assert store.calls[1][1]["require_permission"] is True


def test_external_skill_service_parses_zip_archive_before_upsert() -> None:
    store = FakeStore()
    service = ExternalSkillService(store)

    result = service.upsert_skill_bundle_for_owner(
        owner_ref="external-user",
        archive=skill_zip_bytes("external-service"),
        actor="external-user",
        tags=[{"group_id": "domain", "value": "api"}],
        change_summary=None,
        display_name=None,
        version=None,
        make_current=True,
    )

    assert result["slug"] == "external-service"
    assert [name for name, _ in store.calls] == ["external_skill_upsert_snapshot", "apply_external_skill_upsert"]
    upsert_args = store.calls[1][1]
    assert upsert_args["slug"] == "external-service"
    assert upsert_args["file_count"] == 1
    assert upsert_args["entry_path"] == "SKILL.md"
    assert upsert_args["version"] == "0.0.1"


def test_opencode_provider_sanitizer_removes_sensitive_fields() -> None:
    result = sanitize_opencode_providers(
        {
            "default": {"deepseek": "deepseek-v4-pro"},
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "source": "env",
                    "env": ["DEEPSEEK_API_KEY"],
                    "key": "secret",
                    "options": {"apiKey": "secret"},
                    "models": {
                        "deepseek-v4-pro": {
                            "id": "deepseek-v4-pro",
                            "name": "DeepSeek V4 Pro",
                            "family": "deepseek-thinking",
                            "status": "active",
                            "api": {"url": "https://api.deepseek.com"},
                            "headers": {"authorization": "secret"},
                            "capabilities": {"toolcall": True},
                            "limit": {"context": 1000},
                        }
                    },
                }
            ],
        }
    )

    provider = result["providers"][0]
    model = provider["models"][0]

    assert provider["default_model_id"] == "deepseek-v4-pro"
    assert provider["models"] == [model]
    assert model == {
        "id": "deepseek-v4-pro",
        "name": "DeepSeek V4 Pro",
        "family": "deepseek-thinking",
        "status": "active",
        "capabilities": {"toolcall": True},
        "limit": {"context": 1000},
    }
    assert "secret" not in str(result)
    assert "DEEPSEEK_API_KEY" not in str(result)
    assert "api.deepseek.com" not in str(result)


def test_version_service_requires_content_ref_or_source() -> None:
    service = VersionService(FakeStore())

    with pytest.raises(InvariantError):
        service.create_skill_version(
            skill_id="skill_1",
            source=None,
            content_ref=None,
            change_summary=None,
            display_name=None,
            version=None,
            make_current=True,
            actor="actor",
        )


def test_version_service_creates_version_from_content_ref() -> None:
    store = FakeStore()
    service = VersionService(store)
    content_ref = ContentRef(kind="skill_bundle", locator="memory:reviewer", digest="digest")

    result = service.create_skill_version(
        skill_id="skill_1",
        source=None,
        content_ref=content_ref,
        change_summary=None,
        display_name="Candidate",
        version=None,
        make_current=True,
        actor="actor",
    )

    assert result.skill_version_id == "skill_version_2"
    assert store.calls == [
        (
            "skill_version_create_snapshot",
            {
                "skill_id": "skill_1",
                "actor": "actor",
            },
        ),
        (
            "insert_skill_version",
            {
                "skill_id": "skill_1",
                "content_ref": content_ref,
                "change_summary": "Updated skill version.",
                "display_name": "Candidate",
                "version_number": 2,
                "version": "0.0.2",
                "actor": "actor",
                "make_current": True,
            },
        )
    ]


def test_review_service_creates_review_with_publish_target_snapshot() -> None:
    store = FakeStore()
    service = ReviewService(store)
    targets = [{"publish_target_id": "target_1", "auto_submit_on_pass": True}]

    result = service.create_review_request(skill_id="skill_1", skill_version_id="version_1", publish_targets=targets, actor="maintainer")

    assert result == {"id": "review_1"}
    assert [name for name, _ in store.calls] == [
        "open_review_request",
        "attach_review_publish_targets",
        "create_review_notifications",
        "record_review_created_audit",
        "review_detail",
    ]
    assert store.calls[1][1]["publish_targets"] == targets
    assert store.calls[0][1]["reviewer_sources"] == []
    assert store.calls[2][1]["reviewers"] == ["alice", "bob"]
    assert store.calls[3][1]["reviewer_count"] == 2


def test_review_service_forwards_explicit_reviewer_sources() -> None:
    store = FakeStore()
    service = ReviewService(store)
    sources = [{"subject_type": "group", "subject_id": "group_1"}, {"subject_type": "user", "subject_id": "alice"}]

    service.create_review_request(
        skill_id="skill_1",
        skill_version_id="version_1",
        publish_targets=[],
        reviewer_sources=sources,
        actor="maintainer",
    )

    assert store.calls[0] == (
        "open_review_request",
        {
            "skill_id": "skill_1",
            "skill_version_id": "version_1",
            "reviewer_sources": sources,
            "actor": "maintainer",
        },
    )


def test_review_service_lists_reviewer_candidates() -> None:
    store = FakeStore()
    service = ReviewService(store)

    result = service.reviewer_candidates(skill_id="skill_1", actor="maintainer")

    assert result == {"skill_id": "skill_1", "groups": []}
    assert store.calls == [("reviewer_candidates", {"skill_id": "skill_1", "actor": "maintainer"})]


def test_review_service_closes_review_with_domain_policy_decision() -> None:
    store = FakeStore()
    service = ReviewService(store)

    closed = service.close_review(review_id="review_1", actor="maintainer")

    assert closed == {"id": "review_1"}
    assert [name for name, _ in store.calls] == ["review_closure_snapshot", "apply_review_closure", "publish_confirmation_snapshot", "apply_publish_confirmation", "review_detail"]
    assert store.calls[1][1]["summary"]["checks_passed"] is True
    assert store.calls[1][1]["auto_publish_target_ids"] == ["target_auto"]
    assert store.calls[3][1]["actor"] == "system:auto_publish"


def test_review_service_records_auto_publish_failure_without_reopening_review(monkeypatch) -> None:
    def fail_publish_release(_payload):
        raise RuntimeError("publish hook failed")

    monkeypatch.setattr("skillhub.services.reviews.perform_publish_release", fail_publish_release)
    store = FakeStore()
    service = ReviewService(store)

    closed = service.close_review(review_id="review_1", actor="maintainer")

    assert closed == {"id": "review_1"}
    assert [name for name, _ in store.calls] == ["review_closure_snapshot", "apply_review_closure", "publish_confirmation_snapshot", "apply_publish_failure", "review_detail"]
    assert store.calls[3][1]["actor"] == "system:auto_publish"
    assert store.calls[3][1]["error_message"] == "publish hook failed"


def test_review_service_submits_response_after_snapshot_validation() -> None:
    store = FakeStore()
    service = ReviewService(store)

    result = service.submit_review_response(review_id="review_1", score=1, comment=" LGTM ", actor="alice")

    assert result["responses"] == [{"reviewer_actor": "alice", "score": 1}]
    assert [name for name, _ in store.calls] == ["review_response_snapshot", "apply_review_response"]
    assert store.calls[1][1]["comment"] == "LGTM"
    assert store.calls[1][1]["skill_id"] == "skill_1"


def test_review_service_rejects_invalid_score_before_store_write() -> None:
    store = FakeStore()
    service = ReviewService(store)

    with pytest.raises(InvariantError):
        service.submit_review_response(review_id="review_1", score=2, comment="", actor="alice")

    assert store.calls == []


def test_review_service_rejects_non_reviewer_response() -> None:
    class NonReviewerStore(FakeStore):
        def review_response_snapshot(self, **kwargs):
            self.calls.append(("review_response_snapshot", kwargs))
            return {
                "review": {"id": kwargs["review_id"], "skill_id": "skill_1", "status": "open"},
                "is_reviewer": False,
                "response_exists": False,
            }

    store = NonReviewerStore()
    service = ReviewService(store)

    with pytest.raises(PermissionDeniedError):
        service.submit_review_response(review_id="review_1", score=1, comment="", actor="mallory")

    assert [name for name, _ in store.calls] == ["review_response_snapshot"]


def test_review_service_creates_publish_record() -> None:
    store = FakeStore()
    service = ReviewService(store)

    record = service.create_publish_record(
        skill_id="skill_1",
        skill_version_id="version_1",
        review_request_id="review_1",
        publish_target_id="target_1",
        actor="maintainer",
    )

    assert record["id"] == "publish_record_1"
    assert [name for name, _ in store.calls] == ["publish_request_snapshot", "apply_publish_request"]
    assert record["check_snapshot"][0]["check_id"] == "publish_gate"
    assert store.calls[1][1]["check_snapshot"][0]["passed"] is True


def test_admin_service_confirms_publish_record_with_release_hook_result() -> None:
    store = FakeStore()
    service = AdminService(store)

    result = service.confirm_publish_record(publish_record_id="publish_1")

    assert result["status"] == "released"
    assert [name for name, _ in store.calls] == ["publish_confirmation_snapshot", "apply_publish_confirmation"]
    release_result = store.calls[1][1]["release_result"]
    assert release_result["mode"] == "noop"
    assert release_result["metadata"]["publish_target_key"] == "yunxi"


def test_admin_service_rejects_non_pending_publish_confirmation() -> None:
    class ReleasedPublishStore(FakeStore):
        def publish_confirmation_snapshot(self, **kwargs):
            self.calls.append(("publish_confirmation_snapshot", kwargs))
            return {"record": {"id": kwargs["publish_record_id"], "status": "released"}, "release_payload": {}}

    store = ReleasedPublishStore()
    service = AdminService(store)

    with pytest.raises(InvariantError):
        service.confirm_publish_record(publish_record_id="publish_1")

    assert [name for name, _ in store.calls] == ["publish_confirmation_snapshot"]


def test_admin_service_cancels_publish_record_after_status_check() -> None:
    store = FakeStore()
    service = AdminService(store)

    result = service.cancel_publish_record(publish_record_id="publish_1")

    assert result["status"] == "cancelled"
    assert [name for name, _ in store.calls] == ["publish_cancellation_snapshot", "apply_publish_cancellation"]


def test_saved_view_service_normalizes_config_before_insert() -> None:
    store = FakeStore()
    service = SavedViewService(store)

    result = service.create_saved_view(
        skill_id="skill_1",
        name=" My View ",
        view_type="run_history",
        config={"skill_version_id": " version_1 ", "eval_set_id": "all", "unknown": "ignored"},
        actor="owner",
    )

    assert result["name"] == "My View"
    assert [name for name, _ in store.calls] == ["insert_saved_view"]
    assert store.calls[0][1]["config"] == {"skill_version_id": "version_1"}


def test_saved_view_service_rejects_invalid_type_and_blank_name() -> None:
    store = FakeStore()
    service = SavedViewService(store)

    with pytest.raises(InvariantError):
        service.list_saved_views(skill_id="skill_1", view_type="dashboard")
    with pytest.raises(FieldInvariantError):
        service.create_saved_view(skill_id="skill_1", name="  ", view_type="run_history", config={}, actor="owner")

    assert store.calls == []


def test_evaluation_service_normalizes_eval_set_names() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    created = service.create_eval_set(skill_id="skill_1", name=" Smoke ", description=" daily ", actor="owner")
    updated = service.update_eval_set(eval_set_id="eval_set_1", name=" Regression ", description=None, actor="owner")

    assert created["name"] == "Smoke"
    assert created["description"] == "daily"
    assert updated["name"] == "Regression"
    assert updated["description"] == ""
    assert [name for name, _ in store.calls] == ["insert_eval_set", "rename_eval_set"]


def test_evaluation_service_rejects_blank_eval_set_name() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    with pytest.raises(FieldInvariantError):
        service.create_eval_set(skill_id="skill_1", name=" ", description="", actor="owner")

    assert store.calls == []


def test_evaluation_service_normalizes_eval_case_payload() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    service.create_eval_case(
        skill_id="skill_1",
        eval_set_id="eval_set_1",
        title=" Case title ",
        steps=[
            {
                "input": " 输出 hello ",
                "assertions": [{"assertion_template_id": "agent_output_contains", "assertion_params": {"text": "hello"}}],
            }
        ],
        workspace_name=None,
        workspace_base64=None,
        runner_config={"model_provider_id": " deepseek ", "model_id": " v3 "},
        actor="owner",
        notes=None,
    )

    assert [name for name, _ in store.calls] == ["eval_case_create_snapshot", "insert_eval_case"]
    args = store.calls[1][1]
    assert args["title"] == "Case title"
    assert args["runner_config"] == {"timeout_seconds": None}
    assert args["steps"][0]["id"] == "step-1"
    assert args["steps"][0]["assertions"][0]["id"] == "assertion-1"


def test_evaluation_service_ignores_partial_legacy_model_config() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    service.create_eval_case(
        skill_id="skill_1",
        eval_set_id="eval_set_1",
        title="Case title",
        steps=[{"input": "hello", "assertions": [{"assertion_template_id": "agent_output_contains", "assertion_params": {"text": "hello"}}]}],
        workspace_name=None,
        workspace_base64=None,
        runner_config={"model_provider_id": "deepseek"},
        actor="owner",
        notes=None,
    )

    assert [name for name, _ in store.calls] == ["eval_case_create_snapshot", "insert_eval_case"]
    assert store.calls[1][1]["runner_config"] == {"timeout_seconds": None}


def test_evaluation_service_normalizes_batch_eval_cases_before_insert() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    result = service.create_eval_cases_batch(
        skill_id="skill_1",
        eval_set_id="eval_set_1",
        cases=[
            {
                "title": " Batch case ",
                "steps": [{"input": "hello", "assertions": [{"assertion_template_id": "agent_output_contains", "assertion_params": {"text": "hello"}}]}],
                "runner_config": {},
            }
        ],
        actor="owner",
    )

    assert result["created"] == 1
    assert [name for name, _ in store.calls] == ["eval_case_create_snapshot", "insert_eval_cases_batch"]
    args = store.calls[1][1]
    assert args["cases"][0]["title"] == "Batch case"
    assert args["cases"][0]["steps"][0]["id"] == "step-1"


def test_evaluation_service_rejects_empty_batch_before_store_read() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    with pytest.raises(InvariantError):
        service.create_eval_cases_batch(skill_id="skill_1", eval_set_id="eval_set_1", cases=[], actor="owner")

    assert store.calls == []


def test_evaluation_service_creates_eval_case_version_from_snapshot() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    result = service.create_eval_case_version(
        case_id="case_1",
        eval_set_id="eval_set_1",
        title=" Updated case ",
        steps=[{"input": "hello", "assertions": [{"assertion_template_id": "agent_output_contains", "assertion_params": {"text": "hello"}}]}],
        workspace_name=None,
        workspace_base64=None,
        preserve_workspace=True,
        runner_config={},
        actor="owner",
        notes=None,
        make_current=True,
    )

    assert result["version_number"] == 2
    assert [name for name, _ in store.calls] == ["eval_case_version_create_snapshot", "insert_eval_case_version"]
    args = store.calls[1][1]
    assert args["skill_id"] == "skill_1"
    assert args["eval_set_id"] == "eval_set_1"
    assert args["title"] == "Updated case"
    assert args["steps"][0]["assertions"][0]["id"] == "assertion-1"


def test_evaluation_service_normalizes_run_environment_before_enqueue() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    result = service.enqueue_eval_case_run(
        skill_version_id="skillver_1",
        eval_set_id="eval_set_1",
        case_version_id="casever_1",
        actor="evaluator",
        environment_tags=["windows", "codex", "windows"],
        run_context={"b": 2, "a": 1},
    )

    assert result["environment_tags"] == ["codex", "windows"]
    assert result["run_context"] == {"a": 1, "b": 2}
    assert result["skill_id"] == "skill_1"
    assert [name for name, _ in store.calls] == ["eval_case_run_enqueue_snapshot", "insert_eval_case_run"]


def test_evaluation_service_rejects_non_json_run_context_before_write() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    with pytest.raises(InvariantError):
        service.aggregate_eval_run(
            skill_version_id="skillver_1",
            eval_set_id="eval_set_1",
            actor="evaluator",
            environment_tags=[],
            run_context={"bad": object()},
        )

    assert store.calls == []


def test_evaluation_service_aggregates_from_snapshot_decision() -> None:
    store = FakeStore()
    service = EvaluationService(store)

    result = service.aggregate_eval_run(
        skill_version_id="skillver_1",
        eval_set_id="eval_set_1",
        actor="evaluator",
        environment_tags=["linux", "linux"],
        run_context={"target": "prod"},
    )

    assert result["summary"] == {"passed": 1, "failed": 1, "total": 2}
    assert result["case_results"][0]["case_version_id"] == "casever_1"
    assert [name for name, _ in store.calls] == ["eval_run_aggregation_snapshot", "insert_aggregated_eval_run"]
    assert store.calls[1][1]["environment_tags"] == ["linux"]


def test_workflow_service_import_returns_detail_and_collection_mappings() -> None:
    class WorkflowImportStore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def import_workflow_bundle(self, **kwargs):
            self.calls.append(("import_workflow_bundle", kwargs))
            return {"revision": 2, "collection_mappings": [{"local_id": "status", "definition_id": "collection_1", "revision": 1}]}

        def workflow_detail(self, **kwargs):
            self.calls.append(("workflow_detail", kwargs))
            return {"id": "workflow_1", "revision": 2, "document": {"documentType": "workflow_bundle"}}

    store = WorkflowImportStore()
    service = WorkflowService(store)  # type: ignore[arg-type]
    bundle = {
        "documentType": "workflow_import_bundle",
        "workflow": {
            "metadata": {"name": "Imported", "code": "", "description": "Draft", "industry": "", "device": "", "versions": []},
            "inputs": [],
            "deviceRoles": [],
            "nodes": [],
        },
        "collections": [],
    }

    result = service.import_workflow_bundle(skill_id="skill_1", bundle=bundle, actor="owner")

    assert result["revision"] == 2
    assert result["import_result"]["collection_mappings"][0]["definition_id"] == "collection_1"
    assert [name for name, _ in store.calls] == ["import_workflow_bundle", "workflow_detail"]

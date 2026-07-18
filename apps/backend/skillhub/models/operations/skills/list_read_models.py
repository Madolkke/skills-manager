from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select

from skillhub.models.schema import orm


class ListReadModelMixin:
    def list_skills(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = connection.execute(
                orm.select_entity(orm.Skill).where(orm.Skill.lifecycle_status == "active").order_by(orm.Skill.slug)
            ).mappings().all()
            if not rows:
                return []
            skill_ids = [str(row["id"]) for row in rows]
            tags = self._list_skill_tags(connection, skill_ids)
            versions = self._list_current_versions(connection, rows)
            eval_sets = self._list_primary_eval_sets(connection, skill_ids)
            latest_runs = self._list_latest_eval_runs(connection, versions, eval_sets)
            workflows = self._list_workflow_summaries(connection, rows)
            return [
                {
                    "skill": self._list_skill_record(row, tags),
                    "summary": {
                        "skill": self._list_skill_record(row, tags),
                        "current_version": versions.get(str(row["current_version_id"])),
                        "primary_eval_set": eval_sets.get(str(row["id"])),
                        "latest_accepted_eval_run": latest_runs.get(str(row["id"])),
                    },
                    "workflow": workflows.get(str(row["id"])),
                }
                for row in rows
            ]

    def _list_skill_tags(self, connection, skill_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        rows = connection.execute(
            select(
                orm.SkillTag.skill_id,
                orm.SkillTag.tag_group_id,
                orm.TagGroup.display_name.label("group_display_name"),
                orm.SkillTag.tag_value,
                orm.TagValue.display_name.label("value_display_name"),
            )
            .join(orm.TagGroup, orm.TagGroup.id == orm.SkillTag.tag_group_id)
            .join(
                orm.TagValue,
                (orm.TagValue.tag_group_id == orm.SkillTag.tag_group_id) & (orm.TagValue.value == orm.SkillTag.tag_value),
            )
            .where(orm.SkillTag.skill_id.in_(skill_ids))
            .order_by(orm.TagGroup.sort_order, orm.SkillTag.tag_group_id, orm.TagValue.sort_order, orm.SkillTag.tag_value)
        ).mappings().all()
        if not rows:
            return {}
        groups = self._tag_group_map(connection)
        relations = self._tag_group_relations(connection)
        keys_by_skill: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for row in rows:
            keys_by_skill[str(row["skill_id"])].add((str(row["tag_group_id"]), str(row["tag_value"])))
        validity = {
            skill_id: self._tag_path_validity(connection, keys, groups=groups, relations=relations)
            for skill_id, keys in keys_by_skill.items()
        }
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            skill_id = str(row["skill_id"])
            key = (str(row["tag_group_id"]), str(row["tag_value"]))
            result[skill_id].append(
                {
                    "group_id": row["tag_group_id"],
                    "group_display_name": row["group_display_name"],
                    "value": row["tag_value"],
                    "value_display_name": row["value_display_name"],
                    "path_valid": validity[skill_id][key],
                }
            )
        return dict(result)

    def _list_current_versions(self, connection, skills) -> dict[str, dict[str, Any]]:
        version_ids = [str(row["current_version_id"]) for row in skills if row["current_version_id"]]
        if not version_ids:
            return {}
        version_rows = connection.execute(
            orm.select_entity(orm.SkillVersion).where(orm.SkillVersion.id.in_(version_ids))
        ).mappings().all()
        sync_rows = connection.execute(
            select(
                orm.WorkflowSync.skill_version_id,
                orm.WorkflowSync.workflow_id,
                orm.WorkflowSync.workflow_revision,
                orm.WorkflowSync.generator_version,
                orm.WorkflowSync.created_at,
            ).where(orm.WorkflowSync.skill_version_id.in_(version_ids))
        ).mappings().all()
        syncs = {str(row["skill_version_id"]): self._row_dict(row) for row in sync_rows}
        artifact_ids = {
            str(content_ref["locator"]).split(":", 1)[1]
            for row in version_rows
            if isinstance((content_ref := row["content_ref"]), dict)
            and content_ref.get("kind") == "artifact"
            and str(content_ref.get("locator", "")).startswith("artifact:")
        }
        artifact_rows = (
            connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id.in_(artifact_ids))).mappings().all()
            if artifact_ids
            else []
        )
        artifacts = {str(row["id"]): self._row_dict(row) for row in artifact_rows}
        result: dict[str, dict[str, Any]] = {}
        for row in version_rows:
            detail = self._row_dict(row)
            detail["workflow_sync"] = syncs.get(str(row["id"]))
            content_ref = detail.get("content_ref")
            if isinstance(content_ref, dict) and str(content_ref.get("locator", "")).startswith("artifact:"):
                artifact = artifacts.get(str(content_ref["locator"]).split(":", 1)[1])
                if artifact is not None:
                    detail["bundle_artifact"] = artifact
                    detail["bundle_files"] = self._bundle_files_from_artifact(artifact)
            result[str(row["id"])] = detail
        return result

    def _list_primary_eval_sets(self, connection, skill_ids: list[str]) -> dict[str, dict[str, Any]]:
        rows = connection.execute(
            orm.select_entity(orm.EvalSet).where(orm.EvalSet.skill_id.in_(skill_ids)).where(orm.EvalSet.name == "Primary")
        ).mappings().all()
        return {str(row["skill_id"]): self._row_dict(row) for row in rows}

    def _list_latest_eval_runs(self, connection, versions, eval_sets) -> dict[str, dict[str, Any]]:
        if not versions or not eval_sets:
            return {}
        rows = connection.execute(
            orm.select_entity(orm.EvalRun)
            .where(orm.EvalRun.skill_version_id.in_(versions))
            .where(orm.EvalRun.eval_set_id.in_(str(item["id"]) for item in eval_sets.values()))
            .where(orm.EvalRun.status == "finished")
            .order_by(desc(orm.EvalRun.created_at), desc(orm.EvalRun.id))
        ).mappings().all()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            eval_set = eval_sets.get(str(row["skill_id"]))
            if eval_set is not None and str(row["eval_set_id"]) == str(eval_set["id"]):
                latest.setdefault(str(row["skill_id"]), self._row_dict(row))
        return latest

    def _list_workflow_summaries(self, connection, skills) -> dict[str, dict[str, Any]]:
        skill_ids = [str(row["id"]) for row in skills]
        workflow_rows = connection.execute(
            orm.select_entity(orm.Workflow).where(orm.Workflow.skill_id.in_(skill_ids))
        ).mappings().all()
        if not workflow_rows:
            return {}
        workflow_ids = [str(row["id"]) for row in workflow_rows]
        sync_rows = connection.execute(
            orm.select_entity(orm.WorkflowSync)
            .where(orm.WorkflowSync.workflow_id.in_(workflow_ids))
            .order_by(orm.WorkflowSync.workflow_revision.desc())
        ).mappings().all()
        latest_syncs: dict[str, Any] = {}
        for row in sync_rows:
            latest_syncs.setdefault(str(row["workflow_id"]), row)
        skills_by_id = {str(row["id"]): row for row in skills}
        result: dict[str, dict[str, Any]] = {}
        for workflow in workflow_rows:
            skill_id = str(workflow["skill_id"])
            result[skill_id] = {
                "id": workflow["id"],
                "skill_id": workflow["skill_id"],
                "revision": workflow["revision"],
                "document_schema_version": workflow["document_schema_version"],
                "updated_at": workflow["updated_at"],
                **self._workflow_sync_status_from_latest(
                    latest=latest_syncs.get(str(workflow["id"])),
                    workflow=workflow,
                    skill=skills_by_id[skill_id],
                ),
            }
        return result

    def _list_skill_record(self, skill, tags: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return {**self._row_dict(skill), "tags": tags.get(str(skill["id"]), [])}

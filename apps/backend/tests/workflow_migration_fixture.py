from __future__ import annotations

from skillhub.models.schema import metadata

COLLECTION_DOCUMENTS = [
    {
        "id": "collection-v3",
        "revision": revision,
        "key": "legacy",
        "metadata": {
            "name": f"旧采集 {revision}",
            "description": "",
            "industry": "",
            "device": "",
            "versions": [],
            "tags": [],
        },
        "spec": {
            "collectionType": "cli",
            "commandTemplate": f"show legacy {revision}",
            "outputSamples": [],
        },
        "inputs": [],
        "outputs": [
            {
                "id": "output-table",
                "key": "table",
                "description": f"旧对象 {revision}",
                "dataType": "object",
            }
        ],
    }
    for revision in (1, 2)
]

WORKFLOW_DOCUMENT = {
    "documentType": "workflow_bundle",
    "workflow": {
        "id": "workflow-v3",
        "revision": 1,
        "metadata": {"name": "迁移", "description": "迁移测试"},
        "inputs": [
            {
                "id": "input-rows",
                "key": "rows",
                "name": "数据行",
                "description": "",
                "dataType": "array",
                "required": True,
            }
        ],
        "deviceRoles": [],
        "nodes": [
            {
                "id": "step-v3",
                "name": "采集旧数据",
                "description": "",
                "isStart": True,
                "collectionCalls": [
                    {
                        "id": "call-v3",
                        "key": "legacy",
                        "name": "旧采集",
                        "definition": {"id": "collection-v3", "revision": 1},
                        "sampleCount": 1,
                        "inputBindings": {},
                    }
                ],
                "topology": [],
                "stepType": "expression",
            }
        ],
    },
    "collectionSnapshots": [COLLECTION_DOCUMENTS[0]],
}


def seed_v3_workflow_state(connection) -> None:
    connection.execute(
        metadata.tables["skills"].insert().values(
            id="skill-v3",
            slug="workflow-v3",
            owner_ref="owner",
        )
    )
    connection.execute(
        metadata.tables["artifacts"].insert().values(
            id="artifact-source",
            kind="workflow_source",
            namespace="migration-test",
            locator="inline:source",
            digest="source-digest",
            media_type="application/json",
            size_bytes=2,
            content_text="{}",
            created_by="owner",
        )
    )
    connection.execute(
        metadata.tables["skill_versions"].insert().values(
            id="skillver-workflow",
            skill_id="skill-v3",
            version_number=1,
            version="1.0.0",
            content_ref={
                "kind": "artifact",
                "locator": "artifact:artifact-source",
                "digest": "legacy-content-digest",
            },
            content_digest="legacy-content-digest",
            change_summary="legacy sync",
            created_by="owner",
        )
    )
    connection.execute(
        metadata.tables["skills"]
        .update()
        .where(metadata.tables["skills"].c.id == "skill-v3")
        .values(current_version_id="skillver-workflow")
    )
    connection.execute(
        metadata.tables["workflows"].insert().values(
            id="workflow-v3",
            skill_id="skill-v3",
            revision=1,
            document_schema_version=3,
            document=WORKFLOW_DOCUMENT,
            document_digest="old-workflow-digest",
            created_by="tester",
            last_saved_by="tester",
        )
    )
    connection.execute(
        metadata.tables["workflow_collection_definitions"].insert().values(
            id="collection-v3",
            latest_revision=2,
            created_by="tester",
        )
    )
    for document in COLLECTION_DOCUMENTS:
        connection.execute(
            metadata.tables["workflow_collection_revisions"].insert().values(
                definition_id="collection-v3",
                revision=document["revision"],
                document_schema_version=3,
                definition=document,
                definition_digest=f"old-{document['revision']}",
                created_by="tester",
            )
        )
    connection.execute(
        metadata.tables["workflow_syncs"].insert().values(
            id="sync-existing",
            workflow_id="workflow-v3",
            workflow_revision=1,
            document_schema_version=3,
            source_artifact_id="artifact-source",
            skill_version_id="skillver-workflow",
            generator_version="workflow-skill-v3",
            created_by="owner",
        )
    )

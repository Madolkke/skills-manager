"""向本地测试数据库填充运营看板演示数据，可重复运行。"""

import argparse
import hashlib
import json
from datetime import datetime, timezone

from analytics_mock_data import DEMO_PREFIX, build_mock_data
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from skillhub.models.schema import orm
from skillhub.models.schema.analytics import AnalyticsCollectionState, SkillCreationFact, SkillVisitEvent
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import verify_database_revision


def seed_demo(session: Session, now: datetime, seed: int) -> dict:
    """仅更新演示专属身份，替换其模拟事件，保留其他业务及真实访问。"""
    skills, events, started = build_mock_data(now, seed=seed)
    for skill in skills:
        identity = skill["id"]
        slug = identity
        version_id = f"{identity}-version"
        artifact_id = f"{identity}-artifact"
        content = f"---\nname: {slug}\ndescription: 运营看板演示用排查 Skill。\n---\n# {skill['name']}\n\n1. 采集设备状态。\n2. 检查异常并给出修复建议。\n"
        digest = hashlib.sha256(content.encode()).hexdigest()
        manifest = json.dumps({"files": [{"path": "SKILL.md", "content_text": content, "sha256": digest,
                                         "size_bytes": len(content.encode())}]}, ensure_ascii=False)
        manifest_digest = hashlib.sha256(manifest.encode()).hexdigest()
        created = skill["created_at"]
        session.execute(insert(orm.Artifact).values(
            id=artifact_id, kind="skill_bundle", namespace=DEMO_PREFIX, locator=f"demo:{artifact_id}", digest=manifest_digest,
            media_type="application/json", size_bytes=len(manifest.encode()), content_text=manifest, created_by="analytics-demo", created_at=created,
        ).on_conflict_do_update(index_elements=[orm.Artifact.id], set_={"content_text": manifest, "digest": manifest_digest,
                                                                      "size_bytes": len(manifest.encode()), "created_at": created}))
        values = {"id": identity, "slug": slug, "display_name": skill["name"], "owner_ref": skill["owner_ref"],
                  "created_at": created, "updated_at": created, "lifecycle_status": "active"}
        session.execute(insert(orm.Skill).values(**values).on_conflict_do_update(index_elements=[orm.Skill.id], set_=values))
        version = {"id": version_id, "skill_id": identity, "version_number": 1, "version": "0.0.1", "display_name": skill["name"],
                   "content_ref": {"kind": "artifact", "locator": f"artifact:{artifact_id}", "digest": manifest_digest, "path": "SKILL.md"},
                   "content_digest": manifest_digest, "change_summary": "运营看板演示初始版本。", "created_by": "analytics-demo", "created_at": created}
        session.execute(insert(orm.SkillVersion).values(**version).on_conflict_do_update(index_elements=[orm.SkillVersion.id], set_=version))
        session.execute(update(orm.Skill).where(orm.Skill.id == identity).values(current_version_id=version_id))
        session.execute(insert(orm.EvalSet).values(id=f"{identity}-evalset", skill_id=identity, name="Primary", description="演示评测集")
                        .on_conflict_do_nothing(index_elements=[orm.EvalSet.id]))
        session.execute(insert(orm.RoleAssignment).values(
            id=f"{identity}-role", subject_type="user", subject_id="product-operator", resource_type="skill", resource_id=identity,
            role="owner", created_by="analytics-demo",
        ).on_conflict_do_nothing(index_elements=[orm.RoleAssignment.id]))
        fact = {"skill_id": identity, "name": skill["name"], "owner_ref": skill["owner_ref"], "created_at": created, "is_demo": True}
        session.execute(insert(SkillCreationFact).values(**fact).on_conflict_do_update(index_elements=[SkillCreationFact.skill_id], set_=fact))
    session.execute(delete(SkillVisitEvent).where(SkillVisitEvent.is_demo.is_(True), SkillVisitEvent.skill_id.startswith(DEMO_PREFIX)))
    session.execute(insert(SkillVisitEvent), events)
    state = session.get(AnalyticsCollectionState, "default")
    if state is None:
        session.add(AnalyticsCollectionState(id="default", visits_started_at=now, demo_started_at=started,
                                             creation_history_note="历史新增仅回填上线时仍存在的 Skill；此前永久删除的 Skill 无法恢复。"))
    else:
        state.demo_started_at = started
    return {"skills": len(skills), "actors": 30, "visits": len(events), "demo_started_at": started.isoformat()}


def main() -> None:
    """连接环境变量指定的本地测试数据库并在单一事务内填充数据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260913)
    args = parser.parse_args()
    engine = create_postgres_engine(resolve_database_url())
    try:
        verify_database_revision(engine)
        with Session(engine) as session, session.begin():
            session.execute(select(orm.Skill.id).limit(1))
            result = seed_demo(session, datetime.now(timezone.utc), args.seed)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""生成可复现的运营演示数据，不访问数据库。"""

import random
from datetime import datetime, time, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from skillhub.models.rules.analytics import SHANGHAI, shift_month

DEMO_PREFIX = "analytics-demo-"


def build_mock_data(now: datetime, *, seed: int = 20260913) -> tuple[list[dict], list[dict], datetime]:
    """生成 60 个 Skill 和 12,000 次具有增长、长尾和周末低谷的访问。"""
    rng = random.Random(seed)
    local_now = now.astimezone(SHANGHAI)
    start_day = shift_month(local_now.date().replace(day=1), -11)
    start = datetime.combine(start_day, time.min, SHANGHAI)
    names = ["接口状态检查", "BGP 邻居排查", "CPU 高负载诊断", "内存使用分析", "路由连通性检查", "日志异常定位"]
    skills = []
    for index in range(60):
        month = min(11, int((index / 60) ** .7 * 12))
        created = datetime.combine(shift_month(start_day, month), time.min, SHANGHAI)
        skills.append({"id": f"{DEMO_PREFIX}skill-{index:02}", "name": f"演示 · {names[index % len(names)]} {index + 1:02}",
                       "owner_ref": f"demo-operator-{index % 6 + 1:02}", "created_at": created.astimezone(timezone.utc)})
    days, weights = [], []
    current = start
    while current < local_now:
        if current.day not in {7, 21}:
            days.append(current)
            months = (current.year - start.year) * 12 + current.month - start.month
            weights.append((1 + months * .3) * (.25 if current.weekday() >= 5 else 1))
        current += timedelta(days=1)
    events = []
    for index in range(12000):
        day = rng.choices(days, weights=weights, k=1)[0]
        limit = min(local_now, day + timedelta(days=1))
        visited = day + timedelta(seconds=rng.randrange(max(1, int((limit - day).total_seconds()))))
        eligible = [skill for skill in skills if skill["created_at"] <= visited]
        chosen = rng.choices(eligible, weights=[1 / (i + 1) ** 1.15 for i in range(len(eligible))], k=1)[0]
        events.append({"event_id": uuid5(NAMESPACE_URL, f"{DEMO_PREFIX}visit-{index}"), "skill_id": chosen["id"],
                       "actor": f"demo-visitor-{rng.randrange(30) + 1:02}", "visited_at": visited.astimezone(timezone.utc), "is_demo": True})
    return skills, events, start.astimezone(timezone.utc)

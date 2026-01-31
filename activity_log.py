from datetime import datetime, timezone

from bson import ObjectId

from database import get_db


def log_activity(
    user_id: str,
    log_type: str,
    name: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    try:
        db = get_db()
        db.activityLogs.insert_one(
            {
                "userId": ObjectId(user_id),
                "type": log_type,
                "name": name,
                "description": description,
                "metadata": metadata or {},
                "createdAt": datetime.now(timezone.utc),
            }
        )
    except Exception as e:
        print("Activity log error:", e)

from pymongo.database import Database


def ensure_indexes(db: Database) -> None:
    """Create indexes once at startup. Sync for pymongo."""
    db.users.create_index("email", unique=True)
    db.config.create_index("userId", unique=True)
    db.rooms.create_index([("userId", 1), ("floor", 1), ("roomNumber", 1)], unique=True)
    db.rooms.create_index("userId")
    db.occupants.create_index("userId")
    db.occupants.create_index("roomId")
    db.rentRecords.create_index("userId")
    db.rentRecords.create_index("occupantId")
    db.rentRecords.create_index([("userId", 1), ("month", 1)])
    db.advanceBookings.create_index("userId")
    db.advanceBookings.create_index("expectedJoinDate")
    db.activityLogs.create_index("userId")
    db.activityLogs.create_index([("userId", 1), ("createdAt", -1)])
    db.activityLogs.create_index([("userId", 1), ("name", 1)])

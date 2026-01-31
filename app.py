import json
import logging
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from flask import Flask, request, render_template, redirect, url_for, make_response

from activity_log import log_activity
from auth import (
    clear_session_cookie,
    get_session_user_id,
    hash_password,
    set_session_cookie,
    verify_password,
    require_user,
)
from config import BASE_DIR
from database import get_db
from indexes import ensure_indexes

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.config['SECRET_KEY'] = 'your-secret-key-here'  # For session management


# Initialize database indexes at startup (using lazy initialization pattern)
_indexes_initialized = False

def init_indexes():
    """Run ensure_indexes once at startup."""
    global _indexes_initialized
    if not _indexes_initialized:
        try:
            ensure_indexes(get_db())
            _indexes_initialized = True
        except Exception as e:
            logger.warning("ensure_indexes at startup failed (indexes may exist already): %s", e)


@app.before_request
def ensure_indexes_once():
    """Initialize indexes on first request."""
    init_indexes()


def floor_label(floor_num: int) -> str:
    return "Ground Floor" if floor_num == 0 else f"Floor {floor_num}"


# ---------- Pages (GET) ----------


@app.route("/favicon.ico")
def favicon():
    """Avoid 404 for browser favicon requests."""
    return "", 204


@app.route("/login", methods=["GET"])
def login_page():
    user_id = get_session_user_id()
    if user_id:
        return redirect("/main")
    error = request.args.get("error")
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET"])
def register_page():
    user_id = get_session_user_id()
    if user_id:
        return redirect("/main")
    error = request.args.get("error")
    return render_template("register.html", error=error)


@app.route("/")
@app.route("/main")
@require_user
def main_page(user_id):
    db = get_db()
    uid = ObjectId(user_id)
    config = db.config.find_one({"userId": uid})
    if not config or not config.get("floorConfigs"):
        return redirect("/config")
    rooms = list(db.rooms.find({"userId": uid}).sort([("floor", 1), ("roomNumber", 1)]))
    by_floor = {}
    for r in rooms:
        fid = r["floor"]
        if fid not in by_floor:
            by_floor[fid] = []
        fill = len(r.get("occupantIds") or [])
        by_floor[fid].append(
            {
                "_id": str(r["_id"]),
                "floor": r["floor"],
                "roomNumber": r["roomNumber"],
                "maxPeople": r["maxPeople"],
                "fillCount": fill,
                "emptyCount": r["maxPeople"] - fill,
            }
        )
    floor_numbers = sorted(by_floor.keys())
    return render_template(
        "main.html",
        by_floor=by_floor,
        floor_numbers=floor_numbers,
        floor_label=floor_label,
    )


@app.route("/config", methods=["GET"])
@require_user
def config_page(user_id):
    db = get_db()
    uid = ObjectId(user_id)
    config = db.config.find_one({"userId": uid})
    floor_configs = [{"rooms": [{"maxPeople": 2}]}]
    has_ground_floor = False
    if config and config.get("floorConfigs"):
        floor_configs = []
        for f in config["floorConfigs"]:
            rooms = [{"maxPeople": max(r.get("maxPeople", 2), 1)} for r in f.get("rooms", [])]
            floor_configs.append({"rooms": rooms if rooms else [{"maxPeople": 2}]})
        has_ground_floor = bool(config.get("hasGroundFloor"))
    error = request.args.get("error")
    return render_template(
        "config.html",
        floor_configs=floor_configs,
        has_ground_floor=has_ground_floor,
        error=error,
    )


@app.route("/rooms", methods=["GET"])
@require_user
def rooms_page(user_id):
    db = get_db()
    uid = ObjectId(user_id)
    config = db.config.find_one({"userId": uid})
    if not config or not config.get("floorConfigs"):
        return redirect("/config")
    rooms = list(db.rooms.find({"userId": uid}).sort([("floor", 1), ("roomNumber", 1)]))
    occupants = list(db.occupants.find({"userId": uid}).sort("dateOfJoin", -1))
    rooms_list = []
    for r in rooms:
        oids = r.get("occupantIds") or []
        fill = len(oids)
        rooms_list.append(
            {
                "_id": str(r["_id"]),
                "floor": r["floor"],
                "roomNumber": r["roomNumber"],
                "maxPeople": r["maxPeople"],
                "fillCount": fill,
                "emptyCount": r["maxPeople"] - fill,
                "occupantIds": [str(x) for x in oids],
            }
        )
    occupants_list = [
        {"_id": str(o["_id"]), "roomId": str(o["roomId"]), "name": o["name"], "phone": o["phone"], "dateOfJoin": (o["dateOfJoin"].strftime("%Y-%m-%d") if isinstance(o.get("dateOfJoin"), datetime) else str(o.get("dateOfJoin", ""))[:10])}
        for o in occupants
    ]
    by_floor = {}
    for r in rooms_list:
        fid = r["floor"]
        if fid not in by_floor:
            by_floor[fid] = []
        by_floor[fid].append(r)
    floor_numbers = sorted(by_floor.keys())
    toast = request.args.get("toast")
    return render_template(
        "rooms.html",
        by_floor=by_floor,
        floor_numbers=floor_numbers,
        occupants=occupants_list,
        floor_label=floor_label,
        toast=toast,
    )


@app.route("/rent", methods=["GET"])
@require_user
def rent_page(user_id):
    month = request.args.get("month")
    today = date.today()
    month_key = month or f"{today.year}-{str(today.month).zfill(2)}"
    db = get_db()
    uid = ObjectId(user_id)
    parts = month_key.split("-")
    year, month_num = int(parts[0]), int(parts[1])
    _, last_day_num = monthrange(year, month_num)
    last_day = date(year, month_num, last_day_num)

    occupants = list(db.occupants.find({"userId": uid}))
    room_ids = list({str(o["roomId"]) for o in occupants})
    rooms = list(db.rooms.find({"_id": {"$in": [ObjectId(rid) for rid in room_ids]}}))
    room_map = {str(r["_id"]): r for r in rooms}

    list_rows = []
    for o in occupants:
        join_dt = o["dateOfJoin"] if isinstance(o["dateOfJoin"], datetime) else datetime.fromisoformat(str(o["dateOfJoin"])[:10])
        join_date = join_dt.date() if hasattr(join_dt, "date") else join_dt
        if join_date > last_day:
            continue
        room = room_map.get(str(o["roomId"]))
        room_label = (floor_label(room["floor"]) + " - Room " + str(room["roomNumber"])) if room else "—"
        record = db.rentRecords.find_one(
            {"userId": uid, "occupantId": o["_id"], "month": month_key}
        )
        if not record:
            db.rentRecords.insert_one(
                {
                    "userId": uid,
                    "occupantId": o["_id"],
                    "roomId": o["roomId"],
                    "month": month_key,
                    "paid": False,
                    "dueAmount": 0,
                }
            )
            record = {"paid": False, "dueAmount": 0}
        list_rows.append(
            {
                "occupantId": str(o["_id"]),
                "roomId": str(o["roomId"]),
                "roomLabel": room_label,
                "name": o["name"],
                "phone": o["phone"],
                "dateOfJoin": join_date.isoformat()[:10] if hasattr(join_date, "isoformat") else str(join_date)[:10],
                "paid": record.get("paid", False),
                "dueAmount": record.get("dueAmount", 0),
            }
        )
    list_rows.sort(key=lambda x: (x["roomLabel"], x["name"]))

    months = []
    d = date(today.year - 1, 1, 1)
    end = today
    while d <= end:
        months.append(f"{d.year}-{str(d.month).zfill(2)}")
        if d.month == 12:
            d = d.replace(year=d.year + 1, month=1)
        else:
            d = d.replace(month=d.month + 1)
    months.reverse()
    month_label = datetime(year, month_num, 1).strftime("%B %Y") if len(parts) == 2 else month_key
    month_options = []
    for m in months:
        y, mn = int(m[:4]), int(m[5:7])
        month_options.append({"value": m, "label": datetime(y, mn, 1).strftime("%B %Y")})

    toast = request.args.get("toast")
    return render_template(
        "rent.html",
        month=month_key,
        month_label=month_label,
        list=list_rows,
        month_options=month_options,
        toast=toast,
    )


@app.route("/advance-booking", methods=["GET"])
@require_user
def advance_booking_page(user_id):
    db = get_db()
    uid = ObjectId(user_id)
    bookings = list(db.advanceBookings.find({"userId": uid}).sort("expectedJoinDate", 1))
    bookings_list = [
        {
            "_id": str(b["_id"]),
            "name": b["name"],
            "phone": b["phone"],
            "expectedJoinDate": (b["expectedJoinDate"].strftime("%Y-%m-%d") if isinstance(b.get("expectedJoinDate"), datetime) else str(b.get("expectedJoinDate", ""))[:10]),
            "notes": b.get("notes") or "—",
        }
        for b in bookings
    ]
    error = request.args.get("error")
    toast = request.args.get("toast")
    return render_template(
        "advance_booking.html",
        bookings=bookings_list,
        error=error,
        toast=toast,
    )


@app.route("/history", methods=["GET"])
@require_user
def history_page(user_id):
    db = get_db()
    uid = ObjectId(user_id)
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    name = request.args.get("name")
    type_filter = request.args.get("type")
    
    filter_q = {"userId": uid}
    if from_date or to_date:
        filter_q["createdAt"] = {}
        if from_date:
            try:
                filter_q["createdAt"]["$gte"] = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            except Exception:
                pass
        if to_date:
            try:
                end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
                filter_q["createdAt"]["$lte"] = end
            except Exception:
                pass
    if name and name.strip():
        filter_q["name"] = {"$regex": name.strip(), "$options": "i"}
    if type_filter and type_filter.strip() in (
        "person_created", "person_removed", "advance_booking_added", "advance_booking_removed",
        "rent_paid", "rent_unpaid", "config_updated",
    ):
        filter_q["type"] = type_filter.strip()
    logs = list(db.activityLogs.find(filter_q).sort("createdAt", -1).limit(500))
    type_labels = {
        "person_created": "Person added",
        "person_removed": "Person removed",
        "advance_booking_added": "Advance booking added",
        "advance_booking_removed": "Advance booking removed",
        "rent_paid": "Rent paid",
        "rent_unpaid": "Rent unpaid",
        "config_updated": "Config updated",
    }
    logs_list = [
        {
            "_id": str(l["_id"]),
            "type": l["type"],
            "name": l["name"],
            "description": l["description"],
            "createdAt": l["createdAt"].strftime("%Y-%m-%d %H:%M") if isinstance(l.get("createdAt"), datetime) else str(l.get("createdAt", "")),
        }
        for l in logs
    ]
    return render_template(
        "history.html",
        logs=logs_list,
        type_labels=type_labels,
        from_date=from_date or "",
        to_date=to_date or "",
        name_filter=name or "",
        type_filter=type_filter or "",
    )


# ---------- Auth actions ----------


@app.route("/login", methods=["POST"])
def login_action():
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    from_path = request.form.get("from", "/main")
    
    db = get_db()
    user = db.users.find_one({"email": email.strip().lower()})
    if not user or not verify_password(password, user["passwordHash"]):
        return redirect("/login?error=Invalid+email+or+password")
    
    response = make_response(redirect(from_path or "/main"))
    set_session_cookie(response, str(user["_id"]))
    return response


@app.route("/register", methods=["POST"])
def register_action():
    name = request.form.get("name", "")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    
    db = get_db()
    email_clean = email.strip().lower()
    existing = db.users.find_one({"email": email_clean})
    if existing:
        return redirect("/register?error=Email+already+registered")
    if len(password) < 6:
        return redirect("/register?error=Password+must+be+at+least+6+characters")
    doc = {
        "email": email_clean,
        "passwordHash": hash_password(password),
        "name": name.strip(),
    }
    result = db.users.insert_one(doc)
    response = make_response(redirect("/config"))
    set_session_cookie(response, str(result.inserted_id))
    return response


@app.route("/logout", methods=["POST"])
def logout_action():
    response = make_response(redirect("/login"))
    clear_session_cookie(response)
    return response


# ---------- Config save ----------


@app.route("/config/save", methods=["POST"])
@require_user
def config_save(user_id):
    config_json = request.form.get("config_json")
    if config_json:
        try:
            data = json.loads(config_json)
            has_ground_floor = data.get("has_ground_floor", False)
            floor_configs = data.get("floor_configs", [])
        except Exception:
            return redirect("/config?error=Invalid+config")
    else:
        has_ground_floor = request.form.get("has_ground_floor") == "on"
        floor_count = int(request.form.get("floor_count", 1) or 1)
        floor_configs = []
        for i in range(floor_count):
            room_count = int(request.form.get(f"floor_{i}_rooms") or 1)
            rooms = []
            for j in range(room_count):
                max_p = max(1, min(20, int(request.form.get(f"floor_{i}_room_{j}_max", 2) or 2)))
                rooms.append({"maxPeople": max_p})
            floor_configs.append({"rooms": rooms})
    if not floor_configs or not any(f.get("rooms") for f in floor_configs):
        return redirect("/config?error=At+least+one+floor+with+one+room+required")
    db = get_db()
    uid = ObjectId(user_id)
    db.config.update_one(
        {"userId": uid},
        {
            "$set": {
                "userId": uid,
                "floors": len(floor_configs),
                "hasGroundFloor": has_ground_floor,
                "floorConfigs": floor_configs,
                "updatedAt": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    rooms_to_sync = []
    for idx, fc in enumerate(floor_configs):
        floor_num = idx if has_ground_floor else idx + 1
        for ridx, r in enumerate(fc["rooms"]):
            rooms_to_sync.append({"floor": floor_num, "roomNumber": ridx + 1, "maxPeople": r.get("maxPeople", 2)})
    for r in rooms_to_sync:
        existing = db.rooms.find_one({"userId": uid, "floor": r["floor"], "roomNumber": r["roomNumber"]})
        if existing:
            db.rooms.update_one({"_id": existing["_id"]}, {"$set": {"maxPeople": r["maxPeople"]}})
        else:
            db.rooms.insert_one(
                {"userId": uid, "floor": r["floor"], "roomNumber": r["roomNumber"], "maxPeople": r["maxPeople"], "occupantIds": []}
            )
    existing_rooms = list(db.rooms.find({"userId": uid}))
    expected_keys = {f"{x['floor']}-{x['roomNumber']}" for x in rooms_to_sync}
    for ex in existing_rooms:
        key = f"{ex['floor']}-{ex['roomNumber']}"
        if key not in expected_keys:
            db.occupants.delete_many({"roomId": ex["_id"]})
            db.rooms.delete_one({"_id": ex["_id"]})
    log_activity(
        user_id,
        "config_updated",
        "Building config",
        f"Configuration updated: {len(floor_configs)} floor(s), {len(rooms_to_sync)} room(s)",
        {"floors": len(floor_configs), "roomCount": len(rooms_to_sync)},
    )
    return redirect("/main")


# ---------- Occupants ----------


@app.route("/occupants/add", methods=["POST"])
@require_user
def add_occupant(user_id):
    room_id = request.form.get("room_id", "")
    name = request.form.get("name", "")
    phone = request.form.get("phone", "")
    date_of_join = request.form.get("date_of_join")
    
    db = get_db()
    uid = ObjectId(user_id)
    rid = ObjectId(room_id)
    room = db.rooms.find_one({"_id": rid, "userId": uid})
    if not room:
        return redirect("/rooms?toast=Room+not+found")
    if len(room.get("occupantIds") or []) >= room["maxPeople"]:
        return redirect("/rooms?toast=Room+is+full")
    join_date = datetime.fromisoformat(date_of_join[:10]) if date_of_join else datetime.now(timezone.utc)
    occupant = {
        "userId": uid,
        "roomId": rid,
        "name": name.strip(),
        "phone": phone.strip(),
        "dateOfJoin": join_date,
    }
    result = db.occupants.insert_one(occupant)
    db.rooms.update_one({"_id": rid, "userId": uid}, {"$push": {"occupantIds": result.inserted_id}})
    month_key = join_date.strftime("%Y-%m")
    db.rentRecords.update_one(
        {"userId": uid, "occupantId": result.inserted_id, "month": month_key},
        {
            "$setOnInsert": {
                "userId": uid,
                "occupantId": result.inserted_id,
                "roomId": rid,
                "month": month_key,
                "paid": False,
                "dueAmount": 0,
            }
        },
        upsert=True,
    )
    log_activity(
        user_id,
        "person_created",
        occupant["name"],
        f"Person added: {occupant['name']} ({occupant['phone']})",
        {"occupantId": str(result.inserted_id), "roomId": room_id},
    )
    return redirect("/rooms?toast=Person+added")


@app.route("/occupants/remove", methods=["POST"])
@require_user
def remove_occupant(user_id):
    occupant_id = request.form.get("occupant_id", "")
    
    db = get_db()
    uid = ObjectId(user_id)
    oid = ObjectId(occupant_id)
    occupant = db.occupants.find_one({"_id": oid, "userId": uid})
    if not occupant:
        return redirect("/rooms?toast=Occupant+not+found")
    log_activity(
        user_id,
        "person_removed",
        occupant["name"],
        f"Person removed: {occupant['name']} ({occupant['phone']})",
        {"occupantId": occupant_id},
    )
    db.rooms.update_one({"_id": occupant["roomId"], "userId": uid}, {"$pull": {"occupantIds": oid}})
    db.occupants.delete_one({"_id": oid, "userId": uid})
    return redirect("/rooms?toast=Person+removed")


# ---------- Rent toggle ----------


@app.route("/rent/toggle", methods=["GET"])
@require_user
def rent_toggle(user_id):
    occupant_id = request.args.get("occupant_id", "")
    month = request.args.get("month", "")
    
    db = get_db()
    uid = ObjectId(user_id)
    oid = ObjectId(occupant_id)
    occupant = db.occupants.find_one({"_id": oid, "userId": uid})
    if not occupant:
        return redirect("/rent?toast=Not+found")
    record = db.rentRecords.find_one({"userId": uid, "occupantId": oid, "month": month})
    current_paid = record.get("paid", False) if record else False
    new_paid = not current_paid
    if record:
        db.rentRecords.update_one(
            {"userId": uid, "occupantId": oid, "month": month},
            {"$set": {"paid": new_paid}},
        )
    else:
        db.rentRecords.insert_one(
            {"userId": uid, "occupantId": oid, "roomId": occupant["roomId"], "month": month, "paid": new_paid, "dueAmount": 0}
        )
    log_activity(
        user_id,
        "rent_paid" if new_paid else "rent_unpaid",
        occupant.get("name", "Unknown"),
        f"Rent marked {'paid' if new_paid else 'unpaid'} for {occupant.get('name', 'Unknown')} ({month})",
        {"occupantId": occupant_id, "month": month},
    )
    toast = "Marked+as+paid" if new_paid else "Marked+as+unpaid"
    return redirect(f"/rent?month={month}&toast={toast}")


# ---------- Advance booking ----------


@app.route("/advance-booking/add", methods=["POST"])
@require_user
def advance_booking_add(user_id):
    name = request.form.get("name", "")
    phone = request.form.get("phone", "")
    expected_join_date = request.form.get("expected_join_date")
    notes = request.form.get("notes")
    
    db = get_db()
    uid = ObjectId(user_id)
    join_dt = datetime.fromisoformat(expected_join_date[:10]) if expected_join_date else datetime.now(timezone.utc)
    doc = {
        "userId": uid,
        "name": name.strip(),
        "phone": phone.strip(),
        "expectedJoinDate": join_dt,
        "notes": notes.strip() if notes else None,
        "createdAt": datetime.now(timezone.utc),
    }
    result = db.advanceBookings.insert_one(doc)
    log_activity(
        user_id,
        "advance_booking_added",
        doc["name"],
        f"Advance booking added: {doc['name']} ({doc['phone']})",
        {"bookingId": str(result.inserted_id)},
    )
    return redirect("/advance-booking?toast=Booking+added")


@app.route("/advance-booking/remove", methods=["POST"])
@require_user
def advance_booking_remove(user_id):
    booking_id = request.form.get("id", "")
    
    db = get_db()
    uid = ObjectId(user_id)
    bid = ObjectId(booking_id)
    booking = db.advanceBookings.find_one({"_id": bid, "userId": uid})
    if not booking:
        return redirect("/advance-booking?toast=Booking+not+found")
    db.advanceBookings.delete_one({"_id": bid, "userId": uid})
    log_activity(
        user_id,
        "advance_booking_removed",
        booking["name"],
        f"Advance booking removed: {booking['name']} ({booking['phone']})",
        {"bookingId": booking_id},
    )
    return redirect("/advance-booking?toast=Booking+removed")


if __name__ == "__main__":
    app.run(debug=True)

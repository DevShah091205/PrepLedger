"""PrepLedger - placement and interview preparation tracker."""
import csv
import io
import re
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .auth import create_token, current_user, hash_password, verify_password
from .config import ALLOW_REGISTRATION, TZ_OFFSET_MINUTES
from .db import get_db, init_db

STATIC = Path(__file__).parent / "static"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

AppStatus = Literal["wishlist", "applied", "oa", "interview", "offer", "rejected"]
Difficulty = Literal["easy", "medium", "hard"]
ProbStatus = Literal["todo", "solved", "revisit"]
MockKind = Literal["aptitude", "dsa", "technical", "hr", "interview", "other"]

# days until the next review, by confidence (1 = shaky ... 5 = easy)
REVIEW_GAP = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="PrepLedger", version="1.0.0", lifespan=lifespan)


def today() -> date:
    return (datetime.now(timezone.utc) + timedelta(minutes=TZ_OFFSET_MINUTES)).date()


def clean_url(v: str) -> str:
    v = (v or "").strip()
    if v and not re.match(r"^https?://", v, re.I):
        raise ValueError("Link must start with http:// or https://")
    return v


# ------------------------------------------------------------------ models
class Credentials(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v


class AppIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)
    status: AppStatus = "wishlist"
    ctc_lpa: float | None = Field(default=None, ge=0, le=1000)
    location: str = Field(default="", max_length=80)
    source: str = Field(default="", max_length=80)
    applied_on: date | None = None
    next_date: date | None = None
    next_step: str = Field(default="", max_length=120)
    link: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=4000)

    @field_validator("link")
    @classmethod
    def _link(cls, v):
        return clean_url(v)


class StatusIn(BaseModel):
    status: AppStatus


class ProblemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(default="", max_length=60)
    difficulty: Difficulty = "medium"
    platform: str = Field(default="", max_length=60)
    url: str = Field(default="", max_length=500)
    status: ProbStatus = "todo"
    confidence: int | None = Field(default=None, ge=1, le=5)
    time_min: int | None = Field(default=None, ge=0, le=1440)
    notes: str = Field(default="", max_length=4000)

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        return clean_url(v)


class ReviewIn(BaseModel):
    confidence: int = Field(ge=1, le=5)


class MockIn(BaseModel):
    kind: MockKind = "aptitude"
    title: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    taken_on: date
    notes: str = Field(default="", max_length=2000)


# ----------------------------------------------------------------- helpers
def log_activity(db, uid: int, kind: str):
    db.execute("INSERT INTO activity(user_id, day, kind) VALUES(?,?,?)", (uid, today().isoformat(), kind))


def rows(db, sql, params=()):
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def dump(model: BaseModel) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in model.model_dump().items()}


def insert(db, table: str, uid: int, data: dict) -> int:
    cols = ["user_id", *data]
    cur = db.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                     [uid, *data.values()])
    return cur.lastrowid


def update(db, table: str, rid: int, uid: int, data: dict):
    sets = ",".join(f"{k}=?" for k in data)
    cur = db.execute(f"UPDATE {table} SET {sets} WHERE id=? AND user_id=?", [*data.values(), rid, uid])
    if not cur.rowcount:
        raise HTTPException(404, "Not found")


def remove(db, table: str, rid: int, uid: int):
    if not db.execute(f"DELETE FROM {table} WHERE id=? AND user_id=?", (rid, uid)).rowcount:
        raise HTTPException(404, "Not found")


@app.get("/health")
def health():
    return {"status": "ok"}


# -------------------------------------------------------------------- auth
@app.post("/api/register", status_code=201)
def register(c: Credentials):
    if not ALLOW_REGISTRATION:
        raise HTTPException(403, "Registration is closed")
    with get_db() as db:
        if db.execute("SELECT 1 FROM users WHERE email=?", (c.email,)).fetchone():
            raise HTTPException(409, "That email is already registered")
        uid = db.execute("INSERT INTO users(email,name,password_hash) VALUES(?,?,?)",
                         (c.email, c.name.strip(), hash_password(c.password))).lastrowid
    return {"token": create_token(uid), "name": c.name.strip(), "email": c.email}


@app.post("/api/login")
def login(c: Credentials):
    with get_db() as db:
        u = db.execute("SELECT * FROM users WHERE email=?", (c.email,)).fetchone()
    if not u or not verify_password(c.password, u["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": create_token(u["id"]), "name": u["name"], "email": u["email"]}


# ------------------------------------------------------------ applications
@app.get("/api/applications")
def list_apps(uid: int = Depends(current_user)):
    with get_db() as db:
        return rows(db, "SELECT * FROM applications WHERE user_id=? ORDER BY updated_at DESC, id DESC", (uid,))


@app.post("/api/applications", status_code=201)
def create_app(a: AppIn, uid: int = Depends(current_user)):
    with get_db() as db:
        rid = insert(db, "applications", uid, dump(a))
    return {"id": rid}


@app.put("/api/applications/{rid}")
def edit_app(rid: int, a: AppIn, uid: int = Depends(current_user)):
    with get_db() as db:
        update(db, "applications", rid, uid, {**dump(a), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"id": rid}


@app.patch("/api/applications/{rid}/status")
def set_status(rid: int, s: StatusIn, uid: int = Depends(current_user)):
    with get_db() as db:
        update(db, "applications", rid, uid, {"status": s.status, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"id": rid, "status": s.status}


@app.delete("/api/applications/{rid}", status_code=204)
def delete_app(rid: int, uid: int = Depends(current_user)):
    with get_db() as db:
        remove(db, "applications", rid, uid)


# --------------------------------------------------------------- problems
@app.get("/api/problems")
def list_problems(uid: int = Depends(current_user)):
    with get_db() as db:
        return rows(db, "SELECT * FROM problems WHERE user_id=? ORDER BY id DESC", (uid,))


def _solve_fields(data: dict, existing: dict | None) -> dict:
    """Fill solved_on / next_review when a problem becomes solved."""
    if data["status"] in ("solved", "revisit"):
        conf = data.get("confidence") or 3
        data["confidence"] = conf
        was_solved = existing and existing["status"] in ("solved", "revisit")
        data["solved_on"] = existing["solved_on"] if was_solved and existing["solved_on"] else today().isoformat()
        if not was_solved or existing["confidence"] != conf:
            data["next_review"] = (today() + timedelta(days=REVIEW_GAP[conf])).isoformat()
        else:
            data["next_review"] = existing["next_review"]
    else:
        data.update(solved_on=None, next_review=None, confidence=None)
    return data


@app.post("/api/problems", status_code=201)
def create_problem(p: ProblemIn, uid: int = Depends(current_user)):
    data = _solve_fields(dump(p), None)
    with get_db() as db:
        rid = insert(db, "problems", uid, data)
        if data["status"] != "todo":
            log_activity(db, uid, "solve")
    return {"id": rid}


@app.put("/api/problems/{rid}")
def edit_problem(rid: int, p: ProblemIn, uid: int = Depends(current_user)):
    with get_db() as db:
        old = db.execute("SELECT * FROM problems WHERE id=? AND user_id=?", (rid, uid)).fetchone()
        if not old:
            raise HTTPException(404, "Not found")
        data = _solve_fields(dump(p), dict(old))
        update(db, "problems", rid, uid, data)
        if data["status"] != "todo" and old["status"] == "todo":
            log_activity(db, uid, "solve")
    return {"id": rid}


@app.post("/api/problems/{rid}/review")
def review_problem(rid: int, r: ReviewIn, uid: int = Depends(current_user)):
    nxt = (today() + timedelta(days=REVIEW_GAP[r.confidence])).isoformat()
    with get_db() as db:
        update(db, "problems", rid, uid, {
            "confidence": r.confidence, "last_reviewed": today().isoformat(), "next_review": nxt,
            "status": "revisit" if r.confidence <= 2 else "solved"})
        db.execute("UPDATE problems SET review_count=review_count+1 WHERE id=?", (rid,))
        log_activity(db, uid, "review")
    return {"next_review": nxt}


@app.delete("/api/problems/{rid}", status_code=204)
def delete_problem(rid: int, uid: int = Depends(current_user)):
    with get_db() as db:
        remove(db, "problems", rid, uid)


# ------------------------------------------------------------------ mocks
@app.get("/api/mocks")
def list_mocks(uid: int = Depends(current_user)):
    with get_db() as db:
        return rows(db, "SELECT * FROM mocks WHERE user_id=? ORDER BY taken_on DESC, id DESC", (uid,))


@app.post("/api/mocks", status_code=201)
def create_mock(m: MockIn, uid: int = Depends(current_user)):
    if m.score > m.max_score:
        raise HTTPException(422, "Score cannot be higher than the maximum")
    with get_db() as db:
        rid = insert(db, "mocks", uid, dump(m))
        log_activity(db, uid, "mock")
    return {"id": rid}


@app.delete("/api/mocks/{rid}", status_code=204)
def delete_mock(rid: int, uid: int = Depends(current_user)):
    with get_db() as db:
        remove(db, "mocks", rid, uid)


# -------------------------------------------------------------- dashboard
@app.get("/api/dashboard")
def dashboard(uid: int = Depends(current_user)):
    t = today()
    with get_db() as db:
        user = db.execute("SELECT name, email FROM users WHERE id=?", (uid,)).fetchone()
        apps = rows(db, "SELECT * FROM applications WHERE user_id=?", (uid,))
        probs = rows(db, "SELECT * FROM problems WHERE user_id=?", (uid,))
        mocks = rows(db, "SELECT * FROM mocks WHERE user_id=? ORDER BY taken_on DESC, id DESC LIMIT 10", (uid,))
        since = (t - timedelta(days=83)).isoformat()
        act = rows(db, "SELECT day, COUNT(*) c FROM activity WHERE user_id=? AND day>=? GROUP BY day", (uid, since))
        all_days = {r["day"] for r in rows(db, "SELECT DISTINCT day FROM activity WHERE user_id=?", (uid,))}

    pipeline = Counter(a["status"] for a in apps)
    upcoming = sorted((a for a in apps if a["next_date"] and a["next_date"] >= t.isoformat()
                       and a["status"] not in ("rejected", "offer")), key=lambda a: a["next_date"])[:6]
    done = [p for p in probs if p["status"] in ("solved", "revisit")]
    due = sorted((p for p in done if p["next_review"] and p["next_review"] <= t.isoformat()),
                 key=lambda p: p["next_review"])
    streak, d = 0, t if t.isoformat() in all_days else t - timedelta(days=1)
    while d.isoformat() in all_days:
        streak, d = streak + 1, d - timedelta(days=1)

    return {
        "user": {"name": user["name"], "email": user["email"]},
        "today": t.isoformat(),
        "pipeline": {s: pipeline.get(s, 0) for s in ("wishlist", "applied", "oa", "interview", "offer", "rejected")},
        "totals": {"applications": len(apps), "active": sum(pipeline.get(s, 0) for s in ("applied", "oa", "interview")),
                   "offers": pipeline.get("offer", 0), "solved": len(done), "problems": len(probs),
                   "due": len(due), "streak": streak},
        "upcoming": [{k: a[k] for k in ("id", "company", "role", "status", "next_date", "next_step")} for a in upcoming],
        "due": [{k: p[k] for k in ("id", "title", "topic", "difficulty", "next_review", "confidence", "url")} for p in due[:8]],
        "topics": [{"name": k or "Other", "count": v} for k, v in Counter(p["topic"] for p in done).most_common(8)],
        "difficulty": {k: sum(1 for p in done if p["difficulty"] == k) for k in ("easy", "medium", "hard")},
        "heatmap": {r["day"]: r["c"] for r in act},
        "mocks": [{"title": m["title"], "kind": m["kind"], "taken_on": m["taken_on"],
                   "pct": round(m["score"] / m["max_score"] * 100, 1)} for m in reversed(mocks)],
    }


# ----------------------------------------------------------------- export
EXPORTS = {
    "applications": ("applications", ["company", "role", "status", "ctc_lpa", "location", "source", "applied_on",
                                      "next_date", "next_step", "link", "notes"]),
    "problems": ("problems", ["title", "topic", "difficulty", "platform", "url", "status", "confidence", "time_min",
                              "solved_on", "next_review", "review_count", "notes"]),
    "mocks": ("mocks", ["kind", "title", "score", "max_score", "taken_on", "notes"]),
}


@app.get("/api/export/{name}.csv")
def export_csv(name: str, uid: int = Depends(current_user)):
    if name not in EXPORTS:
        raise HTTPException(404, "Unknown export")
    table, cols = EXPORTS[name]
    with get_db() as db:
        data = rows(db, f"SELECT {','.join(cols)} FROM {table} WHERE user_id=? ORDER BY id", (uid,))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in data:  # guard against spreadsheet formula injection
        w.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in r.items()})
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="prepledger-{name}.csv"'})


# ---------------------------------------------------- sample data / reset
@app.post("/api/demo", status_code=201)
def load_demo(uid: int = Depends(current_user)):
    t = today()
    day = lambda n: (t + timedelta(days=n)).isoformat()
    with get_db() as db:
        if db.execute("SELECT 1 FROM applications WHERE user_id=? UNION SELECT 1 FROM problems WHERE user_id=?",
                      (uid, uid)).fetchone():
            raise HTTPException(409, "Sample data can only be added to an empty account")
        for company, role, status, ctc, loc, src, applied, nxt, step in [
            ("TCS", "Digital", "oa", 7.0, "Pune", "Campus", -9, 3, "Online assessment"),
            ("Infosys", "Specialist Programmer", "applied", 9.5, "Bengaluru", "Campus", -5, 6, "Results of coding round"),
            ("Zoho", "Member Technical Staff", "interview", 8.0, "Chennai", "Referral", -20, 2, "Technical round 2"),
            ("Amazon", "SDE-1", "wishlist", 28.0, "Hyderabad", "Careers page", None, 9, "Application closes"),
            ("Wipro", "Turbo", "offer", 6.5, "Remote", "Campus", -40, None, ""),
            ("Freshworks", "Associate Engineer", "rejected", 11.0, "Chennai", "LinkedIn", -30, None, ""),
        ]:
            insert(db, "applications", uid, dict(company=company, role=role, status=status, ctc_lpa=ctc, location=loc,
                   source=src, applied_on=day(applied) if applied else None, next_date=day(nxt) if nxt else None,
                   next_step=step, link="", notes=""))
        for title, topic, diff, plat, conf, ago in [
            ("Two Sum", "Arrays", "easy", "LeetCode", 5, 20), ("Best Time to Buy and Sell Stock", "Arrays", "easy", "LeetCode", 4, 14),
            ("Longest Substring Without Repeating Characters", "Strings", "medium", "LeetCode", 3, 9),
            ("Valid Parentheses", "Stacks", "easy", "LeetCode", 4, 6), ("Merge Intervals", "Arrays", "medium", "LeetCode", 2, 5),
            ("Reverse Linked List", "Linked List", "easy", "GeeksforGeeks", 5, 4),
            ("Binary Tree Level Order Traversal", "Trees", "medium", "LeetCode", 3, 3),
            ("Coin Change", "Dynamic Programming", "medium", "LeetCode", 1, 2),
            ("Number of Islands", "Graphs", "medium", "LeetCode", 3, 1),
        ]:
            solved = t - timedelta(days=ago)
            insert(db, "problems", uid, dict(title=title, topic=topic, difficulty=diff, platform=plat, url="",
                   status="revisit" if conf <= 2 else "solved", confidence=conf, time_min=25, solved_on=solved.isoformat(),
                   next_review=(solved + timedelta(days=REVIEW_GAP[conf])).isoformat(), review_count=0, notes=""))
            db.execute("INSERT INTO activity(user_id, day, kind) VALUES(?,?,?)", (uid, solved.isoformat(), "solve"))
        for title, topic, diff in [("Sliding Window Maximum", "Arrays", "hard"), ("Word Break", "Dynamic Programming", "medium"),
                                   ("Course Schedule", "Graphs", "medium")]:
            insert(db, "problems", uid, dict(title=title, topic=topic, difficulty=diff, platform="LeetCode", url="",
                   status="todo", notes=""))
        for kind, title, sc, mx, ago in [("aptitude", "Quant sectional 1", 14, 25, 25), ("aptitude", "Quant sectional 2", 17, 25, 18),
                                         ("dsa", "Coding round mock", 120, 300, 12), ("dsa", "Coding round mock 2", 180, 300, 6),
                                         ("interview", "Mock technical with senior", 6, 10, 2)]:
            d = (t - timedelta(days=ago)).isoformat()
            insert(db, "mocks", uid, dict(kind=kind, title=title, score=sc, max_score=mx, taken_on=d, notes=""))
            db.execute("INSERT INTO activity(user_id, day, kind) VALUES(?,?,?)", (uid, d, "mock"))
        for n in (0, 1, 2, 3, 4, 7, 8, 10, 11, 15, 16, 22, 23, 24, 30, 31, 40, 41, 42, 50):
            db.execute("INSERT INTO activity(user_id, day, kind) VALUES(?,?,?)", (uid, (t - timedelta(days=n)).isoformat(), "solve"))
    return {"ok": True}


@app.delete("/api/data", status_code=204)
def wipe(uid: int = Depends(current_user)):
    with get_db() as db:
        for table in ("applications", "problems", "mocks", "activity"):
            db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))


# --------------------------------------------------------------- frontend
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")

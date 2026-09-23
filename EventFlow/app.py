
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
from datetime import date, datetime
from functools import wraps

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"

app = Flask(__name__)
app.secret_key = "event-management-prototype-secret"

STATUSES = ["Planning", "In Progress", "Completed", "Cancelled"]
TASK_STATUSES = ["To Do", "In Progress", "Completed"]
PRIORITIES = ["Low", "Medium", "High"]
PAYMENT_STATUSES = ["Pending", "Partial", "Paid"]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def query(sql, params=(), one=False):
    conn = get_db()
    cur = conn.execute(sql, params)
    rows = cur.fetchone() if one else cur.fetchall()
    conn.close()
    return rows

def execute(sql, params=()):
    conn = get_db()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

def log_activity(event_id, message):
    execute("INSERT INTO activities(event_id, message, created_at) VALUES (?, ?, ?)",
            (event_id, message, datetime.now().isoformat(timespec="seconds")))

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        event_date TEXT NOT NULL,
        start_time TEXT DEFAULT '',
        end_time TEXT DEFAULT '',
        venue TEXT DEFAULT '',
        organizer_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Planning',
        created_at TEXT NOT NULL,
        FOREIGN KEY(organizer_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        phone TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        assigned_to INTEGER,
        due_date TEXT DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'Medium',
        status TEXT NOT NULL DEFAULT 'To Do',
        elapsed_seconds INTEGER NOT NULL DEFAULT 0,
        timer_started_at TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY(assigned_to) REFERENCES team_members(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT '',
        required_qty REAL NOT NULL DEFAULT 0,
        available_qty REAL NOT NULL DEFAULT 0,
        unit TEXT DEFAULT 'pieces',
        supplier TEXT DEFAULT '',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        service TEXT DEFAULT '',
        contact TEXT DEFAULT '',
        estimated_cost REAL NOT NULL DEFAULT 0,
        actual_cost REAL NOT NULL DEFAULT 0,
        payment_status TEXT NOT NULL DEFAULT 'Pending',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    """)
    # Create login accounts only. Real event data starts empty.
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.executemany("INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)", [
            ("Admin User", "admin@example.com", "admin123", "Admin"),
            ("Demo Member", "member@example.com", "member123", "Team Member")
        ])

    # Safe migration for databases created by older EventFlow versions.
    task_cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "elapsed_seconds" not in task_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN elapsed_seconds INTEGER NOT NULL DEFAULT 0")
    if "timer_started_at" not in task_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN timer_started_at TEXT DEFAULT ''")

    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "Admin":
            flash("Admin permission is required for this action.", "error")
            return redirect(request.referrer or url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

def event_progress(event_id):
    row = query("SELECT COUNT(*) total, SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) completed FROM tasks WHERE event_id=?", (event_id,), True)
    total = row["total"] or 0
    completed = row["completed"] or 0
    return round(completed * 100 / total) if total else 0

def material_status(m):
    if m["available_qty"] <= 0:
        return "Out of Stock"
    if m["available_qty"] < m["required_qty"]:
        return "Shortage"
    return "Available"

@app.context_processor
def inject_helpers():
    return {"material_status": material_status, "event_progress": event_progress}

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        user = query("SELECT * FROM users WHERE email=? AND password=?", (email,password), True)
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "events": query("SELECT COUNT(*) c FROM events", one=True)["c"],
        "upcoming": query("SELECT COUNT(*) c FROM events WHERE event_date >= date('now') AND status!='Completed'", one=True)["c"],
        "pending": query("SELECT COUNT(*) c FROM tasks WHERE status!='Completed'", one=True)["c"],
        "completed": query("SELECT COUNT(*) c FROM tasks WHERE status='Completed'", one=True)["c"],
        "low_stock": query("SELECT COUNT(*) c FROM materials WHERE available_qty < required_qty", one=True)["c"]
    }
    events = query("SELECT * FROM events ORDER BY event_date LIMIT 6")
    activities = query("""SELECT a.*, e.name event_name FROM activities a
                          JOIN events e ON e.id=a.event_id ORDER BY a.id DESC LIMIT 8""")
    alerts = []
    for m in query("SELECT * FROM materials WHERE available_qty < required_qty"):
        alerts.append(f"{m['name']} is below required quantity.")
    for t in query("SELECT * FROM tasks WHERE status!='Completed' AND due_date!='' AND due_date < date('now')"):
        alerts.append(f"Task '{t['title']}' is overdue.")
    return render_template("dashboard.html", stats=stats, events=events, activities=activities, alerts=alerts)

@app.route("/demo/load", methods=["POST"])
@admin_required
def load_demo():
    # Deliberately opt-in: demo data is never created automatically.
    admin_id = session["user_id"]
    now = datetime.now().isoformat(timespec="seconds")
    cur = get_db()
    try:
        c = cur.cursor()
        c.execute("INSERT INTO events(name,description,event_date,start_time,end_time,venue,organizer_id,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  ("College Fest 2026", "Optional demonstration event.", "2026-10-15", "10:00", "18:00", "College Main Ground", admin_id, "Planning", now))
        eid=c.lastrowid
        c.executemany("INSERT INTO team_members(event_id,name,email,role,phone) VALUES (?,?,?,?,?)", [(eid,"John Sharma","john@example.com","Technical","9800000001"),(eid,"Sarah Rai","sarah@example.com","Marketing","9800000002")])
        mids={r["name"]:r["id"] for r in c.execute("SELECT id,name FROM team_members WHERE event_id=?",(eid,))}
        c.executemany("INSERT INTO tasks(event_id,title,description,assigned_to,due_date,priority,status) VALUES (?,?,?,?,?,?,?)", [(eid,"Stage Setup","Prepare the main stage.",mids["John Sharma"],"2026-10-10","High","To Do"),(eid,"Social Media Campaign","Publish announcements.",mids["Sarah Rai"],"2026-10-08","Medium","To Do")])
        c.executemany("INSERT INTO materials(event_id,name,category,required_qty,available_qty,unit,supplier) VALUES (?,?,?,?,?,?,?)", [(eid,"Plastic Chairs","Furniture",100,75,"pieces","City Rentals"),(eid,"Wireless Microphones","Audio",6,3,"pieces","Sound Hub")])
        c.execute("INSERT INTO activities(event_id,message,created_at) VALUES (?,?,?)",(eid,"Demo event loaded",now))
        cur.commit()
        flash("Demo data loaded. You can edit or delete everything.","success")
    finally:
        cur.close()
    return redirect(url_for("event_detail",event_id=eid))

@app.route("/events")
@login_required
def events():
    q = request.args.get("q","").strip()
    status = request.args.get("status","")
    sql = "SELECT * FROM events WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR venue LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if status:
        sql += " AND status=?"; params.append(status)
    sql += " ORDER BY event_date"
    return render_template("events.html", events=query(sql, params), statuses=STATUSES, q=q, status=status)

@app.route("/events/create", methods=["POST"])
@admin_required
def create_event():
    f = request.form
    eid = execute("""INSERT INTO events(name,description,event_date,start_time,end_time,venue,organizer_id,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                  (f["name"], f.get("description",""), f["event_date"], f.get("start_time",""),
                   f.get("end_time",""), f.get("venue",""), session["user_id"], f.get("status","Planning"),
                   datetime.now().isoformat(timespec="seconds")))
    log_activity(eid, f"Event '{f['name']}' created")
    flash("Event created successfully.", "success")
    return redirect(url_for("event_detail", event_id=eid))

@app.route("/events/<int:event_id>/edit", methods=["POST"])
@admin_required
def edit_event(event_id):
    f=request.form
    execute("""UPDATE events SET name=?,description=?,event_date=?,start_time=?,end_time=?,venue=?,status=? WHERE id=?""",
            (f["name"],f.get("description",""),f["event_date"],f.get("start_time",""),f.get("end_time",""),
             f.get("venue",""),f.get("status","Planning"),event_id))
    log_activity(event_id, f"Event '{f['name']}' updated")
    flash("Event updated.", "success")
    return redirect(url_for("event_detail", event_id=event_id))

@app.route("/events/<int:event_id>/delete", methods=["POST"])
@admin_required
def delete_event(event_id):
    e=query("SELECT name FROM events WHERE id=?", (event_id,), True)
    execute("DELETE FROM events WHERE id=?", (event_id,))
    flash(f"Event '{e['name']}' deleted.", "success")
    return redirect(url_for("events"))

@app.route("/events/<int:event_id>")
@login_required
def event_detail(event_id):
    event = query("SELECT * FROM events WHERE id=?", (event_id,), True)
    if not event:
        return "Event not found", 404
    team = query("SELECT * FROM team_members WHERE event_id=? ORDER BY name", (event_id,))
    tasks = query("""SELECT t.*, tm.name assignee FROM tasks t
                     LEFT JOIN team_members tm ON tm.id=t.assigned_to
                     WHERE t.event_id=? ORDER BY CASE t.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, t.id DESC""", (event_id,))
    materials = query("SELECT * FROM materials WHERE event_id=? ORDER BY name", (event_id,))
    vendors = query("SELECT * FROM vendors WHERE event_id=? ORDER BY name", (event_id,))
    activities = query("SELECT * FROM activities WHERE event_id=? ORDER BY id DESC LIMIT 10", (event_id,))
    budget = query("""SELECT COALESCE(SUM(estimated_cost),0) estimated, COALESCE(SUM(actual_cost),0) actual
                     FROM vendors WHERE event_id=?""", (event_id,), True)
    return render_template("event.html", event=event, team=team, tasks=tasks, materials=materials,
                           vendors=vendors, activities=activities, budget=budget)

@app.route("/events/<int:event_id>/team/add", methods=["POST"])
@admin_required
def add_team(event_id):
    f=request.form
    execute("INSERT INTO team_members(event_id,name,email,role,phone) VALUES (?,?,?,?,?)",
            (event_id,f["name"],f["email"],f["role"],f.get("phone","")))
    log_activity(event_id, f"New team member {f['name']} added")
    flash("Team member added.", "success")
    return redirect(url_for("event_detail", event_id=event_id) + "#team")

@app.route("/team/<int:member_id>/delete", methods=["POST"])
@admin_required
def delete_team(member_id):
    member=query("SELECT * FROM team_members WHERE id=?", (member_id,), True)
    if member:
        execute("DELETE FROM team_members WHERE id=?", (member_id,))
        log_activity(member["event_id"], f"Team member {member['name']} removed")
        flash("Team member removed.", "success")
        return redirect(url_for("event_detail", event_id=member["event_id"]) + "#team")
    return redirect(url_for("dashboard"))

@app.route("/events/<int:event_id>/tasks/add", methods=["POST"])
@admin_required
def add_task(event_id):
    f=request.form
    execute("""INSERT INTO tasks(event_id,title,description,assigned_to,due_date,priority,status)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id,f["title"],f.get("description",""),f.get("assigned_to") or None,f.get("due_date",""),
             f.get("priority","Medium"),f.get("status","To Do")))
    log_activity(event_id, f"Task '{f['title']}' created")
    flash("Task created.", "success")
    return redirect(url_for("event_detail", event_id=event_id) + "#tasks")

def task_elapsed_seconds(task):
    total = int(task["elapsed_seconds"] or 0)
    if task["timer_started_at"]:
        try:
            started = datetime.fromisoformat(task["timer_started_at"])
            total += max(0, int((datetime.now() - started).total_seconds()))
        except ValueError:
            pass
    return total

@app.route("/tasks/<int:task_id>/timer/start", methods=["POST"])
@login_required
def start_task_timer(task_id):
    task=query("SELECT * FROM tasks WHERE id=?", (task_id,), True)
    if not task: return jsonify({"error":"Task not found"}),404
    if not task["timer_started_at"]:
        execute("UPDATE tasks SET timer_started_at=?, status='In Progress' WHERE id=?", (datetime.now().isoformat(timespec="seconds"),task_id))
        log_activity(task["event_id"], f"Timer started for {task['title']}")
    return redirect(url_for("event_detail",event_id=task["event_id"]) + "#tasks")

@app.route("/tasks/<int:task_id>/timer/pause", methods=["POST"])
@login_required
def pause_task_timer(task_id):
    task=query("SELECT * FROM tasks WHERE id=?", (task_id,), True)
    if not task: return jsonify({"error":"Task not found"}),404
    elapsed=task_elapsed_seconds(task)
    execute("UPDATE tasks SET elapsed_seconds=?, timer_started_at='' WHERE id=?", (elapsed,task_id))
    log_activity(task["event_id"], f"Timer paused for {task['title']}")
    return redirect(url_for("event_detail",event_id=task["event_id"]) + "#tasks")

@app.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_task_status(task_id):
    task=query("SELECT * FROM tasks WHERE id=?", (task_id,), True)
    if not task: return jsonify({"error":"Task not found"}),404
    status=request.form.get("status","To Do")
    if status not in TASK_STATUSES: return jsonify({"error":"Invalid status"}),400
    if status == "Completed":
        elapsed = task_elapsed_seconds(task)
        execute("UPDATE tasks SET status=?, elapsed_seconds=?, timer_started_at='' WHERE id=?", (status, elapsed, task_id))
    else:
        execute("UPDATE tasks SET status=? WHERE id=?", (status,task_id))
    if status=="Completed":
        log_activity(task["event_id"], f"{task['title']} completed")
    else:
        log_activity(task["event_id"], f"{task['title']} moved to {status}")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok":True, "progress":event_progress(task["event_id"])})
    return redirect(url_for("event_detail", event_id=task["event_id"]) + "#tasks")

@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@admin_required
def delete_task(task_id):
    task=query("SELECT * FROM tasks WHERE id=?", (task_id,), True)
    if task:
        execute("DELETE FROM tasks WHERE id=?", (task_id,))
        log_activity(task["event_id"], f"Task '{task['title']}' deleted")
        flash("Task deleted.", "success")
        return redirect(url_for("event_detail", event_id=task["event_id"]) + "#tasks")
    return redirect(url_for("dashboard"))

@app.route("/events/<int:event_id>/materials/add", methods=["POST"])
@admin_required
def add_material(event_id):
    f=request.form
    req=float(f.get("required_qty",0)); avail=float(f.get("available_qty",0))
    if req < 0 or avail < 0:
        flash("Quantities cannot be negative.", "error")
        return redirect(url_for("event_detail", event_id=event_id)+"#materials")
    execute("""INSERT INTO materials(event_id,name,category,required_qty,available_qty,unit,supplier)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id,f["name"],f.get("category",""),req,avail,f.get("unit","pieces"),f.get("supplier","")))
    log_activity(event_id, f"Material '{f['name']}' added")
    flash("Material added.", "success")
    return redirect(url_for("event_detail", event_id=event_id)+"#materials")

@app.route("/materials/<int:material_id>/update", methods=["POST"])
@admin_required
def update_material(material_id):
    m=query("SELECT * FROM materials WHERE id=?", (material_id,), True)
    if not m: return redirect(url_for("dashboard"))
    f=request.form
    req=float(f.get("required_qty",0)); avail=float(f.get("available_qty",0))
    if req < 0 or avail < 0:
        flash("Quantities cannot be negative.", "error")
        return redirect(url_for("event_detail", event_id=m["event_id"])+"#materials")
    execute("""UPDATE materials SET name=?,category=?,required_qty=?,available_qty=?,unit=?,supplier=? WHERE id=?""",
            (f["name"],f.get("category",""),req,avail,f.get("unit","pieces"),f.get("supplier",""),material_id))
    log_activity(m["event_id"], f"Material '{f['name']}' quantity updated")
    flash("Material updated.", "success")
    return redirect(url_for("event_detail", event_id=m["event_id"])+"#materials")

@app.route("/materials/<int:material_id>/delete", methods=["POST"])
@admin_required
def delete_material(material_id):
    m=query("SELECT * FROM materials WHERE id=?", (material_id,), True)
    if m:
        execute("DELETE FROM materials WHERE id=?", (material_id,))
        log_activity(m["event_id"], f"Material '{m['name']}' deleted")
        flash("Material deleted.", "success")
        return redirect(url_for("event_detail", event_id=m["event_id"])+"#materials")
    return redirect(url_for("dashboard"))

@app.route("/events/<int:event_id>/vendors/add", methods=["POST"])
@admin_required
def add_vendor(event_id):
    f=request.form
    execute("""INSERT INTO vendors(event_id,name,service,contact,estimated_cost,actual_cost,payment_status)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id,f["name"],f.get("service",""),f.get("contact",""),
             float(f.get("estimated_cost",0)),float(f.get("actual_cost",0)),f.get("payment_status","Pending")))
    log_activity(event_id, f"Vendor '{f['name']}' added")
    flash("Vendor added.", "success")
    return redirect(url_for("event_detail", event_id=event_id)+"#budget")

@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
@admin_required
def delete_vendor(vendor_id):
    v=query("SELECT * FROM vendors WHERE id=?", (vendor_id,), True)
    if v:
        execute("DELETE FROM vendors WHERE id=?", (vendor_id,))
        log_activity(v["event_id"], f"Vendor '{v['name']}' deleted")
        flash("Vendor deleted.", "success")
        return redirect(url_for("event_detail", event_id=v["event_id"])+"#budget")
    return redirect(url_for("dashboard"))


@app.route("/team/<int:member_id>/edit", methods=["POST"])
@admin_required
def edit_team(member_id):
    m = query("SELECT * FROM team_members WHERE id=?", (member_id,), True)
    if not m:
        return "Team member not found", 404
    f = request.form
    name = f.get("name", "").strip()
    email = f.get("email", "").strip()
    role = f.get("role", "").strip()
    if not name or not email or not role:
        flash("Name, email and role are required.", "error")
        return redirect(url_for("event_detail", event_id=m["event_id"]) + "#team")
    execute("UPDATE team_members SET name=?,email=?,role=?,phone=? WHERE id=?", (name,email,role,f.get("phone",""),member_id))
    log_activity(m["event_id"], f"Team member {name} updated")
    flash("Team member updated.", "success")
    return redirect(url_for("event_detail", event_id=m["event_id"]) + "#team")

@app.route("/tasks/<int:task_id>/edit", methods=["POST"])
@admin_required
def edit_task(task_id):
    t = query("SELECT * FROM tasks WHERE id=?", (task_id,), True)
    if not t:
        return "Task not found", 404
    f = request.form
    title = f.get("title", "").strip()
    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("event_detail", event_id=t["event_id"]) + "#tasks")
    execute("UPDATE tasks SET title=?,description=?,assigned_to=?,due_date=?,priority=?,status=? WHERE id=?", (title,f.get("description",""),f.get("assigned_to") or None,f.get("due_date",""),f.get("priority","Medium"),f.get("status","To Do"),task_id))
    log_activity(t["event_id"], f"Task '{title}' updated")
    flash("Task updated.", "success")
    return redirect(url_for("event_detail", event_id=t["event_id"]) + "#tasks")

@app.route("/vendors/<int:vendor_id>/edit", methods=["POST"])
@admin_required
def edit_vendor(vendor_id):
    v = query("SELECT * FROM vendors WHERE id=?", (vendor_id,), True)
    if not v:
        return "Vendor not found", 404
    f=request.form
    try:
        estimated=float(f.get("estimated_cost",0)); actual=float(f.get("actual_cost",0))
        if estimated < 0 or actual < 0: raise ValueError
    except ValueError:
        flash("Costs cannot be negative.", "error")
        return redirect(url_for("event_detail", event_id=v["event_id"]) + "#budget")
    name=f.get("name","").strip()
    if not name:
        flash("Vendor name is required.", "error")
        return redirect(url_for("event_detail", event_id=v["event_id"]) + "#budget")
    execute("UPDATE vendors SET name=?,service=?,contact=?,estimated_cost=?,actual_cost=?,payment_status=? WHERE id=?", (name,f.get("service",""),f.get("contact",""),estimated,actual,f.get("payment_status","Pending"),vendor_id))
    log_activity(v["event_id"], f"Vendor '{name}' updated")
    flash("Vendor updated.", "success")
    return redirect(url_for("event_detail", event_id=v["event_id"]) + "#budget")

@app.route("/team")
@login_required
def team_page():
    q=request.args.get("q","").strip()
    sql="""SELECT tm.*,e.name event_name,(SELECT COUNT(*) FROM tasks t WHERE t.assigned_to=tm.id) task_count
           FROM team_members tm JOIN events e ON e.id=tm.event_id WHERE 1=1"""
    params=[]
    if q:
        sql += " AND (tm.name LIKE ? OR tm.role LIKE ? OR e.name LIKE ?)"
        params += [f"%{q}%"]*3
    sql += " ORDER BY tm.name"
    return render_template("list.html", page_title="Team", page_desc="People and responsibilities across all events.", kind="team", rows=query(sql,params), q=q)

@app.route("/tasks")
@login_required
def tasks_page():
    q=request.args.get("q","").strip(); status=request.args.get("status",""); priority=request.args.get("priority","")
    sql="""SELECT t.*,e.name event_name,tm.name assignee FROM tasks t JOIN events e ON e.id=t.event_id
           LEFT JOIN team_members tm ON tm.id=t.assigned_to WHERE 1=1"""
    params=[]
    if q:
        sql += " AND (t.title LIKE ? OR t.description LIKE ? OR e.name LIKE ?)"; params += [f"%{q}%"]*3
    if status: sql += " AND t.status=?"; params.append(status)
    if priority: sql += " AND t.priority=?"; params.append(priority)
    sql += " ORDER BY t.due_date, t.id DESC"
    return render_template("list.html", page_title="Tasks", page_desc="A single view of work across every event.", kind="tasks", rows=query(sql,params), q=q, status=status, priority=priority, task_statuses=TASK_STATUSES, priorities=PRIORITIES)

@app.route("/materials")
@login_required
def materials_page():
    q=request.args.get("q","").strip(); status=request.args.get("status","")
    sql="SELECT m.*,e.name event_name FROM materials m JOIN events e ON e.id=m.event_id WHERE 1=1"; params=[]
    if q:
        sql += " AND (m.name LIKE ? OR m.category LIKE ? OR e.name LIKE ?)"; params += [f"%{q}%"]*3
    rows=query(sql+" ORDER BY m.name",params)
    if status:
        rows=[r for r in rows if material_status(r)==status]
    return render_template("list.html", page_title="Materials", page_desc="Inventory readiness across all events.", kind="materials", rows=rows, q=q, status=status)

@app.route("/vendors")
@login_required
def vendors_page():
    q=request.args.get("q","").strip()
    sql="SELECT v.*,e.name event_name FROM vendors v JOIN events e ON e.id=v.event_id WHERE 1=1"; params=[]
    if q:
        sql += " AND (v.name LIKE ? OR v.service LIKE ? OR e.name LIKE ?)"; params += [f"%{q}%"]*3
    rows=query(sql+" ORDER BY v.name",params)
    totals=query("SELECT COALESCE(SUM(estimated_cost),0) estimated,COALESCE(SUM(actual_cost),0) actual FROM vendors",one=True)
    return render_template("list.html", page_title="Vendors & Budget", page_desc="Suppliers, payments and spending across your events.", kind="vendors", rows=rows, q=q, totals=totals)

@app.route("/activity")
@login_required
def activity_page():
    rows=query("SELECT a.*,e.name event_name FROM activities a JOIN events e ON e.id=a.event_id ORDER BY a.id DESC LIMIT 100")
    return render_template("list.html", page_title="Activity", page_desc="A history of important changes in EventFlow.", kind="activity", rows=rows)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)

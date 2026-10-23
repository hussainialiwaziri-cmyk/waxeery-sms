
from flask import Flask, request, jsonify, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps

app = Flask(__name__)
import os
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "544ba16e251ef025ac5bf5d0fd169339d14901ed9b5fe73c198e00bb2c0ca186")

DB_NAME = "students.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                matric TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                level TEXT NOT NULL,
                course TEXT NOT NULL DEFAULT ''
            )
        """)

        columns = [
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(students)"
            ).fetchall()
        ]

        if "course" not in columns:
            db.execute("""
                ALTER TABLE students
                ADD COLUMN course TEXT NOT NULL DEFAULT ''
            """)

        user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            ("admin",)
        ).fetchone()

        if user is None:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                ("admin", generate_password_hash("Admin123!"))
            )


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return jsonify({
            "message": "Login successful",
            "redirect": "/dashboard"
        })

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/students", methods=["GET", "POST"])
@login_required
def students():
    with get_db() as db:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}

            name = data.get("name", "").strip()
            matric = data.get("matric", "").strip()
            department = data.get("department", "").strip()
            level = data.get("level", "").strip()
            course = data.get("course", "").strip()

            if not all([name, matric, department, level]):
                return jsonify({
                    "error": "Name, matric, department and level are required"
                }), 400

            try:
                db.execute("""
                    INSERT INTO students
                    (name, matric, department, level, course)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, matric, department, level, course))
            except sqlite3.IntegrityError:
                return jsonify({
                    "error": "Matric number already exists"
                }), 409

            return jsonify({
                "message": "Student added successfully"
            }), 201

        rows = db.execute(
            "SELECT * FROM students ORDER BY id DESC"
        ).fetchall()

        return jsonify([dict(row) for row in rows])


@app.route("/api/students/<int:student_id>", methods=["PUT", "DELETE"])
@login_required
def student_detail(student_id):
    with get_db() as db:
        student = db.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if student is None:
            return jsonify({"error": "Student not found"}), 404

        if request.method == "PUT":
            data = request.get_json(silent=True) or {}

            name = data.get("name", "").strip()
            matric = data.get("matric", "").strip()
            department = data.get("department", "").strip()
            level = data.get("level", "").strip()
            course = data.get("course", "").strip()

            if not all([name, matric, department, level]):
                return jsonify({
                    "error": "Name, matric, department and level are required"
                }), 400

            try:
                db.execute("""
                    UPDATE students
                    SET name = ?, matric = ?, department = ?,
                        level = ?, course = ?
                    WHERE id = ?
                """, (
                    name, matric, department, level,
                    course, student_id
                ))
            except sqlite3.IntegrityError:
                return jsonify({
                    "error": "Matric number already exists"
                }), 409

            return jsonify({
                "message": "Student updated successfully"
            })

        db.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )
        return jsonify({
            "message": "Student deleted successfully"
        })



@app.route("/api/course-registrations", methods=["GET", "POST"])
@login_required
def course_registrations():
    with get_db() as db:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}

            student_id = data.get("student_id")
            course_code = data.get("course_code", "").strip().upper()
            course_title = data.get("course_title", "").strip()
            semester = data.get("semester", "First Semester").strip()
            session_name = data.get("session", "2026/2027").strip()

            if not student_id or not course_code:
                return jsonify({
                    "error": "Student ID and course code are required"
                }), 400

            student = db.execute(
                "SELECT id FROM students WHERE id = ?",
                (student_id,)
            ).fetchone()

            if student is None:
                return jsonify({"error": "Student not found"}), 404

            try:
                db.execute("""
                    INSERT INTO course_registrations
                    (student_id, course_code, course_title, semester, session)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id, course_code, course_title,
                    semester, session_name
                ))
            except sqlite3.IntegrityError:
                return jsonify({
                    "error": "This course is already registered for this semester and session"
                }), 409

            return jsonify({
                "message": "Course registered successfully"
            }), 201

        student_id = request.args.get("student_id")

        if student_id:
            rows = db.execute("""
                SELECT cr.*, s.name, s.matric
                FROM course_registrations cr
                JOIN students s ON s.id = cr.student_id
                WHERE cr.student_id = ?
                ORDER BY cr.id DESC
            """, (student_id,)).fetchall()
        else:
            rows = db.execute("""
                SELECT cr.*, s.name, s.matric
                FROM course_registrations cr
                JOIN students s ON s.id = cr.student_id
                ORDER BY cr.id DESC
            """).fetchall()

        return jsonify([dict(row) for row in rows])


@app.route("/api/course-registrations/<int:registration_id>", methods=["DELETE"])
@login_required
def delete_course_registration(registration_id):
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM course_registrations WHERE id = ?",
            (registration_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({"error": "Registration not found"}), 404

        return jsonify({"message": "Course registration deleted successfully"})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)




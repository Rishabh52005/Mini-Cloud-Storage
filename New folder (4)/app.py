import mimetypes
import os
import re
import secrets
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

import mysql.connector
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from mysql.connector import Error, IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "storage" / "uploads"
DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
SCHEMA_READY = False

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    DB_HOST=os.environ.get("DB_HOST", "localhost"),
    DB_PORT=int(os.environ.get("DB_PORT", "3306")),
    DB_USER=os.environ.get("DB_USER", "root"),
    DB_PASSWORD=os.environ.get("DB_PASSWORD", "Chugh123@"),
    DB_NAME=os.environ.get("DB_NAME", "skyshelf"),
    UPLOAD_FOLDER=str(UPLOAD_FOLDER),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
)

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def utcnow_trimmed():
    return datetime.utcnow().replace(microsecond=0)


def validate_database_name(name):
    if not DATABASE_NAME_PATTERN.fullmatch(name):
        raise ValueError("DB_NAME can only contain letters, numbers, and underscores.")
    return name


def build_db_config(use_database=True):
    config = {
        "host": app.config["DB_HOST"],
        "port": app.config["DB_PORT"],
        "user": app.config["DB_USER"],
        "password": app.config["DB_PASSWORD"],
        "charset": "utf8mb4",
    }
    if use_database:
        config["database"] = validate_database_name(app.config["DB_NAME"])
    return config


def create_db_connection(use_database=True):
    return mysql.connector.connect(**build_db_config(use_database=use_database))


def get_db():
    if "db" not in g:
        g.db = create_db_connection(use_database=True)
    else:
        try:
            g.db.ping(reconnect=True, attempts=1, delay=0)
        except Error:
            g.db.close()
            g.db = create_db_connection(use_database=True)
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def fetch_one(query, params=None):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()


def fetch_all(query, params=None):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()


def execute_write(query, params=None):
    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def init_db():
    global SCHEMA_READY

    db_name = validate_database_name(app.config["DB_NAME"])

    server_connection = create_db_connection(use_database=False)
    server_cursor = server_connection.cursor()
    try:
        server_cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        server_connection.commit()
    finally:
        server_cursor.close()
        server_connection.close()

    schema_connection = create_db_connection(use_database=True)
    schema_cursor = schema_connection.cursor()
    try:
        schema_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL
            ) ENGINE=InnoDB
            """
        )
        schema_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id INT NOT NULL,
                original_name VARCHAR(255) NOT NULL,
                stored_name VARCHAR(255) NOT NULL UNIQUE,
                size BIGINT NOT NULL,
                mime_type VARCHAR(255) NOT NULL,
                is_public BOOLEAN NOT NULL DEFAULT FALSE,
                share_token VARCHAR(255) UNIQUE,
                uploaded_at DATETIME NOT NULL,
                CONSTRAINT fk_files_owner
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
            """
        )
        schema_connection.commit()
    finally:
        schema_cursor.close()
        schema_connection.close()

    SCHEMA_READY = True


def ensure_db_ready():
    if not SCHEMA_READY:
        init_db()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def get_owned_file(file_id):
    file_row = fetch_one(
        """
        SELECT id, owner_id, original_name, stored_name, size, mime_type,
               is_public, share_token, uploaded_at
        FROM files
        WHERE id = %s AND owner_id = %s
        """,
        (file_id, g.user["id"]),
    )

    if file_row is None:
        abort(404)
    return file_row


def get_public_file(token):
    file_row = fetch_one(
        """
        SELECT f.id, f.original_name, f.stored_name, f.size, f.mime_type,
               f.uploaded_at, u.username
        FROM files f
        JOIN users u ON u.id = f.owner_id
        WHERE f.share_token = %s AND f.is_public = 1
        """,
        (token,),
    )

    if file_row is None:
        abort(404)
    return file_row


@app.template_filter("filesize")
def format_filesize(size):
    value = float(size or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"


@app.template_filter("humandate")
def format_humandate(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return value
    return parsed.strftime("%b %d, %Y at %I:%M %p")


@app.before_request
def load_logged_in_user():
    ensure_db_ready()
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = fetch_one(
            "SELECT id, username, created_at FROM users WHERE id = %s",
            (user_id,),
        )


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(_error):
    flash("That file is too large. The current limit is 50 MB.", "warning")
    destination = "dashboard" if session.get("user_id") else "home"
    return redirect(url_for(destination))


@app.errorhandler(404)
def not_found(_error):
    return render_template("not_found.html"), 404


@app.route("/")
def home():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3:
            flash("Choose a username with at least 3 characters.", "warning")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Choose a password with at least 6 characters.", "warning")
            return redirect(url_for("register"))

        try:
            execute_write(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (%s, %s, %s)
                """,
                (username, generate_password_hash(password), utcnow_trimmed()),
            )
        except IntegrityError:
            flash("That username is already taken.", "danger")
            return redirect(url_for("register"))

        flash("Account created. Sign in to start uploading.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = fetch_one(
            """
            SELECT id, username, password_hash
            FROM users
            WHERE username = %s
            """,
            (username,),
        )

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "danger")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['username']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    files = fetch_all(
        """
        SELECT id, original_name, stored_name, size, mime_type,
               is_public, share_token, uploaded_at
        FROM files
        WHERE owner_id = %s
        ORDER BY uploaded_at DESC
        """,
        (g.user["id"],),
    )

    stats = fetch_one(
        """
        SELECT COUNT(*) AS file_count,
               COALESCE(SUM(size), 0) AS storage_used,
               COALESCE(SUM(CASE WHEN is_public = 1 THEN 1 ELSE 0 END), 0) AS public_files
        FROM files
        WHERE owner_id = %s
        """,
        (g.user["id"],),
    )

    return render_template("dashboard.html", files=files, stats=stats)


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or uploaded_file.filename == "":
        flash("Choose a file before uploading.", "warning")
        return redirect(url_for("dashboard"))

    safe_name = secure_filename(uploaded_file.filename) or f"upload-{uuid.uuid4().hex}"
    stored_name = f"{uuid.uuid4().hex}{Path(safe_name).suffix}"
    file_path = Path(app.config["UPLOAD_FOLDER"]) / stored_name

    uploaded_file.save(file_path)

    mime_type = (
        uploaded_file.mimetype
        or mimetypes.guess_type(safe_name)[0]
        or "application/octet-stream"
    )
    size = file_path.stat().st_size

    execute_write(
        """
        INSERT INTO files (
            owner_id, original_name, stored_name, size,
            mime_type, uploaded_at
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (g.user["id"], safe_name, stored_name, size, mime_type, utcnow_trimmed()),
    )

    flash(f"{safe_name} uploaded successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/files/<int:file_id>/download")
@login_required
def download_file(file_id):
    file_row = get_owned_file(file_id)
    file_path = Path(app.config["UPLOAD_FOLDER"]) / file_row["stored_name"]
    if not file_path.exists():
        abort(404)

    return send_file(
        BytesIO(file_path.read_bytes()),
        as_attachment=True,
        download_name=file_row["original_name"],
        mimetype=file_row["mime_type"],
    )


@app.route("/files/<int:file_id>/share", methods=["POST"])
@login_required
def share_file(file_id):
    file_row = get_owned_file(file_id)
    share_token = file_row["share_token"] or secrets.token_urlsafe(18)

    execute_write(
        """
        UPDATE files
        SET is_public = 1, share_token = %s
        WHERE id = %s
        """,
        (share_token, file_row["id"]),
    )

    flash("Share link is live and ready to copy.", "success")
    return redirect(url_for("dashboard"))


@app.route("/files/<int:file_id>/revoke", methods=["POST"])
@login_required
def revoke_share(file_id):
    file_row = get_owned_file(file_id)

    execute_write(
        "UPDATE files SET is_public = 0 WHERE id = %s",
        (file_row["id"],),
    )

    flash("Public access revoked for that file.", "success")
    return redirect(url_for("dashboard"))


@app.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def delete_file(file_id):
    file_row = get_owned_file(file_id)
    file_path = Path(app.config["UPLOAD_FOLDER"]) / file_row["stored_name"]

    execute_write("DELETE FROM files WHERE id = %s", (file_row["id"],))

    if file_path.exists():
        file_path.unlink()

    flash(f"{file_row['original_name']} was deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/s/<token>")
def public_share(token):
    shared_file = get_public_file(token)
    return render_template("share.html", shared_file=shared_file, share_token=token)


@app.route("/s/<token>/download")
def public_download(token):
    shared_file = get_public_file(token)
    file_path = Path(app.config["UPLOAD_FOLDER"]) / shared_file["stored_name"]
    if not file_path.exists():
        abort(404)

    return send_file(
        BytesIO(file_path.read_bytes()),
        as_attachment=True,
        download_name=shared_file["original_name"],
        mimetype=shared_file["mime_type"],
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

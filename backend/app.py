import os
import time
from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

def get_connection():
    config = {
        "host": os.getenv("DB_HOST", "db"),
        "database": os.getenv("MYSQL_DATABASE", "taskflow"),
        "user": os.getenv("MYSQL_USER", "taskflow_user"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "connection_timeout": 5,
    }

    last_error = None
    for _ in range(10):
        try:
            return mysql.connector.connect(**config)
        except Error as exc:
            last_error = exc
            time.sleep(2)

    raise last_error

@app.get("/api/health")
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify(status="healthy", database="connected")
    except Exception:
        app.logger.exception("Database health check failed")
        return jsonify(status="unhealthy", database="unavailable"), 503

@app.get("/api/tasks")
def list_tasks():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, title, status, created_at FROM tasks ORDER BY id DESC"
        )
        tasks = cursor.fetchall()
        for task in tasks:
            task["created_at"] = task["created_at"].isoformat()
        return jsonify(tasks)
    except Exception:
        app.logger.exception("Could not list tasks")
        return jsonify(error="Unable to load tasks"), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="Task title is required"), 400
    if len(title.strip()) > 200:
        return jsonify(error="Title must be 200 characters or fewer"), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title) VALUES (%s)", (title.strip(),)
        )
        conn.commit()
        task_id = cursor.lastrowid
        return jsonify(id=task_id, title=title.strip(),
                       status="Pending"), 201
    except Exception:
        app.logger.exception("Could not create task")
        return jsonify(error="Unable to create task"), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed = {"Pending", "In Progress", "Completed"}

    if status not in allowed:
        return jsonify(error="Invalid task status"), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = %s WHERE id = %s",
            (status, task_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify(error="Task not found"), 404
        return jsonify(id=task_id, status=status)
    except Exception:
        app.logger.exception("Could not update task")
        return jsonify(error="Unable to update task"), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify(error="Task not found"), 404
        return jsonify(message="Task deleted")
    except Exception:
        app.logger.exception("Could not delete task")
        return jsonify(error="Unable to delete task"), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

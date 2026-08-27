"""
University Library Management System
--------------------------------------
A Flask web application that catalogs books across academic categories,
supports search/filtering, and lets staff add new titles.

Run directly:
    python main.py

The app listens on 0.0.0.0:8080 by default (overridable with the PORT
environment variable), which matches the port exposed in the Dockerfile.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime

from flask import Flask, render_template, request, g, redirect, url_for, flash, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(APP_DIR, "library.db")
PORT = int(os.environ.get("PORT", 8080))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# ---------------------------------------------------------------------------
# Categories recognized by the "universal library standard" used here, loosely
# modeled on common academic library classification groupings.
# ---------------------------------------------------------------------------
CATEGORIES = [
    "Computer Science",
    "Mathematics",
    "Physics",
    "Engineering",
    "Life Sciences",
    "Business & Economics",
    "Law",
    "Medicine",
    "History",
    "Philosophy",
    "Literature",
    "Arts & Design",
    "Social Sciences",
    "Languages",
    "Reference",
]

SEED_BOOKS = [
    ("Introduction to Algorithms", "Cormen, Leiserson, Rivest, Stein", "Computer Science", 2009, "004.5", 12, "A comprehensive guide to modern algorithm design and analysis."),
    ("Clean Code", "Robert C. Martin", "Computer Science", 2008, "005.1", 8, "A handbook of agile software craftsmanship."),
    ("Structure and Interpretation of Computer Programs", "Abelson & Sussman", "Computer Science", 1996, "005.13", 5, "Classic MIT text on programming fundamentals."),
    ("Calculus", "James Stewart", "Mathematics", 2015, "515", 15, "Early transcendentals approach to calculus."),
    ("Linear Algebra Done Right", "Sheldon Axler", "Mathematics", 2015, "512.5", 10, "A theorem-proof approach to linear algebra."),
    ("Introduction to Probability", "Bertsekas & Tsitsiklis", "Mathematics", 2008, "519.2", 6, "Foundational probability theory for engineers."),
    ("The Feynman Lectures on Physics", "Richard Feynman", "Physics", 1964, "530", 9, "Landmark physics lecture series covering mechanics to quantum theory."),
    ("Introduction to Electrodynamics", "David J. Griffiths", "Physics", 2017, "537", 7, "Standard undergraduate text on electromagnetism."),
    ("Fundamentals of Fluid Mechanics", "Munson et al.", "Engineering", 2012, "620.1", 4, "Core mechanical engineering reference."),
    ("Materials Science and Engineering", "William D. Callister", "Engineering", 2013, "620.11", 6, "An introduction to materials properties and applications."),
    ("Campbell Biology", "Reece et al.", "Life Sciences", 2016, "570", 11, "Comprehensive introductory biology textbook."),
    ("The Selfish Gene", "Richard Dawkins", "Life Sciences", 1976, "576.5", 5, "Influential work on evolutionary biology."),
    ("Principles of Economics", "N. Gregory Mankiw", "Business & Economics", 2020, "330", 14, "Widely used introductory economics textbook."),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "Business & Economics", 2011, "153.4", 9, "Behavioral economics and decision-making."),
    ("Constitutional Law", "Erwin Chemerinsky", "Law", 2019, "342", 3, "Principles and policies of constitutional law."),
    ("Gray's Anatomy", "Henry Gray", "Medicine", 2020, "611", 4, "Definitive reference on human anatomy."),
    ("A People's History of the United States", "Howard Zinn", "History", 1980, "973", 8, "American history from a bottom-up perspective."),
    ("Sapiens: A Brief History of Humankind", "Yuval Noah Harari", "History", 2011, "909", 13, "A sweeping narrative of human history."),
    ("Meditations", "Marcus Aurelius", "Philosophy", 180, "188", 10, "Stoic philosophy in the form of personal reflections."),
    ("Being and Time", "Martin Heidegger", "Philosophy", 1927, "111", 3, "Foundational text of existential phenomenology."),
    ("One Hundred Years of Solitude", "Gabriel García Márquez", "Literature", 1967, "863", 7, "Magical realism masterpiece of the Buendía family."),
    ("Pride and Prejudice", "Jane Austen", "Literature", 1813, "823", 9, "Classic novel of manners and marriage in Regency England."),
    ("The Story of Art", "E.H. Gombrich", "Arts & Design", 1950, "709", 6, "A beloved survey of the history of art."),
    ("Design of Everyday Things", "Don Norman", "Arts & Design", 2013, "745.2", 8, "A foundational text on human-centered design."),
    ("The Social Construction of Reality", "Berger & Luckmann", "Social Sciences", 1966, "301", 4, "Foundational text in the sociology of knowledge."),
    ("Outliers", "Malcolm Gladwell", "Social Sciences", 2008, "305", 12, "An exploration of the factors behind success."),
    ("501 Spanish Verbs", "Christopher Kendris", "Languages", 2018, "468.2", 6, "Comprehensive Spanish verb conjugation reference."),
    ("Oxford English Dictionary (Concise)", "Oxford University Press", "Reference", 2011, "423", 5, "Authoritative reference for the English language."),
]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DATABASE)) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                year INTEGER,
                call_number TEXT,
                copies INTEGER DEFAULT 1,
                description TEXT,
                created_at TEXT
            )
            """
        )
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            now = datetime.utcnow().isoformat()
            db.executemany(
                """INSERT INTO books
                   (title, author, category, year, call_number, copies, description, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(t, a, c, y, cn, cp, desc, now) for (t, a, c, y, cn, cp, desc) in SEED_BOOKS],
            )
            db.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    category_counts = db.execute(
        "SELECT category, COUNT(*) as total, SUM(copies) as copies FROM books GROUP BY category"
    ).fetchall()
    counts_by_cat = {row["category"]: row for row in category_counts}
    total_books = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    total_copies = db.execute("SELECT SUM(copies) FROM books").fetchone()[0] or 0
    recent = db.execute("SELECT * FROM books ORDER BY id DESC LIMIT 6").fetchall()
    return render_template(
        "index.html",
        categories=CATEGORIES,
        counts_by_cat=counts_by_cat,
        total_books=total_books,
        total_copies=total_copies,
        recent=recent,
    )


@app.route("/category/<path:category>")
def category_view(category):
    db = get_db()
    books = db.execute(
        "SELECT * FROM books WHERE category = ? ORDER BY title", (category,)
    ).fetchall()
    return render_template("category.html", category=category, books=books, categories=CATEGORIES)


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        flash("Book not found.")
        return redirect(url_for("index"))
    return render_template("book.html", book=book, categories=CATEGORIES)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        like = f"%{q}%"
        books = db.execute(
            """SELECT * FROM books
               WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
               ORDER BY title""",
            (like, like, like),
        ).fetchall()
    else:
        books = []
    return render_template("search.html", query=q, books=books, categories=CATEGORIES)


@app.route("/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        year = request.form.get("year", "").strip() or None
        call_number = request.form.get("call_number", "").strip()
        copies = request.form.get("copies", "1").strip() or "1"
        description = request.form.get("description", "").strip()

        if not title or not author or not category:
            flash("Title, author, and category are required.")
            return redirect(url_for("add_book"))

        db = get_db()
        db.execute(
            """INSERT INTO books (title, author, category, year, call_number, copies, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, author, category, year, call_number, int(copies), description, datetime.utcnow().isoformat()),
        )
        db.commit()
        flash(f'"{title}" was added to the catalog.')
        return redirect(url_for("category_view", category=category))

    return render_template("add.html", categories=CATEGORIES)


@app.route("/api/books")
def api_books():
    """JSON API endpoint, e.g. /api/books?category=Physics"""
    db = get_db()
    category = request.args.get("category")
    if category:
        rows = db.execute("SELECT * FROM books WHERE category = ?", (category,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM books").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
else:
    # Ensure DB is initialized when run under a WSGI server (e.g. gunicorn)
    init_db()

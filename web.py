from flask import Flask
import os
import json
import random
from datetime import datetime
from email.mime.text import MIMEText
import smtplib

# === Config ===
GMAIL_ADDRESS = os.environ['GMAIL_ADDRESS']
APP_PASSWORD = os.environ['APP_PASSWORD']
RECIPIENTS = os.environ['RECIPIENTS'].split(',')
PUZZLE_FILE = "puzzles.json"

# === Init ===
app = Flask(__name__)

with open(PUZZLE_FILE, "r") as f:
    all_puzzles = json.load(f)


def load_counter():
    return db.get("counter", {
        "used_ids": [],
        "used_titles": [],
        "alternator": 0
    })


def save_counter(counter):
    db["counter"] = counter


def log_sent_email(subject, body):
    now = datetime.now().isoformat()
    logs = db.get("email_logs", [])
    logs.append({"timestamp": now, "subject": subject, "body": body})
    db["email_logs"] = logs


def select_diverse_puzzles(puzzles, counter):
    used_ids = set(counter.get("used_ids", []))
    used_titles = set(counter.get("used_titles", []))
    alt_count = counter.get("alternator", 0)

    fresh = [
        p for p in puzzles
        if p['id'] not in used_ids and p['title'] not in used_titles
    ]
    easy = [p for p in fresh if p.get('difficulty') == 'easy']
    medium = [p for p in fresh if p.get('difficulty') == 'medium']
    hard = [p for p in fresh if p.get('difficulty') == 'hard']

    hard_or_medium = hard if alt_count % 2 == 0 else medium
    if not easy or not hard_or_medium:
        raise Exception("Not enough puzzles to satisfy constraints")

    selected = [random.choice(easy), random.choice(hard_or_medium)]

    counter['used_ids'].extend([p['id'] for p in selected])
    counter['used_titles'].extend([p['title'] for p in selected])
    counter['alternator'] = alt_count + 1

    return selected


def format_puzzles(puzzles, mode="question"):
    formatted = []
    for i, p in enumerate(puzzles):
        parts = [f"🧩 Puzzle {i+1}: {p['title']} ({p['difficulty']})"]
        if mode == "question":
            parts.append(p['Question'])
        elif mode == "hint" and 'Hint' in p:
            parts.append(f"💡 Hint: {p['Hint']}")
        elif mode == "solution":
            parts.append(
                f"✅ Answer: {p.get('Answer', 'N/A')}\n🧠 Solution: {p.get('Solution', 'N/A')}"
            )
        parts.append(
            f"🔗 https://brainstellar.com/puzzles/{p['difficulty']}/{p['id']}\n{'-'*40}"
        )
        formatted.append("\n".join(parts))
    return "\n\n".join(formatted)


def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = ", ".join(RECIPIENTS)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(GMAIL_ADDRESS, APP_PASSWORD)
        smtp.sendmail(GMAIL_ADDRESS, RECIPIENTS, msg.as_string())

    log_sent_email(subject, body)


def handle_send(mode):
    subject_map = {
        "question": "🧩 Your Daily Puzzle Challenge",
        "hint": "💡 Hints for Today’s Puzzle",
        "solution": "✅ Solutions to Today’s Puzzle"
    }

    if mode == "question":
        counter = load_counter()
        puzzles = select_diverse_puzzles(all_puzzles, counter)
        save_counter(counter)
        db["today_puzzles"] = puzzles  # 🔐 Save today's puzzles
    else:
        puzzles = db.get("today_puzzles")
        if not puzzles:
            raise Exception(
                "No puzzles stored for today. Run /send-question first.")

    email_subject = subject_map[mode]
    email_body = format_puzzles(puzzles, mode=mode)
    send_email(email_subject, email_body)


# === Web Endpoints ===
@app.route("/")
def home():
    return "🧠 PuzzleMailer is running!"


@app.route("/send-question")
def send_question():
    handle_send("question")
    return "✅ Sent question email"


@app.route("/send-hint")
def send_hint():
    handle_send("hint")
    return "✅ Sent hint email"


@app.route("/send-solution")
def send_solution():
    handle_send("solution")
    return "✅ Sent solution email"


# === Start Flask server ===
app.run(host="0.0.0.0", port=3000)

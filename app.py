from flask import Flask, request, jsonify, render_template, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
import os
import csv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

CSV_FILE = "survey_results.csv"
call_data = {}

# Variables de entorno
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

# Voz preferida
PREFERRED_VOICE = "Polly.Joanna-Generative"
VOICE_LANGUAGE = "en-US"


def normalize_phone(phone_number: str) -> str:
    phone_number = phone_number.strip()
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    return phone_number


def ensure_csv_exists():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "timestamp_utc",
                "call_sid",
                "to_number",
                "from_number",
                "question_1",
                "question_2",
                "question_3",
                "short_notes"
            ])


def build_short_notes(q1: str, q2: str, q3: str) -> str:
    return (
        f"Related to: {q1 or 'No answer'}. "
        f"Main issue: {q2 or 'No answer'}. "
        f"Situation: {q3 or 'No answer'}."
    )


def save_to_csv(call_sid: str):
    ensure_csv_exists()
    data = call_data.get(call_sid, {})

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.utcnow().isoformat(),
            call_sid,
            data.get("to_number", ""),
            data.get("from_number", ""),
            data.get("q1", ""),
            data.get("q2", ""),
            data.get("q3", ""),
            build_short_notes(
                data.get("q1", ""),
                data.get("q2", ""),
                data.get("q3", "")
            )
        ])


def create_client():
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )


@app.route("/", methods=["GET"])
def home():
    return render_template("dashboard.html")


@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/results-json", methods=["GET"])
def results_json():
    ensure_csv_exists()
    rows = []
    with open(CSV_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(row)
    return jsonify(rows)


@app.route("/download-results", methods=["GET"])
def download_results():
    ensure_csv_exists()
    return send_file(
        CSV_FILE,
        as_attachment=True,
        download_name="survey_results.csv",
        mimetype="text/csv"
    )


@app.route("/voice", methods=["GET", "POST"])
def voice():
    response = VoiceResponse()

    call_sid = request.values.get("CallSid", "")
    to_number = request.values.get("To", "")
    from_number = request.values.get("From", "")

    call_data[call_sid] = {
        "to_number": to_number,
        "from_number": from_number,
        "q1": "",
        "q2": "",
        "q3": ""
    }

    gather = Gather(
        input="speech dtmf",
        timeout=2,
        speech_timeout="auto",
        num_digits=1,
        action="/question1",
        method="POST"
    )

    gather.say(
        (
            "Hello. This is an automated survey call from Command Alkon. "
            "This call may be recorded for quality and documentation purposes. "
            "Do you have two minutes to answer three short questions? "
            "Press 1 or say yes to continue."
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        "We did not receive a response. Goodbye.",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question1", methods=["GET", "POST"])
def question1():
    speech = request.form.get("SpeechResult", "")
    digits = request.form.get("Digits", "")

    response = VoiceResponse()
    accepted = digits == "1" or "yes" in speech.lower()

    if not accepted:
        response.say(
            "No problem. Goodbye.",
            voice=PREFERRED_VOICE,
            language=VOICE_LANGUAGE
        )
        response.hangup()
        return str(response), 200, {"Content-Type": "text/xml"}

    gather = Gather(
        input="speech",
        timeout=2,
        speech_timeout="auto",
        action="/question2",
        method="POST"
    )
    gather.say(
        "First question. Is this related to a recent support case, or is it something more general?",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question2", methods=["GET", "POST"])
def question2():
    answer1 = request.form.get("SpeechResult", "").strip()
    call_sid = request.values.get("CallSid", "")

    if call_sid in call_data:
        call_data[call_sid]["q1"] = answer1

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        timeout=2,
        speech_timeout="auto",
        action="/question3",
        method="POST"
    )
    gather.say(
        "Second question. What was the main issue you experienced?",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question3", methods=["GET", "POST"])
def question3():
    answer2 = request.form.get("SpeechResult", "").strip()
    call_sid = request.values.get("CallSid", "")

    if call_sid in call_data:
        call_data[call_sid]["q2"] = answer2

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        timeout=2,
        speech_timeout="auto",
        action="/complete",
        method="POST"
    )
    gather.say(
        "Final question. Has this been recurring, or was it a one time issue?",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/complete", methods=["GET", "POST"])
def complete():
    answer3 = request.form.get("SpeechResult", "").strip()
    call_sid = request.values.get("CallSid", "")

    if call_sid in call_data:
        call_data[call_sid]["q3"] = answer3
        save_to_csv(call_sid)

    response = VoiceResponse()
    response.say(
        "Thank you. Your responses have been recorded. Goodbye.",
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/call/<path:phone_number>", methods=["GET"])
def make_call_pretty(phone_number):
    try:
        client = create_client()
        clean_number = normalize_phone(phone_number)

        call = client.calls.create(
            to=clean_number,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            url=f"{os.getenv('PUBLIC_BASE_URL')}/voice"
        )

        return jsonify({
            "message": "Call started successfully",
            "to": clean_number,
            "call_sid": call.sid
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug-logo", methods=["GET"])
def debug_logo():
    return jsonify({
        "logo_expected_path": "/static/logo.png",
        "public_logo_url": f"{os.getenv('PUBLIC_BASE_URL')}/static/logo.png"
    })


if __name__ == "__main__":
    ensure_csv_exists()
    app.run(host="0.0.0.0", port=5000, debug=True)

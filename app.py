from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
import os
import csv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Variables de entorno
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

# Almacenamiento temporal en memoria para el piloto
# Clave: CallSid
call_data = {}

CSV_FILE = "survey_results.csv"


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
    q1_clean = q1.strip() if q1 else "No answer"
    q2_clean = q2.strip() if q2 else "No answer"
    q3_clean = q3.strip() if q3 else "No answer"

    return (
        f"Related to: {q1_clean}. "
        f"Main issue: {q2_clean}. "
        f"Situation: {q3_clean}."
    )


def save_to_csv(call_sid: str):
    ensure_csv_exists()

    data = call_data.get(call_sid, {})
    short_notes = build_short_notes(
        data.get("q1", ""),
        data.get("q2", ""),
        data.get("q3", "")
    )

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
            short_notes
        ])


@app.route("/", methods=["GET"])
def home():
    return "COMMAND ALKON survey backend running"


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
        timeout=5,
        num_digits=1,
        action="/question1",
        method="POST"
    )

    gather.say(
        "Hello. This is an automated survey call from Command Alkon. "
        "This call may be recorded for quality and documentation purposes. "
        "Do you have two minutes to answer three short questions? "
        "Press 1 or say yes to continue.",
        voice="alice",
        language="en-US"
    )

    response.append(gather)
    response.say(
        "We did not receive a response. Goodbye.",
        voice="alice",
        language="en-US"
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question1", methods=["GET", "POST"])
def question1():
    speech = request.form.get("SpeechResult", "")
    digits = request.form.get("Digits", "")
    call_sid = request.values.get("CallSid", "")

    response = VoiceResponse()
    accepted = digits == "1" or "yes" in speech.lower()

    if not accepted:
        response.say(
            "No problem. Goodbye.",
            voice="alice",
            language="en-US"
        )
        response.hangup()
        return str(response), 200, {"Content-Type": "text/xml"}

    gather = Gather(
        input="speech",
        timeout=6,
        action="/question2",
        method="POST"
    )
    gather.say(
        "First question. Is this related to a recent support case or something more general?",
        voice="alice",
        language="en-US"
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice="alice",
        language="en-US"
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
        timeout=6,
        action="/question3",
        method="POST"
    )
    gather.say(
        "Second question. What was the main issue for you?",
        voice="alice",
        language="en-US"
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice="alice",
        language="en-US"
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
        timeout=6,
        action="/complete",
        method="POST"
    )
    gather.say(
        "Final question. Is this something recurring or a one time situation?",
        voice="alice",
        language="en-US"
    )

    response.append(gather)
    response.say(
        "No response received. Goodbye.",
        voice="alice",
        language="en-US"
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
        voice="alice",
        language="en-US"
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/call/<path:phone_number>", methods=["GET"])
def make_call_pretty(phone_number):
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        public_base_url = os.getenv("PUBLIC_BASE_URL")

        client = Client(account_sid, auth_token)
        clean_number = normalize_phone(phone_number)

        call = client.calls.create(
            to=clean_number,
            from_=twilio_phone,
            url=f"{public_base_url}/voice"
        )

        return jsonify({
            "message": "Call started",
            "to": clean_number,
            "call_sid": call.sid
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/results", methods=["GET"])
def results_info():
    return jsonify({
        "message": "Results file path",
        "file": CSV_FILE
    })


if __name__ == "__main__":
    ensure_csv_exists()
    app.run(host="0.0.0.0", port=5000, debug=True)

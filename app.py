from flask import Flask, request, jsonify, render_template, send_file, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
import os
import csv
import requests
from datetime import datetime

load_dotenv()

app = Flask(__name__)

CSV_FILE = "survey_results.csv"
call_data = {}

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

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
                "question_1_used_community",
                "question_2_email_permission",
                "question_3_interested_session",
                "short_notes",
                "recording_url",
                "recording_sid"
            ])


def build_short_notes(q1: str, q2: str, q3: str) -> str:
    return (
        f"Used Community: {q1 or 'No answer'}. "
        f"Email permission: {q2 or 'No answer'}. "
        f"Interested in guided session: {q3 or 'No answer'}."
    )


def row_exists(call_sid: str) -> bool:
    if not os.path.exists(CSV_FILE):
        return False

    with open(CSV_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row.get("call_sid") == call_sid:
                return True
    return False


def save_to_csv(call_sid: str):
    ensure_csv_exists()

    if row_exists(call_sid):
        return

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
            ),
            data.get("recording_url", ""),
            data.get("recording_sid", "")
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


@app.route("/debug-logo", methods=["GET"])
def debug_logo():
    return jsonify({
        "logo_expected_path": "/static/logo.png",
        "public_logo_url": f"{os.getenv('PUBLIC_BASE_URL')}/static/logo.png"
    })


@app.route("/debug-twilio", methods=["GET"])
def debug_twilio():
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    phone = os.getenv("TWILIO_PHONE_NUMBER", "")
    public_base = os.getenv("PUBLIC_BASE_URL", "")

    return jsonify({
        "account_sid": sid,
        "account_sid_last4": sid[-4:] if sid else "",
        "from_number": phone,
        "public_base_url": public_base,
        "has_sid": bool(sid),
        "has_auth_token": bool(os.getenv("TWILIO_AUTH_TOKEN")),
        "has_phone_number": bool(phone)
    })


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
        "q3": "",
        "recording_url": "",
        "recording_sid": "",
        "survey_finished": False
    }

    gather = Gather(
        input="speech",
        timeout=5,
        speech_timeout=2,
        action="/question2",
        method="POST"
    )

    gather.say(
        (
            "Hello, and thank you for taking this call. "
            "My name is Emma, and I am a virtual community guide from Command Alkon. "
            "I would love to briefly introduce you to the Command Alkon Community, "
            "where you can manage your cases, review knowledge articles, create support cases, "
            "and access helpful groups designed to support your experience. "
            "This call may be recorded for quality and documentation purposes. "
            "I will ask you three short questions, and you can answer naturally after each one. "
            "First question. Have you used the Command Alkon Community before?"
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        (
            "We were not able to capture a response. "
            "Thank you for your time, and we hope to connect with you soon. Goodbye."
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.pause(length=1)
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
        timeout=5,
        speech_timeout=2,
        action="/question3",
        method="POST"
    )

    gather.say(
        (
            "Thank you. "
            "Second question. "
            "Would you feel comfortable sharing your email address so our team can contact you and continue supporting you if needed?"
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        (
            "We were not able to capture a response. "
            "Thank you for your time, and we hope to connect with you soon. Goodbye."
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.pause(length=1)
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
        timeout=5,
        speech_timeout=2,
        action="/complete",
        method="POST"
    )

    gather.say(
        (
            "Thank you. "
            "Final question. "
            "Would you be interested in a dedicated session to help you learn how to use the Community, "
            "including how to create your first cases and explore the available resources?"
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )

    response.append(gather)
    response.say(
        (
            "We were not able to capture a response. "
            "Thank you for your time, and we hope to connect with you soon. Goodbye."
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.pause(length=1)
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/complete", methods=["GET", "POST"])
def complete():
    answer3 = request.form.get("SpeechResult", "").strip()
    call_sid = request.values.get("CallSid", "")

    if call_sid in call_data:
        call_data[call_sid]["q3"] = answer3
        call_data[call_sid]["survey_finished"] = True

    response = VoiceResponse()
    response.say(
        (
            "Thank you so much for your time today. "
            "We truly appreciate your feedback. "
            "If you would like, you can visit the Command Alkon Community "
            "to manage your cases, view knowledge articles, create cases, and access community groups. "
            "We look forward to supporting you there. "
            "Have a wonderful day. Goodbye."
        ),
        voice=PREFERRED_VOICE,
        language=VOICE_LANGUAGE
    )
    response.pause(length=1)
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/recording-status", methods=["POST"])
def recording_status():
    call_sid = request.values.get("CallSid", "")
    recording_url = request.values.get("RecordingUrl", "")
    recording_sid = request.values.get("RecordingSid", "")
    recording_status = request.values.get("RecordingStatus", "")

    if call_sid in call_data and recording_status == "completed":
        call_data[call_sid]["recording_url"] = recording_url + ".mp3"
        call_data[call_sid]["recording_sid"] = recording_sid

        if call_data[call_sid].get("survey_finished"):
            save_to_csv(call_sid)

    return ("", 204)


@app.route("/recording/<recording_sid>", methods=["GET"])
def stream_recording(recording_sid):
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")

        audio_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.mp3"

        twilio_response = requests.get(
            audio_url,
            auth=(account_sid, auth_token),
            timeout=30
        )

        return Response(
            twilio_response.content,
            mimetype="audio/mpeg"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/call/<path:phone_number>", methods=["GET"])
def make_call_pretty(phone_number):
    try:
        client = create_client()
        clean_number = normalize_phone(phone_number)

        call = client.calls.create(
            to=clean_number,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            url=f"{os.getenv('PUBLIC_BASE_URL')}/voice",
            record=True,
            recording_status_callback=f"{os.getenv('PUBLIC_BASE_URL')}/recording-status",
            recording_status_callback_method="POST"
        )

        return jsonify({
            "message": "Call started successfully",
            "to": clean_number,
            "call_sid": call.sid
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "help": "Check that United States/Canada is enabled in Geo Permissions, confirm Render is using the same Account SID as the Twilio project you configured, and verify the Twilio phone number is voice-enabled."
        }), 500


if __name__ == "__main__":
    ensure_csv_exists()
    app.run(host="0.0.0.0", port=5000, debug=True)

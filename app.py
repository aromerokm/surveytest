from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.route("/", methods=["GET"])
def home():
    return "Survey backend running"


@app.route("/voice", methods=["GET", "POST"])
def voice():
    response = VoiceResponse()

    gather = Gather(
        input="speech dtmf",
        timeout=5,
        num_digits=1,
        action="/question1",
        method="POST"
    )

    gather.say(
        "Hello. This is an automated survey in English. "
        "Do you have two minutes to answer three short questions? "
        "Press 1 or say yes to continue.",
        voice="alice",
        language="en-US"
    )

    response.append(gather)
    response.say("We did not receive a response. Goodbye.", voice="alice", language="en-US")
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question1", methods=["GET", "POST"])
def question1():
    speech = request.form.get("SpeechResult", "")
    digits = request.form.get("Digits", "")

    response = VoiceResponse()

    accepted = digits == "1" or "yes" in speech.lower()

    if not accepted:
        response.say("No problem. Goodbye.", voice="alice", language="en-US")
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
    response.say("No response received. Goodbye.", voice="alice", language="en-US")
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question2", methods=["GET", "POST"])
def question2():
    answer1 = request.form.get("SpeechResult", "")
    print("Q1:", answer1)

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
    response.say("No response received. Goodbye.", voice="alice", language="en-US")
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/question3", methods=["GET", "POST"])
def question3():
    answer2 = request.form.get("SpeechResult", "")
    print("Q2:", answer2)

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
    response.say("No response received. Goodbye.", voice="alice", language="en-US")
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/complete", methods=["GET", "POST"])
def complete():
    answer3 = request.form.get("SpeechResult", "")
    print("Q3:", answer3)

    response = VoiceResponse()
    response.say(
        "Thank you. Your answers have been recorded. Goodbye.",
        voice="alice",
        language="en-US"
    )
    response.hangup()

    return str(response), 200, {"Content-Type": "text/xml"}


@app.route("/make-call", methods=["POST", "GET"])
def make_call():
    to_number = request.args.get("to")
    if not to_number:
        return {"error": "Missing ?to=+1XXXXXXXXXX"}, 400

    call = client.calls.create(
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        url=f"{PUBLIC_BASE_URL}/voice"
    )

    return {"message": "Call started", "call_sid": call.sid}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

# =========================
# Imports
# =========================

from authlib.integrations.flask_client import OAuth, OAuthError, FlaskOAuth2App
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, flash, get_flashed_messages, jsonify, redirect, render_template, request, send_from_directory, session
from functools import wraps
import json
from os import environ as env
from secrets import token_urlsafe
from sys import argv
from time import time

# =========================
# Global Setup
# =========================

load_dotenv("secrets.env")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_prefixed_env()

oauth = OAuth(app)
client_state: str

cookie_expiration_duration = timedelta(minutes=5)
"""Default cookie expiration time, set to five minutes"""

oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    api_base_url="https://classroom.googleapis.com",
    client_kwargs={
        "scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/classroom.courses.readonly https://www.googleapis.com/auth/classroom.student-submissions.students.readonly https://www.googleapis.com/auth/classroom.coursework.me",
        "prompt": "select_account",
        "include_granted_scopes": "true",
        "hd": "barabooschools.net"
    }
)

googleyeyes: FlaskOAuth2App = oauth.google # type: ignore
"""Create an instance of `oauth.google` to provide typehinting and other IntelliSense features"""

# =========================
# Logging
# =========================

def fileLogger(unmodifiedText, modifiedText, title: str):
    """Store the json response from Google's API for debugging and improvement"""
    epoch = int(time())
    name = str(session["token"]["userinfo"]["name"]).split()[0]
    with open(f"datadump/{epoch}.{title}.unmodified.{name}.json", "w") as unmodifiedFile:
        json.dump(unmodifiedText, unmodifiedFile, ensure_ascii=True, indent=4)
    with open(f"datadump/{epoch}.{title}.modified.{name}.json", "w") as modifiedFile:
        json.dump(modifiedText, modifiedFile, ensure_ascii=True, indent=4)

# =========================
# Parse Data
# =========================    

def parserInator(callType: str, source: str, params: dict) -> list[dict[str, str]] | None:
    """Fetch a JSON list from the specified source, using the parameters, and parse it down to the needed elements"""

    ogList: dict = {}
    parsedList: list[dict[str, str]] = []

    try:
        ogList = googleyeyes.get(source, token=session["token"], params=params).json()

        for key in ogList[next(iter(ogList))]:
            parsedKey = {"itemName": "Name not found", "itemID": "0"}

            if "name" in key:
                parsedKey["itemName"] = key["name"]
            elif "title" in key:
                parsedKey["itemName"] = key["title"]
            
            if "id" in key:
                parsedKey["itemID"] = key["id"]

            if "section" in key:
                parsedKey["itemSection"] = key["section"].removeprefix("Period: ")

            if "maxPoints" in key:
                parsedKey["itemMaxPoints"] = key["maxPoints"]

            parsedList.append(parsedKey)

        if "nextPageToken" in ogList:
            params["pageToken"] = ogList["nextPageToken"]
            parsedList = [*parsedList, *parserInator(callType, source, params)] # type: ignore

        return sorted(parsedList, key=lambda l: l["itemName"].lower())

    except Exception as error:
        flash(str(error))
        print(f"Modern parsing of the list failed with error: {error}")
        return None
    
    finally:
        fileLogger(ogList, parsedList, callType)

# =========================
# Fetch User Info
# =========================

def getUsername(username: str):
    """Fetch the username of the signed in user"""
    spaceIndex = username.find(" ")
    username = str(username[0:spaceIndex]) + str(username[spaceIndex:spaceIndex + 2])
    return username

# =========================
# Enforce logged-in status
# =========================

# Define a wrapper function to ensure a user is signed in
def login_required(f):
    """Requires a user to be signed in before being able to navigate to this route"""
    @wraps(f)
    def wrap(*args, **kwargs):
        if "token" in session:
            return f(*args, **kwargs)
        else:
            session.clear()
            return redirect("/login")
    return wrap

# =========================
# Cookie Duration
# =========================

@app.before_request
def cookie_expirey():
    """Sets the cookie expiration to five minutes without any new requests to Google"""

    global app
    global cookie_expiration_duration

    if app.debug:
        cookie_expiration_duration = timedelta(minutes=15)

    # Marking the cookie as permenant allows for customization of its duration
    session.permanent = True
    app.permanent_session_lifetime = cookie_expiration_duration

# =========================
# Robots
# =========================

@app.route("/robots.txt")
def robots():
    """Allows for navigation to the robots.txt file"""
    return send_from_directory(app.static_folder or env["MIMIR_STATIC_PATH"], request.path[1:])

# =========================
# Index
# =========================

# Index page
@app.route("/")
def index():
    """Provides the initial user-facing page"""
    if "token" in session:
        return redirect("/user/")
    else:
        return render_template("index.html", mimirVersion=env["MIMIR_VERSION"], messages=get_flashed_messages())

# =========================
# Login Helpers
# =========================

# Main login page, authenticates users with Google
@app.route("/login/")
def login():
    """Provides the login page, that serves redirect information for a user to sign in"""
    
    global client_state
    client_state = token_urlsafe(16)
    redirectLink = request.base_url + "auth/"

    if "token" in session:
        return redirect("/user/")
    else:
        return googleyeyes.authorize_redirect(redirect_uri=redirectLink, state=client_state)
    

# TODO: Add token refresh config


# Login Callback page, for authentication with Google
@app.route("/login/auth/")
def loginAuth():
    """Provides the callback page for user login, to handle the parsing and storage of tokens"""
    
    global client_state
    
    try:
        googleToken = googleyeyes.authorize_access_token()
        session["token"] = googleToken
    
        gState = request.args.get("state") or ""

        if client_state == gState:
            print("The client's state matched. Yay!")
        else:
            print("STATE MISMATCH DETECTED")
            print(f"OLD STATE: {client_state}")
            print(f"NEW STATE: {gState}, len: {len(gState)}")

        return redirect("/user/")
    except OAuthError as error:
        return render_template("error.html", error=f"Authentication processing failed with error: {error}")
    except Exception as error:
        return render_template("error.html", error=f"An unexpected authentication error occured: {error}")

# =========================
# Logout Helpers
# =========================

# Log users out by clearing the session cookie
@app.route("/logout/")
def logout():
    """Provide a way to log users out, by clearing the session cookie"""
    session.clear()
    flash("You've been logged out")
    return redirect("/")


# Handle automatic logging out
@app.route("/logout/auto")
def autologout():
    """Provides the auto-logout route"""
    session.clear()
    flash("Sorry, you were automatically logged out due to inactivity.")
    return redirect("/")

# =========================
# Logged-in Home Page
# =========================

@app.route("/user/")
@login_required
def userPage():
    try:
        username = getUsername(session["token"]["userinfo"]["name"])
        return render_template("user.html", username=username, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")

# =========================
# Class List
# =========================

@app.route("/user/classes/")
@login_required
def classesPage():
    try:
        classes = parserInator(callType="classes", source="v1/courses/", params={"courseStates": ["ACTIVE"]})
        return render_template("classes.html", classes=classes, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")

# =========================
# Assignment List
# =========================

@app.route("/user/classes/<string:classID>/assignments/")
@login_required 
def assignmentsPage(classID):
    try:
        assignments = parserInator(callType="assignments", source=f"v1/courses/{classID}/courseWork", params={})
        return render_template("assignments.html", assignments=assignments, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The assignments page for class {classID} failed to load with error: {error}")

# =========================
# Assignment Options
# =========================

@app.route("/user/classes/<string:classID>/assignments/<string:assignmentID>/")
@login_required
def assignmentOptionsPage(classID, assignmentID):
    try:
        assignment = parserInator(callType="assignmentitem", source=f"v1/courses/{classID}/courseWork/{assignmentID}/studentSubmissions", params={})
        return render_template("assignmentOptions.html", selectedAssignment=assignmentID, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The assignment options page for class {classID} and assignment {assignmentID} failed to load with error: {error}")

# =========================
# Runtime Handler
# =========================

# Run the server on all IPs with port 80, and sets debug mode
if __name__ == "__main__":
    runWithDebug = "-d" in argv or "--debug" in argv
    app.run(host="0.0.0.0", port=80, debug=runWithDebug)
else:
    gunicornApp = app


from authlib.integrations.flask_client import OAuth, OAuthError
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, flash, get_flashed_messages, jsonify, redirect, render_template, request, send_from_directory, session
from functools import wraps
from hashlib import blake2b
import json
from os import environ as env
from os import urandom
from sys import argv
from time import time
from warnings import warn

load_dotenv("secrets.env")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_prefixed_env()

oauth = OAuth(app)
client_state: str = blake2b(urandom(1024)).hexdigest()

cookie_expiration_duration = timedelta(minutes=5)

oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    api_base_url="https://classroom.googleapis.com",
    client_kwargs={
        "scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/classroom.courses.readonly https://www.googleapis.com/auth/classroom.student-submissions.students.readonly https://www.googleapis.com/auth/classroom.coursework.me",
        "state": client_state,
        "prompt": "select_account",
        "include_granted_scopes": "true",
        "hd": "barabooschools.net"
    }
)


def fileLogger(unmodifiedText, modifiedText, title: str):
    """Store the json response from Google's API for debugging and improvement"""
    epoch = int(time())
    name = session["token"]["userinfo"]["name"].split()[0]
    with open(f"datadump/{epoch}.{title}.unmodified.{name}.json", "w") as unmodifiedFile:
        json.dump(unmodifiedText, unmodifiedFile, ensure_ascii=True, indent=4)
    with open(f"datadump/{epoch}.{title}.modified.{name}.json", "w") as modifiedFile:
        json.dump(modifiedText, modifiedFile, ensure_ascii=True, indent=4)
    

def parserInator(type: str, source: str, params: dict) -> dict | None:
    """Fetch a JSON list from the specified source, using the parameters, and pare it down to the needed elements"""
    try:
        ogList = oauth.google.get(source, token=session["token"], params=params).json()
        parsedList = []

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

            parsedList.append(parsedKey)

        if "nextPageToken" in ogList:
            params["pageToken"] = ogList["nextPageToken"]
            parsedList.append(parserInator(source, params))

        fileLogger(ogList, parsedList, type)

        return sorted(parsedList, key=lambda l: l["itemName"].lower())

    except Exception as error:
        flash(error)
        print(f"(Modern) Parsing the list failed with error: {error}")
        fileLogger(ogList, parsedList, f"FAIL.{type}")
        return None


def getUsername(username: str):
    """Fetch the username of the signed in user"""
    spaceIndex = username.find(" ")
    username = str(username[0:spaceIndex]) + str(username[spaceIndex:spaceIndex + 2])
    return username


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


@app.route("/robots.txt")
def robots():
    """Allows for navigation to the robots.txt file"""
    return send_from_directory(app.static_folder, request.path[1:])


# Index page
@app.route("/")
def index():
    """Provides the initial user-facing page"""
    if "token" in session:
        return redirect("/user/")
    else:
        return render_template("index.html", mimirVersion=env["MIMIR_VERSION"], messages=get_flashed_messages())


# Main login page, authenticates users with Google
@app.route("/login/")
def login():
    """Provides the login page, that serves redirect information for a user to sign in"""
    redirectLink = request.base_url + "auth/"
    return oauth.google.authorize_redirect(redirectLink)


# Login Callback page, for authentication with Google
@app.route("/login/auth/")
def loginAuth():
    """Provides the callback page for user login, to handle the parsing and storage of tokens"""
    try:
        googleToken = oauth.google.authorize_access_token()
        session["token"] = googleToken
 
        # TODO: Implement state (csrf) parameter verification
        
        return redirect("/user/")
    except OAuthError as error:
        return render_template("error.html", error=f"Authentication processing failed with error: {error}")
    except Exception as error:
        return render_template("error.html", error=f"An unexpected authentication error occured: {error}")


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


@app.route("/user/")
@login_required
def userPage():
    try:
        username = getUsername(session["token"]["userinfo"]["name"])
        return render_template("user.html", username=username, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")


@app.route("/user/classes/")
@login_required
def classesPage():
    try:
        classes = parserInator(type="classes", source="v1/courses/", params={"courseStates": ["ACTIVE"]})
        return render_template("classes.html", classes=classes, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")


@app.route("/user/classes/<string:classID>/assignments/")
@login_required 
def assignmentsPage(classID):
    try:
        assignments = parserInator(type="assignments", source=f"v1/courses/{classID}/courseWork", params={})
        # return jsonify(parserInator(source=f"v1/courses/{classID}/courseWork", params={}))
        return render_template("assignments.html", assignments=assignments, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The assignments page for class {classID} failed to load with error: {error}")


@app.route("/user/classes/<string:classID>/assignments/<string:assignmentID>/")
@login_required
def assignmentOptionsPage(classID, assignmentID):
    try:
        # assignment = parserInator(type="work", source=f"v1/courses/{classID}/courseWork/{assignmentID}", params={})
        return jsonify(oauth.google.get(f"v1/courses/{classID}/courseWork/{assignmentID}/studentSubmissions", token=session["token"]).json())
        # return render_template("assignmentOptions.html", selectedClass=classID, selectedAssignment=assignmentID, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The assignment options page for class {classID} and assignment {assignmentID} failed to load with error: {error}")


# Run the server on all IPs with port 80, and sets debug mode
if __name__ == "__main__":
    runWithDebug = "-d" in argv or "--debug" in argv
    app.run(host="0.0.0.0", port=80, debug=runWithDebug)
else:
    gunicornApp = app


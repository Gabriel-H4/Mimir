from authlib.integrations.flask_client import OAuth, OAuthError
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, flash, get_flashed_messages, jsonify, redirect, render_template, request, send_from_directory, session
from functools import wraps
from hashlib import blake2b
import json
from os import environ as env
from os import urandom
from sys import argv
from warnings import warn

load_dotenv("secrets.env")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_prefixed_env()

oauth = OAuth(app)
client_state: str = blake2b(urandom(1024)).hexdigest()

oauth.register(
    name="googleuser",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    api_base_url="https://oauth2.googleapis.com"
)

oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    api_base_url="https://classroom.googleapis.com",
    client_kwargs={
        "scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/classroom.courses.readonly https://www.googleapis.com/auth/classroom.student-submissions.students.readonly https://www.googleapis.com/auth/classroom.coursework.me",
        "state": client_state,
        "prompt": "select_account consent",
        "include_granted_scopes": "true",
        "hd": "barabooschools.net"
    }
)


def fileLogger(unmodifiedText, modifiedText, title: str):
    """Store the json response from Google's API for debugging and improvement"""
    currentDate = datetime.today().strftime("%Y-%m-%d")
    name = session["token"]["userinfo"]["name"].split()[0]
    with open(f"datadump/{title}.unmodified.{name}.{currentDate}.json", "w") as unmodifiedFile:
        json.dump(unmodifiedText, unmodifiedFile, ensure_ascii=True, indent=4)
    with open(f"datadump/{title}.modified.{name}.{currentDate}.json", "w") as modifiedFile:
        json.dump(modifiedText, modifiedFile, ensure_ascii=True, indent=4)
    

def parseClasses(list: dict) -> dict:
    """Parse a Google Classroom class list response into a simplified one"""
    try:
        parsedResult = []
        for key in list["courses"]:
            parsedKey = {"name": key["name"], "classID": key["id"]}
            if "section" in key:
                parsedKey["section"] = key["section"]
            else:
                parsedKey["section"] = "Class Period not found"
            parsedResult.append(parsedKey)
        if "nextPageToken" in list:
            # TODO: Implement nextPage fetching
            print(f"There is another page of classes available. Please actually fetch it.")
            raise NotImplementedError
        fileLogger(list, parsedResult, "classlist")
        return sorted(parsedResult, key=lambda l: l["name"].lower())
    except Exception as error:
        flash(error)
        print(f"Could not parse the class list with error: {error}")
        return None
    

def parseAssignments(list: dict) -> dict:
    """Parse a Google Classroom Assignments response dictionary into a simplified one"""
    try:
        parsedResult = []
        for key in list["courseWork"]:
            parsedWork = {"title": key["title"], "workId": key["id"]}
            if "maxPoints" in key:
                parsedWork["maxPoints"] = key["maxPoints"]
            else:
                parsedWork["maxPoints"] = "0"
            parsedResult.append(parsedWork)
            fileLogger(list, parsedResult, "assignmentlist")
        return sorted(parsedResult, key=lambda l: l["title"].lower())
    except Exception as error:
        flash(error)
        print(f"Could not parse the assignment list with error: {error}")
        return None


def parseAssignmentObject(assignment: dict) -> dict:
    """Parse an individual Assignment response dictionary into a simplified one"""
    try:
        NotImplementedError
        fileLogger(assignment, assignment, "assignment")
    except Exception as error:
        flash(error)
        print(f"Could not parse the assignment response with error: {error}")
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

    # Marking the cookie as permenant allows for customization of its duration
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=5)


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


# Revokes a user's Google Access token
@app.route("/revoke/")
def revokeTokens():
    """Revoke a user's Google access token"""

    if "token" in session:
        revocation = oauth.googleuser.post("revoke", token="", params={"token": session["token"]}, headers={"content-type": "application/x-www-form-urlencoded"})
        statusCode = getattr(revocation ,"status_code")
        if statusCode == 200:
            flash("You've successfully revoked Mimir's access to your Google account")
            return render_template("index.html", messages=get_flashed_messages())
        else:
            flash(f"There was an error revoking Mimir's access to your Google account: {statusCode}")
            return render_template("error.html", error=f"There was an error revoking credentials: {statusCode}")
    else:
        flash("No valid token was found to revoke, please sign in and try again")
        return render_template("index.html", mimirVersion=env["MIMIR_VERSION"], messages=get_flashed_messages())


@app.route("/user/")
@login_required
def userPage():
    try:
        flash("default message: hey there!")
        username = getUsername(session["token"]["userinfo"]["name"])
        return render_template("user.html", username=username, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")


@app.route("/user/classes/")
@login_required
def classesPage():
    try:
        classes = parseClasses(oauth.google.get("v1/courses/", token=session["token"], params={"courseStates": ["ACTIVE"]}).json())
        return render_template("classes.html", classes=classes, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The user page failed to load with error: {error}")


@app.route("/user/classes/<string:classID>/assignments/")
@login_required 
def assignmentsPage(classID):
    try:
        assignments = parseAssignments(oauth.google.get(f"v1/courses/{classID}/courseWork", token=session["token"]).json())
        # return jsonify(oauth.google.get(f"v1/courses/{classID}/courseWork", token=session["token"]).json())
        return render_template("assignments.html", assignments=assignments, messages=get_flashed_messages())
    except Exception as error:
        return render_template("error.html", error=f"The assignments page for class {classID} failed to load with error: {error}")


@app.route("/user/classes/<string:classID>/assignments/<string:assignmentID>/")
@login_required
def assignmentOptionsPage(classID, assignmentID):
    try:
        # assignment = parseAssignmentObject(oauth.google.get(f"v1/courses/{classID}/courseWork/{assignmentID}", token=session["token"]).json())
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


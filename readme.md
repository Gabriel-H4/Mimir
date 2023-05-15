# Welcome to Mimir

*The best tool to sync Google Classroom grades into Infinite Campus!*

<br>

## Developed by Gabriel Hassebrock

<br>

## Requirements

* Python 3.11 (newer verions not yet tested)
* Incoming Network Port 80/tcp
* User device outgoing network access to the following domains:
    * `accounts.google.com`
    * `classroom.google.com`
    * `infinitecampus.com`

<br>

## Getting Started

<br>

### Terminal

1. Download the code onto your computer
2. Open a terminal and `cd` into the folder
3. Setup your virtual environment
    * **macOS:** `python3 -m venv venv`
    * **Windows:** `python3.11 -m venv venv`
4. Activate your virtual environment
    * **macOS:** `. venv/Scripts/Activate`
    * **Windows:** `venv/Scripts/Activate`
5. Install the dependencies
    * `pip install -r requirements.txt`
6. Run Mimir!
    * **macOS:** `python3 -u mimir.py`
    * **Windows:** `python3.11 -u mimir.py`

<br>

### Docker

***(Not yet public)***

<br>

#### Manually Build the Image

1. `cd` into dirctory
2. `docker build -t gabrielh4/mimir:latest .`
3. `docker run -d --name mimir -p 80:80 --restart unless-stopped`

<br>

#### Prebuilt Image

1. Download and install Docker
2. Pull the container
    * `docker pull gabrielh4/mimir`
3. Run the container

    ```bash
    docker run -d \
    --name mimir \
    -p 80:80 \
    --restart unless-stopped
    ```

<br>

## Use Cases

You might be thinking: *"Wow! Great job Gabe! But how does this affect me?"*

Well, Mimir is the easiest tool for teachers to use to sync grades from Google Classroom into Infinite Campus. It runs locally, and only makes the necessary calls to Google and Infinite Campus to fetch and update the grades, without doing any logging itself.

Students work almost exclusively within the Google suite of products for most assignments, and it just makes sense for teachers to be able to take advantage of that. When a Google Form is used as an assignment, teachers can have it automatically return a grade to a student, but not update in Infinite Campus. **Teachers still manually have to feed that data into IC**. Being able to have students view their grades with their work means that teachers have to grade twice: once in Classroom and once in Infinite Campus. **This tool eliminates that frustration** by making it so teachers can spend more time educating, or living their lives outside of school.

### Features:

* View all active classes
* [ WIP ] View all assignments in an active class
* [ SOON ] Sync assignment status (late, missing, etc)
* [ SOON ] Sync numerical grades
* [ SOON ] Sync rubric-based grades

<br>

## Security

When using Mimir, the target audience is educators. With that in mind, data security is my number one priority. This Python app uses well-established, and industry-standard tools. Here is a quick rundown of the methods I use to keep data secure:

* Secure, scoped, user authentication with Google OAuth 2.0
    * Teachers have to consent to each scope I utilize, every time they login
    * Scopes Used:
        * `openid` - Required for usage of the OpenID Connect API
        * `userinfo.profile` - Access the user's name
        * `classroom.courses.readonly` - Access the user's Google Classroom classes and their data
        * `classroom.student-submissions.students.readonly` - Access student(s) data within a class, i.e. their assignments and grades
* Credentials are only stored in the teacher's browser session while in use
* The only cookie being used, `session`, expires after 5 minutes of inactivity
    * Activity is defined as a user requesting a page from Mimir: a new one or refreshing the current one
* The only network requests made by Mimir are for:
    * User authentication through Google and Infinite Campus
        * [ **NOTE** ] Infinite Campus has not yet been implemented
    * Google Classroom read-only API requests
    * Infinite Campus read & write API requests
        * [ **NOTE** ] This interaction is not currently in use
* Secret keys are kept in a .env file
* All code is in the following files, UTF-8, plaintext:
    * `mimir2.py` - core of this app, version 2
    * `requirements.txt` - Python requirements file
    * `templates` - directory containing HTML pages
    * `static/main.css` - CSS for styling the HTML pages
    * `static/manifest.json` - Dictates how to render Mimir as a PWA

<br>

## Changelog

* **Version 1.0.0**
    * Initial internal build
    * Supports Google OAuth
    * Shows hard-coded list of assignments and classes
* **Version 2.0.0**
    * Complete rewrite
    * Handles Google OAuth using Authlib
    * Utilizes `secrets.env` for Google secret keys
    * Improved error handling
* **Version 2.0.1**
    * Added version tracking through `secrets.env`, viewable while a user is on the home page
    * Added the ability to load a user's list of classes
        * This list is currently rendered in JSON as an HTML `<p>` element, and does not yet utilize the `user.html` template
* **Version 2.0.2**
    * Render the list of a user's classes through `user.html`
    * Made user's Google authentication token reusable by placing inside the session cookie
    * Move the JSON list of classes outside of session cookie, and into request body
        * Big stability and perfomance improvement: yay!
* **Version 2.0.3**
    * Switched from CSS grid to flex
    * Added `/revoke/` for users to revoke access to Mimir, experimental right now
    * Added `robots.txt` to disallow most web crawlers
    * Added user's name to `user.html`, viewable on the list of classes once they sign in
* **Version 2.0.4**
    * Added a `manifest.json` to improve support when used as a PWA
    * Began utilizing Flashes, a way of displaying temporary messages
        * Currently used for notifying logged in and out
        * Will later be used for displaying anticipated errors that occur
    * Improved accessibility by restructuring HTML
* **Version 2.1.0**
    * Improved color scheme by using a new palette
        * You can find the palette [here](https://coolors.co/palette/0d1b2a-1b263b-415a77-778da9-e0e1dd)
    * Improved `border-radius` CSS properties by using rems instead of percentages and hard-coded numbers
    * Standardized box corner rounding
    * Fixed a typo that prevented `@media (prefers-color-scheme: dark) {...}` from working
    * Improved accessibility by achieving WCAG 2.0 compliance
    * Refactored the `parseClasses()` method slightly, reducing computations used
    * Removed the authentication requirement from `/revoke/` and notify the user of the failure instead
* **Version 2.1.1**
    * Expanded `/user/` page to show several buttons for better user control of their experience
    * Added `/classes/` page to display the list of classes
    * Added `<- Back` buttons on most pages, to improve navigation flow
* **Version 2.1.2**
    * Added Docker support
    * Updated to Python 3.11
    * Updated dependencies
        * cryptography: 39.0.0 -> 39.0.1
        * MarkupSafe: 2.1.1 -> 2.1.2
        * python-dotenv: 0.21.0 -> 0.21.1

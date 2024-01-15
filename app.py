from flask import Flask, render_template, redirect, request, session, url_for, Response, jsonify
import pyrebase
import numpy as np
from datetime import datetime
import cv2
from posedetector import poseDetector

app = Flask(__name__)
app.secret_key = 'deeps'
camera = None
detector = poseDetector()
count = 0
direction = 0
form = 0
feedback = "Fix Form"
stop_requested = False

firebaseConfig = {
  "apiKey": "AIzaSyAHx1SzHjB95PfWuwF5qkxLpcswDpq2-Jo",
  "authDomain": "fitbyit2024.firebaseapp.com",
  "projectId": "fitbyit2024",
  "storageBucket": "fitbyit2024.appspot.com",
  "messagingSenderId": "292945432667",
  "appId": "1:292945432667:web:f966259207ea3a7789ef7e",
  "databaseURL": "https://fitbyit2024-default-rtdb.firebaseio.com/"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()

def initialize_camera():
    global camera
    if camera is None:
        try : 
            camera = cv2.VideoCapture('./video/test1.mp4')
        except:
            return None

def release_camera():
    global camera
    if camera is not None:
        camera.release()
        camera = None

## SignUp Logic
def create_user(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        session['user_id'] = user['idToken']
        return user
    except Exception as e:
        return None 

## Sign Up Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = create_user(email, password)
        if user:
            return redirect('/verify')
        else:
            return render_template('signup.html', error= "Something went wrong. Try Again !!")
    return render_template('signup.html')

## Verify Up Route
@app.route('/verify', methods=['GET', 'POST'])
def verification():
    try:
        user_id = session.get('user_id')
        getinfo = auth.get_account_info(user_id)
        emailcheck = getinfo["users"][0]["emailVerified"]
        email = getinfo["users"][0]["email"]
        if emailcheck==True:
            return redirect("/")
        else:
            auth.send_email_verification(user_id)
        return render_template("verify.html", email = email)
    except:
        return render_template("404.html")


## Login Logic
def verify_user(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_info = auth.get_account_info(user['idToken'])
        session['user_id'] = user['idToken']
        return user
    except Exception as e:
        return False
    
# Home Route 
@app.route('/')
def home():
    user_id = session.get('user_id')
    if user_id:
        try:
            user_info = auth.get_account_info(user_id)
            user_ref = 'users/' + user_info["users"][0]["localId"]
            user_data = db.child(user_ref).get().val()
            if user_data:
                count = user_data.get('count', 0)
                date = user_data.get('date', 'NA')
                return render_template('home.html', user_info = user_info, countdata = count, date= date)
            else:
                return render_template('home.html', user_info = user_info, countdata = "NA", date= "NA")
        except Exception as e:
            session.pop('user_id', None)
            return render_template('login.html', error=e)
    return redirect("/login")


## Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if not session.get('user_id'):
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            user = verify_user(email, password)
            if user:
                return redirect('/verify')
            else:
                return render_template('login.html', error="Invalid Email or Password")
        return render_template('login.html')
    return redirect("/")

## Logout Route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

## Forget Password Route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            auth.send_password_reset_email(email)
            return render_template("login.html", error = "Password reset email sent.")
        except Exception as e:
            return render_template("forgot_password.html", error = "Failed to send email.")
    return render_template('forgot_password.html')
    
## 404 Route
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/count', methods=['GET', 'POST'])
def startCount():
    global stop_requested
    if not stop_requested:
        initialize_camera()
        stop_requested = True
    return render_template('counter.html', pushup_count=count)

## Check Landmarks
def check_pushup_position(landmarks):
    shoulder_y = landmarks[11][1]
    elbow_y = landmarks[13][1]
    wrist_y = landmarks[15][1]
    return elbow_y > shoulder_y and wrist_y > elbow_y

def generate_frames():
    global count, direction, form, feedback, stop_requested
    while stop_requested==True:
        success, frame = camera.read()
        if not success:
            camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        else:
            frame = detector.findPose(frame, False)
            lmList = detector.findPosition(frame, False)
            if len(lmList) != 0:
                elbow = detector.findAngle(frame, 11, 13, 15)
                shoulder = detector.findAngle(frame, 13, 11, 23)
                hip = detector.findAngle(frame, 11, 23, 25)
                per = np.interp(elbow, (90, 160), (0, 100))
                bar = np.interp(elbow, (90, 160), (380, 50))
                if elbow > 160 and shoulder > 40 and hip > 160:
                    form = 1
                if form == 1:
                    if per == 0:
                        if elbow <= 90 and hip > 160:
                            feedback = "Up"
                            if direction == 0:
                                count += 0.5
                                direction = 1
                        else:
                            feedback = "Fix Form"
                    if per == 100:
                        if elbow > 160 and shoulder > 40 and hip > 160:
                            feedback = "Down"
                            if direction == 1:
                                count += 0.5
                                direction = 0
                        else:
                            feedback = "Fix Form"
            # Draw Bar
            if form == 1:
                cv2.rectangle(frame, (580, 50), (600, 380), (0, 255, 0), 3)
                cv2.rectangle(frame, (580, int(bar)), (600, 380), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, f'{int(per)}%', (565, 430), cv2.FONT_HERSHEY_PLAIN, 2,
                            (255, 0, 0), 2)
            # Pushup counter
            cv2.rectangle(frame, (0, 380), (100, 480), (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, str(int(count)), (25, 455), cv2.FONT_HERSHEY_PLAIN, 5,
                        (255, 0, 0), 5)
            # Feedback
            cv2.rectangle(frame, (500, 0), (640, 40), (255, 255, 255), cv2.FILLED)
            cv2.putText(frame, feedback, (500, 40), cv2.FONT_HERSHEY_PLAIN, 2,
                        (0, 255, 0), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            

@app.route('/video_feed', methods=['GET', 'POST'])
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_pushup_count', methods=['GET'])
def get_pushup_count():
    global count
    return jsonify({'count': count})

def update_pushup_count_in_firebase(localId, count):
    today_date = datetime.now().strftime('%d %b %y')
    user_ref = f'users/{localId}'
    user_data = {'count': count, 'date': today_date}
    db.child(user_ref).set(user_data) 

@app.route('/stopcount', methods=['POST', "GET"])
def stopcount():
    global stop_requested, count
    stop_requested = False
    release_camera()
    user_id = session.get('user_id')
    user_info = auth.get_account_info(user_id)
    localId = user_info["users"][0]["localId"]
    update_pushup_count_in_firebase(localId, round(count))
    count = 0
    return redirect("/")

if __name__ == '__main__':
    app.run()

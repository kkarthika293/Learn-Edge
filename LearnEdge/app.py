import base64
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import matplotlib.pyplot as plt
import os
import json
from g4f.client import Client
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elearning.db'
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy()
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

db.init_app(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # <-- Add email field
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="user")
    
    def is_active(self):
        return True

    def get_id(self):
        return str(self.id)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contents = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    thumbnail = db.Column(db.String(300), nullable=True)
    pdf_file = db.Column(db.String(300), nullable=True)
    views = db.Column(db.Integer, default=0)
    users_completed = db.Column(db.Integer, default=0)
    
    # Relationship to CourseVideo
    videos = db.relationship('CourseVideo', backref='course', lazy=True)

class CourseVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_link = db.Column(db.String(300), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender_name = db.Column(db.String(100))
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='scores')
    course = db.relationship('Course', backref='scores')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(100), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)  # Add course_id

    course = db.relationship('Course', backref='questions')
 
class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/educator_register', methods=['GET', 'POST'])
def educator_register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        # Check if user already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Username or Email already exists", "danger")
            return redirect(url_for('educator_register'))

        # Create educator user
        user = User(username=username, email=email, password=password, role='educator')
        db.session.add(user)
        db.session.commit()
        flash("Educator registered successfully! Please login.", "success")
        return redirect(url_for('educator_login'))

    return render_template('educator_register.html')

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        message_text = request.form['message']
        chat_message = ChatMessage(
            sender_id=current_user.id,
            sender_name=current_user.username,
            message=message_text
        )
        db.session.add(chat_message)
        db.session.commit()
        return redirect(url_for('chat'))

    # Fetch last 50 messages in descending order (newest first)
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(50).all()

    return render_template('chat.html', messages=messages)

@app.route('/educator_login', methods=['GET', 'POST'])
def educator_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, role='educator').first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for('cadmin_dashboard'))
        else:
            flash("Invalid credentials or not an educator account", "danger")
            return redirect(url_for('educator_login'))

    return render_template('educator_login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash("Invalid Admin Credentials", "danger")
    return render_template('admin.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with app.app_context():
        courses = Course.query.all()
    
    course_names = [c.name for c in courses]
    views = [c.views for c in courses]

    plt.bar(course_names, views, color='blue')
    plt.xlabel('Courses')
    plt.ylabel('Views')
    plt.title('Course Popularity')
    plt.xticks(rotation=45)
    
    plt.savefig('static/analysis.png')
    plt.close()

    return render_template('admin_dashboard.html', courses=courses)

@app.route('/cadmin_dashboard')
def cadmin_dashboard():
    
    with app.app_context():
        courses = Course.query.all()
    
    course_names = [c.name for c in courses]
    views = [c.views for c in courses]

    plt.bar(course_names, views, color='blue')
    plt.xlabel('Courses')
    plt.ylabel('Views')
    plt.title('Course Popularity')
    plt.xticks(rotation=45)
    
    plt.savefig('static/analysis.png')
    plt.close()

    return render_template('cadmin_dashboard.html', courses=courses)

@app.route('/')
def index():
    return render_template('cindex.html')

@app.route('/resume')
def resume():
    return render_template('resume.html')

import os
from werkzeug.utils import secure_filename

# Set the allowed extensions for the uploaded PDF
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/ccreate_course', methods=['GET', 'POST'])
def create_course():
    if request.method == 'POST':
        name = request.form['name']
        contents = request.form['contents']
        duration = int(request.form['duration'])
        description = request.form.get('description', '')
        difficulty = request.form.get('difficulty', 'intermediate')
        category = request.form.get('category', '')

        # Thumbnail upload
        thumbnail_file = request.files.get('thumbnail')
        thumbnail_filename = None
        if thumbnail_file and thumbnail_file.filename != '':
            thumbnail_filename = secure_filename(thumbnail_file.filename)
            thumbnail_file.save(os.path.join('static/uploads/thumbnails', thumbnail_filename))

        # PDF upload
        pdf_file = request.files.get('pdf')
        pdf_filename = None
        if pdf_file and allowed_file(pdf_file.filename):
            pdf_filename = secure_filename(pdf_file.filename)
            pdf_file.save(os.path.join('static/uploads/pdf', pdf_filename))

        # Create and save course
        new_course = Course(
            name=name,
            contents=contents,
            duration=duration,
            description=description,
            difficulty=difficulty,
            category=category,
            thumbnail=thumbnail_filename,
            pdf_file=pdf_filename  # Save the PDF filename here
        )
        db.session.add(new_course)
        db.session.commit()

        # Save up to 10 optional video links
        for i in range(1, 11):
            video_link = request.form.get(f'video{i}')
            if video_link:
                new_video = CourseVideo(video_link=video_link, course_id=new_course.id)
                db.session.add(new_video)

        db.session.commit()
        return redirect(url_for('cadmin_dashboard'))

    return render_template('ccreate_course.html')

from flask import send_from_directory
@app.route('/download_pdf/<filename>')
def download_pdf(filename):
    # Define the path to the PDF directory
    pdf_dir = os.path.join(app.root_path, 'static', 'uploads', 'pdf')
    # Send the file from the specified directory
    return send_from_directory(pdf_dir, filename, as_attachment=True)

@app.route('/logout')
@login_required
def logout():
    # Your logout logic here
    return redirect(url_for('login'))  # Ensure this redirects to the correct login page


@app.route('/cregister', methods=['GET', 'POST'])
def cregister():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']  # <-- Get email from form
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        
        # Create and save the user
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Registration Successful! Please Login", "success")
        return redirect(url_for('clogin'))
    
    return render_template('cregister.html')


@app.route('/clogin', methods=['GET', 'POST'])
def clogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('cuser_dashboard'))
        
        flash("Invalid Credentials", "danger")
    return render_template('clogin.html')

@app.route('/cuser_dashboard')
@login_required
def cuser_dashboard():
    courses = Course.query.all()
    return render_template('cuser_dashboard.html', courses=courses)

@app.route('/view_course/<int:course_id>')
@login_required
def view_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.views += 1
    db.session.commit()
    return render_template('view_course.html', course=course, required_minutes=course.duration, progress=50)

@app.route('/complete_course/<int:course_id>')
@login_required
def complete_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.users_completed += 1
    db.session.commit()
    flash("Course Completion Recorded!", "success")
    return redirect(url_for('cuser_dashboard'))


from flask_mail import Mail, Message
from fpdf import FPDF  # or you can use ReportLab, PIL, etc.
import os

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'daminmain@gmail.com'  # Your email
app.config['MAIL_PASSWORD'] = 'kpqtxqskedcykwjz'     # Use App Password
mail = Mail(app)

from fpdf import FPDF
import os
from datetime import date, datetime
import random

import os
import random
from fpdf import FPDF
from datetime import date


def generate_certificate(username):
    try:
        # Generate 13-digit certificate number
        cert_number = ''.join(str(random.randint(0, 9)) for _ in range(13))

        # Create PDF document
        pdf = FPDF('L', 'mm', 'A4')  # Landscape A4
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Set a border
        pdf.set_line_width(1.5)
        pdf.rect(10, 10, 277, 190)

        # Certificate Title
        pdf.set_font("Arial", 'B', 36)
        pdf.set_text_color(0, 76, 153)
        pdf.ln(30)
        pdf.cell(0, 20, "Certificate of Completion", ln=True, align='C')

        # Decorative line
        pdf.set_draw_color(0, 76, 153)
        pdf.set_line_width(0.5)
        pdf.line(50, pdf.get_y() + 5, 250, pdf.get_y() + 5)
        pdf.ln(15)

        # Subtitle
        pdf.set_font("Arial", '', 16)
        pdf.set_text_color(0)
        pdf.cell(0, 10, "This is to certify that", ln=True, align='C')

        # Recipient Name
        pdf.set_font("Arial", 'B', 26)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 15, username, ln=True, align='C')

        # Completion Message
        pdf.set_font("Arial", '', 16)
        pdf.set_text_color(0)
        pdf.ln(5)
        pdf.multi_cell(0, 10,
            "has successfully completed the course and demonstrated outstanding performance "
            "in the final assessment conducted by our institution.",
            align='C'
        )

        # Date of Issue
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 12)
        pdf.cell(0, 10, f"Issued on: {date.today().strftime('%B %d, %Y')}", ln=True, align='C')
        
        # Certificate Number
        pdf.ln(15)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 10, f"Certificate Number: {cert_number}", ln=True, align='R')

        # Signature Lines
        pdf.ln(25)
        pdf.set_font("Arial", '', 12)
        pdf.cell(90, 10, "_______________________", ln=0, align='C')
        pdf.cell(100, 10, "", ln=0)
        pdf.cell(90, 10, "_______________________", ln=1, align='C')
        pdf.cell(90, 5, "Authorized Signature", ln=0, align='C')
        pdf.cell(100, 5, "", ln=0)
        pdf.cell(90, 5, "Course Instructor", ln=1, align='C')

        # Optional: Add watermark or background text
        pdf.set_font("Arial", 'B', 50)
        pdf.set_text_color(200, 200, 200)  # Light grey for watermark
        pdf.rotate(45)
        pdf.text(90, 150, "CERTIFICATE")

        # Create the certificates directory if not exists
        os.makedirs("certificates", exist_ok=True)

        # Check if the certificate already exists, append a number if necessary
        certificate_path = f"certificates/{username}_certificate.pdf"
        counter = 1
        while os.path.exists(certificate_path):
            certificate_path = f"certificates/{username}_certificate_{counter}.pdf"
            counter += 1

        # Save PDF
        pdf.output(certificate_path)
        return certificate_path

    except Exception as e:
        print(f"Error generating certificate: {e}")
        return None

# Send email with certificate
def send_certificate_email(user_email, username, certificate_path):
    msg = Message('Your Course Certificate', sender='your_email@gmail.com', recipients=[user_email])
    msg.body = f"Hi {username},\n\nCongratulations! You scored well and have earned a certificate."
    with open(certificate_path, 'rb') as f:
        msg.attach(f"{username}_certificate.pdf", "application/pdf", f.read())
    mail.send(msg)


@app.route('/generate_mcq/<int:course_id>', methods=['GET'])
@login_required
def generate_mcq(course_id):
    course = Course.query.get_or_404(course_id)
    client = Client()

    prompt = (
        f"Generate 10 multiple-choice questions based on the following course content:\n\n{course.contents}\n\n"
        "Each question should have 4 options and one correct answer. "
        "Return only a raw JSON array of objects (no markdown, no explanation), where each object contains:\n"
        "'question' (string), 'options' (array of 4 strings), and 'correct_answer' (integer from 0 to 3).\n"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            web_search=False
        )
        raw_response = response.choices[0].message.content
        print("Raw GPT response:", raw_response)

        try:
            mcqs = json.loads(raw_response)
            if not isinstance(mcqs, list):
                raise ValueError("Response is not a JSON array")
            for mcq in mcqs:
                if not all(k in mcq for k in ['question', 'options', 'correct_answer']):
                    raise ValueError("Invalid MCQ format")
                if not isinstance(mcq['options'], list) or len(mcq['options']) != 4:
                    raise ValueError("Options must be an array of 4 strings")
                if not isinstance(mcq['correct_answer'], int) or not (0 <= mcq['correct_answer'] <= 3):
                    raise ValueError("Correct answer must be between 0 and 3")

            # Simulate user score logic (replace this with real scoring logic)
            score_value = 8  # Hardcoded for now

            # Save score to database
            new_score = Score(user_id=current_user.id, course_id=course.id, score=score_value)
            db.session.add(new_score)
            db.session.commit()

            # Optionally send certificate
            if score_value >= 7:
                cert_path = generate_certificate(current_user.username)
                send_certificate_email(current_user.email, current_user.username, cert_path)

            return jsonify({"mcqs": mcqs, "score": score_value})

        except json.JSONDecodeError as e:
            return jsonify({"error": f"Failed to parse GPT response as JSON: {str(e)}"}), 500
        except ValueError as e:
            return jsonify({"error": f"Invalid response format: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Error generating MCQs: {str(e)}"}), 500



@app.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])

def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.name = request.form['name']
        course.contents = request.form['contents']
        course.duration = request.form['duration']
        course.video = request.form.get('video')
        db.session.commit()
        flash("Course updated successfully!", "success")
        return redirect(url_for('cadmin_dashboard'))  # adjust as needed
    return render_template('edit_course.html', course=course)


@app.route('/delete_course/<int:course_id>', methods=['POST'])

def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash("Course deleted successfully.", "danger")
    return redirect(url_for('cadmin_dashboard'))  # adjust as needed

@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    user_message = data.get('message', '')
    
    prompt = (
        f"You are EduBot, an assistant for an e-learning platform. Help users by answering questions like:\n"
        f"- How to register or login\n"
        f"- Course progress, MCQ tests\n"
        f"- Certificate generation\n"
        f"\nUser: {user_message}\nEduBot:"
    )

    try:
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            web_search=False
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = "Oops! I had trouble answering that. Please try again later."

    return jsonify({"reply": reply})

import random
from itsdangerous import URLSafeTimedSerializer as Serializer
from werkzeug.security import generate_password_hash, check_password_hash


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if user:
            
            otp = random.randint(100000, 999999)
            user.otp = otp  # Assuming 'otp' field is in your User model
            db.session.commit()
            
            # Send the OTP to user's email
            msg = Message('Password Reset OTP', sender='your_email@gmail.com', recipients=[user.email])
            msg.body = f'Your OTP for password reset is: {otp}'
            mail.send(msg)
            
            flash('An OTP has been sent to your email. Please enter it below to reset your password.', 'info')
            return redirect(url_for('reset_password', token=user.id))  # Redirect to reset password with user ID in token
        else:
            flash('No account found with that email address.', 'danger')
    
    return render_template('forgot_password.html')

# Reset Password Route
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.get(int(token))  # Get the user by token (user ID)

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        entered_otp = request.form['otp']
        new_password = request.form['password']

        if str(user.otp) == entered_otp:
            # If OTP matches, update the password
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            user.otp = None  # Clear the OTP after successful password reset
            db.session.commit()
            
            flash('Your password has been updated successfully!', 'success')
            return redirect(url_for('clogin'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    
    return render_template('reset_password.html', token=token)


@app.route('/my_courses')
@login_required
def my_courses():
    user = current_user
    domain = user.domain

    # Match domain with course name or category
    matched_courses = Course.query.filter(
        (Course.name.ilike(f'%{domain}%')) | (Course.category.ilike(f'%{domain}%'))
    ).all()

    return render_template('my_courses.html', courses=matched_courses)

from flask import Flask, request, jsonify, render_template
import g4f
@app.route('/minichatbot', methods=['GET', 'POST'])
def minichatbot():
    if request.method == 'POST':
        user_message = request.json.get('message')

        # Get response using g4f
        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4,  # or gpt_3.5
                messages=[{"role": "user", "content": user_message}],
            )
            return jsonify({"reply": response})
        except Exception as e:
            return jsonify({"reply": f"Error: {str(e)}"})

    return render_template('minichatbot.html')

@app.route('/score')
def score():
    scores = Score.query.join(User).join(Course).all()
    return render_template('score.html', scores=scores)

@app.route('/view_certificate/<int:user_id>')
def view_certificate(user_id):
    user = User.query.get(user_id)
    if user is None:
        return "User not found", 404

    # Get the score for the user
    score = Score.query.filter_by(user_id=user.id).first()
    if not score:
        return "No score found for this user", 404

    # Generate the certificate PDF
    certificate_path = generate_certificate(user.username)
    if certificate_path is None:
        return "Error generating certificate", 500

    # Send the certificate by email
    send_certificate_email(user.email, user.username, certificate_path)

    return render_template('certificate.html', user=user, score=score)

@app.route('/educator/add_questions', methods=['GET', 'POST'])
@login_required
def add_questions():
    if current_user.role != 'educator':
        flash('Access denied.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        topic = request.form['topic']
        for i in range(1, 11):
            q = Question(
                topic=topic,
                text=request.form[f'q{i}'],
                option_a=request.form[f'q{i}_a'],
                option_b=request.form[f'q{i}_b'],
                option_c=request.form[f'q{i}_c'],
                option_d=request.form[f'q{i}_d'],
                correct_answer=request.form[f'q{i}_correct']
            )
            db.session.add(q)
        db.session.commit()
        flash('Questions added successfully.')
        return redirect(url_for('index'))

    return render_template('add_questions.html')

@app.route('/topics')
@login_required
def topics():
    topics = db.session.query(Question.topic).distinct().all()
    # topics will be a list of tuples, so we flatten it
    topics = [t[0] for t in topics]
    return render_template('topics.html', topics=topics)

@app.route('/quiz/<topic>', methods=['GET', 'POST'])
@login_required
def quiz_by_topic(topic):
    questions = Question.query.filter_by(topic=topic).limit(10).all()
    if not questions:
        flash('No questions found for this topic.')
        return redirect(url_for('home'))  # or another fallback page

    course = Question.query.filter_by(topic=topic).first()  # Retrieve course by topic (or another identifier)
    if not course:
        flash('No course found for this topic.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        score = 0
        for q in questions:
            selected = request.form.get(str(q.id))
            is_correct = selected == q.correct_answer
            if is_correct:
                score += 1
            ua = UserAnswer(
                user_id=current_user.id,
                question_id=q.id,
                selected_answer=selected,
                is_correct=is_correct
            )
            db.session.add(ua)
        
        # Use course_id from the fetched Course
        quiz_score = Score(
            user_id=current_user.id,
            score=score,
            course_id=course.id  # Get the course_id from the Course object
        )
        db.session.add(quiz_score)
        db.session.commit()
        flash(f'You scored {score} out of {len(questions)}')
        return redirect(url_for('quiz_result'))

    return render_template('quiz.html', questions=questions)

@app.route('/quiz_result')
@login_required
def quiz_result():
    score = session.get('last_score')
    total = session.get('total_questions')
    topic = session.get('topic')

    if score is None or total is None:
        flash('No quiz result found.')
        return redirect(url_for('topics'))

    return render_template('quiz_result.html', score=score, total=total, topic=topic)

@app.route('/profile')
@login_required
def profile():
    user = current_user
    scores = Score.query.filter_by(user_id=user.id).all()
    return render_template('profile.html', user=user, scores=scores)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
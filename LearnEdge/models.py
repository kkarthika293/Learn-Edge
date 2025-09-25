from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elearning.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="user")  # user or admin

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contents = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    video = db.Column(db.String(300), nullable=True)
    views = db.Column(db.Integer, default=0)
    users_completed = db.Column(db.Integer, default=0)

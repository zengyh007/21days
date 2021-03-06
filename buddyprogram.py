#all that imports
from flask import Flask, request, session, g, redirect, url_for, abort, render_template,flash
from contextlib import closing
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, UserMixin, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, DateField, DateTimeField, SelectField, SubmitField
from wtforms.validators import InputRequired, Email, EqualTo, Length
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_assets import Bundle, Environment



import os
import sqlite3
import sys

#create application
app = Flask(__name__)
app.config['SECRET_KEY']= 'GRADSCHOOLNOLIFE'
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:////Users/zengyh/myproject/21days/buddyprogram.db'
#app.config['SQLALCHEMY_DATABASE_URI']='sqlite:////Users/Yu/Desktop/buddy/buddyprogram.db'
#app.config['SQLALCHEMY_DATABASE_URI']='sqlite:////Users/bichengxu/Desktop/si699_03_developing_social_computing/21days/buddyprogram.db'

cs = Bundle('devices.min.css','bootstrap.min.css', output='gen/main.css')
assets = Environment(app)
assets.register('main_css',cs)

db = SQLAlchemy(app)
login_manager = LoginManager() #handle user session
login_manager.init_app(app)
login_manager.login_view = 'login'

# config for updating intermediate table participate
###########################
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'buddyprogram.db'),
))
app.config.from_envvar('BUDDY_SETTINGS', silent=True)
def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv
def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


#Database Table

participate = db.Table('participate',
    db.Column('uid',db.Integer, db.ForeignKey('user.id')),
    db.Column('pid',db.Integer, db.ForeignKey('program.id'))
)

class User(UserMixin,db.Model):
    id = db.Column (db.Integer, primary_key=True)
    email = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(80),nullable=False)
    username = db.Column(db.String(15),nullable=False)
    program = db.relationship('Program',secondary=participate,backref=db.backref('participants',lazy='dynamic')) #many to many
    # buddy = db.relationship('User',secondary=friend,backref=db.backref('friends',lazy='dynamic',cascade='all, delete-orphan')) #many to many
    log = db.relationship('Dailylog',backref='user',lazy='dynamic')#one to many


@login_manager.user_loader #get the user object to manage
def load_user(user_id):
     return User.query.get(int(user_id))

class Program(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(80))
    activity = db.Column(db.String(80),nullable=False)
    start_date = db.Column(db.DateTime,nullable=False)
    activity_time = db.Column(db.DateTime,nullable=False)
    log = db.relationship('Dailylog',backref='programs',lazy='dynamic')#one to many
    user = db.relationship('User',secondary=participate,backref=db.backref('participants',lazy='dynamic')) #many to many


class Dailylog(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    date = db.Column(db.DateTime)
    checkin = db.Column(db.Boolean)
    reason = db.Column(db.Text)
    note = db.Column(db.Text)
    user_id=db.Column(db.Integer, db.ForeignKey('user.id'))
    program_id=db.Column(db.Integer, db.ForeignKey('program.id'))


#Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Email()])
    password = PasswordField('Password', validators=[InputRequired(),Length(min=8,max=80)])
    remember = BooleanField('Keep me logged in')

@app.route('/login',methods=['GET','POST']) #form needs to write and inqury so get and post are needed
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                # check whether to create or home
                login_user(user,remember=form.remember.data)
                db = get_db()
                query = 'select * from participate where uid =\'' + str(user.id) + '\''
                if db.execute(query).fetchall():
                    return redirect(url_for('home'))
                else:
                    return redirect(url_for('create_buddy'))
        return 'Invalid email or password'
    return render_template('login.html', form=form)

class ResigeationForm(FlaskForm):
    email = StringField('Email',validators=[Email()])
    password = PasswordField('Input Password',validators=[InputRequired(),Length(min=8,max=80)])
    confirm = PasswordField('Confirm Password', validators=[EqualTo('password',message='Password does not match')])
    username = StringField('Username',validators=[InputRequired(),Length(min=4,max=15)])
    accept_tos = BooleanField('I accept the Term of Service',validators=[InputRequired()])

@app.route('/register',methods=['GET','POST'])
def register():
    form = ResigeationForm(request.form)
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='sha256')#for security, encode plain text password
        new_user = User(email=form.email.data, password=hashed_password,username=form.username.data)
        db.session.add(new_user)
        db.session.commit()
        db.session.close()# close the db.session
        return redirect(url_for('login'))
    return render_template('register.html',form=form)


# create buddy
class CreateForm(FlaskForm):
    name = StringField('Program Name', validators=[InputRequired(),Length(min=1,max=80)])
    activity = StringField('What you wanna do', validators=[InputRequired(),Length(min=1,max=80)])
    start_date = DateField('Start Date', format='%Y-%m-%d', default=datetime.today)
    activity_time = DateTimeField('Activity Time', format='%H:%M:%S', default=datetime.now().time())
    buddy = SelectField('Buddy', choices=[], coerce=int)

@app.route('/create', methods=['GET','POST'])
def create_buddy():
    form = CreateForm(request.form)

    # initial display selection
    if request.method == 'GET':
        db_buddy = get_db()
        query_buddy = 'select id, username from user where id <>\'' + str(current_user.id) + '\'order by id asc'
        cur = db_buddy.execute(query_buddy)
        entries = cur.fetchall()
        form.buddy.choices=[(a[0], a[1]) for a in entries]

    # validate form
    if request.method == 'POST':
        # insert to program
        new_program = Program(name=form.name.data, activity=form.activity.data, start_date=form.start_date.data, activity_time=form.activity_time.data)
        db.session.add(new_program)
        db.session.commit()
        db.session.close()

        # insert to intermediate table participate
        db1 = get_db()
        query_buddy_id = 'select id from user where id =\'' + str(form.buddy.data) + '\''

        cur1 = db1.execute(query_buddy_id)
        my_buddy = cur1.fetchone()
        program_current = Program.query.order_by(Program.id.desc()).first()

        db1.execute('insert into participate (uid, pid) values (?, ?)',
                 [current_user.id, program_current.id])
        db1.execute('insert into participate (uid, pid) values (?, ?)',
                 [my_buddy[0], program_current.id])
        db1.commit()


        flash('New buddy program created!')

        return redirect(url_for('home'))
    return render_template('create.html',form=form)



@app.route('/')
@login_required
def home():
    program_current = Program.query.filter(Program.participants.any(id=current_user.id)).order_by(Program.id.desc()).first() #select the most current program
    buddy = User.query.filter(User.participants.any(id=program_current.id))
    for user in buddy:
        if(user.id!=current_user.id):
            buddy_id=user.id
    my_logs = Dailylog.query.filter_by(user_id = current_user.id, program_id = program_current.id) #get my previous checkin data
    buddy_logs = Dailylog.query.filter_by(user_id = buddy_id, program_id = program_current.id ) #get my buddy's previous checkin data
    if my_logs.count() == 21:
        in_progress = False
    else:
        in_progress = True

    return render_template('home.html',
    name=current_user.username,
    time=datetime.now(),
    my_logs = my_logs,
    buddy_logs = buddy_logs,
    updated=session.get('updated', False),in_progress = in_progress)

class UpdateForm(FlaskForm):
    check_status = SelectField("I'm", choices=[(False, "not going."),(True,"Here!")],coerce = lambda x: x=='True', validators=[InputRequired()])
    reason = StringField('Reason')
    submit = SubmitField('Submit')

@app.route('/update', methods=['GET','POST'])
def update():
    form = UpdateForm(request.form)
    if form.validate_on_submit():
        program_current = Program.query.filter(Program.participants.any(id=current_user.id)).order_by(Program.id.desc()).first()
        new_log = Dailylog(
        date = datetime.now(),
        checkin = form.check_status.data,
        reason = form.reason.data,
        user_id = current_user.id,
        program_id = program_current.id
        )
        db.session.add(new_log)
        db.session.commit()
        db.session.close()

        session['updated'] = True
        return redirect(url_for('between'))

    return render_template('update.html',form=form)

@app.route('/between')
def between():
    program_current = Program.query.filter(Program.participants.any(id=current_user.id)).order_by(Program.id.desc()).first()
    logs = Dailylog.query.filter_by(user_id = current_user.id, program_id = program_current.id )

    if logs.count()==21:
        return redirect(url_for('cong'))
    else:
        return redirect(url_for('home'))


@app.route('/cong')
def cong():
    return render_template('cong.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('updated', None)
    logout_user()
    return redirect(url_for('login'))





if __name__ == '__main__':
    app.run(debug=True)

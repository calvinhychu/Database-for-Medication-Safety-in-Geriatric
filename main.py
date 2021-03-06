from flask import Flask, render_template, request, flash, session, redirect, \
    url_for
from forms import RegisterForm, LoginForm, NoteForm
from models import User, Drug, Drugclass, Note
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from extensions import *
import datetime
import os

app = Flask(__name__)
app.config.from_pyfile('config.cfg')

Bootstrap.init_app(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
mail.init_app(app)
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.route("/")
@app.route("/home/")
def home():
    return render_template('home.html', load_user=load_user)

@app.route("/about/")
def about():
    return render_template('about.html', load_user=load_user)

@app.errorhandler(404) 
def not_found(error):  
  return render_template("error_page.html", load_user=load_user)

@app.route("/register/", methods=["POST", "GET"])
def register():
    if current_user.is_authenticated:
        flash('Please logout before signing up.')
        return redirect(url_for('home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first() is not None:
            flash('Email already registered!')
            return redirect(url_for('register'))
        else:
            hashed_password = generate_password_hash(form.password.data, method='sha256')
            token = s.dumps([form.name.data, form.profession.data, form.department.data, form.email.data, hashed_password])
            msg = Message('Confirmation Email for Database for Medication Safety in Geriatric Population Patients', sender=app.config['MAIL_USERNAME'], recipients=[form.email.data])
            link = url_for('confirm_email', token=token, _external=True)
            msg.body = 'You have registered for an account for Database for Medication Safety in Geriatric Population Patients. Please click on this link {} to confirm your registration.'.format(link)
            mail.send(msg)
            flash('Confirmation email sent. Please click on sent link to confirm your account registration.')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        user_info = s.loads(token, max_age=3600)
        new_user = User(name=user_info[0], profession=user_info[1], department=user_info[2], email=user_info[3], password=user_info[4])
        db.session.add(new_user)
        db.session.commit()
    except SignatureExpired:
        flash('Token has expired, please register again.')
        return redirect(url_for('register'))
    flash('Registration completed. You can now login to your account.')
    return redirect(url_for('login'))


@app.route("/login/", methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        flash('Already Logged in!')
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user_email = User.query.filter_by(email=form.email.data).first()
        if user_email and check_password_hash(user_email.password, form.password.data):
                login_user(user_email)
                flash('Logged in succesfully.')
                return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
    return render_template('login.html', form=form)

@app.route('/logout/')
@login_required
def logout():
    logout_user()
    flash('Logged out succesfully.')
    return redirect(url_for('home'))

@app.route('/drugclass/')
def drugclass():
    all_drug_classes = Drugclass.query.all()
    return render_template('medication_list.html', names=all_drug_classes, title="Drug Classes", load_user=load_user)

@app.route('/drugclass/<drug>/')
def show_drug_class_information(drug):
    med_class = Drugclass.query.filter_by(name=drug).first()
    if med_class is None:
        return render_template('error_page.html', load_user=load_user)
    beers = med_class.beers_criteria
    stopp_start = med_class.stopp_start_criteria
    return render_template('drugclass.html', drug=drug, beers=beers, stopp_start=stopp_start, list_of_meds=med_class.drugs, category="Drug Class", load_user=load_user)

@app.route('/medications/')
def medication():
    all_medications = Drug.query.all()
    return render_template('medication_list.html', names=all_medications, title="Medications", load_user=load_user)


@app.route('/medications/<drug>/')
def show_med_information(drug):
    med = Drug.query.filter_by(name=drug).first()
    if med is None:
        return render_template('error_page.html', load_user=load_user)
    beers = med.beers_criteria
    stopp_start = med.stopp_start_criteria
    med_class = Drugclass.query.get(med.drug_class_id)
    med_class_name = med_class.name
    return render_template('drugclass.html', drug=drug, beers=beers, stopp_start=stopp_start, 
    list_of_meds=med_class.drugs, drugclass_name=med_class_name, category="Medication", load_user=load_user)


@app.route('/<category>/<drug>/notes/')
@login_required
def show_notes(category, drug):
    if category == "drugclass":
        med = Drugclass.query.filter_by(name=drug).first()
        if med is None:
            return render_template('error_page.html', load_user=load_user)
        else:
            return render_template('notes.html', notes=med.notes, load_user=load_user)
    elif category == "medications":
        med = Drug.query.filter_by(name=drug).first()
        if med is None:
            return render_template('error_page.html', load_user=load_user)
        else:
            return render_template('notes.html', notes=med.notes, load_user=load_user)
    else:
        return render_template('error_page.html', load_user=load_user)

@app.route('/<category>/<drug>/submit_notes/', methods=["POST", "GET"])
@login_required
def submit_notes(category, drug):
    form = NoteForm()
    if category == "drugclass":
        med = Drugclass.query.filter_by(name=drug).first()
        if med is None:
            return render_template('error_page.html', load_user=load_user)
        else:
            current_note = Note.query.filter_by(drugclass_id=med.id, user_id=current_user.get_id()).first()
            if form.validate_on_submit():
                if current_note is None:
                    new_note = Note(content=form.content.data, user_id=current_user.get_id(), drugclass_id=med.id)
                    db.session.add(new_note)
                    db.session.commit()
                    flash('Note Added')
                else:
                    current_note.content = form.content.data
                    current_note.date_posted = datetime.datetime.now()
                    db.session.commit()
                    flash('Note Updated') 
            return render_template('submit.html', form=form, medclass="drugclass", med=med.name, current_note = current_note, load_user=load_user)
    elif category == "medications":
        med = Drug.query.filter_by(name=drug).first()
        if med is None:
            return render_template('error_page.html', load_user=load_user)
        else:
            current_note = Note.query.filter_by(drug_id=med.id, user_id=current_user.get_id()).first()
            if form.validate_on_submit():
                if current_note is None:
                    new_note = Note(content=form.content.data, user_id=current_user.get_id(), drug_id=med.id)
                    db.session.add(new_note)
                    db.session.commit()
                    flash('Note Added')
                else:
                    current_note.content = form.content.data
                    current_note.date_posted = datetime.datetime.now()
                    db.session.commit()
                    flash('Note Updated')
            return render_template('submit.html', form=form, medclass="medications", med=med.name, current_note = current_note, load_user=load_user)
    else:
        return render_template('error_page.html', load_user=load_user)


if __name__ == "__main__":
    app.run()
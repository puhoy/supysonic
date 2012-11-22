# coding: utf-8

from flask import request, session, flash, render_template, redirect, url_for
import requests, hashlib

from web import app
from user_manager import UserManager
from db import User, session as db_sess
import config

@app.before_request
def check_admin():
	if not request.path.startswith('/user'):
		return

	if request.endpoint == 'add_user' and User.query.filter(User.admin == True).count() == 0:
		return

	if request.endpoint in ('user_index', 'add_user', 'del_user') and not UserManager.get(session.get('userid'))[1].admin:
		return redirect(url_for('index'))

@app.route('/user')
def user_index():
	return render_template('users.html', users = User.query.all())

@app.route('/user/me')
def user_profile():
	return render_template('profile.html', user = UserManager.get(session.get('userid'))[1], api_key = config.get('LASTFM_KEY'))

@app.route('/user/changemail', methods = [ 'GET', 'POST' ])
def change_mail():
	user = UserManager.get(session.get('userid'))[1]
	if request.method == 'POST':
		mail = request.form.get('mail')
		# No validation, lol.
		user.mail = mail
		db_sess.commit()
		return redirect(url_for('user_profile'))

	return render_template('change_mail.html', user = user)

@app.route('/user/changepass', methods = [ 'GET', 'POST' ])
def change_password():
	if request.method == 'POST':
		current, new, confirm = map(request.form.get, [ 'current', 'new', 'confirm' ])
		error = False
		if current in ('', None):
			flash('The current password is required')
			error = True
		if new in ('', None):
			flash('The new password is required')
			error = True
		if new != confirm:
			flash("The new password and its confirmation don't match")
			error = True

		if not error:
			status = UserManager.change_password(session.get('userid'), current, new)
			if status != UserManager.SUCCESS:
				flash(UserManager.error_str(status))
			else:
				flash('Password changed')
				return redirect(url_for('user_profile'))

	return render_template('change_pass.html', user = UserManager.get(session.get('userid'))[1].name)

@app.route('/user/add', methods = [ 'GET', 'POST' ])
def add_user():
	if request.method == 'GET':
		return render_template('adduser.html')

	error = False
	(name, passwd, passwd_confirm, mail, admin) = map(request.form.get, [ 'name', 'passwd', 'passwd_confirm', 'mail', 'admin' ])
	if name in (None, ''):
		flash('The name is required.')
		error = True
	if passwd in (None, ''):
		flash('Please provide a password.')
		error = True
	elif passwd != passwd_confirm:
		flash("The passwords don't match.")
		error = True

	if admin is None:
		admin = True if User.query.filter(User.admin == True).count() == 0 else False
	else:
		admin = True

	if not error:
		status = UserManager.add(name, passwd, mail, admin)
		if status == UserManager.SUCCESS:
			flash("User '%s' successfully added" % name)
			return redirect(url_for('user_index'))
		else:
			flash(UserManager.error_str(status))

	return render_template('adduser.html')


@app.route('/user/del/<uid>')
def del_user(uid):
	status = UserManager.delete(uid)
	if status == UserManager.SUCCESS:
		flash('Deleted user')
	else:
		flash(UserManager.error_str(status))

	return redirect(url_for('user_index'))

@app.route('/user/lastfm/link')
def lastfm_reg():
	token = request.args.get('token')
	if token in ('', None):
		flash('Missing LastFM auth token')
		return redirect(url_for('user_profile'))

	p = {
		'api_key': config.get('LASTFM_KEY'),
		'method': 'auth.getSession',
		'token': token
	}
	sig_str = ''
	for k, v in sorted(p.iteritems()):
		sig_str += k + v
	sig = hashlib.md5(sig_str + config.get('LASTFM_SECRET')).hexdigest()

	p['api_sig'] = sig
	p['format'] = 'json'

	r = requests.get('http://ws.audioscrobbler.com/2.0/', params = p)
	if 'error' in r.json:
		flash('Error %i: %s' % (r.json['error'], r.json['message']))
	else:
		user = UserManager.get(session.get('userid'))[1]
		user.lastfm_session = r.json['session']['key']
		user.lastfm_status = True
		db_sess.commit()
		flash('Successfully linked LastFM account')

	return redirect(url_for('user_profile'))

@app.route('/user/lastfm/unlink')
def lastfm_unreg():
	user = UserManager.get(session.get('userid'))[1]
	user.lastfm_session = None
	user.lastfm_status = True
	db_sess.commit()
	flash('Unliked LastFM account')
	return redirect(url_for('user_profile'))

@app.route('/user/login', methods = [ 'GET', 'POST'])
def login():
	return_url = request.args.get('returnUrl') or url_for('index')
	if session.get('userid'):
		flash('Already logged in')
		return redirect(return_url)

	if request.method == 'GET':
		return render_template('login.html')

	name, password = map(request.form.get, [ 'user', 'password' ])
	error = False
	if name in ('', None):
		flash('Missing user name')
		error = True
	if password in ('', None):
		flash('Missing password')
		error = True

	if not error:
		status, user = UserManager.try_auth(name, password)
		if status == UserManager.SUCCESS:
			session['userid'] = str(user.id)
			session['username'] = user.name
			flash('Logged in!')
			return redirect(return_url)
		else:
			flash(UserManager.error_str(status))

	return render_template('login.html')

@app.route('/user/logout')
def logout():
	session.clear()
	flash('Logged out!')
	return redirect(url_for('login'))


import os
from flask import Blueprint, render_template, request, redirect, url_for, session

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '3326')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin.master_view'))
        else:
            return "<script>alert('비밀번호가 틀렸습니다.'); history.back();</script>"
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

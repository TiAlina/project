from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from app.models import User

# Создаем blueprint для аутентификации
bp = Blueprint('auth', __name__, url_prefix='/auth')

# Инициализация менеджера логинов
def init_login_manager(app):
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Для доступа к этой странице нужно пройти аутентификацию.'
    login_manager.login_message_category = 'warning'
    login_manager.user_loader(load_user)
    login_manager.init_app(app)

# Загрузка пользователя по ID
def load_user(user_id):
    return User.query.get(user_id)

# Обработчик для входа пользователя
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        if login and password:
            user = User.query.filter_by(login=login).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Вы успешно вошли в систему.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
        flash('Ошибка аутентификации. Проверьте логин и пароль.', 'danger')
    return render_template('auth/login.html')

# Декоратор для проверки прав доступа
def permission_check(action):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            user = load_user(user_id) if user_id else None
            if not current_user.can(action, user):
                flash('У вас недостаточно прав для выполнения этого действия.', 'warning')
                return redirect(url_for('index'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Обработчик для выхода пользователя
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

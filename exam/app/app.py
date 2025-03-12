from flask import Flask, render_template, abort, send_from_directory
from flask_migrate import Migrate

from app.auth import bp as auth_bp, init_login_manager
from app.books import bp as books_bp
from app.collections_books import bp as collections_bp
from app.models import db, Image

# Создаем экземпляр приложения Flask
app = Flask(__name__)
application = app

# Загружаем конфигурацию из файла
app.config.from_pyfile('config.py')

# Инициализация базы данных и миграций
db.init_app(app)
migrate = Migrate(app, db)

# Регистрация blueprint'ов
app.register_blueprint(auth_bp)
app.register_blueprint(books_bp)
app.register_blueprint(collections_bp)

# Инициализация менеджера сессий
init_login_manager(app)

# Обработчик для главной страницы
@app.route('/')
def index():
    return render_template('index.html')

# Обработчик для отображения изображений
@app.route('/images/<image_id>')
def image(image_id):
    img = Image.query.get(image_id)
    if img is None:
        abort(404)
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        img.storage_filename
    )

# Точка входа
if __name__ == '__main__':
    app.run()

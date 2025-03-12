from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
import sqlalchemy as sa

from app.models import db, Book, Genre, Collection
from app.auth import permission_check

bp = Blueprint('collections', __name__, url_prefix='/collections')


def get_search_params():
    return {
        'name': request.args.get('name'),
        'genre_ids': request.args.getlist('genre_ids'),
    }


@bp.route('/')
@login_required
@permission_check('show_collections')
def index():
    page = request.args.get('page', 1, type=int)
    user_id = current_user.id
    user_collections = Collection.query.filter_by(user_id=user_id).paginate(page, 4)
    collections = user_collections.items
    books_count = {collection.id: len(collection.books) for collection in collections}

    return render_template(
        'collections/index.html',
        collections=collections,
        pagination=user_collections,
        books_count=books_count,
        search_params={}
    )


@bp.route('/create', methods=['POST'])
@login_required
@permission_check('show_collections')
def create():
    name = request.form.get('name')
    desc = request.form.get('desc')

    if not name:
        flash('Название подборки обязательно.', 'danger')
        return redirect(url_for('collections.index'))

    new_collection = Collection(
        user_id=current_user.id,
        name=name,
        desc=desc
    )

    try:
        db.session.add(new_collection)
        db.session.commit()
        flash(f'Подборка "{new_collection.name}" успешно создана!', 'success')
    except sa.exc.SQLAlchemyError:
        db.session.rollback()
        flash('Произошла ошибка при создании подборки.', 'danger')

    return redirect(url_for('collections.index'))


@bp.route('/<int:book_id>/add_book', methods=['POST'])
@login_required
@permission_check('show_collections')
def add_book(book_id):
    collection_id = request.form.get('collection_id')
    collection = Collection.query.get(collection_id)
    book = Book.query.get(book_id)

    if not collection or not book:
        flash('Неверные данные о подборке или книге.', 'danger')
        return redirect(url_for('books.show', book_id=book_id))

    try:
        collection.books.append(book)
        db.session.commit()
        flash(f'Книга "{book.name}" добавлена в подборку "{collection.name}"!', 'success')
    except sa.exc.SQLAlchemyError:
        db.session.rollback()
        flash('Ошибка при добавлении книги в подборку.', 'danger')

    return redirect(url_for('books.show', book_id=book_id))


@bp.route('/<int:collection_id>')
@login_required
@permission_check('show_collections')
def show_collection(collection_id):
    collection = Collection.query.get(collection_id)
    if not collection:
        flash('Подборка не найдена.', 'danger')
        return redirect(url_for('collections.index'))

    books = collection.books
    reviews_count = {book.id: len(book.reviews) for book in books}
    genres = Genre.query.all()

    return render_template(
        'collections/show_collection.html',
        collection=collection,
        genres=genres,
        books=books,
        search_params=get_search_params(),
        reviews_count=reviews_count
    )


@bp.route('/<int:collection_id>/delete', methods=['POST'])
@login_required
@permission_check('show_collections')
def delete_collection(collection_id):
    collection = Collection.query.get(collection_id)
    if not collection:
        flash('Подборка не найдена.', 'danger')
        return redirect(url_for('collections.index'))

    if collection.user_id != current_user.id:
        flash('Вы не можете удалить эту подборку.', 'danger')
        return redirect(url_for('collections.index'))

    try:
        db.session.delete(collection)
        db.session.commit()
        flash(f'Подборка "{collection.name}" была удалена.', 'success')
    except sa.exc.SQLAlchemyError:
        db.session.rollback()
        flash('Ошибка при удалении подборки.', 'danger')

    return redirect(url_for('collections.index'))

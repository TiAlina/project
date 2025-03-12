import os

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
import sqlalchemy as sa
import markdown
import bleach

from app import app
from app.auth import permission_check
from app.constants import REVIEW_STATUSES
from app.models import db, Book, Genre, User, Review, Image, Collection
from app.tools import BooksFilter, ImageSaver
from sqlalchemy import distinct
bp = Blueprint('books', __name__, url_prefix='/books')

PER_PAGE = 9

BOOK_PARAMS = [
    'author', 'name', 'publishing_house', 'volume', 'created_at'
]


def params():
    return {
        p: request.form.get(p) for p in BOOK_PARAMS
    }


def search_params():
    return {
        'name': request.args.get('name'),
        'genre_ids': request.args.getlist('genre_ids'),
    }


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    
    # Получаем уникальные значения даты создания из базы данных и сортируем их
    created_at_dates = db.session.query(distinct(Book.created_at)).order_by(Book.created_at.asc()).all()
    created_at_dates = [date[0] for date in created_at_dates if date[0]]  # Преобразуем в список

    filter_params = {
        'name': request.args.get('name', ''),
        'author': request.args.get('author', ''),
        'genre_ids': request.args.getlist('genre_ids', type=int),
        'volume_from': request.args.get('volume_from', ''),
        'volume_to': request.args.get('volume_to', ''),
        'created_at': request.args.getlist('created_at')  # Параметр для выбранной даты создания
    }

    books_query = BooksFilter(**filter_params).perform()
    pagination = books_query.paginate(page, PER_PAGE, error_out=False)
    books = pagination.items
    reviews_count = {book.id: len(book.reviews) for book in books}
    genres = Genre.query.all()
    
    return render_template('books/index.html',
                           books=books,
                           genres=genres,
                           pagination=pagination,
                           search_params=filter_params,
                           reviews_count=reviews_count,
                           created_at_dates=created_at_dates)  # Передаем created_at_dates в шаблон

@bp.route('/new')
@login_required
@permission_check('create')
def new():
    genres = Genre.query.all()
    return render_template('books/new.html',
                           genres=genres,
                           book={})


@bp.route('/create', methods=['POST'])
@login_required
@permission_check('create')
def create():
    f = request.files.get('background_img')
    img = None
    if f and f.filename:
        img = ImageSaver(f).save()

    try:
        genres = request.form.getlist('genres')
        genres = list(map(Genre.query.get, genres))
        short_desc = markdown.markdown(bleach.clean(request.form.get('short_desc')))
        book = Book(**params())
        book.genres = genres
        book.short_desc = short_desc

        if not img:
            db.session.rollback()
            flash('Выберите картинку', 'danger')
            genres = Genre.query.all()
            return render_template('books/new.html',
                                   genres=genres, book=book)

        book.background_image_id = img.id

        for key in BOOK_PARAMS:
            if not getattr(book, key) or not book.short_desc or not book.genres:
                db.session.rollback()
                flash('Заполните все поля', 'danger')
                genres = Genre.query.all()
                return render_template('books/new.html',
                                       genres=genres, book=book)

        db.session.add(book)
        db.session.commit()
        flash(f'Книга "{book.name}" была успешно добавлена!', 'success')

    except sa.exc.SQLAlchemyError:
        db.session.rollback()
        flash(f'При сохранении книги произошла ошибка', 'danger')
        genres = Genre.query.all()
        return render_template(
            'books/new.html',
            genres=genres,
            book=book
        )
    return redirect(url_for('books.index'))


@bp.route('/<int:book_id>/edit')
@login_required
@permission_check('update')
def edit(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    genres = Genre.query.all()
    return render_template('books/update.html',
                           book=book,
                           genres=genres)


@bp.route('/<int:book_id>/updating', methods=['POST'])
@login_required
@permission_check('update')
def update(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    parametres = params().items()
    print('=' * 30, '\n', parametres)
    try:
        genres = request.form.getlist('genres')
        genres = list(map(Genre.query.get, genres))
        for key, value in parametres:
            if value:
                setattr(book, key, value)
        book.genres = genres
        for key in BOOK_PARAMS:
            if not getattr(book, key) or not book.short_desc or not book.genres:
                db.session.rollback()
                flash('Все поля должны быть заполнены', 'danger')
                genres = Genre.query.all()
                return render_template('books/update.html',
                                       genres=genres, book=book)
        db.session.commit()
        flash(f'Книга {book.name} была успешно изменена!', 'success')

    except sa.exc.SQLAlchemyError:
        flash(f'При сохранении книги произошла ошибка', 'danger')
        db.session.rollback()
        book = Book.query.get(book_id)
        genres = Genre.query.all()
        return render_template('books/update.html',
                               book=book,
                               genres=genres)
    return redirect(url_for('books.show', book_id=book.id))


@bp.route('/<int:book_id>')
@login_required
def show(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    reviews_count = len(book.reviews)
    user_review = Review()
    collections = Collection.query.filter_by(user_id=current_user.id)
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(user_id=current_user.id).filter_by(book_id=book_id).first()
    book_reviews = Review.query \
        .filter_by(book_id=book_id, status_id=REVIEW_STATUSES['APPROVED']['id']) \
        .order_by(Review.created_at.desc()) \
        .limit(5) \
        .all()
    return render_template(
        'books/show.html',
        book=book,
        review=user_review,
        book_reviews=book_reviews,
        reviews_count=reviews_count,
        collections=collections
    )


@bp.route('/<int:book_id>/delete', methods=['POST'])
@login_required
@permission_check('delete')
def delete(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    books_image = Book.query.filter_by(background_image_id=book.bg_image.id).count()
    try:
        db.session.delete(book)
        if book.background_image_id:
            if books_image == 1:
                image = Image.query.get(book.background_image_id)
                if image:
                    os.remove(os.path.join(app.app.config['UPLOAD_FOLDER'],
                                           image.storage_filename))
                db.session.delete(image)
        db.session.commit()
        flash(f'Книга "{book.name}" успешно удалена', 'success')

    except sa.exc.SQLAlchemyError:
        flash(f'При удалении книги произошла ошибка', 'danger')
        db.session.rollback()
        return render_template('books/index.html')
    return redirect(url_for('books.index'))


@bp.route('/<int:book_id>/give_review')
@login_required
def give_review(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    user = User.query.get(current_user.id)
    return render_template(
        'books/give_review.html',
        book=book,
        user=user
    )


@bp.route('/<int:book_id>/send', methods=['POST'])
@login_required
def send_review(book_id):
    book = Book.query.get(book_id)

    if not book:
        flash(f'Такой книги не существует', 'warning')
        return redirect(url_for('books.index'))

    try:
        text = markdown.markdown(bleach.clean(request.form.get('text_review')))
        rating = int(request.form.get('rating_id'))
        review = Review(text=text, rating=rating, book_id=book_id, user_id=current_user.id)
        db.session.add(review)
        db.session.commit()
        flash(f'Ваш отзыв был отправлен на рассмотрение!', 'success')

    except sa.exc.SQLAlchemyError:
        flash(f'При отправке отзыва произошла ошибка', 'danger')
        db.session.rollback()
        book = Book.query.get(book_id)
        user = User.query.get(current_user.id)
        return render_template('books/give_review.html',
                               book=book,
                               user=user)
    return redirect(url_for('books.show', book_id=book_id))


@bp.route('/<int:book_id>/reviews')
@login_required
def reviews(book_id):
    page = request.args.get('page', 1, type=int)
    book_reviews = Review.query.filter_by(book_id=book_id, status_id=REVIEW_STATUSES['APPROVED']['id'])

    if not book_reviews.all():
        flash(f'У этой книги еще нет отзывов!', 'warning')
        return redirect(url_for('books.show', book_id=book_id))

    sort_reviews = request.args.get('sort_reviews')
    dictionary_reviews = {'reviews_filter': sort_reviews, 'book_id': book_id}
    if sort_reviews == 'positive':
        book_reviews = book_reviews.order_by(Review.rating.desc())
    elif sort_reviews == 'negative':
        book_reviews = book_reviews.order_by(Review.rating.asc())
    else:
        book_reviews = book_reviews.order_by(Review.created_at.desc())
    pagination = book_reviews.paginate(page, 5)
    book_reviews = pagination.items

    return render_template('reviews/reviews.html',
                           book_reviews=book_reviews,
                           book_id=book_id,
                           pagination=pagination,
                           params=dictionary_reviews
                           )


@bp.route('/my_reviews')
@login_required
def my_reviews():
    page = request.args.get('page', 1, type=int)

    my_reviews = Review.query.filter_by(user_id=current_user.id)

    sort_reviews = request.args.get('sort_reviews')
    dictionary_reviews = {'reviews_filter': sort_reviews}
    if sort_reviews == 'positive':
        book_reviews = my_reviews.order_by(Review.rating.desc())
    elif sort_reviews == 'negative':
        book_reviews = my_reviews.order_by(Review.rating.asc())
    else:
        book_reviews = my_reviews.order_by(Review.created_at.desc())
    pagination = book_reviews.paginate(page, 5)
    my_reviews = pagination.items

    return render_template(
        'reviews/my_reviews.html',
        my_reviews=my_reviews,
        pagination=pagination,
        params=dictionary_reviews
    )


@bp.route('/reviews_to_moderate')
@login_required
@permission_check('reviews_to_moderate')
def reviews_to_moderate():
    page = request.args.get('page', 1, type=int)

    reviews_pagination = Review.query.filter_by(
        status_id=REVIEW_STATUSES['UNDER_MODERATION']['id']).order_by(Review.created_at.desc()) \
        .paginate(page=page, per_page=5, error_out=False)
    reviews = reviews_pagination.items

    return render_template(
        'reviews/reviews_to_moderate.html',
        reviews=reviews,
        pagination=reviews_pagination
    )


@bp.route('/review/<int:review_id>', methods=['GET', 'POST'])
@login_required
@permission_check('review')
def review(review_id):
    review = Review.query.get(review_id)

    if not review:
        flash(f'Такого отзыва не существует', 'warning')
        return redirect(url_for('books.reviews_to_moderate'))

    try:
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'approve':
                review.status_id = 2
                review.book.rating_up(review.rating)
                db.session.commit()
                flash('Рецензия одобрена', 'success')
            elif action == 'reject':
                review.status_id = 3
                db.session.commit()
                flash('Рецензия отклонена', 'success')
            return redirect(url_for('books.reviews_to_moderate'))
    except sa.exc.SQLAlchemyError:
        flash('Произошла ошибка базы данных', 'error')
        return redirect(url_for('books.reviews_to_moderate', review_id=review_id))

    return render_template('reviews/review.html', review=review)

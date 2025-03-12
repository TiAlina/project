import os

from flask import url_for
from flask_login import UserMixin
import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, and_
from werkzeug.security import check_password_hash, generate_password_hash

from app.users_policy import UsersPolicy
from app.constants import REVIEW_STATUSES, RATING_WORDS


convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)

book_genre = db.Table(
        'book_genre',
        db.Column('book.id', db.Integer, db.ForeignKey('books.id')),
        db.Column('genre.id', db.Integer, db.ForeignKey('genres.id'))
    )


class Genre(db.Model):
    __tablename__ = 'genres'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return '<Genre %r>' % self.name


book_collection = db.Table(
        'book_collection',
        db.Column('book.id', db.Integer, db.ForeignKey('books.id')),
        db.Column('collection.id', db.Integer, db.ForeignKey('collections.id'))
    )


class Collection(db.Model):
    __tablename__ = 'collections'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    desc = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    books = db.relationship('Book', secondary=book_collection, backref='collections')

    user = db.relationship('User')

    def __repr__(self):
        return '<Collection %r>' % self.name


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime,
                           nullable=False,
                           server_default=sa.sql.func.now())
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status_id = db.Column(
        db.Integer,
        db.ForeignKey('review_statuses.id'),
        default=REVIEW_STATUSES['UNDER_MODERATION']['id']
    )

    book = db.relationship('Book')
    user = db.relationship('User')
    status = db.relationship(
        'ReviewStatus',
        backref=db.backref('reviews', lazy=True),
    )

    @property
    def rating_word(self):
        return RATING_WORDS.get(self.rating)

    def __repr__(self):
        return '<Review %r>' % self.text[:10]


class ReviewStatus(db.Model):
    __tablename__ = 'review_statuses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_desc = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(4), nullable=False)
    publishing_house = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    volume = db.Column(db.Integer, nullable=False)
    rating_sum = db.Column(db.Integer, nullable=False, default=0)
    rating_num = db.Column(db.Integer, nullable=False, default=0)
    genres = db.relationship('Genre', secondary=book_genre, backref='books')
    background_image_id = db.Column(db.String(100), db.ForeignKey('images.id'))

    bg_image = db.relationship('Image')
    reviews = db.relationship(
        'Review',
        cascade='all, delete',
        primaryjoin=and_(
            Review.book_id == id,
            Review.status_id == REVIEW_STATUSES['APPROVED']['id']
        )
    )

    def __repr__(self):
        return '<Book %r>' % self.name

    @property
    def rating(self):
        if self.rating_num > 0:
            return self.rating_sum / self.rating_num
        return 0

    def rating_up(self, n: int):
        self.rating_num += 1
        self.rating_sum += n


class Image(db.Model):
    __tablename__ = 'images'

    id = db.Column(db.String(100), primary_key=True)
    file_name = db.Column(db.String(100), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime,
                           nullable=False,
                           server_default=sa.sql.func.now())

    def __repr__(self):
        return '<Image %r>' % self.file_name

    @property
    def storage_filename(self):
        _, ext = os.path.splitext(self.file_name)
        return self.id + ext

    @property
    def url(self):
        return url_for('image', image_id=self.id)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, nullable=False, server_default=sa.sql.func.now())
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    roles = db.relationship('Role')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return ' '.join([self.last_name, self.first_name, self.middle_name or ''])

    @property
    def is_admin(self):
        return self.roles.name == 'Администратор'

    @property
    def is_moder(self):
        return self.roles.name == 'Администратор' or self.roles.name == 'Модератор'

    def can(self, action, record=None):
        users_policy = UsersPolicy(record)
        method = getattr(users_policy, action, None)
        if method:
            return method()
        return False

    def __repr__(self):
        return '<User %r>' % self.login


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    desc = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return '<Role %r>' % self.name

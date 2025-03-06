import hashlib
import uuid
import os

from werkzeug.utils import secure_filename

from app import app
from app.models import db, Book, Image, Genre


from sqlalchemy.orm import joinedload

from sqlalchemy import func

class BooksFilter:
    def __init__(self, name='', author='', genre_ids=None, volume_from='', volume_to='', created_at=None):
        self.query = Book.query
        if name:
            self.query = self.query.filter(Book.name.ilike(f'%{name}%'))
        if author:
            self.query = self.query.filter(Book.author.ilike(f'%{author}%'))
        if genre_ids:
            self.query = self.query.filter(Book.genres.any(Genre.id.in_(genre_ids)))
        if volume_from:
            self.query = self.query.filter(Book.volume >= volume_from)
        if volume_to:
            self.query = self.query.filter(Book.volume <= volume_to)
        if created_at:
            self.query = self.query.filter(Book.created_at.in_(created_at))

    def perform(self):
        return self.query.order_by(Book.created_at.desc())

 


class ImageSaver:
    def __init__(self, file):
        self.file = file

    def save(self):
        self.img = self.__find_by_md5_hash()
        if self.img is not None:
            return self.img
        file_name = secure_filename(self.file.filename)
        self.img = Image(
            id=str(uuid.uuid4()),
            file_name=file_name,
            mime_type=self.file.mimetype,
            md5_hash=self.md5_hash)
        self.file.save(
            os.path.join(app.app.config['UPLOAD_FOLDER'],
                         self.img.storage_filename))
        db.session.add(self.img)
        db.session.commit()
        return self.img

    def __find_by_md5_hash(self):
        self.md5_hash = hashlib.md5(self.file.read()).hexdigest()
        self.file.seek(0)
        return Image.query.filter(Image.md5_hash == self.md5_hash).first()

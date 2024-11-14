from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import config

from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Определение модели пользователя
class User(UserMixin, db.Model):
    __table_args__ = {'extend_existing': True}  # Добавляем extend_existing
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    balance = db.Column(db.Float, default=1000)  # Начальный баланс пользователя

# Определение модели книги
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Связь с пользователем
    creator = db.relationship('User', backref=db.backref('books', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Главная страница перенаправляет на страницу регистрации
@app.route('/')
def index():
    return redirect(url_for('register'))

# Регистрация пользователя
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User(username=username, password=password, balance=1000)
        db.session.add(user)
        db.session.commit()
        flash("Успешная регистрация!")
        return redirect(url_for('login'))
    return render_template('register.html')

# Вход пользователя
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('library'))
        flash("Неправильные учетные данные")
    return render_template('login.html')

# Выход пользователя
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Страница библиотеки
@app.route('/library')
@login_required
def library():
    page = request.args.get('page', 1, type=int)  # Получаем текущую страницу
    per_page = 10  # Количество книг на странице
    books = Book.query.paginate(page=page, per_page=per_page)  # Пагинация

    return render_template('library.html', books=books)

# Поиск книг по названию и автору
@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    query = request.form.get('query', '')
    if query:
        # Фильтруем книги, которые содержат ключевое слово в названии или авторе
        books = Book.query.filter(
            (Book.title.ilike(f'%{query}%')) | (Book.author.ilike(f'%{query}%'))
        ).all()
    else:
        books = []
    return render_template('search_results.html', books=books, query=query)


# маршрут для страницы добавления книги
@app.route('/add_book_page')
@login_required
def add_book_page():
    return render_template('add_book.html')

# Добавление книги
@app.route('/add_book', methods=['POST'])
@login_required
def add_book():
    title = request.form.get('title')
    author = request.form.get('author')
    price = float(request.form.get('price'))

    file = request.files.get('image')
    image_path = None
    if file:
        filename = secure_filename(file.filename)
        image_path = filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    book = Book(title=title, author=author, price=price, user_id=current_user.id, image_path=image_path)
    db.session.add(book)
    db.session.commit()
    flash("Книга успешно добавлена.")
    return redirect(url_for('library'))

# Остальные маршруты остаются прежними

# Маршрут для редактирования книги
@app.route('/edit_book/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_book(id):
    book = Book.query.get_or_404(id)
    if book.user_id != current_user.id:
        flash("Вы не можете редактировать эту книгу, так как вы не являетесь её создателем.")
        return redirect(url_for('library'))
    
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form['author']
        book.price = float(request.form['price'])
        
        file = request.files.get('image')
        if file:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(image_path)
            book.image_path = 'uploads/' + file.filename
        
        db.session.commit()
        flash("Книга успешно обновлена.")
        return redirect(url_for('library'))

    return render_template('edit_book.html', book=book)


# Удаление книги (только для создателя)
@app.route('/delete_book/<int:id>', methods=['POST'])
@login_required
def delete_book(id):
    book = Book.query.get_or_404(id)
    if book.user_id != current_user.id:
        flash("Вы не можете удалить эту книгу, так как вы не являетесь её создателем.")
        return redirect(url_for('library'))
    
    db.session.delete(book)
    db.session.commit()
    flash("Книга успешно удалена.")
    return redirect(url_for('library'))

# Покупка книги через банковскую карточку

@app.route('/buy_book/<int:id>', methods=['GET', 'POST'])
@login_required
def buy_book(id):
    book = Book.query.get_or_404(id)
    if request.method == 'POST':
        # Проверка наличия всех полей формы
        if 'card_number' not in request.form or 'expiry_date' not in request.form or 'cvv' not in request.form:
            flash("Пожалуйста, заполните все данные карты.")
            return redirect(url_for('buy_book', id=book.id))

        # Получаем данные из формы
        card_number = request.form['card_number']
        expiry_date = request.form['expiry_date']
        cvv = request.form['cvv']

        # Проверка, хватает ли у пользователя средств на покупку
        if current_user.balance >= book.price:
            current_user.balance -= book.price
            book.user_id = current_user.id
            db.session.commit()
            flash("Вы успешно купили книгу через карту.")
        else:
            flash("Недостаточно средств для покупки.")
        return redirect(url_for('library'))
    
    return render_template('buy_book.html', book=book)

# Продажа книги
@app.route('/sell_book/<int:id>', methods=['POST'])
@login_required
def sell_book(id):
    book = Book.query.get_or_404(id)
    if book.user_id == current_user.id:
        current_user.balance += book.price
        db.session.delete(book)
        db.session.commit()
        flash("Книга успешно продана.")
    else:
        flash("Вы не можете продать книгу, которой не владеете.")
    return redirect(url_for('library'))

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


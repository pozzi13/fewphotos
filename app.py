from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "super_secret_fewphotos_key"

# Настройка базы данных SQLite в текущей папке
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "models.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# МОДЕЛИ БАЗЫ ДАННЫХ

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(32), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    role = db.relationship("Role")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(512), nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Service {self.title}>"


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="new")
    total_amount = db.Column(db.Float, nullable=False, default=0.0)

    user = db.relationship("User", backref="orders")

    def __repr__(self):
        return f"<Order {self.id} user={self.user_id}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_moment = db.Column(db.Float, nullable=False, default=0.0)

    order = db.relationship("Order", backref="items")
    service = db.relationship("Service")

    def __repr__(self):
        return f"<OrderItem order={self.order_id} service={self.service_id}>"


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

def init_db():
    """Создание таблиц и начальные данные."""
    db.create_all()

    # Создание ролей, если их нет
    if Role.query.count() == 0:
        admin_role = Role(name="admin")
        client_role = Role(name="client")
        db.session.add(admin_role)
        db.session.add(client_role)
        db.session.commit()

    # Создание администратора, если ещё нет
    if User.query.filter_by(email="admin@fewphotos.ru").first() is None:
        admin_role = Role.query.filter_by(name="admin").first()
        admin = User(
            full_name="Администратор FewPhotos",
            email="admin@fewphotos.ru",
            phone="0000000000",
            role_id=admin_role.id
        )
        admin.set_password("Admin123!")
        db.session.add(admin)
        db.session.commit()

    # Создание стартовых услуг, если их нет
    if Service.query.count() == 0:
        s1 = Service(
            title="Фотосессия товара",
            description="Профессиональная предметная фотосъёмка товаров для интернет-магазинов.",
            price=3000.0,
            is_active=True
        )
        s2 = Service(
            title="Портретная фотосессия",
            description="Студийная фотосъёмка портретов с профессиональной обработкой.",
            price=4000.0,
            is_active=True
        )
        s3 = Service(
            title="Обработка фотографий",
            description="Цветокоррекция и ретушь уже готовых фотографий.",
            price=1500.0,
            is_active=True
        )
        db.session.add_all([s1, s2, s3])
        db.session.commit()


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return User.query.get(user_id)


def is_admin():
    user = get_current_user()
    if user is None:
        return False
    return user.role.name == "admin"


def get_cart():
    """Корзина хранится в сессии как список id услуг."""
    cart = session.get("cart")
    if cart is None:
        cart = []
        session["cart"] = cart
    return cart


# МАРШРУТЫ ПРИЛОЖЕНИЯ

@app.route("/")
def index():
    user = get_current_user()
    return render_template("index.html", user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # Простые проверки
        if not full_name or not email or not password or not password_confirm:
            flash("Все обязательные поля должны быть заполнены.")
            return redirect(url_for("register"))

        if "@" not in email:
            flash("Неверный формат email.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Пароль должен содержать не менее 6 символов.")
            return redirect(url_for("register"))

        if password != password_confirm:
            flash("Пароли не совпадают.")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user is not None:
            flash("Пользователь с таким email уже существует.")
            return redirect(url_for("register"))

        client_role = Role.query.filter_by(name="client").first()
        new_user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role_id=client_role.id
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Регистрация успешна. Теперь войдите в систему.")
        return redirect(url_for("login"))

    user = get_current_user()
    return render_template("register.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Неверный логин или пароль.")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash("Вы успешно вошли в систему.")
        return redirect(url_for("catalog"))

    user = get_current_user()
    return render_template("login.html", user=user)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("cart", None)
    flash("Вы вышли из системы.")
    return redirect(url_for("index"))


@app.route("/catalog")
def catalog():
    user = get_current_user()
    services = Service.query.filter_by(is_active=True).all()
    return render_template("catalog.html", user=user, services=services)


@app.route("/add_to_cart/<int:service_id>")
def add_to_cart(service_id):
    user = get_current_user()
    if user is None:
        flash("Чтобы добавить услугу в корзину, войдите в систему.")
        return redirect(url_for("login"))

    service = Service.query.get(service_id)
    if service is None or not service.is_active:
        flash("Услуга не найдена или недоступна.")
        return redirect(url_for("catalog"))

    cart = get_cart()
    cart.append(service_id)
    session["cart"] = cart
    flash("Услуга добавлена в корзину.")
    return redirect(url_for("catalog"))


@app.route("/cart")
def cart():
    user = get_current_user()
    if user is None:
        flash("Чтобы просмотреть корзину, войдите в систему.")
        return redirect(url_for("login"))

    cart_ids = get_cart()
    services = []
    total = 0.0
    for service_id in cart_ids:
        service = Service.query.get(service_id)
        if service is not None:
            services.append(service)
            total += service.price

    return render_template("cart.html", user=user, services=services, total=total)


@app.route("/checkout", methods=["POST"])
def checkout():
    user = get_current_user()
    if user is None:
        flash("Чтобы оформить заказ, войдите в систему.")
        return redirect(url_for("login"))

    cart_ids = get_cart()
    if not cart_ids:
        flash("Корзина пуста. Добавьте услуги перед оформлением заказа.")
        return redirect(url_for("cart"))

    # Создаём заказ
    order = Order(user_id=user.id, status="new", total_amount=0.0)
    db.session.add(order)
    db.session.commit()

    total = 0.0
    for service_id in cart_ids:
        service = Service.query.get(service_id)
        if service is not None:
            item = OrderItem(
                order_id=order.id,
                service_id=service.id,
                quantity=1,
                price_at_moment=service.price
            )
            total += service.price
            db.session.add(item)

    order.total_amount = total
    db.session.commit()

    # Очищаем корзину
    session["cart"] = []
    flash("Заказ успешно оформлен.")
    return redirect(url_for("catalog"))


@app.route("/admin")
def admin():
    user = get_current_user()
    if user is None or not is_admin():
        flash("Доступ в административную панель запрещён.")
        return redirect(url_for("index"))

    orders = Order.query.all()
    services = Service.query.all()
    return render_template("admin.html", user=user, orders=orders, services=services)


@app.route("/admin/order/<int:order_id>/set_status", methods=["POST"])
def admin_set_order_status(order_id):
    user = get_current_user()
    if user is None or not is_admin():
        flash("Доступ запрещён.")
        return redirect(url_for("index"))

    new_status = request.form.get("status", "new")
    order = Order.query.get(order_id)
    if order is None:
        flash("Заказ не найден.")
        return redirect(url_for("admin"))

    order.status = new_status
    db.session.commit()
    flash("Статус заказа обновлён.")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)

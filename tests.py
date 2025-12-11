import unittest
from app import app, db, User, Role, Service, Order, OrderItem
from flask import session


class FewPhotosTestCase(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Создаём роли
            admin_role = Role(name="admin")
            client_role = Role(name="client")
            db.session.add_all([admin_role, client_role])
            db.session.commit()

            # Создаём пользователей
            admin = User(
                full_name="Админ",
                email="admin@test.com",
                phone="0000000000",
                role_id=admin_role.id
            )
            admin.set_password("adminpass")

            client = User(
                full_name="Клиент",
                email="client@test.com",
                phone="1111111111",
                role_id=client_role.id
            )
            client.set_password("12345")

            db.session.add_all([admin, client])

            # Создаём услуги
            s1 = Service(title="Услуга А", description="Тест A", price=1000, is_active=True)
            s2 = Service(title="Услуга Б", description="Тест B", price=2000, is_active=True)
            db.session.add_all([s1, s2])
            db.session.commit()

    def login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True
        )

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

    # ----------------------------------------------------
    # Тесты авторизации
    # ----------------------------------------------------

    def test_successful_login(self):
        response = self.login("client@test.com", "12345")
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)

    def test_failed_login(self):
        response = self.login("client@test.com", "WRONG")
        html = response.data.decode("utf-8").lower()
        self.assertIn("неверный логин", html)

    # ----------------------------------------------------
    # Тест регистрации
    # ----------------------------------------------------

    def test_register_new_user(self):
        response = self.client.post(
            "/register",
            data={
                "full_name": "Новый",
                "email": "new@test.com",
                "phone": "55555",
                "password": "qwerty1",
                "password_confirm": "qwerty1"
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            user = User.query.filter_by(email="new@test.com").first()
            self.assertIsNotNone(user)

    # ----------------------------------------------------
    # Каталог
    # ----------------------------------------------------

    def test_catalog_available(self):
        response = self.client.get("/catalog")
        self.assertEqual(response.status_code, 200)

    # ----------------------------------------------------
    # Корзина и добавление услуг
    # ----------------------------------------------------

    def test_add_to_cart_requires_login(self):
        response = self.client.get("/add_to_cart/1", follow_redirects=True)
        html = response.data.decode("utf-8").lower()
        self.assertIn("войдите", html)

    def test_add_to_cart_ok(self):
        self.login("client@test.com", "12345")
        response = self.client.get("/add_to_cart/1", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIn("cart", sess)
            self.assertGreater(len(sess["cart"]), 0)

    # ----------------------------------------------------
    # Оформление заказа
    # ----------------------------------------------------

    def test_checkout(self):
        self.login("client@test.com", "12345")
        self.client.get("/add_to_cart/1", follow_redirects=True)

        response = self.client.post("/checkout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            orders = Order.query.all()
            self.assertEqual(len(orders), 1)

    # ----------------------------------------------------
    # Админ-панель
    # ----------------------------------------------------

    def test_admin_restricted_for_client(self):
        self.login("client@test.com", "12345")
        response = self.client.get("/admin", follow_redirects=True)
        html = response.data.decode("utf-8").lower()
        self.assertIn("запрещ", html)

    def test_admin_access(self):
        self.login("admin@test.com", "adminpass")
        response = self.client.get("/admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_admin_change_order_status(self):
        # клиент создаёт заказ
        self.login("client@test.com", "12345")
        self.client.get("/add_to_cart/1", follow_redirects=True)
        self.client.post("/checkout", follow_redirects=True)
        self.logout()

        # админ меняет статус
        self.login("admin@test.com", "adminpass")

        with app.app_context():
            order = Order.query.first()

        response = self.client.post(
            f"/admin/order/{order.id}/set_status",
            data={"status": "completed"},
            follow_redirects=True
        )

        self.assertEqual(response.status_code, 200)

        with app.app_context():
            updated = Order.query.first()
            self.assertEqual(updated.status, "completed")

    # ----------------------------------------------------
    # Выход
    # ----------------------------------------------------

    def test_logout(self):
        self.login("client@test.com", "12345")
        self.logout()

        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)


if __name__ == "__main__":
    unittest.main()

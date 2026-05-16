import random
import string
import io
from locust import HttpUser, task, between


def random_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase, k=n))


# Минимальный валидный JPEG (для upload аватара)
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\xff\xd9"
)


class MessengerUser(HttpUser):
    """
    Сценарный класс — покрывает NFR с числовыми ограничениями (latency / размер).
    Запуск: locust -f Locustfile.py MessengerUser --headless -u 50 -r 5
    """
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    # ── setup ────────────────────────────────────────────────────────────────

    def on_start(self):
        self.token = None
        self.headers = {}
        self.my_id = None
        self.chat_id = None
        self.group_chat_id = None
        self.last_message_id = None
        self.other_user_id = None
        self.bot_token = None
        self.contact_added = False

        suffix = random_str()
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@test.com",
            "password": "testpass123",
            "display_name": f"User {suffix}",
        }, name="/api/v1/auth/register POST")
        if res.status_code != 201:
            return

        data = res.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        me = self.client.get("/api/v1/users/me", headers=self.headers)
        if me.status_code == 200:
            self.my_id = me.json()["id"]

        self._setup_direct_chat()
        self._setup_group_chat()

    def _register_bot(self):
        """Регистрирует вспомогательного пользователя, возвращает (id, token)."""
        suffix = random_str()
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"bot_{suffix}",
            "email": f"bot_{suffix}@test.com",
            "password": "testpass123",
        }, name="/api/v1/auth/register POST")
        if res.status_code != 201:
            return None, None
        bot_token = res.json()["access_token"]
        bot_headers = {"Authorization": f"Bearer {bot_token}"}
        me = self.client.get("/api/v1/users/me", headers=bot_headers)
        if me.status_code != 200:
            return None, None
        return me.json()["id"], bot_token

    def _setup_direct_chat(self):
        other_id, bot_token = self._register_bot()
        if not other_id:
            return
        self.other_user_id = other_id
        self.bot_token = bot_token

        res = self.client.post("/api/v1/chats/", json={
            "type": "direct",
            "member_ids": [other_id],
        }, headers=self.headers)
        if res.status_code == 201:
            self.chat_id = res.json()["id"]

    def _setup_group_chat(self):
        """Групповой чат с 9 ботами — граница лимита 10 участников (req 14)."""
        ids = []
        for _ in range(9):
            uid, _ = self._register_bot()
            if uid:
                ids.append(uid)
        if not ids:
            return
        res = self.client.post("/api/v1/chats/", json={
            "type": "group",
            "name": f"group_{random_str()}",
            "member_ids": ids,
        }, headers=self.headers)
        if res.status_code == 201:
            self.group_chat_id = res.json()["id"]

    # ── req 1: регистрация ≤3 сек, авторизация ≤500 мс ──────────────────────

    @task(1)
    def login(self):
        """Регистрируем + логинимся, меряем latency обоих шагов."""
        suffix = random_str()
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"tmp_{suffix}",
            "email": f"tmp_{suffix}@test.com",
            "password": "testpass123",
        }, name="/api/v1/auth/register POST")
        if reg.status_code != 201:
            return
        self.client.post("/api/v1/auth/login", json={
            "email": f"tmp_{suffix}@test.com",
            "password": "testpass123",
        }, name="/api/v1/auth/login POST")

    # ── req 2: аватар ≤5 МБ, форматы jpg/png ────────────────────────────────

    @task(1)
    def upload_avatar(self):
        """POST /users/me/avatar — валидный JPEG, проверяем latency и 200."""
        if not self.token:
            return
        self.client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("avatar.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
            headers=self.headers,
            name="/api/v1/users/me/avatar POST",
        )

    # ── req 2: профиль (get/update) ──────────────────────────────────────────

    @task(1)
    def get_me(self):
        if not self.token:
            return
        self.client.get("/api/v1/users/me", headers=self.headers)

    @task(1)
    def update_profile(self):
        if not self.token:
            return
        self.client.patch("/api/v1/users/me", json={
            "display_name": f"Name {random_str()}",
            "status_text": f"status {random_str()}",
        }, headers=self.headers, name="/api/v1/users/me PATCH")

    # ── req 3: поиск ≤300 мс ────────────────────────────────────────────────

    @task(2)
    def search_by_username(self):
        if not self.token:
            return
        self.client.get(
            f"/api/v1/users/search?username=user_{random_str()}",
            headers=self.headers,
            name="/api/v1/users/search GET",
        )

    # ── req 4: добавление контакта ≤500 мс ──────────────────────────────────

    @task(1)
    def add_contact(self):
        if not self.token or not self.other_user_id or self.contact_added:
            return
        res = self.client.post(
            f"/api/v1/contacts/{self.other_user_id}",
            headers=self.headers,
            name="/api/v1/contacts/[id] POST",
        )
        if res.status_code == 201:
            self.contact_added = True

    @task(1)
    def get_contacts(self):
        if not self.token:
            return
        self.client.get("/api/v1/contacts/", headers=self.headers)

    # ── req 5: онлайн-статус ≤2 сек ─────────────────────────────────────────

    @task(2)
    def check_online(self):
        """POST /users/online — реальный эндпоинт статусов."""
        if not self.token or not self.other_user_id:
            return
        self.client.post(
            "/api/v1/users/online",
            json=[self.other_user_id],
            headers=self.headers,
            name="/api/v1/users/online POST",
        )

    # ── req 7: отправка сообщения ≤300 мс ───────────────────────────────────

    @task(5)
    def send_message(self):
        if not self.chat_id or not self.token:
            return
        res = self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages",
            json={"content": f"hello {random_str()}", "type": "text"},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages POST",
        )
        if res.status_code == 201:
            self.last_message_id = res.json().get("id")

    # ── req 8: статус прочтения ≤1 сек ──────────────────────────────────────

    @task(2)
    def mark_message_read(self):
        """Читаем сообщение от лица бота-получателя."""
        if not self.chat_id or not self.last_message_id or not self.bot_token:
            return
        bot_headers = {"Authorization": f"Bearer {self.bot_token}"}
        self.client.post(
            f"/api/v1/chats/messages/{self.last_message_id}/read",
            headers=bot_headers,
            name="/api/v1/chats/[id]/messages/[id]/read POST",
        )

    # ── req 7/13: чтение сообщений ───────────────────────────────────────────

    @task(3)
    def get_messages(self):
        if not self.chat_id or not self.token:
            return
        self.client.get(
            f"/api/v1/chats/{self.chat_id}/messages",
            headers=self.headers,
            name="/api/v1/chats/[id]/messages GET",
        )

    # ── req 13: upload файла ≤50 МБ ─────────────────────────────────────────

    @task(1)
    def upload_attachment_small(self):
        """Типичный файл ~100 КБ — основная latency."""
        if not self.chat_id or not self.token:
            return
        self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages/upload",
            files={"file": ("test.bin", io.BytesIO(b"x" * 100 * 1024), "application/octet-stream")},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages/upload POST (100KB)",
        )

    @task(1)
    def upload_attachment_boundary(self):
        """Граничный файл ~49 МБ — проверка лимита 50 МБ (req 13)."""
        if not self.chat_id or not self.token:
            return
        self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages/upload",
            files={"file": ("big.bin", io.BytesIO(b"x" * 49 * 1024 * 1024), "application/octet-stream")},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages/upload POST (49MB)",
        )

    # ── req 14: групповой чат ────────────────────────────────────────────────

    @task(2)
    def send_group_message(self):
        if not self.group_chat_id or not self.token:
            return
        self.client.post(
            f"/api/v1/chats/{self.group_chat_id}/messages",
            json={"content": f"group msg {random_str()}", "type": "text"},
            headers=self.headers,
            name="/api/v1/chats/[group_id]/messages POST",
        )

    @task(2)
    def get_chats(self):
        if not self.token:
            return
        self.client.get("/api/v1/chats/", headers=self.headers)


# ── стресс-класс (горячие NFR-эндпоинты) ────────────────────────────────────

class StressUser(HttpUser):
    """
    Изолированный стресс на критичные NFR-эндпоинты:
      - отправка сообщений (req 7, ≤300 мс)
      - чтение сообщений (req 7, read-heavy)
      - поиск (req 3, ≤300 мс)
      - онлайн-статус (req 5, ≤2 сек)
    Запуск: locust -f Locustfile.py StressUser --headless -u 50 -r 5
    """
    wait_time = between(0.05, 0.2)
    host = "http://localhost:8000"

    def on_start(self):
        self.token = None
        self.headers = {}
        self.chat_id = None
        self.other_user_id = None

        suffix = random_str()
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"stress_{suffix}",
            "email": f"stress_{suffix}@test.com",
            "password": "testpass123",
            "display_name": f"Stress {suffix}",
        }, name="/api/v1/auth/register POST")
        if res.status_code != 201:
            return
        self.token = res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        suffix2 = random_str()
        res2 = self.client.post("/api/v1/auth/register", json={
            "username": f"sb_{suffix2}",
            "email": f"sb_{suffix2}@test.com",
            "password": "testpass123",
        }, name="/api/v1/auth/register POST")
        if res2.status_code != 201:
            return
        bot_token = res2.json()["access_token"]
        bot_headers = {"Authorization": f"Bearer {bot_token}"}
        me = self.client.get("/api/v1/users/me", headers=bot_headers)
        if me.status_code != 200:
            return
        self.other_user_id = me.json()["id"]

        chat = self.client.post("/api/v1/chats/", json={
            "type": "direct",
            "member_ids": [self.other_user_id],
        }, headers=self.headers)
        if chat.status_code == 201:
            self.chat_id = chat.json()["id"]

    @task(5)
    def send_message(self):
        if not self.chat_id:
            return
        self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages",
            json={"content": f"stress {random_str()}", "type": "text"},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages POST",
        )

    @task(3)
    def get_messages(self):
        if not self.chat_id:
            return
        self.client.get(
            f"/api/v1/chats/{self.chat_id}/messages",
            headers=self.headers,
            name="/api/v1/chats/[id]/messages GET",
        )

    @task(2)
    def search_user(self):
        if not self.token:
            return
        self.client.get(
            f"/api/v1/users/search?username=user_{random_str()}",
            headers=self.headers,
            name="/api/v1/users/search GET",
        )

    @task(2)
    def check_online(self):
        if not self.token or not self.other_user_id:
            return
        self.client.post(
            "/api/v1/users/online",
            json=[self.other_user_id],
            headers=self.headers,
            name="/api/v1/users/online POST",
        )

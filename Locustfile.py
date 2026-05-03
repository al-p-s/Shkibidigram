import random
import string
import io
from locust import HttpUser, task, between

BASE = "http://localhost:8000/api/v1"


def random_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase, k=n))


class MessengerUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    # ── setup ──

    def on_start(self):
        self.token = None
        self.headers = {}
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
        })
        if res.status_code != 201:
            return

        data = res.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self._setup_direct_chat()
        self._setup_group_chat()

    def _register_bot(self):
        """Регистрирует вспомогательного пользователя, возвращает (id, token)."""
        suffix = random_str()
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"bot_{suffix}",
            "email": f"bot_{suffix}@test.com",
            "password": "testpass123",
        })
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

        chat_res = self.client.post("/api/v1/chats/", json={
            "type": "direct",
            "member_ids": [other_id],
        }, headers=self.headers)
        if chat_res.status_code == 201:
            self.chat_id = chat_res.json()["id"]

    def _setup_group_chat(self):
        """Создаём групповой чат с двумя ботами."""
        ids = []
        for _ in range(2):
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

    # ── req 1: авторизация (≤500 мс) ────────────────────────────────────────

    @task(1)
    def login(self):
        """Измеряем latency входа отдельным task-ом."""
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

    # ── req 2: профиль ───────────────────────────────────────────────────────

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

    # ── req 3: поиск (≤300 мс) ──────────────────────────────────────────────

    @task(2)
    def search_by_username(self):
        if not self.token:
            return
        self.client.get(
            f"/api/v1/users/search?username=user_{random_str()}",
            headers=self.headers,
            name="/api/v1/users/search?username GET",
        )

    # ── req 4: контакты (≤500 мс) ───────────────────────────────────────────

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

    # ── req 5: онлайн-статус (≤2 сек, polling) ──────────────────────────────

    @task(2)
    def get_online_status(self):
        if not self.token or not self.other_user_id:
            return
        self.client.get(
            f"/api/v1/users/{self.other_user_id}/public",
            headers=self.headers,
            name="/api/v1/users/[id]/public GET",
        )

    # ── req 6: блокировка ────────────────────────────────────────────────────

    @task(1)
    def block_unblock_user(self):
        if not self.token or not self.other_user_id:
            return
        uid, _ = self._register_bot()
        if not uid:
            return
        self.client.post(
            f"/api/v1/contacts/blocked/{uid}",
            headers=self.headers,
            name="/api/v1/contacts/blocked/[id] POST",
        )
        self.client.delete(
            f"/api/v1/contacts/blocked/{uid}",
            headers=self.headers,
            name="/api/v1/contacts/blocked/[id] DELETE",
        )

    # ── req 7: отправка сообщений (≤300 мс) ─────────────────────────────────

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

    # ── req 8: статус доставки (≤1 сек) ─────────────────────────────────────

    @task(2)
    def mark_message_read(self):
        if not self.chat_id or not self.last_message_id or not self.bot_token:
            return
        # читаем сообщение от лица бота-получателя
        bot_headers = {"Authorization": f"Bearer {self.bot_token}"}
        self.client.post(
            f"/api/v1/chats/messages/{self.last_message_id}/read",
            headers=bot_headers,
            name="/api/v1/chats/[id]/messages/[id]/read POST",
        )

    # ── req 9: reply ─────────────────────────────────────────────────────────

    @task(2)
    def send_reply(self):
        if not self.chat_id or not self.last_message_id or not self.token:
            return
        self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages",
            json={
                "content": f"reply {random_str()}",
                "type": "text",
                "reply_to_id": self.last_message_id,
            },
            headers=self.headers,
            name="/api/v1/chats/[id]/messages POST (reply)",
        )

    # ── req 10: редактирование (доступно 24 ч) ───────────────────────────────

    @task(2)
    def edit_message(self):
        if not self.chat_id or not self.last_message_id or not self.token:
            return
        self.client.patch(
            f"/api/v1/chats/messages/{self.last_message_id}",
            json={"content": f"edited {random_str()}"},
            headers=self.headers,
            name="/api/v1/messages/[id] PATCH",
        )

    # ── req 11: удаление у всех ──────────────────────────────────────────────

    @task(1)
    def delete_message_for_all(self):
        if not self.chat_id or not self.token:
            return
        # создаём одноразовое сообщение и сразу удаляем
        res = self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages",
            json={"content": "to delete", "type": "text"},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages POST",
        )
        if res.status_code != 201:
            return
        msg_id = res.json().get("id")
        self.client.delete(
            f"/api/v1/chats/messages/{msg_id}/all",
            headers=self.headers,
            name="/api/v1/messages/[id]/all DELETE",
        )

    # ── req 12: удаление у себя ──────────────────────────────────────────────

    @task(1)
    def delete_message_for_me(self):
        if not self.chat_id or not self.token:
            return
        res = self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages",
            json={"content": "to delete me", "type": "text"},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages POST",
        )
        if res.status_code != 201:
            return
        msg_id = res.json().get("id")
        self.client.delete(
            f"/api/v1/chats/messages/{msg_id}/me",
            headers=self.headers,
            name="/api/v1/messages/[id]/me DELETE",
        )

    # ── req 13: медиа (≤50 МБ) ───────────────────────────────────────────────

    @task(1)
    def upload_attachment(self):
        """
        Загружаем синтетический файл ~100 КБ.
        Если у вас attachments идут через отдельный endpoint — поправьте URL.
        Если через multipart прямо в POST /messages — замените тело запроса.
        """
        if not self.chat_id or not self.token:
            return
        fake_file = io.BytesIO(b"x" * 100 * 1024)  # 100 КБ
        self.client.post(
            f"/api/v1/chats/{self.chat_id}/messages/upload",
            files={"file": ("test.bin", fake_file, "application/octet-stream")},
            headers=self.headers,
            name="/api/v1/chats/[id]/messages/upload POST",
        )

    # ── req 13: чтение (get messages) ────────────────────────────────────────

    @task(3)
    def get_messages(self):
        if not self.chat_id or not self.token:
            return
        self.client.get(
            f"/api/v1/chats/{self.chat_id}/messages",
            headers=self.headers,
            name="/api/v1/chats/[id]/messages GET",
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

    @task(1)
    def get_group_messages(self):
        if not self.group_chat_id or not self.token:
            return
        self.client.get(
            f"/api/v1/chats/{self.group_chat_id}/messages",
            headers=self.headers,
            name="/api/v1/chats/[group_id]/messages GET",
        )

    @task(2)
    def get_chats(self):
        if not self.token:
            return
        self.client.get("/api/v1/chats/", headers=self.headers)


# ── стресс-класс (без паузы, только горячие эндпоинты) ──────────────────────

class StressUser(HttpUser):
    """
    Изолированный стресс на критичные NFR-эндпоинты:
      - отправка сообщений (≤300 мс)
      - чтение сообщений (read-heavy)
      - поиск пользователей (≤300 мс)
    Запускать отдельно: locust -f locustfile.py StressUser --headless -u 500 -r 50
    """
    wait_time = between(0.05, 0.2)
    host = "http://localhost:8000"

    def on_start(self):
        self.token = None
        self.headers = {}
        self.chat_id = None
        self.contact_added = False

        suffix = random_str()
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"stress_{suffix}",
            "email": f"stress_{suffix}@test.com",
            "password": "testpass123",
            "display_name": f"Stress {suffix}",
        })
        if res.status_code != 201:
            return
        self.token = res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # второй юзер для чата
        suffix2 = random_str()
        res2 = self.client.post("/api/v1/auth/register", json={
            "username": f"sb_{suffix2}",
            "email": f"sb_{suffix2}@test.com",
            "password": "testpass123",
        })
        if res2.status_code != 201:
            return
        bot_token = res2.json()["access_token"]
        bot_headers = {"Authorization": f"Bearer {bot_token}"}
        me = self.client.get("/api/v1/users/me", headers=bot_headers)
        if me.status_code != 200:
            return
        other_id = me.json()["id"]

        chat = self.client.post("/api/v1/chats/", json={
            "type": "direct",
            "member_ids": [other_id],
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
            name="/api/v1/users/search?username GET",
        )

# Shkibidigram

Мессенджер. FastAPI + PostgreSQL + Redis + MinIO.

## Требования

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)
- Python 3.12 (для генерации миграций локально)

## Быстрый старт (Quick fuck)

```bash
# 1. Клонировать
# через UI в PyCharm, умоляю

# 2. Создать .env (шаблон тут же, ниже)
# Отредактировать .env под себя

# 3. Установить некий Make, добавить его в PATH
winget install GnuWin32.Make
echo 'export PATH=$PATH:"/c/Program Files (x86)/GnuWin32/bin"' >> ~/.bashrc
source ~/.bashrc

# Проверь, брашки
make --version

# 4. Поднять контейнеры
docker compose up -d

# 5. Накатить миграции
make migrate
```

Апп доступен на `http://localhost:8000`.

## Команды

| Команда | Что делает |
|---|---|
| `docker compose up -d` | Поднять все сервисы |
| `docker compose down` | Остановить |
| `make migrate` | Накатить миграции |
| `make makemigrations msg="..."` | Создать миграцию |

## Сервисы

| Сервис | Порт |
|---|---|
| App (FastAPI) | 8000 |
| PostgreSQL | 5433 |
| Redis | 6379 |
| MinIO | 9000 / 9001 (консоль) |

## Миграции

Если менял модели — генери локально и пушь:

```bash
# Установить зависимости локально (один раз)
pip install -r requirements.txt

# В .env временно поменять DATABASE_URL на localhost:5433
# Потом:
alembic revision --autogenerate -m "ОПИСАТЬ ЧЕ ИЗМЕНИЛ"

# Вернуть DATABASE_URL обратно на db:5432
# Запушить, сообщить нам, мы делаем make migrate (вообще лучше всегда после pull делать make migrate)
```
## .env
 
Возьми эту структуру и заполни строки со словом 'YOUR':
 
```env
# App
APP_SECRET_KEY=YOUR_random_secret_32_chars
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
 
# PostgreSQL
POSTGRES_USER=YOUR_user
POSTGRES_PASSWORD=YOUR_password
POSTGRES_DB=shkibidigram
DATABASE_URL=postgresql+asyncpg://YOUR_user:YOUR_password@db:5432/shkibidigram
 
# Redis
REDIS_URL=redis://redis:6379/0
 
# MinIO
MINIO_ROOT_USER=YOUR_minio_user
MINIO_ROOT_PASSWORD=YOUR_minio_password
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET_MEDIA=media
MINIO_BUCKET_AVATARS=avatars
 
# JWT
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```
 
> `APP_SECRET_KEY` — любая случайная строка 32+ символа.

## Структура

```
app/
├── core/          # db, redis, security, storage, websocket
├── features/      # фичи: auth, users, chats, messages, calls, contacts
└── main.py
```
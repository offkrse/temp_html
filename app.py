from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
import pathlib, json, os
from dotenv import load_dotenv

# === Загрузка .env ===
load_dotenv("/opt/vk_checker/.env")

# === Пути и настройки ===
APP_DIR = pathlib.Path("/opt/vk_checker/webapp")
USER_DIR = pathlib.Path("/opt/vk_checker/data/users")
USER_DIR.mkdir(parents=True, exist_ok=True)

# === Инициализация FastAPI ===
app = FastAPI(title="VK Checker Mini App")
templates = Environment(loader=FileSystemLoader(str(APP_DIR / "templates")))
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


# === Вспомогательные функции ===
def get_user_path(uid: str) -> pathlib.Path:
    return USER_DIR / f"{uid}.json"

def load_user(uid: str) -> dict | None:
    p = get_user_path(uid)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None

def save_user(user: dict):
    p = get_user_path(str(user["telegram_id"]))
    p.write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")


# === Маршруты ===

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)   # 👈 добавили alias
async def index(request: Request):
    """Главная страница mini app"""
    return templates.get_template("index.html").render(title="VK Checker")


@app.post("/api/login")
async def login(request: Request):
    """Авторизация пользователя по данным Telegram WebApp"""
    data = await request.json()
    uid = str(data.get("telegram_id"))
    name = data.get("name", "User")

    if not uid or not uid.isdigit():
        raise HTTPException(400, "Некорректный Telegram ID")

    user = load_user(uid)
    if not user:
        user = {
            "telegram_id": int(uid),
            "name": name,
            "chat_id": uid,
            "cabinets": []
        }
        save_user(user)
    else:
        user["name"] = name
        save_user(user)

    return {"ok": True, "message": f"Добро пожаловать, {name}!", "user": user}


@app.get("/api/user/{telegram_id}")
async def get_user_data(telegram_id: int):
    """Возвращает данные пользователя"""
    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return user


@app.post("/api/toggle/{cabinet_id}")
async def toggle_cabinet(cabinet_id: int, request: Request):
    """Переключает статус кабинета (активен / выключен)"""
    data = await request.json()
    uid = str(data.get("telegram_id"))
    user = load_user(uid)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for c in user["cabinets"]:
        if c["id"] == cabinet_id:
            c["active"] = not c.get("active", True)
            save_user(user)
            return {"message": f"Статус: {'🟢 Активен' if c['active'] else '🔴 Отключен'}"}
    return {"message": "Кабинет не найден"}

@app.get("/api/cabinet/{telegram_id}/{cabinet_id}")
async def get_cabinet(telegram_id: int, cabinet_id: int):
    """Возвращает данные по одному кабинету"""
    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for cab in user["cabinets"]:
        if cab["id"] == cabinet_id:
            return cab
    raise HTTPException(404, "Кабинет не найден")


@app.get("/api/cabinet_campaigns/{telegram_id}/{cabinet_id}")
async def get_campaigns(telegram_id: int, cabinet_id: int):
    """Возвращает список кампаний кабинета"""
    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for cab in user["cabinets"]:
        if cab["id"] == cabinet_id:
            path = cab.get("allowed_campaigns_file")
            if not path or not os.path.exists(path):
                return {"campaigns": []}
            with open(path, "r", encoding="utf-8") as f:
                campaigns = [line.strip() for line in f if line.strip()]
            return {"campaigns": campaigns}

    raise HTTPException(404, "Кабинет не найден")

@app.post("/api/update_filter/{telegram_id}/{cabinet_id}")
async def update_filter(telegram_id: int, cabinet_id: int, request: Request):
    """Обновление фильтра для кабинета"""
    data = await request.json()
    new_filter = data.get("filter")

    if not isinstance(new_filter, dict):
        raise HTTPException(400, "Некорректный формат фильтра")

    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for cab in user["cabinets"]:
        if cab["id"] == cabinet_id:
            cab["filter"].update(new_filter)
            save_user(user)
            return {"ok": True, "message": "Фильтр успешно обновлён"}

    raise HTTPException(404, "Кабинет не найден")


@app.post("/api/add_campaigns/{telegram_id}/{cabinet_id}")
async def add_campaigns(telegram_id: int, cabinet_id: int, request: Request):
    """Добавляет новые кампании в allowed_campaigns_file без дубликатов"""
    data = await request.json()
    new_campaigns = data.get("campaigns", [])

    if not new_campaigns or not isinstance(new_campaigns, list):
        raise HTTPException(400, "Некорректные данные")

    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for cab in user["cabinets"]:
        if cab["id"] == cabinet_id:
            path = cab.get("allowed_campaigns_file")
            if not path:
                raise HTTPException(400, "Не задан путь к файлу кампаний")

            # Читаем существующие кампании (если файл есть)
            existing = set()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = {line.strip() for line in f if line.strip()}

            # Добавляем только уникальные
            new_unique = [c for c in new_campaigns if c not in existing]

            if not new_unique:
                return {"ok": True, "message": "Все кампании уже есть в списке."}

            # Записываем новые
            with open(path, "a", encoding="utf-8") as f:
                for c in new_unique:
                    f.write(f"{c}\n")

            return {"ok": True, "message": f"Компании добавлены"}

    raise HTTPException(404, "Кабинет не найден")


@app.get("/cabinet/{cabinet_id}", response_class=HTMLResponse)
async def cabinet_settings(request: Request, cabinet_id: int):
    """Страница настроек конкретного кабинета"""
    template = templates.get_template("cabinet.html")
    return template.render(title="Настройки кабинета", cabinet_id=cabinet_id)


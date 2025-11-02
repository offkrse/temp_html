from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
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

@app.get("/cabinet/{cabinet_id}", response_class=HTMLResponse)
async def cabinet_settings(request: Request, cabinet_id: int):
    """Страница настроек конкретного кабинета"""
    template = templates.get_template("cabinet.html")
    return template.render(title="Настройки кабинета", cabinet_id=cabinet_id)


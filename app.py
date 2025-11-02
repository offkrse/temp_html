from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
import pathlib, json, os
from dotenv import load_dotenv

# === Настройки ===
load_dotenv("/opt/vk_checker/.env")

APP_DIR = pathlib.Path("/opt/vk_checker/webapp")
USER_DIR = pathlib.Path("/opt/vk_checker/data/users")
USER_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="VK Checker Mini App")
templates = Environment(loader=FileSystemLoader(str(APP_DIR / "templates")))

# Подключаем статику
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


# === Основные маршруты ===

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse("<h3>VK Checker Mini App работает ✅</h3>")

@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница мини-приложения"""
    return templates.get_template("index.html").render(title="VK Checker")

@app.post("/dashboard/api/login")
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
            "cabinets": [
                {"id": 1, "name": "MAIN", "active": False},
            ]
        ]
        save_user(user)
    else:
        user["name"] = name
        save_user(user)

    return {"ok": True, "message": f"Добро пожаловать, {name}!", "user": user}

@app.get("/dashboard/api/user/{telegram_id}")
async def get_user_data(telegram_id: int):
    """Возвращает данные пользователя"""
    user = load_user(str(telegram_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return user

@app.post("/dashboard/api/toggle/{cabinet_id}")
async def toggle_cabinet(cabinet_id: int, request: Request):
    """Переключает статус кабинета"""
    data = await request.json()
    uid = str(data.get("telegram_id"))
    user = load_user(uid)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    for c in user["cabinets"]:
        if c["id"] == cabinet_id:
            c["active"] = not c.get("active", False)
            save_user(user)
            return {"message": f"Статус: {'🟢 Включён' if c['active'] else '🔴 Отключён'}"}
    return {"message": "Кабинет не найден"}

@app.get("/dashboard/cabinet/{cabinet_id}", response_class=HTMLResponse)
async def cabinet_page(request: Request, cabinet_id: int):
    """Страница одного кабинета"""
    telegram_id = request.query_params.get("uid")
    if not telegram_id:
        return HTMLResponse("Ошибка: не указан uid", status_code=400)

    user = load_user(telegram_id)
    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)

    cab = next((c for c in user["cabinets"] if c["id"] == cabinet_id), None)
    if not cab:
        return HTMLResponse("Кабинет не найден", status_code=404)

    return templates.get_template("cabinet.html").render(title=cab["name"], cabinet=cab, user=user)

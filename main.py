# main.py
import os
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from starlette.staticfiles import StaticFiles
from typing import Dict, Optional

# --- CONFIG from env ---
APP_USER = os.environ.get("WEB_USER", "admin")
APP_PASS = os.environ.get("WEB_PASS", "changeme")
SECRET = os.environ.get("SECRET_KEY", "please-change-this")
COOKIE_NAME = "session"

DEVICES = ["esp1", "esp2"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
serializer = URLSafeTimedSerializer(SECRET, salt="session-salt")

# mount static folder (if you put index.html in ./static)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# per-device ephemeral storage (in-memory)
last_command: Dict[str, Optional[str]] = {d: None for d in DEVICES}
last_status: Dict[str, Dict] = {d: {"io": {}, "led": {}, "last_seen": None} for d in DEVICES}


# ---- helpers ----
def create_token(username: str):
    return serializer.dumps({"user": username, "time": datetime.utcnow().isoformat()})

def verify_token(token: str):
    try:
        data = serializer.loads(token, max_age=86400)  # 24h validity for cookie check
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None

def get_current_user(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    username = verify_token(cookie)
    if username != APP_USER:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return username


# ---- auth / ui endpoints ----
@app.get("/login", response_class=HTMLResponse)
def login_page():
    # keep simple login page (served from code)
    return HTMLResponse("""
    <html><head><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#f3f4f6}
    .box{background:#fff;padding:32px;border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,0.08);width:320px;text-align:center}
    input{width:90%;padding:10px;margin:8px 0;border-radius:8px;border:1px solid #ccc}
    button{width:95%;padding:10px;border-radius:8px;border:none;background:#007BFF;color:#fff;cursor:pointer}
    </style></head><body>
    <div class="box">
      <h3>Đăng nhập</h3>
      <form method="post" action="/login">
        <input name="username" placeholder="Tên đăng nhập" required /><br/>
        <input name="password" type="password" placeholder="Mật khẩu" required /><br/>
        <button type="submit">Đăng nhập</button>
      </form>
    </div>
    </body></html>
    """)

@app.post("/login")
def do_login(response: Response, username: str = Form(...), password: str = Form(...)):
    if username == APP_USER and password == APP_PASS:
        token = create_token(username)
        res = RedirectResponse(url="/", status_code=303)
        res.set_cookie(COOKIE_NAME, token, httponly=True, max_age=86400, samesite="Lax")
        return res
    return HTMLResponse("<h3>Login failed</h3><a href='/login'>Try again</a>", status_code=401)

@app.get("/logout")
def logout(response: Response):
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie(COOKIE_NAME)
    return res

# Serve index.html as a separate file (keeps 2-file structure).
# Put index.html at repo root or in ./static/index.html and adjust path below.
INDEX_PATH = "index.html"
if not os.path.isfile(INDEX_PATH) and os.path.isfile("static/index.html"):
    INDEX_PATH = "static/index.html"

@app.get("/", response_class=HTMLResponse)
def home(user: str = Depends(get_current_user)):
    # return static index.html file
    return FileResponse(INDEX_PATH, media_type="text/html")


# ---- web UI actions -> set per-device command ----
@app.post("/action/{device}/{cmd}")
def control(device: str, cmd: str, user: str = Depends(get_current_user)):
    if device not in DEVICES:
        raise HTTPException(status_code=404, detail="Unknown device")
    last_command[device] = cmd
    print(f"[WEB] User {user} set command for {device}: {cmd}")
    return {"status": "ok", "cmd": cmd}


# ---- ESP endpoints ----
# ESP polls: GET /esp/get_cmd/{device}  -> returns {"command":"..."} and clears it (one-time)
@app.get("/esp/get_cmd/{device}")
def esp_get_cmd(device: str):
    if device not in DEVICES:
        return JSONResponse({"command": ""})
    cmd = last_command.get(device)
    last_command[device] = None
    return {"command": cmd or ""}

# ESP posts status: POST /esp/status  (json)
# Expected payload examples:
# esp1: {"device":"esp1","io":{"door": "open", ...}}
# esp2: {"device":"esp2","io":{"dev1":1,"dev2":0,"t1":9,"t2":0}}
@app.post("/esp/status")
async def esp_status(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "err": "invalid json"}
    device = payload.get("device")
    if not device or device not in DEVICES:
        return {"ok": False, "err": "unknown device"}
    last_status[device] = {
        "io": payload.get("io", {}),
        "led": payload.get("led", {}),
        "last_seen": datetime.utcnow().isoformat(timespec="seconds")
    }
    return {"ok": True}

# Web UI can query latest status:
@app.get("/status/{device}")
def get_status(device: str):
    s = last_status.get(device) or {"io": {}, "led": {}, "last_seen": None}
    online = False
    if s.get("last_seen"):
        try:
            t = datetime.fromisoformat(s["last_seen"])
            online = (datetime.utcnow() - t) < timedelta(seconds=15)
        except Exception:

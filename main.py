import os
import json
from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeSerializer

# --- config ---
APP_USER = os.environ.get("WEB_USER", "admin")
APP_PASS = os.environ.get("WEB_PASS", "changeme")
SECRET = os.environ.get("SECRET_KEY", "please-change-this")
COOKIE_NAME = "session"

serializer = URLSafeSerializer(SECRET, salt="session-salt")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# in-memory last command (simple)
last_command = None

def get_current_user(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        data = serializer.loads(cookie)
        username = data.get("user")
        if username != APP_USER:
            raise HTTPException(status_code=401, detail="Invalid user")
        return username
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse("""
    <html><body style="font-family:sans-serif">
      <h3>Đăng nhập</h3>
      <form method="post" action="/login">
        <input name="username" placeholder="username"/><br/><br/>
        <input name="password" type="password" placeholder="password"/><br/><br/>
        <button type="submit">Đăng nhập</button>
      </form>
    </body></html>
    """)

@app.post("/login")
def do_login(response: Response, username: str = Form(...), password: str = Form(...)):
    if username == APP_USER and password == APP_PASS:
        token = serializer.dumps({"user": username})
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(COOKIE_NAME, token, httponly=True, secure=True, samesite="Lax")
        return response
    return HTMLResponse("<h3>Login failed</h3><a href='/login'>Try again</a>", status_code=401)

@app.get("/", response_class=HTMLResponse)
def home(user: str = Depends(get_current_user)):
    # serve index.html file if exists, else simple UI
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return HTMLResponse(f"<h3>Welcome {user}</h3><p>UI not found</p>")

@app.post("/action/{cmd}")
def control(cmd: str, user: str = Depends(get_current_user)):
    global last_command
    last_command = cmd
    print(f"[WEB] User {user} sent command: {cmd}")
    return {"status":"ok","cmd":cmd}

@app.get("/get_cmd")
def get_cmd():
    # ESP can poll this without auth (or you can protect it if needed)
    global last_command
    cmd = last_command
    last_command = None
    return {"command": cmd or ""}

# optional logout
@app.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response

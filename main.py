import os
import json
from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeSerializer
from fastapi.responses import RedirectResponse

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
        return RedirectResponse(url="/login", status_code=303)
    try:
        data = serializer.loads(cookie)
        username = data.get("user")
        if username != APP_USER:
            return RedirectResponse(url="/login", status_code=303)
        return username
    except Exception:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse("""
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {
          font-family: sans-serif;
          display: flex;
          justify-content: center;
          align-items: center;
          height: 100vh;
          background: #f3f4f6;
        }
        .login-box {
          background: white;
          padding: 40px 50px;
          border-radius: 15px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.1);
          text-align: center;
          width: 90%;
          max-width: 400px;
        }
        input {
          width: 90%;
          padding: 12px;
          margin: 10px 0;
          border: 1px solid #ccc;
          border-radius: 8px;
          font-size: 16px;
        }
        button {
          width: 95%;
          padding: 12px;
          background-color: #007BFF;
          border: none;
          color: white;
          font-size: 18px;
          border-radius: 8px;
          cursor: pointer;
        }
        button:hover {
          background-color: #0056b3;
        }
      </style>
    </head>
    <body>
      <div class="login-box">
        <h2>Đăng nhập</h2>
        <form method="post" action="/login">
          <input name="username" placeholder="Tên đăng nhập" required/><br/>
          <input name="password" type="password" placeholder="Mật khẩu" required/><br/>
          <button type="submit">Đăng nhập</button>
        </form>
      </div>
    </body>
    </html>
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

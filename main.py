import os
import json
from datetime import timedelta, datetime
from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# --- CONFIG ---
APP_USER = os.environ.get("WEB_USER", "admin")
APP_PASS = os.environ.get("WEB_PASS", "changeme")
SECRET = os.environ.get("SECRET_KEY", "please-change-this")
COOKIE_NAME = "session"

# --- Init App ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
serializer = URLSafeTimedSerializer(SECRET, salt="session-salt")
last_command = None


# --- Helpers ---
def create_token(username: str):
    return serializer.dumps({"user": username, "time": datetime.utcnow().isoformat()})


def verify_token(token: str):
    try:
        data = serializer.loads(token, max_age=86400)  # 24h timeout
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None


# --- Dependencies ---
def get_current_user(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    username = verify_token(cookie)
    if username != APP_USER:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return username


# --- Routes ---
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
        token = create_token(username)
        res = RedirectResponse(url="/", status_code=303)
        res.set_cookie(COOKIE_NAME, token, httponly=True, max_age=86400, samesite="Lax")
        return res
    return HTMLResponse("<h3>Login failed</h3><a href='/login'>Try again</a>", status_code=401)


@app.get("/", response_class=HTMLResponse)
def home(user: str = Depends(get_current_user)):
    return HTMLResponse(f"""
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{
          font-family: sans-serif;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          background: #e8eef2;
        }}
        h2 {{
          margin-bottom: 40px;
        }}
        button {{
          width: 200px;
          padding: 20px;
          margin: 15px;
          font-size: 22px;
          border: none;
          border-radius: 10px;
          cursor: pointer;
          color: white;
          transition: 0.2s;
        }}
        .open {{ background: #28a745; }}
        .stop {{ background: #ffc107; color: black; }}
        .close {{ background: #dc3545; }}
        button:hover {{ opacity: 0.85; }}
      </style>
    </head>
    <body>
      <h2>Điều khiển I/O</h2>
      <button class="open" onclick="sendCmd('open')">Mở</button>
      <button class="stop" onclick="sendCmd('stop')">Dừng</button>
      <button class="close" onclick="sendCmd('close')">Đóng</button>

      <script>
        async function sendCmd(cmd) {{
          await fetch('/action/' + cmd, {{ method: 'POST' }});
          alert('Đã gửi lệnh: ' + cmd);
        }}
      </script>
    </body>
    </html>
    """)


@app.post("/action/{cmd}")
def control(cmd: str, user: str = Depends(get_current_user)):
    global last_command
    last_command = cmd
    print(f"[WEB] User {user} sent command: {cmd}")
    return {"status": "ok", "cmd": cmd}


@app.get("/get_cmd")
def get_cmd():
    global last_command
    cmd = last_command
    last_command = None
    return {"command": cmd or ""}


@app.get("/logout")
def logout(response: Response):
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie(COOKIE_NAME)
    return res

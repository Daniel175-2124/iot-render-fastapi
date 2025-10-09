from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json, os

app = FastAPI(title="ESP8266 IoT Relay")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = "state.json"
API_KEY = os.getenv("API_KEY", "")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"led": False}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

@app.on_event("startup")
async def startup():
    if not os.path.exists(STATE_FILE):
        save_state({"led": False})

def check_api_key(req: Request):
    if API_KEY:
        key = req.headers.get("x-api-key") or req.headers.get("authorization")
        if not key or key != API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/", response_class=HTMLResponse)
async def index():
    html = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ESP8266 I/O Control</title>
</head>
<body style="font-family:Arial;text-align:center;padding:20px">
  <h2>ESP8266 I/O Control</h2>
  <div>
    <p>LED trạng thái: <span id="state">?</span></p>
    <button onclick="setState(true)" style="padding:10px 20px;margin:5px">Bật</button>
    <button onclick="setState(false)" style="padding:10px 20px;margin:5px">Tắt</button>
  </div>
  <script>
    async function loadState(){
      const res = await fetch('/api/state');
      const j = await res.json();
      document.getElementById('state').innerText = j.led ? 'ON' : 'OFF';
    }
    async function setState(val){
      await fetch('/api/state', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({led: !!val})
      });
      await loadState();
    }
    loadState();
    setInterval(loadState, 5000);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/api/state")
async def get_state():
    return load_state()

@app.post("/api/state")
async def set_state(request: Request):
    check_api_key(request)
    payload = await request.json()
    state = load_state()
    if "led" in payload:
        state["led"] = bool(payload["led"])
    save_state(state)
    return state

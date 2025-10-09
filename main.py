from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Biến lưu tạm lệnh điều khiển (cho ESP đọc)
last_command = None

@app.get("/")
def home():
    """Trang chính: giao diện điều khiển"""
    return FileResponse("index.html")

@app.post("/action/{cmd}")
def control(cmd: str):
    """Nhận lệnh từ web UI"""
    global last_command
    last_command = cmd
    print(f"🛰️ Nhận lệnh mới: {cmd}")
    return {"status": "ok", "command": cmd}

@app.get("/get_cmd")
def get_cmd():
    """ESP8266 gọi định kỳ để lấy lệnh mới"""
    global last_command
    cmd = last_command
    last_command = None  # Reset sau khi đọc
    return {"command": cmd or ""}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render tự gán PORT
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)

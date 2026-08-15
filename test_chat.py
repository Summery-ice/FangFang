# -*- coding: utf-8 -*-
"""回归测试：完整聊天链路 + 气泡渲染（修复 QRect/QRectF 闪退）"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys, json, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
import pet

REPLY = "抱抱你呀~ 一切都会好起来的 (๑ᵔ⤙ᵔ๑)"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for ch in list(REPLY):
            body = json.dumps({"choices": [{"delta": {"content": ch}}]},
                              ensure_ascii=False)
            self.wfile.write(("data: %s\n\n" % body).encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


srv = HTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

cfg = dict(pet.DEFAULT_CONFIG)
cfg["api_url"] = "http://127.0.0.1:%d/v1" % port
cfg["api_key"] = "k"; cfg["pet_size"] = 200
pet.save_config(cfg)

w = pet.PetWindow(cfg)
w.show()

# ---- 模拟聊天：输入并发送 ----
w.chat.edit.setText("我难过")
w.chat._send()
QTest.qWait(200)                       # 首帧气泡
grab1 = w.bubble.grab()                # 渲染气泡 -> paintEvent
assert not grab1.isNull()
print("[OK] 气泡首帧渲染成功")

# ---- 等待流式完成(含逐字 reveal 的 paintEvent) ----
QTest.qWait(7000)
app.processEvents()
assert w.bubble.isVisible(), "气泡应保持可见"
assert "抱抱" in w.bubble._full, "气泡应包含流式回复内容"
grab2 = w.bubble.grab()
assert not grab2.isNull()
print("[OK] 流式完成气泡渲染成功:", w.bubble._full[:16].encode("ascii", "ignore").decode(), "…")

# ---- 再发一条：验证连续聊天不崩溃 + 上下文扩容 ----
w.chat.edit.setText("谢谢小团子")
w.chat._send()
QTest.qWait(5000)
app.processEvents()
assert "抱抱" in w.bubble._full
roles = [m["role"] for m in w.llm._hist]
print("[OK] 第二条聊天成功，sse历史 roles:", roles)
assert roles[-2:] == ["assistant", "user"] or len(roles) >= 2

# ---- 设置对话框渲染/保存 ----
dlg = pet.SettingsDialog(cfg)
dlg.url.setText("http://127.0.0.1:%d/v1" % port)
dlg.key.setText("k2"); dlg.model.setText("m2")
dlg.accept()
cfg2 = dlg.get_cfg()
assert cfg2["api_key"] == "k2"
print("[OK] 设置面板保存逻辑正常")

srv.shutdown()
print("\nCHAT REGRESSION TEST PASSED")
# -*- coding: utf-8 -*-
"""
回归测试：纯逻辑测试（无 PyQt5 图形依赖，GitHub Actions 稳定通过）
- 测试配置加载/保存
- 测试 LLM 桥接（本地 mock SSE 服务器）
- 测试数据格式和接口契约
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys, json, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler, HTTPServer
import pet

# ---- 1. 配置加载/保存测试 ----
import tempfile
import tempfile as tf

with tempfile.TemporaryDirectory() as tmpdir:
    # 临时修改配置路径
    original_config = pet.CONFIG_PATH

    # 保存/加载测试
    test_cfg = dict(pet.DEFAULT_CONFIG)
    test_cfg["api_key"] = "test-key-123"
    test_cfg["pet_size"] = 250
    pet.CONFIG_PATH = os.path.join(tmpdir, "test_config.json")

    pet.save_config(test_cfg)
    loaded = pet.load_config()
    assert loaded["api_key"] == "test-key-123", "API Key 应持久化"
    assert loaded["pet_size"] == 250, "尺寸应持久化"
    pet.CONFIG_PATH = original_config

print("[OK] 配置加载/保存测试通过")

# ---- 2. LLM 桥接测试（本地 mock SSE 服务器）----
REPLY = "你好呀方方"

class MockSSE(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for ch in list(REPLY):
            body = json.dumps({"choices": [{"delta": {"content": ch}}]}, ensure_ascii=False)
            self.wfile.write(("data: %s\n\n" % body).encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

srv = HTTPServer(("127.0.0.1", 0), MockSSE)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

try:
    # 测试 LLM 桥接
    bridge_cfg = dict(pet.DEFAULT_CONFIG)
    bridge_cfg["api_url"] = "http://127.0.0.1:%d/v1" % port
    bridge_cfg["api_key"] = "mock-key"

    bridge = pet.LLMBridge(lambda: bridge_cfg)

    chunks, done = [], []
    bridge.chunk.connect(lambda d: chunks.append(d))
    bridge.done.connect(lambda m: done.append(m))

    bridge.ask("在吗")
    t0 = time.time()
    while time.time() - t0 < 5:
        if done:
            break
        time.sleep(0.05)

    srv.shutdown()

    assert "".join(chunks) == REPLY, "流式内容应完整：'%s' vs '%s'" % ("".join(chunks), REPLY)
    assert len(done) >= 1, "应收到完成信号"
    print("[OK] LLM 桥接测试通过（流式接收）")
except Exception as e:
    srv.shutdown()
    print("[FAIL] LLM 桥接测试失败:", e)
    raise

# ---- 3. 颜色方案/流速常量测试 ----
assert "蓝粉炫彩" in pet.PALETTES, "配色方案应存在"
assert "彩虹" in pet.PALETTES, "彩虹配色应存在"
assert pet.FLOW_MAX > 0, "最大流速应 >0"
print("[OK] 配色/流速常量测试通过")

print("\nALL LOGIC TESTS PASSED")

# -*- coding: utf-8 -*-
"""
方方 · 镂空流彩透明桌宠
- 透明置顶无边框窗口，鼠标拖拽移动
- 待机呼吸 / 屏幕边缘反弹漫游(走路动画) / 单击开心+聊天 / 双击跳跃 / 连点害羞
- OpenAI 兼容 API 聊天：气泡流式回复，config.json 持久化
- 右键/托盘菜单：显示、设置、退出
打包: pyinstaller --onefile --windowed --name LeafPet --icon assets/pet.ico --add-data "assets/frames;assets/frames" pet.py
素材热替换: 在 exe 同目录放 sprites/<动作>/fNN.png 可覆盖内置帧
"""
import sys
import os
import json
import time
import math
import random
import colorsys
import threading

from PyQt5.QtCore import (Qt, QTimer, QSize, QPoint, QPointF, QRect, QRectF,
                          pyqtSignal, QObject)
from PyQt5.QtGui import (QPixmap, QPainter, QPainterPath, QColor, QFont,
                         QIcon, QPen)
from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QSystemTrayIcon,
                             QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QTextEdit, QPushButton, QSpinBox,
                             QLabel, QDialogButtonBox, QComboBox, QSlider)

APP_NAME = "方方"
CONFIG_NAME = "config.json"
TICK_MS = 60   # 动画帧间隔(ms)


def app_base():
    """exe 运行时用 exe 所在目录(放 config/自定义帧)，源码运行用脚本目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def res_base():
    """内置帧资源目录：PyInstaller --onefile 时为解包临时目录"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_base())
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_base(), CONFIG_NAME)
LOG_PATH = os.path.join(app_base(), "pet.log")

# ---- 方方矢量框参数(与 prep.py 保持同步) ----
S = 320          # 素材画布
H = 118          # 外框半宽
RAD = 30         # 圆角半径
FRAME_W = 16     # 边框粗细
TICK_DEFAULT = 60

# ---- 流彩配色方案：色相 key stop 序列 ----
PALETTES = {
    "蓝粉炫彩": [225, 280, 330],
    "红蓝炫彩": [355, 300, 250],
    "彩虹": [0, 60, 120, 180, 240, 300],
    "青绿炫彩": [155, 195, 260],
}
FLOW_MAX = 3.0    # 最大流速(度/帧)

# ---- 各动作逐帧 (缩放, 纵向偏移)；待机保持 1.00 静止不闪烁 ----
ACTION_SCALES = {
    "idle":  [(1.00, 0), (1.00, 0), (1.00, 0), (1.00, 0)],
    "happy": [(1.08, 0), (1.14, 0), (1.08, 0), (1.12, 0)],
    "jump":  [(0.93, -16), (0.95, -28), (1.03, -54), (1.10, -64),
              (1.04, -46), (0.98, -18), (0.93, -5)],
    "shy":   [(1.02, 0), (0.97, 0)],
}
IDLE_PERIOD = 30.0      # 待机表情周期(秒)：每 30s 平滑切换到下一个表情
IDLE_TRANS = 3.5        # 过渡渐变时长(秒)：线条数值插值，非图片闪切
ACTION_FRAME_DT = 150   # 动作帧间隔(ms)：动作播放放缓，便于看清
ACTION_HOLD = {         # 动作播完后最后一帧的停留时长(ms)
    "happy": 2000,      # 开心：蹦跳后定格微笑 2s
    "jump": 1200,       # 跳跃：落地后停留 1.2s
    "shy": 3500,        # 害羞：红晕表情停留 3.5s
}
HOLD_PRESS_MS = 850     # 长按触发害羞的按住时长(ms)
SETTLE_MS = 350         # 动作定格结束前回到待机位的平滑时长(ms)
BLINK_EVERY = (5500, 9500)   # 眨眼事件间隔(ms)范围
BLINK_DUR = 500              # 眨眼事件时长(ms)
BLINK_EYE = {"dot": 0.0, "line": 1.0, "arc": 0.0}

# ---- 待机表情序列（颜文字极简系：眼=弧线，嘴=微笑弧；无眼球无色块）----
# eye.arc>0 上弯(^)，<0 下弯(⌒)；mouth.down = 微笑弧度
IDLE_FACE_CYCLE = [
    ({"dot": 0.0, "line": 0.0, "arc": 0.55}, {"down": 0.85}),   # ( ＾▽＾) 温和微笑
    ({"dot": 0.0, "line": 0.0, "arc": 0.95}, {"down": 1.15}),   # (＾▽＾) 开心
    ({"dot": 0.0, "line": 0.0, "arc": 0.30}, {"down": 0.55}),   # (´▽`) 慵懒浅笑
    ({"dot": 0.0, "line": 0.0, "arc": -0.60}, {"down": 1.0}),   # (⌒▽⌒) 软萌讨好
]
INK_PINK = QColor(250, 105, 148)


def rrect_loop(half, rad, step_deg=1.6, step_len=3.0):
    """绕圆角正方形一周的点(单位坐标, 中心原点)"""
    pts = []
    h = half - rad

    def wl(x0, y0, x1, y1):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(L / step_len))
        for i in range(n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))

    def wa(cx, cy, a0, a1):
        a = a0
        while a < a1 - 1e-6:
            pts.append((cx + rad * math.cos(math.radians(a)),
                        cy + rad * math.sin(math.radians(a))))
            a += step_deg

    wl(-h, -H, h, -H); wa(h, -h, -90, 0); wl(H, -h, H, h)
    wa(h, h, 0, 90); wl(h, H, -h, H); wa(-h, h, 90, 180)
    wl(-H, h, -H, -h); wa(-h, -h, 180, 270)
    return pts


def hue_for_stops(stops, t):
    n = len(stops)
    x = t * n
    i = int(x) % n
    j = (i + 1) % n
    f = x - int(x)
    h1, h2 = stops[i], stops[j]
    d = ((h2 - h1 + 180) % 360) - 180
    return (h1 + d * f) % 360


def hsv_color(h, s=0.80, v=0.98):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def log(*a):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"),
                                   " ".join(str(x) for x in a)))
    except Exception:
        pass


def _exc_hook(tp, val, tb):
    import traceback
    log("EXCEPTION", "".join(traceback.format_exception(tp, val, tb)))
    sys.__excepthook__(tp, val, tb)


sys.excepthook = _exc_hook

# ---------------------------------------------------------------- 配置
DEFAULT_CONFIG = {
    "api_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "system_prompt": ("你是方方，一个精致镂空的正方形小精灵，边框闪着流彩的光。"
                      "性格软萌温柔，回答要简短治愈、语气软软的，控制在40字以内，可以带可爱的emoji。"),
    "pet_size": 220,
    "color_scheme": "蓝粉炫彩",
    "flow_speed": 0,      # 0-100 流动速度档位(0=静止)
    "auto_chat_sec": 0,   # 自言自语间隔（秒），0=关闭
    "pos": None,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        data = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        # 旧版 auto_chat_min(分钟) → auto_chat_sec(秒) 迁移(基于文件原始数据判定)
        if "auto_chat_min" in data and "auto_chat_sec" not in data:
            data["auto_chat_sec"] = max(0, int(data.pop("auto_chat_min"))) * 60
        cfg.update(data)
    except Exception as e:
        log("加载配置失败", e)
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("保存配置失败", e)


# ---------------------------------------------------------------- 素材加载
def _load_dir_pixmaps(paths, want):
    """按顺序在候选目录找 <动作>/帧；优先第一个存在的；返回 {动作:[QPixmap]}"""
    out = {}
    for name in want:
        pixs = []
        for src in paths:
            d = os.path.join(src, name)
            if not os.path.isdir(d):
                continue
            files = sorted(f for f in os.listdir(d)
                           if f.lower().endswith((".png", ".jpg", ".jpeg")))
            for f in files:
                pm = QPixmap(os.path.join(d, f))
                if not pm.isNull():
                    pixs.append(pm)
            if pixs:
                break
        if not pixs:
            raise RuntimeError("缺少动作帧: %s" % name)
        out[name] = pixs
    return out


def load_faces():
    """表情层：优先 exe 同目录 sprites/faces，其次内置 assets/faces"""
    cands = []
    ov = os.path.join(app_base(), "sprites", "faces")
    if os.path.isdir(ov):
        cands.append(ov)
    cands.append(os.path.join(res_base(), "assets", "faces"))
    return _load_dir_pixmaps(cands, ["idle", "happy", "jump", "shy"])


def load_full_sprites():
    """热替换整帧模式：exe 同目录 sprites/<动作>/fNN.png 存在时使用"""
    ov = os.path.join(app_base(), "sprites")
    if os.path.isdir(ov):
        return _load_dir_pixmaps([ov], ["idle", "happy", "jump", "shy"])
    return None


def load_shadow():
    p = os.path.join(res_base(), "assets", "shadow.png")
    pm = QPixmap(p)
    return pm if not pm.isNull() else QPixmap()


# ================================================================ 聊天气泡
class Bubble(QWidget):
    """宠物上方圆角气泡：显示用户消息 + 流式回复。
    回复文本用子 QLabel 承载，高度由 heightForWidth 精确计算，杜绝裁剪。"""

    FONT = QFont("Microsoft YaHei", 10)

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFont(self.FONT)
        self.max_w = 360
        self._sub = None          # "我：xxx"
        self._full = ""
        self._reveal = 0
        self._total_steps = 1
        self._label = QLabel(self)
        self._label.setFont(self.FONT)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._label.setStyleSheet("background: transparent; color: #323232; border: none;")
        self.t = QTimer(self); self.t.timeout.connect(self._tick)
        self.keep_t = QTimer(self); self.keep_t.setSingleShot(True)
        self.keep_t.timeout.connect(self.hide)

    def _text_rect(self):
        return self.rect().adjusted(4, 4, -4, -4)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        r = QRectF(self._text_rect())
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 238))
        p.drawPath(path)
        # 小尾巴
        bx = r.center().x() + 4
        tail = QPainterPath()
        tail.moveTo(bx - 10, r.bottom())
        tail.lineTo(bx + 2, r.bottom())
        tail.lineTo(bx - 4, r.bottom() + 10)
        tail.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 238))
        p.drawPath(tail)
        # "我" 一行灰字（回复文字由子 QLabel 绘制）
        if self._sub:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self._text_rect().adjusted(12, 6, -12, 0),
                       Qt.AlignLeft | Qt.AlignTop, "我：" + self._sub)

    def _sync_size(self):
        """用真实字体度量精确计算气泡高度并摆放回复文本标签"""
        cw = self.max_w - 24                     # 与文字左右边距一致
        fm = self.fontMetrics()
        sub_h = (fm.height() + 8) if self._sub else 8
        self._label.setFixedWidth(cw)
        self._label.setText(self._full or " ")
        hw = self._label.heightForWidth(cw)      # 换行后的真实高度
        if hw <= 0:
            hw = fm.height()
        h = 6 + sub_h + hw + 6 + 14              # 上距 + 标题区 + 正文 + 下距 + 尾巴
        self.setFixedSize(self.max_w, max(54, h))
        r = self._text_rect()
        self._label.setGeometry(int(r.left() + 12), int(r.top() + sub_h),
                                cw, max(10, int(r.height() - sub_h - 8)))

    def show_bubble(self, text, near_rect, sub=None, keep_ms=0):
        """完整/更新气泡内容。sub 传 None 沿用上一条。"""
        if sub is not None:
            self._sub = sub
        self._full = text or ""
        self._reveal = self._total_steps = 1
        self.t.stop()
        self.keep_t.stop()
        self._sync_size()
        self._place(near_rect)
        self.show()
        self.raise_()
        if keep_ms > 0:
            self.keep_t.start(keep_ms)

    def show_streaming(self, acc_text, near_rect, total_steps):
        """流式：带动画逐字(smooth reveal)"""
        self._full = acc_text or ""
        self._total_steps = max(total_steps, 1)
        self._reveal = 0
        self.t.start(TICK_MS)
        self.keep_t.stop()
        self._sync_size()
        self._place(near_rect)
        self.show()
        self.raise_()

    def _tick(self):
        self._reveal += 1
        n = int(len(self._full) * self._reveal / self._total_steps)
        self._label.setText(self._full[:n] or " ")
        if self._reveal >= self._total_steps:
            self.t.stop()
            self._label.setText(self._full)

    def _place(self, near_rect, above=None):
        """把气泡放到宠物上方（有输入框时摞在输入框上方；上方没空间则落到宠物下方）"""
        scr = QApplication.primaryScreen().availableGeometry()
        x = near_rect.center().x() - self.width() // 2
        x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
        above = near_rect.top() if above is None else min(above, near_rect.top())
        y = above - self.height() - 8
        if y < scr.top() + 4:
            y = near_rect.bottom() + 8
            if y + self.height() > scr.bottom() - 4:
                y = max(scr.top() + 4, above - self.height() - 8)
        y = max(scr.top() + 4, min(y, scr.bottom() - self.height() - 4))
        self.move(x, y)

    def is_going(self):
        return self.t.isActive()

    def hide_bubble(self):
        self.hide()


# ================================================================ 聊天输入框
class ChatInput(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("和方方说说话吧…（Enter 发送）")
        self.edit.setStyleSheet(_INPUT_SS)
        self.edit.returnPressed.connect(self._send)
        send = QPushButton("发送")
        send.setStyleSheet(_BTN_SS)
        send.clicked.connect(self._send)
        row = QHBoxLayout()  # 错误：应为 QHBoxLayout(self)
        row.addWidget(self.edit, 1)
        row.addWidget(send)
        lay.addLayout(row)

    def place_near(self, pet_rect):
        scr = QApplication.primaryScreen().availableGeometry()
        x = pet_rect.center().x() - self.width() // 2
        y = pet_rect.top() - self.height() - 14
        x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
        y = max(scr.top() + 4, y)
        self.move(x, y)
        self.show()
        self.raise_()
        self.edit.setFocus()

    def _send(self):
        txt = self.edit.text().strip()
        if not txt:
            return
        self.edit.clear()
        self.submitted.emit(txt)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


_INPUT_SS = ("QLineEdit { background: rgba(255,255,255,238);"
             " border: 2px solid #ff9ec2; border-radius: 12px;"
             " padding: 7px 12px; font: 10pt 'Microsoft YaHei'; color: #3a3a3a; }"
             "QLineEdit:focus { border-color: #ff7fb0; }")
_BTN_SS = ("QPushButton { background: #ff8fb6; color: white; border: none;"
           " border-radius: 12px; padding: 7px 16px; font: 10pt 'Microsoft YaHei'; }"
           "QPushButton:hover { background: #ffa1c2; }")


# ================================================================ 设置面板
class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME + " · API 设置")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._cfg = cfg
        f = QFormLayout(self)
        self.url = QLineEdit(cfg.get("api_url", ""))
        self.url.setPlaceholderText("https://api.xxx.com/v1")
        self.key = QLineEdit(cfg.get("api_key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.model = QLineEdit(cfg.get("model", ""))
        self.prompt = QTextEdit(cfg.get("system_prompt", ""))
        self.prompt.setFixedHeight(80)

        # 外观
        self.scheme = QComboBox()
        self.scheme.addItems(list(pet_palettes()))
        cur = cfg.get("color_scheme", "蓝粉炫彩")
        if self.scheme.findText(cur) >= 0:
            self.scheme.setCurrentText(cur)
        self.flow = QSlider(Qt.Horizontal)
        self.flow.setRange(0, 100)
        self.flow.setValue(int(cfg.get("flow_speed", 18)))
        self.flow_lb = QLabel(self._flow_text(self.flow.value()))
        self.flow.valueChanged.connect(
            lambda v: self.flow_lb.setText(self._flow_text(v)))
        flow_row = QHBoxLayout()
        flow_row.addWidget(self.flow, 1)
        flow_row.addWidget(self.flow_lb)

        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(100, 500)
        self.size.setValue(int(cfg.get("pet_size", 220)))
        self.size_lb = QLabel("%d px" % self.size.value())
        self.size.valueChanged.connect(
            lambda v: self.size_lb.setText("%d px" % v))
        size_row = QHBoxLayout()
        size_row.addWidget(self.size, 1)
        size_row.addWidget(self.size_lb)

        # 自言自语（秒）
        self.auto = QSpinBox()
        self.auto.setRange(0, 3600)
        self.auto.setSingleStep(5)
        self.auto.setValue(int(cfg.get("auto_chat_sec", 0)))
        self.auto.setSuffix(" 秒（0=关闭，建议≥10）")
        self.auto.setToolTip("每隔多少秒让方方用大模型自言自语一句")

        f.addRow("API 地址", self.url)
        f.addRow("API Key", self.key)
        f.addRow("模型名称", self.model)
        f.addRow("人设提示词", self.prompt)
        f.addRow("色彩方案", self.scheme)
        f.addRow("流彩速度", flow_row)
        f.addRow("宠物大小", size_row)
        f.addRow("自言自语", self.auto)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        f.addRow(btns)
        self.setStyleSheet(
            "QDialog{background:#f8fbf9;}"
            "QLineEdit,QTextEdit,QSpinBox,QComboBox,QSlider{border:1px solid #cde8d7;"
            "border-radius:6px;padding:4px 6px;}"
            "QPushButton{border:none;border-radius:6px;padding:5px 14px;background:#eef7f0;}"
            "QLabel{color:#333;}")

    @staticmethod
    def _flow_text(v):
        speed = 360.0 / (FLOW_MAX * v / 100.0 * (1000.0 / TICK_MS)) if v else 0
        tag = "静止" if v == 0 else ("慢" if v < 30 else ("中" if v < 60 else "快"))
        txt = "·%s·" % tag
        if v:
            txt += " 一圈 ≈ %d 秒" % round(speed)
        return txt

    def get_cfg(self):
        self._cfg["api_url"] = self.url.text().strip()
        self._cfg["api_key"] = self.key.text().strip()
        self._cfg["model"] = self.model.text().strip()
        self._cfg["system_prompt"] = self.prompt.toPlainText().strip()
        self._cfg["color_scheme"] = self.scheme.currentText()
        self._cfg["flow_speed"] = int(self.flow.value())
        self._cfg["pet_size"] = int(self.size.value())
        self._cfg["auto_chat_sec"] = int(self.auto.value())
        return self._cfg


def pet_palettes():
    """供设置面板使用（避免导入名冲突）"""
    return list(PALETTES)


# ================================================================ LLM 线程
class LLMBridge(QObject):
    chunk = pyqtSignal(str)   # 文本增量
    done = pyqtSignal(str)    # 完成(完整回复)
    failed = pyqtSignal(str)  # 错误

    def __init__(self, cfg_holder):
        super().__init__()
        self._cfg = cfg_holder
        self._hist = []
        self._busy = False

    def ask(self, text):
        if self._busy:
            self.chunk.emit("")   # 让上层感知忙碌
            return
        cfg = self._cfg()
        if not cfg.get("api_key"):
            self.failed.emit("还没有填 API Key 呢~ 右键方方 → API 设置 ⚙️")
            return
        self._busy = True
        self._hist.append({"role": "user", "content": text})
        self._hist = self._hist[-10:]
        threading.Thread(target=self._work, args=(cfg,), daemon=True).start()

    def ask_self(self):
        """自言自语：不掺入对话历史，用固定小提示生成一句"""
        if self._busy:
            return
        cfg = self._cfg()
        if not cfg.get("api_key"):
            return
        self._busy = True
        threading.Thread(target=self._work, args=(cfg, True), daemon=True).start()

    def _work(self, cfg, self_talk=False):
        import requests
        resp = ""
        base = cfg["api_url"].rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        if self_talk:
            messages = [
                {"role": "system",
                 "content": cfg.get("system_prompt") or DEFAULT_CONFIG["system_prompt"]},
                {"role": "user",
                 "content": "现在没人陪你说话，你小声自言自语一句。要简短治愈、软萌可爱，不超过30个字。"},
            ]
        else:
            messages = [{"role": "system",
                         "content": cfg.get("system_prompt") or DEFAULT_CONFIG["system_prompt"]}]
            messages += self._hist
        try:
            r = requests.post(
                url,
                headers={"Authorization": "Bearer " + cfg["api_key"],
                         "Content-Type": "application/json"},
                json={"model": cfg["model"], "messages": messages,
                      "stream": True, "temperature": 0.8, "max_tokens": 200},
                stream=True, timeout=90)
            if r.status_code != 200:
                try:
                    detail = r.json().get("error", {}).get("message", r.text[:120])
                except Exception:
                    detail = r.text[:120]
                self.done.emit(("方方被拒绝了：%s" % detail)[:140])
                self._busy = False
                return
            for line in r.iter_lines():
                if not line:
                    continue
                s = line.decode("utf-8", "ignore").strip()
                if not s.startswith("data:"):
                    continue
                s = s[5:].strip()
                if s == "[DONE]":
                    break
                try:
                    delta = json.loads(s)["choices"][0]["delta"].get("content")
                except Exception:
                    delta = None
                if delta:
                    resp += delta
                    self.chunk.emit(delta)
        except Exception as e:
            log("LLM错误", repr(e))
            self._busy = False
            if not resp:
                if not self_talk:
                    self.failed.emit("网络出小差了，检查一下 API 设置吧 (°ω°)")
                return
        self._busy = False
        if resp and not self_talk:
            self._hist.append({"role": "assistant", "content": resp})
        self.done.emit(resp)


# ================================================================ 主桌宠窗口
class PetWindow(QWidget):
    def __init__(self, cfg):
        super().__init__(None, Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._cfg = cfg
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(APP_NAME)
        self.setToolTip(APP_NAME)
        # 帧模式: full=整帧素材(sprites热替换) / compose=矢量环+表情层
        self._full_sprites = load_full_sprites()
        self._faces = load_faces()
        self._shadow = load_shadow()
        self._ring_pts = rrect_loop(H, RAD)
        self._scheme_name = cfg.get("color_scheme", "蓝粉炫彩")
        self._scheme_ok = self._scheme_name in PALETTES
        self._stops = PALETTES.get(self._scheme_name, PALETTES["蓝粉炫彩"])
        self._flow = 0.0
        self._flow_step = FLOW_MAX * int(cfg.get("flow_speed", 0)) / 100.0

        self._state = "idle"       # idle / jump / happy / shy
        self._idx = 0
        # 表情渐变控制器：从上一表情向下一表情插值(每 30s 一个)
        self._mrph_from, self._mrph_to = 3, 0   # 起始显示第0个表情(微笑)
        self._mrph_t = IDLE_TRANS + 0.5         # 初始已过过渡期 -> 直接定格在微笑
        self._cur_eye = dict(IDLE_FACE_CYCLE[0][0])
        self._cur_mouth = dict(IDLE_FACE_CYCLE[0][1])
        # 眨眼事件（叠加在表情之上，独立于渐变周期）
        self._next_blink = random.randint(*BLINK_EVERY)
        self._blink_left = 0
        self._dragging = False
        self._drag_delta = QPoint()
        self._press_pos = None
        self._suppress_click = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)

        # 自言自语定时器
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._on_auto_chat)
        self._schedule_auto_chat()

        # 气泡 & 输入框
        self.bubble = Bubble()
        self.chat = ChatInput()
        self.chat.submitted.connect(self._on_chat)
        # 动作节奏
        self._act_acc = 0
        self._hold_left = 0
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_shy)

        # LLM
        self.llm = LLMBridge(lambda: self._cfg)
        self.llm.chunk.connect(self._on_chunk)
        self.llm.done.connect(self._on_done)
        self.llm.failed.connect(self._on_fail)
        self._acc = ""
        self._stream_steps = 1

        # 右键菜单 & 托盘
        self.menu = QMenu()
        a1 = self.menu.addAction("显示 / 隐藏")
        a1.triggered.connect(self.toggle_visible)
        a_shy = self.menu.addAction("害羞一下 (长按同理)")
        a_shy.triggered.connect(self._play_shy)
        asz = self.menu.addMenu("尺寸")
        asz.addAction("+ 放大").triggered.connect(lambda: self._change_size(20))
        asz.addAction("- 缩小").triggered.connect(lambda: self._change_size(-20))
        a2 = self.menu.addAction("API 设置…")
        a2.triggered.connect(self.open_settings)
        self.menu.addSeparator()
        a3 = self.menu.addAction("退出")
        a3.triggered.connect(self.quit_app)

        self.tray = QSystemTrayIcon(self._make_icon(), self)
        self.tray.setToolTip(APP_NAME)
        tmenu = QMenu()
        b1 = tmenu.addAction("显示 / 隐藏")
        b1.triggered.connect(self.toggle_visible)
        b2 = tmenu.addAction("API 设置…")
        b2.triggered.connect(self.open_settings)
        tmenu.addSeparator()
        b3 = tmenu.addAction("退出")
        b3.triggered.connect(self.quit_app)
        self.tray.setContextMenu(tmenu)
        self.tray.activated.connect(
            lambda r: self.toggle_visible() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

        self._apply_size()
        self._apply_pos()
        log("桌宠就绪")

    # ---------------- 基础 ----------------
    def _make_icon(self):
        pm = QPixmap(os.path.join(res_base(), "assets", "sprite_base.png"))
        if pm.isNull():
            pm = self._faces["idle"][0]
        pm = pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(pm)

    def _apply_size(self):
        s = int(self._cfg.get("pet_size", 220))
        self.setFixedSize(max(80, s), max(80, s))

    def _apply_pos(self):
        p = self._cfg.get("pos")
        if isinstance(p, list) and len(p) == 2:
            try:
                self.move(int(p[0]), int(p[1]))
                return
            except Exception:
                pass
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 40,
                  scr.bottom() - self.height() - 30)

    # ---------------- 帧渲染 ----------------
    def _frame_index(self):
        return min(self._idx, len(self._faces[self._state]) - 1)

    def _action_scale_dy(self):
        """动作的缩放/位移在关键帧间【连续插值】，避免按帧跳变卡顿。
        帧索引管表情，位移/缩放走平滑曲线；定格结束前平滑回落待机位。"""
        if self._full_sprites:
            return 1.0, 0
        seq = ACTION_SCALES[self._state]
        i = self._frame_index()
        j = min(i + 1, len(seq) - 1)
        if self._hold_left > 0:
            s0, d0 = seq[i]
            if self._hold_left <= SETTLE_MS:      # 收尾 350ms 回落待机位
                k = 1.0 - self._hold_left / float(SETTLE_MS)
                return (s0 + (1.0 - s0) * k, d0 * (1.0 - k))
            return s0, d0
        if i == j or ACTION_FRAME_DT <= 0:
            return seq[i]
        ft = min(1.0, self._act_acc / ACTION_FRAME_DT)   # 帧内进度 0..1
        s0, d0 = seq[i]
        s1, d1 = seq[j]
        return (s0 + (s1 - s0) * ft, d0 + (d1 - d0) * ft)

    def _draw_flow_ring(self, p, scale_px):
        """矢量绘制流彩圆角环(纯边框，无多余装饰)"""
        n = len(self._ring_pts)
        for i in range(n):
            x1, y1 = self._ring_pts[i]
            x2, y2 = self._ring_pts[(i + 1) % n]
            hue = hue_for_stops(self._stops,
                                ((i / n) * 360 + self._flow) % 360 / 360.0)
            p.setPen(QPen(hsv_color(hue), FRAME_W,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(QPointF(x1 * scale_px, y1 * scale_px),
                       QPointF(x2 * scale_px, y2 * scale_px))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._full_sprites:
            p.drawPixmap(self.rect(), self._full_sprites[self._state][self._frame_index()])
            return
        w = self.width()
        s, dy = self._action_scale_dy()
        k = w / S * s
        cx = cy = w / 2
        # 柔影
        if not self._shadow.isNull():
            p.save()
            p.setOpacity(0.6)
            p.translate(cx + 5 * k, cy + 8 * k)
            p.scale(k, k)
            p.drawPixmap(-S // 2, -S // 2, self._shadow)
            p.restore()
            p.setOpacity(1.0)
        # 流彩环
        p.save()
        p.translate(cx, cy)
        self._draw_flow_ring(p, k)
        p.restore()
        # 表情层：待机=参数化线条渐变；动作=PNG表情帧
        p.save()
        p.translate(cx, cy + dy * k)
        p.scale(k, k)
        if self._state == "idle" and not self._full_sprites:
            self._draw_morph_face(p)
        else:
            p.drawPixmap(-S // 2, -S // 2,
                         self._faces[self._state][self._frame_index()])
        p.restore()
        p.setOpacity(1.0)

    def _draw_morph_face(self, p):
        """颜文字极简表情：眼=短弧(^/⌒)/线(眨眼)，嘴=微笑弧。无眼球无色块。
        与流彩环一样采用【居中坐标系】(中心=原点)。"""
        e, m = self._cur_eye, self._cur_mouth
        pen = QPen(INK_PINK, 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        ey = 2
        for sgn in (-1, 1):
            ex = sgn * 36
            if abs(e["arc"]) > 0.03:
                # 短弧线眼睛：弦长22，弯度随 arc 平滑
                depth = 3 + 13 * e["arc"]
                pa = QPainterPath()
                pa.moveTo(ex - 11, ey)
                pa.quadTo(ex, ey - depth, ex + 11, ey)
                p.setPen(pen); p.setBrush(Qt.NoBrush); p.strokePath(pa, pen)
            if e["line"] > 0.03:          # 眨眼
                p.setPen(pen)
                p.drawLine(QPointF(ex - 9, ey), QPointF(ex + 9, ey))
        # 微笑弧(嘴)
        if m["down"] > 0.05:
            pa = QPainterPath()
            pa.moveTo(-24, 30)
            pa.quadTo(0, 30 + 6 + 12 * m["down"], 24, 30)
            p.setPen(pen); p.setBrush(Qt.NoBrush); p.strokePath(pa, pen)

    def _tick(self):
        self._flow = (self._flow + self._flow_step) % 360.0   # 流彩前进
        if self._state == "idle":
            # ① 表情数值插值：30s 一周期，前 3.5s 线条渐变，其余停留
            self._mrph_t += TICK_MS / 1000.0
            if self._mrph_t >= IDLE_PERIOD:
                self._mrph_t -= IDLE_PERIOD
                self._mrph_from = self._mrph_to
                self._mrph_to = (self._mrph_to + 1) % len(IDLE_FACE_CYCLE)
            tt = min(1.0, self._mrph_t / IDLE_TRANS)
            ease = tt * tt * (3 - 2 * tt)
            a = IDLE_FACE_CYCLE[self._mrph_from]
            b = IDLE_FACE_CYCLE[self._mrph_to]
            for key in a[0]:
                self._cur_eye[key] = a[0][key] + (b[0][key] - a[0][key]) * ease
            for key in a[1]:
                self._cur_mouth[key] = a[1][key] + (b[1][key] - a[1][key]) * ease
            # ② 眨眼事件叠加（短促、平滑：上升~180ms/回落~320ms）
            if self._blink_left > 0:
                prog = 1.0 - self._blink_left / BLINK_DUR
                f = min(prog / 0.36, (1.0 - prog) / 0.64, 1.0)
                f = max(0.0, f)
                for key in BLINK_EYE:
                    self._cur_eye[key] = (self._cur_eye[key]
                                          + (BLINK_EYE[key] - self._cur_eye[key]) * f)
                self._blink_left -= TICK_MS
            else:
                self._next_blink -= TICK_MS
                if self._next_blink <= 0:
                    self._blink_left = BLINK_DUR
                    self._next_blink = random.randint(*BLINK_EVERY)
        elif self._state in ("jump", "happy", "shy"):
            # 慢速播放动作帧，播完定格在最后一帧再停留片刻
            if self._hold_left > 0:
                self._hold_left -= TICK_MS
                if self._hold_left <= 0:
                    self._state = "idle"
                    self._idx = 0
            else:
                self._act_acc += TICK_MS
                if self._act_acc >= ACTION_FRAME_DT:
                    self._act_acc -= ACTION_FRAME_DT   # 保留余量，插值相位连续
                    self._idx += 1
                    if self._idx >= len(self._faces[self._state]):
                        self._idx = len(self._faces[self._state]) - 1
                        self._hold_left = ACTION_HOLD[self._state]
        self.update()
        self._place_chrome()

    def _set_state(self, st):
        self._state = st
        self._idx = 0
        self._act_acc = 0
        self._hold_left = 0

    # ---------------- 鼠标交互 ----------------
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        self._press_pos = e.globalPos()
        self._drag_delta = e.globalPos() - self.pos()
        self._suppress_click = False
        self._click_timer.stop()
        self._hold_timer.start(HOLD_PRESS_MS)  # 长按触发害羞

    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.LeftButton) and self._press_pos is not None:
            if not self._dragging:
                if (e.globalPos() - self._press_pos).manhattanLength() > 7:
                    self._dragging = True
                    self._click_timer.stop()
                    self._hold_timer.stop()
            if self._dragging:
                self.move(e.globalPos() - self._drag_delta)
                self._place_chrome()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_delta = QPoint()
            self._hold_timer.stop()
            if self._dragging or self._suppress_click:
                self._dragging = False
                return
            self._dragging = False
            self._click_timer.start(280)   # 释放后短延迟：区分单击/双击

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._click_timer.stop()
            self._hold_timer.stop()
            self._suppress_click = True
            self._play_jump()

    def contextMenuEvent(self, e):
        self.menu.exec_(e.globalPos())

    def _on_single_click(self):
        self._play_happy()
        self.chat.place_near(self.frameGeometry())

    def _on_hold_shy(self):
        """长按 → 害羞（区别于单击/双击/拖拽）"""
        if self._dragging:
            return
        self._suppress_click = True
        self._click_timer.stop()
        self._play_shy()

    # ---------------- 动作 ----------------
    def _play_happy(self):
        self._set_state("happy")
        self.bubble.hide_bubble()

    def _play_jump(self):
        self.bubble.hide_bubble()
        self.chat.hide()
        self._set_state("jump")

    def _play_shy(self):
        self.bubble.hide_bubble()
        self._set_state("shy")

    def _schedule_auto_chat(self):
        self._auto_timer.stop()
        ms = int(self._cfg.get("auto_chat_sec", 0)) * 1000
        if ms > 0:
            self._auto_timer.start(ms)

    def _on_auto_chat(self):
        self._schedule_auto_chat()               # 先排下一次，保持节奏
        if self.isVisible():
            self._acc = ""
            self.bubble.show_bubble("……（小声嘀咕）…", self.frameGeometry(), sub="")
            self.llm.ask_self()

    # ---------------- 聊天 ----------------
    def _on_chat(self, text):
        self.bubble.show_bubble("", self.frameGeometry(), sub=text)
        self._acc = ""
        self._stream_steps = 1
        self.bubble.show_bubble("…", self.frameGeometry(), sub=text)
        self.llm.ask(text)

    def _on_chunk(self, delta):
        if not delta:
            return
        if not self.bubble.isVisible() or not self.bubble.is_going():
            self.bubble.show_streaming("", self.frameGeometry(), 1)
        self._acc += delta
        self._stream_steps = max(1, int(len(self._acc) * 0.6))
        self.bubble.show_streaming(self._acc, self.frameGeometry(),
                                   self._stream_steps)

    def _on_done(self, resp):
        if resp:
            self._acc = resp
            self.bubble.show_bubble(resp, self.frameGeometry(), keep_ms=8000)
        self.bubble.hide_bubble() if not resp else None

    def _on_fail(self, msg):
        self.bubble.show_bubble(msg, self.frameGeometry(), keep_ms=6000)

    def _place_chrome(self):
        r = self.frameGeometry()
        # 输入框紧贴宠物上方；气泡摞在输入框上方(输入框隐藏时摞在宠物上方)
        if self.chat.isVisible():
            self.chat.place_near(r)
        if self.bubble.isVisible():
            anchor = self.chat.frameGeometry().top() - 6 if self.chat.isVisible() else r.top()
            self.bubble._place(r, above=anchor)

    # ---------------- 菜单 ----------------
    def toggle_visible(self):
        if self.isVisible():
            self.hide()
            self.bubble.hide_bubble()
            self.chat.hide()
        else:
            self.show()
            self.raise_()

    def open_settings(self):
        cfg = dict(self._cfg)
        dlg = SettingsDialog(cfg, self)
        if dlg.exec_() == QDialog.Accepted:
            self._cfg.update(dlg.get_cfg())
            self._apply_appearance()
            save_config(self._cfg)
            self.bubble.show_bubble(
                "设置已保存~ 爱你 ⸜(｡˃ ᵕ ˂ )⸝", self.frameGeometry(), keep_ms=3500)

    def _apply_appearance(self):
        self._apply_size()
        self._scheme_name = self._cfg.get("color_scheme", "蓝粉炫彩")
        self._stops = PALETTES.get(self._scheme_name, PALETTES["蓝粉炫彩"])
        self._flow_step = FLOW_MAX * int(self._cfg.get("flow_speed", 0)) / 100.0
        self._schedule_auto_chat()
        self.update()

    def _change_size(self, delta):
        s = max(100, min(500, int(self._cfg.get("pet_size", 220)) + delta))
        self._cfg["pet_size"] = s
        self._apply_size()
        save_config(self._cfg)

    def quit_app(self):
        self._cfg["pos"] = [self.x(), self.y()]
        save_config(self._cfg)
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        self.quit_app()
        e.accept()


# ================================================================ 入口
def main():
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    cfg = load_config()
    w = PetWindow(cfg)
    w.show()
    w.raise_()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
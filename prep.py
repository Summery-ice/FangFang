# -*- coding: utf-8 -*-
"""
prep.py — 「方方」素材生成 v2
- faces/   各动作的【粗线条表情+腮红】透明层（运行时与矢量流彩环叠合绘制）
- shadow.png  柔影层
- sprite_base.png/pet.ico  由「环+表情」合成（预览/图标用）
- preview_*.png  全套动作预览
说明: 流彩环由 pet.py 运行时矢量绘制（配色/流速实时可调），这里仅用于合成预览与图标。
运行: python prep.py
"""
import math
import colorsys
import os
from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "assets")
S = 320            # 最终画布
RES = 640          # 渲染分辨率(2x，抗锯齿更精致)
K = RES // S

# ---- 镂空圆角方框参数(与 pet.py 保持同步) ----
H = 118            # 外框半宽
R = 30             # 圆角半径
W = 16             # 边框粗细


def rrect_loop(half, rad, step_deg=1.6, step_len=3.0):
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

    wl(-h, -H, h, -H)
    wa(h, -h, -90, 0)
    wl(H, -h, H, h)
    wa(h, h, 0, 90)
    wl(h, H, -h, H)
    wa(-h, h, 90, 180)
    wl(-H, h, -H, -h)
    wa(-h, -h, 180, 270)
    return pts


# ---- 色彩方案：关键色调 stop（用于流彩渐变）----
SCHEMES = {
    "蓝粉炫彩": [225, 280, 330],
    "红蓝炫彩": [355, 300, 250],
    "彩虹": [0, 60, 120, 180, 240, 300],
    "青绿炫彩": [155, 195, 260],
}


def hue_for(stops, t):
    """在 stop 序列间沿最小弧线性插值，t∈[0,1) 返回色相角"""
    n = len(stops)
    x = t * n
    i = int(x) % n
    j = (i + 1) % n
    f = x - int(x)
    h1, h2 = stops[i], stops[j]
    d = ((h2 - h1 + 180) % 360) - 180
    return (h1 + d * f) % 360


def hsv(h, s=0.80, v=0.98):
    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
    return (int(r * 255), int(g * 255), int(b * 255), 255)


def draw_ring_rgb(hue_off=0, scheme_name="蓝粉炫彩"):
    """纯色相渐变环 (RES尺寸)，供预览/阴影合成。运行时由 pet.py 矢量绘制等效物。"""
    stops = SCHEMES[scheme_name]
    pts = rrect_loop(H, R, step_deg=0.6, step_len=1.2)   # 细密采样
    img = Image.new("RGBA", (RES, RES), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n = len(pts)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        hue = hue_for(stops, ((i / n) * 360 + hue_off) % 360 / 360)
        d.line([(S + p1[0] * K, S + p1[1] * K), (S + p2[0] * K, S + p2[1] * K)],
               fill=hsv(hue), width=W * K, joint="curve")
    return img


# ---- 粉色粗线条灵动表情(无腮红) ----
INK = (250, 105, 148, 255)   # 粉色


def draw_face_layer(face_canvas, eye, mouth, cx=S // 2, cy=S // 2):
    """cx/cy 为基准分辨率坐标；内部×K 到渲染分辨率"""
    d = ImageDraw.Draw(face_canvas)
    gx, gy = cx * K, cy * K
    ex1, ex2, ey = gx - 30 * K, gx + 30 * K, gy - 4 * K
    for ex in (ex1, ex2):
        if eye == "dot":
            d.ellipse([ex - 9 * K, ey - 9 * K, ex + 9 * K, ey + 9 * K], fill=INK)
        elif eye == "closed":
            d.line([ex - 12 * K, ey, ex + 12 * K, ey], fill=INK, width=8 * K)
        elif eye == "arc":
            d.arc([ex - 12 * K, ey - 11 * K, ex + 12 * K, ey + 11 * K],
                  180, 360, fill=INK, width=7 * K)
        elif eye == "down":
            d.arc([ex - 12 * K, ey - 11 * K, ex + 12 * K, ey + 11 * K],
                  0, 180, fill=INK, width=7 * K)
        elif eye == "o":
            d.arc([ex - 11 * K, ey - 11 * K, ex + 11 * K, ey + 11 * K],
                  0, 360, fill=INK, width=8 * K)
    my = gy + 30 * K
    if mouth == "smile":
        d.arc([gx - 24 * K, my - 16 * K, gx + 24 * K, my + 18 * K],
              20, 160, fill=INK, width=8 * K)
    elif mouth == "bigsmile":
        d.arc([gx - 30 * K, my - 20 * K, gx + 30 * K, my + 24 * K],
              10, 170, fill=INK, width=9 * K)
    elif mouth == "open":
        d.ellipse([gx - 13 * K, my - 7 * K, gx + 13 * K, my + 13 * K], fill=INK)
    elif mouth == "flat":
        d.line([gx - 16 * K, my, gx + 16 * K, my], fill=INK, width=8 * K)
    elif mouth == "o":
        d.ellipse([gx - 6 * K, my - 2 * K, gx + 6 * K, my + 10 * K], fill=INK)
    return face_canvas


# ---- 动作集: (eye, mouth) 表情逐帧；scale/dy 由 pet.py 控制 ----
SETS = {
    "idle": [("dot", "smile"), ("closed", "smile"),
             ("arc", "open"), ("dot", "smile")],
    "happy": [("arc", "bigsmile"), ("arc", "bigsmile"),
              ("o", "open"), ("arc", "smile")],
    "jump": [("dot", "flat"), ("dot", "smile"), ("arc", "open"),
             ("o", "open"), ("arc", "open"),
             ("dot", "smile"), ("dot", "flat")],
    "shy": [("down", "smile"), ("down", "o")],
}


def make_shadow():
    """柔影：环轮廓模糊后偏移"""
    ring = draw_ring_rgb(0, "蓝粉炫彩")
    a = ring.split()[3]
    sh = Image.new("RGBA", (RES, RES), (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * 70 / 255)))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    out = Image.new("RGBA", (RES, RES), (0, 0, 0, 0))
    out.alpha_composite(sh, (5 * K, 8 * K))
    return out.resize((S, S), Image.LANCZOS)


def downscale(img):
    return img.resize((S, S), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "faces"), exist_ok=True)
    # 表情层
    for name, frames in SETS.items():
        d = os.path.join(OUT, "faces", name)
        os.makedirs(d, exist_ok=True)
        for i, (eye, mo) in enumerate(frames):
            fc = Image.new("RGBA", (RES, RES), (0, 0, 0, 0))
            fc = draw_face_layer(fc, eye, mo)
            downscale(fc).save(os.path.join(d, "f%02d.png" % i))
        print("表情层 %-5s %d 帧" % (name, len(frames)))
    # 阴影
    make_shadow().save(os.path.join(OUT, "shadow.png"))
    # 合成预览/图标（环+表情，蓝粉炫彩）
    ring = downscale(draw_ring_rgb(0, "蓝粉炫彩"))
    base = Image.alpha_composite(ring, Image.open(os.path.join(OUT, "faces", "idle", "f00.png")))
    base.save(os.path.join(OUT, "sprite_base.png"))
    base.save(os.path.join(OUT, "pet.ico"), sizes=[(16, 16), (24, 24), (32, 32),
                                                    (48, 48), (64, 64), (128, 128),
                                                    (256, 256)])
    print("sprite_base.png / pet.ico / shadow.png 已生成")


if __name__ == "__main__":
    main()
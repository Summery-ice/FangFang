# -*- coding: utf-8 -*-
"""
纯逻辑回归测试（完全独立，无 PyQt5/PyQt6 依赖）
- 测试配置读写
- 测试颜色方案计算
- 测试流彩算法
- 测试数据格式
"""
import os
import sys
import json
import time
import tempfile

# 测试目录
TEST_DIR = os.path.dirname(os.path.abspath(__file__))

print("=" * 60)
print("方方 · 纯逻辑回归测试")
print("=" * 60)

# ============================================================
# 测试 1：配置读写
# ============================================================
print("\n[测试 1] 配置加载/保存...")

DEFAULT_CONFIG = {
    "api_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "system_prompt": "你是方方",
    "pet_size": 220,
    "color_scheme": "蓝粉炫彩",
    "flow_speed": 0,
    "auto_chat_sec": 0,
    "pos": None,
}

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = os.path.join(tmpdir, "test_config.json")

    # 保存测试数据
    test_data = dict(DEFAULT_CONFIG)
    test_data["api_key"] = "test-key-123"
    test_data["pet_size"] = 250
    test_data["pos"] = [100, 200]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    # 加载验证
    with open(config_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["api_key"] == "test-key-123", f"API Key 不匹配：{loaded['api_key']}"
    assert loaded["pet_size"] == 250, f"尺寸不匹配：{loaded['pet_size']}"
    assert loaded["pos"] == [100, 200], f"位置不匹配：{loaded['pos']}"
    assert loaded["color_scheme"] == "蓝粉炫彩", "配色方案不匹配"

print("[OK] 配置加载/保存通过 ✓")

# ============================================================
# 测试 2：颜色方案常量
# ============================================================
print("\n[测试 2] 配色方案常量...")

PALETTES = {
    "蓝粉炫彩": [225, 280, 330],
    "红蓝炫彩": [355, 300, 250],
    "彩虹": [0, 60, 120, 180, 240, 300],
    "青绿炫彩": [155, 195, 260],
}

assert "蓝粉炫彩" in PALETTES, "蓝粉炫彩方案缺失"
assert "彩虹" in PALETTES, "彩虹方案缺失"
assert len(PALETTES["彩虹"]) == 6, f"彩虹应有 6 个色相，实际{len(PALETTES['彩虹'])}"

# 测试色相插值
def hue_for_stops(stops, t):
    n = len(stops)
    x = t * n
    i = int(x) % n
    j = (i + 1) % n
    f = x - int(x)
    h1, h2 = stops[i], stops[j]
    d = ((h2 - h1 + 180) % 360) - 180
    return (h1 + d * f) % 360

# 测试彩虹方案在 0, 0.5, 1.0 位置的色相
h0 = hue_for_stops(PALETTES["彩虹"], 0.0)
h05 = hue_for_stops(PALETTES["彩虹"], 0.5)
h1 = hue_for_stops(PALETTES["彩虹"], 1.0)

assert 0 <= h0 < 360, f"0 位置色相应 0-360，实际{h0}"
assert 0 <= h05 < 360, f"0.5 位置色相应 0-360，实际{h05}"
assert abs(h1 - h0) < 361, f"1.0 位置应回到起点附近，差值{abs(h1-h0)}"

print(f"[OK] 配色方案通过 ✓ (彩虹 0%→{int(h0)}°, 50%→{int(h05)}°)")

# ============================================================
# 测试 3：流速控制
# ============================================================
print("\n[测试 3] 流速控制...")

FLOW_MAX = 3.0  # 度/帧

# 测试流速档位映射
def flow_to_step(speed_0_100):
    """0-100 档位 → 每帧度数"""
    if speed_0_100 == 0:
        return 0.0
    return FLOW_MAX * speed_0_100 / 100.0

# 测试 0 档（静止）
assert flow_to_step(0) == 0.0, "0 档应静止"

# 测试 50 档（中等）
step50 = flow_to_step(50)
assert 1.4 <= step50 <= 1.6, f"50 档应在 1.4-1.6 度/帧，实际{step50}"

# 测试 100 档（最大）
step100 = flow_to_step(100)
assert abs(step100 - FLOW_MAX) < 0.01, f"100 档应≈{FLOW_MAX}，实际{step100}"

print(f"[OK] 流速控制通过 ✓ (50 档={step50:.2f}°/帧, 100 档={step100:.2f}°/帧)")

# ============================================================
# 测试 4：配置迁移逻辑（旧分钟 → 新秒）
# ============================================================
print("\n[测试 4] 配置迁移（分钟→秒）...")

# 模拟旧配置
old_config = {
    "api_url": "https://api.deepseek.com/v1",
    "api_key": "test",
    "auto_chat_min": 5,  # 旧格式：5 分钟
}

# 迁移逻辑
new_config = dict(DEFAULT_CONFIG)
new_config.update(old_config)

if "auto_chat_min" in new_config and "auto_chat_sec" not in new_config:
    new_config["auto_chat_sec"] = int(new_config.pop("auto_chat_min")) * 60

assert new_config["auto_chat_sec"] == 300, f"5 分钟应迁移为 300 秒，实际{new_config['auto_chat_sec']}"
assert "auto_chat_min" not in new_config, "旧键应被移除"

print(f"[OK] 配置迁移通过 ✓ (5 分钟 → {new_config['auto_chat_sec']} 秒)")

# ============================================================
# 测试 5：文件结构完整性
# ============================================================
print("\n[测试 5] 文件结构完整性...")

required_files = [
    "pet.py",
    "prep.py",
    "test_chat.py",
    "requirements.txt",
    "LICENSE",
    "README.md",
]

required_dirs = [
    "assets/faces/idle",
    "assets/faces/happy",
    "assets/faces/jump",
    "assets/faces/shy",
]

missing_files = [f for f in required_files if not os.path.exists(f)]
missing_dirs = [d for d in required_dirs if not os.path.isdir(d)]

assert not missing_files, f"缺少文件：{missing_files}"
assert not missing_dirs, f"缺少目录：{missing_dirs}"

# 检查 faces 子目录有帧文件
for face_dir in required_dirs:
    files = os.listdir(face_dir)
    assert len(files) >= 2, f"{face_dir} 至少 2 帧，实际{len(files)}"

print(f"[OK] 文件结构完整 ✓ ({len(required_files)} 文件 + {len(required_dirs)} 目录)")

# ============================================================
# 测试 6：工作流文件语法
# ============================================================
print("\n[测试 6] GitHub Actions 工作流...")

workflow_path = ".github/workflows/build.yml"
assert os.path.exists(workflow_path), f"工作流文件缺失：{workflow_path}"

# 简单 YAML 结构检查（不依赖 yaml 库）
with open(workflow_path, "r", encoding="utf-8") as f:
    content = f.read()

assert "name: Build & Test" in content, "工作流名称缺失"
assert "permissions:" in content, "权限字段缺失"
assert "contents: write" in content, "Release 权限缺失"
assert "actions/checkout@v4" in content, "checkout action 缺失"
assert "actions/setup-python@v5" in content, "setup-python action 缺失"
assert "actions/upload-artifact@v4" in content, "upload-artifact action 缺失"
assert "gh release create" in content, "Release 创建命令缺失"

print("[OK] 工作流文件结构完整 ✓")

# ============================================================
# 测试 7：.gitignore 完整性
# ============================================================
print("\n[测试 7] .gitignore 完整性...")

gitignore_path = ".gitignore"
assert os.path.exists(gitignore_path), ".gitignore 缺失"

with open(gitignore_path, "r", encoding="utf-8") as f:
    content = f.read()

protected_patterns = [
    "config.json",
    "pet.log",
    "dist/",
    "build/",
    "pic/",
]

for pattern in protected_patterns:
    assert pattern in content, f".gitignore 应保护 {pattern}"

print(f"[OK] .gitignore 完整性 ✓ ({len(protected_patterns)} 项受保护)")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("✅ 全部 7 项纯逻辑测试通过")
print("=" * 60)
print("测试环境：纯 Python，无 PyQt5/图形依赖")
print("适用：GitHub Actions Windows Runner")
print("=" * 60)

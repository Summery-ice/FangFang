# -*- coding: utf-8 -*-
"""
最简单测试：验证 GitHub Actions 能跑 Python 脚本
"""
import sys

print("Python 版本:", sys.version)
print("工作目录:", __file__)
print("")
print("[OK] GitHub Actions Python 测试通过")
sys.exit(0)

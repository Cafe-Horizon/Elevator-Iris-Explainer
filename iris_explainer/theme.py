"""
theme.py — 全シーン共通のカラーパレットとスタイル定数。

色は16進文字列で定義し、Manim の color 引数にそのまま渡せる。
Manim には依存しない (純データ)。
"""

from __future__ import annotations

# 背景
BG = "#0E1116"

# 羽根 (shader の _Color 既定 (0.2,0.2,0.2) を少し持ち上げた金属グレー)
BLADE = "#3A4048"
BLADE_EDGE = "#6B7682"
BLADE_FILL_OPACITY = 0.85

# ヒンジ / ピボット (機構の主役。暖色アクセント)
PIVOT = "#FF7A59"
PIVOT_DIM = "#9C4A36"

# プロフィール画像 / アパーチャ中心
PROFILE = "#4FD6C9"
APERTURE = "#4FD6C9"

# 座標軸
AXIS_X = "#E0556B"   # X
AXIS_Y = "#5BD06A"   # Blender Y
AXIS_Z = "#5B8DEF"   # Unity Z

# 数式・行列
INK = "#E8EDF2"      # 通常テキスト
MUTED = "#8A94A2"    # 補助テキスト
HILITE = "#FFD166"   # 強調 (回転角など)
MATRIX_BRACKET = "#AAB4C0"

# 円・補助線
GUIDE = "#3A4250"
CIRCLE = "#5B8DEF"

# 解説で項ごとに使う固定色 (行列・成分・シェーダーコードで同じ項を同じ色に結ぶ)
TERM_COS = "#FFD166"    # cos
TERM_SIN = "#EF6F6C"    # sin
TERM_QX = "#62D67E"     # q'_x / pos.x
TERM_QY = "#5B9CF0"     # q'_y / pos.z
TERM_LOCAL = "#4FD6C9"  # ローカル座標 (1.2, 0)

# フォント
FONT_MAIN = "Meiryo"         # 日本語が出るフォント (Windows 標準)。無ければ Manim が代替。
FONT_MONO = "Consolas"       # 行列・数式の等幅フォント。

# レイアウト
TITLE_SCALE = 0.8
LABEL_SCALE = 0.5

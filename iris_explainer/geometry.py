"""
geometry.py — エレベーター蓋(メカニカルアイリス)機構の「数学の単一情報源」。

このモジュールは Manim に依存しない純粋な numpy 実装で、2 つのソースの
行列計算を 1:1 で再現する:

  1. 生成時 (Blender) ......... IrisGen/scripts/main.py
  2. 実行時 (Unity / GPU) ..... Cafe-Horizon-World-Framework の
                               Assets/.../MechanicalIris/Shader/MechanicalIris.shader

座標系について:
  - Blender では羽根は XY 平面 (上方向 = +Z) に生成され、Z 軸まわりに配置される。
  - FBX 経由で Unity に取り込むと Z-up(右手系) → Y-up(左手系) 変換が入り、羽根は
    Unity の XZ 平面 (上方向 = +Y) に寝た状態になる (Blender(x, y) → Unity(x, z))。
  - 本モジュールは平面を (u, v) と呼び、Blender では (x, y)、Unity では (x, z) に
    対応づける。シェーダーが pos.x と pos.z を回しているのはこのため。
  - 注意 (未検証の仮定): 本モジュールが Blender 生成座標で shader リテラルの +α を
    素直に適用すると、アパーチャは開かず閉じたままに見える (opened_blade_world の
    退行テスト test_iris_opens_as_open_increases が検出した実際の症状)。これを
    -α (open_angle_runtime / RUNTIME_ROTATION_SIGN) で補正しているが、原因を
    「右手系→左手系変換による平面の向き(orientation)反転」と推測しているのは
    本解説プロジェクト側の当時の仮説であり、実際の Unity/VRChat 実機や FBX の
    軸変換設定 (MechanicalIris.fbx.meta の bakeAxisConversion など) で検証した
    ものではない。符号補正そのものは「本解説の可視化が意図通り開いて見える」ことの
    保証だと理解し、原因の断定的な記述は避けること。
"""

from __future__ import annotations

import numpy as np

# --- 機構パラメータ (IrisGen/scripts/main.py と shader プロパティに一致) ---
NUM_BLADES = 6           # main.py: num_blades
PIVOT_DIST = 1.2         # main.py: pivot_dist  (ヒンジ円の半径)
PROFILE_RADIUS = 1.0     # main.py: profile_radius / shader のクリップ円半径
MAX_ANGLE_DEG = 60.0     # shader: _MaxAngle (羽根が開く最大角)
PROFILE_TILT = 0.03      # main.py: z = coord[1] * 0.03 (重なり防止の傾き)

# 頂点カラーへピボットを焼き込む際のエンコード範囲。
# main.py:  r = (pivot.x + 2)/4,  g = (pivot.y + 2)/4   → [-2, 2] を [0, 1] へ。
COLOR_ENCODE_HALF_RANGE = 2.0

# 羽根プロファイルのローカル 2D 頂点 (main.py: v_coords)。
BLADE_PROFILE_LOCAL = np.array(
    [
        [0.0, 0.0],
        [0.4, 1.2],
        [1.6, 1.3],
        [1.8, -0.2],
        [0.4, -0.5],
    ],
    dtype=float,
)


# ---------------------------------------------------------------------------
# 基本の回転行列
# ---------------------------------------------------------------------------
def rot2(theta: float) -> np.ndarray:
    """2x2 の反時計回り回転行列 R(θ) = [[c, -s], [s, c]]。"""
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]], dtype=float)


def rot_z_4x4(theta: float) -> np.ndarray:
    """Blender の Matrix.Rotation(theta, 4, 'Z') に対応する 4x4 行列。"""
    c, s = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [c, -s, 0.0, 0.0],
            [s, c, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# 生成時 (Blender / IrisGen) の配置
# ---------------------------------------------------------------------------
def blade_angle(i: int) -> float:
    """羽根 i の配置角 θ_i = i * (2π / NUM_BLADES)。"""
    return i * (2.0 * np.pi / NUM_BLADES)


def hinge_world(i: int) -> np.ndarray:
    """
    羽根 i のヒンジ(ピボット)ワールド座標。
    main.py:  pivot_world = rot_z @ (pivot_dist, 0, 0)
    → 半径 PIVOT_DIST の円周上を 60° 刻みで並ぶ。
    """
    return rot2(blade_angle(i)) @ np.array([PIVOT_DIST, 0.0])


def blade_profile_world(i: int) -> np.ndarray:
    """羽根 i のプロファイル頂点をワールドへ回した (N, 2) 配列。"""
    R = rot2(blade_angle(i))
    return BLADE_PROFILE_LOCAL @ R.T  # 各行 v に対し (R @ v) を計算


# ---------------------------------------------------------------------------
# 頂点カラーへのピボット焼き込み (エンコード / デコード)
# ---------------------------------------------------------------------------
def encode_pivot(p: np.ndarray) -> np.ndarray:
    """
    ピボット座標 [-2, 2] を頂点カラー [0, 1] へ。
    main.py:  c = (p + 2) / 4
    """
    p = np.asarray(p, dtype=float)
    return (p + COLOR_ENCODE_HALF_RANGE) / (2.0 * COLOR_ENCODE_HALF_RANGE)


def decode_pivot(c: np.ndarray) -> np.ndarray:
    """
    頂点カラー [0, 1] をピボット座標 [-2, 2] へ (GPU 側の逆変換)。
    shader:  pivot = (v.color.rg * 4) - 2
    """
    c = np.asarray(c, dtype=float)
    return c * (2.0 * COLOR_ENCODE_HALF_RANGE) - COLOR_ENCODE_HALF_RANGE


# ---------------------------------------------------------------------------
# 実行時 (Unity shader) の開閉回転 — 機構の核心
# ---------------------------------------------------------------------------
def open_angle(open_amount: float, max_angle_deg: float = MAX_ANGLE_DEG) -> float:
    """
    開き量 _Open ∈ [0, 1] を回転角 α [rad] へ (shader リテラル)。
    shader:  angle = _Open * _MaxAngle * (π / 180)
    """
    return open_amount * max_angle_deg * np.pi / 180.0


# --- 生成座標での回転符号補正 (原因は未検証の仮説) ---
# 本ライブラリが Blender 生成座標をそのまま使い、シェーダーの正の α を素直に適用すると、
# アパーチャが開かず閉じたままに見える (回帰テスト test_iris_opens_as_open_increases が
# この症状を検出する)。これを補正するため符号を反転した -α を使う。
# 「右手系(Blender)→左手系(Unity)の FBX 変換で平面の向き(orientation)が反転するため」
# という説明は本解説プロジェクトが当時立てた仮説であり、実機(Unity/VRChat)や実際の
# FBX 軸変換設定で検証されたものではない。符号を反転する必要があるという事実だけは
# 上記の回帰テストで裏付けられているが、その原因がハンドネス反転なのか、羽根プロファイル
# とヒンジの位置関係という単なる 2D 幾何の性質なのかは未確定。
RUNTIME_ROTATION_SIGN = -1.0


def open_angle_runtime(open_amount: float, max_angle_deg: float = MAX_ANGLE_DEG) -> float:
    """
    実行時(Unity)で蓋が「開く」向きの回転角を Blender 生成座標で表したもの。
    手系反転を含むため、shader リテラルの open_angle に対し符号が反転する。
    """
    return RUNTIME_ROTATION_SIGN * open_angle(open_amount, max_angle_deg)


def rotate_about_pivot(point: np.ndarray, pivot: np.ndarray, alpha: float) -> np.ndarray:
    """
    任意のピボット点まわりに点を α 回転する (平面内)。
    shader の手順そのまま:  translate(-pivot) → rotate(α) → translate(+pivot)。
    """
    pivot = np.asarray(pivot, dtype=float)
    q = rot2(alpha) @ (np.asarray(point, dtype=float) - pivot)
    return q + pivot


def rotate_about_pivot_matrix(pivot: np.ndarray, alpha: float) -> np.ndarray:
    """
    上記を 1 つの 3x3 同次アフィン行列 M = T(p) · R(α) · T(-p) として返す。
    並進部は  t = p - R·p。
    """
    pivot = np.asarray(pivot, dtype=float)
    R = rot2(alpha)
    M = np.eye(3)
    M[:2, :2] = R
    M[:2, 2] = pivot - R @ pivot
    return M


def rotate_direction(direction: np.ndarray, alpha: float) -> np.ndarray:
    """
    法線・接線などの方向ベクトルの回転。並進を持たない線形部 R(α) のみ。
    shader の法線/接線回転に対応。
    """
    return rot2(alpha) @ np.asarray(direction, dtype=float)


# ---------------------------------------------------------------------------
# フラッシュ (closed 時に蓋を床と面一にする y スケール)
# ---------------------------------------------------------------------------
FLUSH_NORMAL_THRESHOLD = 0.707  # shader: step(0.707, v.normal.y) ≒ 上向き 45°以上


def flush_y_multiplier(normal_y: float, flush_amount: float) -> float:
    """
    shader:  multiplier = lerp(1, max(0.001, 1 - _FlushAmount), step(0.707, normal.y))
    上面 (normal.y ≥ 0.707) の頂点のみ y を圧縮し、ドームを平らにする。
    """
    if normal_y >= FLUSH_NORMAL_THRESHOLD:
        return max(0.001, 1.0 - flush_amount)
    return 1.0


# ---------------------------------------------------------------------------
# 羽根ポリゴンの開閉後の頂点 (可視化・検証用のまとめ関数)
# ---------------------------------------------------------------------------
def opened_blade_world(i: int, open_amount: float) -> np.ndarray:
    """
    羽根 i を open_amount だけ「開いた」後のワールド頂点 (N, 2)。
    各頂点を自分のヒンジ hinge_world(i) まわりに open_angle_runtime 回転する。
    開く向きに正しく動くよう、手系反転を含む実行時角 (open_angle_runtime) を使う。
    """
    alpha = open_angle_runtime(open_amount)
    pivot = hinge_world(i)
    verts = blade_profile_world(i)
    return np.array([rotate_about_pivot(v, pivot, alpha) for v in verts])


# ---------------------------------------------------------------------------
# 描画フレーム: 本解説で一貫して使う frame (shader フレーム)
# ---------------------------------------------------------------------------
# 本解説は、羽根を反時計回りではなく時計回りに配置角 -θ_i で並べた frame を
# 最初から使う。この配置なら shader リテラルの +α (open_angle) がそのまま
# 「開く」向きになるので、表示するコード(+α)と画面の動きが一致して説明しやすい
# (生成座標側で +α を素直に使うと閉じたままに見える件は RUNTIME_ROTATION_SIGN
# 節を参照)。この frame は Blender 生成座標を v 反転した鏡像と数値的には一致するが、
# 本解説では「生成座標を計算してから反転する」という工程は経由せず、この配置を
# 最初からの出発点として扱う。
#   - shader(実行時) を解説するシーン (scene.py) はこの frame を使う。
BLADE_PROFILE_LOCAL_SHADER = BLADE_PROFILE_LOCAL * np.array([1.0, -1.0])


def hinge_world_shader(i: int) -> np.ndarray:
    """羽根 i のヒンジ (本解説の frame)。半径 PIVOT_DIST の円周上を -60° 刻みで並ぶ。"""
    return rot2(-blade_angle(i)) @ np.array([PIVOT_DIST, 0.0])


def blade_profile_world_shader(i: int) -> np.ndarray:
    """羽根 i の(閉じた)プロファイル頂点 (本解説の frame, N, 2)。"""
    R = rot2(-blade_angle(i))
    return BLADE_PROFILE_LOCAL_SHADER @ R.T


def opened_blade_world_shader(i: int, open_amount: float) -> np.ndarray:
    """
    羽根 i を open_amount だけ開いた後の頂点 (本解説の frame, N, 2)。
    shader と同じ +α (open_angle) を各頂点のヒンジまわりに適用する。
    """
    alpha = open_angle(open_amount)  # shader リテラルの +α
    pivot = hinge_world_shader(i)
    verts = blade_profile_world_shader(i)
    return np.array([rotate_about_pivot(v, pivot, alpha) for v in verts])

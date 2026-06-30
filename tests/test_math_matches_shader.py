"""
test_math_matches_shader.py — geometry.py が元ソースの計算と一致することを検証する。

実行:  python -m pytest tests/         (pytest があれば)
   or:  python tests/test_math_matches_shader.py   (素の assert として実行)

Manim/LaTeX には依存しない (numpy のみ)。
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris_explainer import geometry as g  # noqa: E402


def test_encode_decode_roundtrip():
    """頂点カラー焼き込み(エンコード)→ GPU 復元(デコード)で元に戻る。"""
    for p in [(-2.0, -2.0), (0.0, 0.0), (1.2, 0.0), (-0.6, 1.039), (2.0, 2.0)]:
        c = g.encode_pivot(p)
        assert np.all(c >= -1e-9) and np.all(c <= 1 + 1e-9), f"color out of [0,1]: {c}"
        back = g.decode_pivot(c)
        assert np.allclose(back, p), f"{p} -> {c} -> {back}"


def test_decode_matches_shader_formula():
    """decode が shader の  pivot = v.color.rg * 4 - 2  と一致。"""
    rng = np.random.default_rng(0)
    for _ in range(50):
        c = rng.random(2)
        assert np.allclose(g.decode_pivot(c), c * 4.0 - 2.0)


def test_hinges_on_circle():
    """6 個のヒンジが半径 PIVOT_DIST の円周上を 60° 刻みで並ぶ。"""
    for i in range(g.NUM_BLADES):
        h = g.hinge_world(i)
        assert np.isclose(np.linalg.norm(h), g.PIVOT_DIST)
        ang = np.arctan2(h[1], h[0]) % (2 * np.pi)
        assert np.isclose(ang, g.blade_angle(i) % (2 * np.pi))


def test_rotate_about_pivot_matches_explicit_shader_steps():
    """
    rotate_about_pivot が shader の明示的な手順と一致:
        pos -= pivot; newX = pos.x*cos - pos.z*sin; newZ = pos.x*sin + pos.z*cos; pos += pivot
    """
    rng = np.random.default_rng(1)
    for _ in range(100):
        point = rng.uniform(-3, 3, size=2)
        pivot = rng.uniform(-2, 2, size=2)
        alpha = rng.uniform(0, np.pi / 3)
        c, s = np.cos(alpha), np.sin(alpha)
        px, pz = point - pivot
        shader = np.array([px * c - pz * s, px * s + pz * c]) + pivot
        assert np.allclose(g.rotate_about_pivot(point, pivot, alpha), shader)


def test_composite_matrix_equals_stepwise():
    """3x3 同次行列 T(p)R(α)T(-p) が逐次計算と一致。"""
    rng = np.random.default_rng(2)
    for _ in range(100):
        point = rng.uniform(-3, 3, size=2)
        pivot = rng.uniform(-2, 2, size=2)
        alpha = rng.uniform(0, np.pi / 3)
        M = g.rotate_about_pivot_matrix(pivot, alpha)
        homo = np.array([point[0], point[1], 1.0])
        via_matrix = (M @ homo)[:2]
        assert np.allclose(via_matrix, g.rotate_about_pivot(point, pivot, alpha))


def test_translation_part_is_p_minus_Rp():
    """同次行列の並進部が  t = p - R·p  であること。"""
    pivot = np.array([1.2, 0.3])
    alpha = np.radians(37)
    M = g.rotate_about_pivot_matrix(pivot, alpha)
    R = g.rot2(alpha)
    assert np.allclose(M[:2, 2], pivot - R @ pivot)


def test_open_angle_endpoints():
    """_Open=0 で 0°、_Open=1 で MAX_ANGLE_DEG。"""
    assert np.isclose(g.open_angle(0.0), 0.0)
    assert np.isclose(g.open_angle(1.0), np.radians(g.MAX_ANGLE_DEG))


def test_direction_rotation_ignores_translation():
    """方向ベクトルの回転は線形部のみ (ピボット位置に依存しない)。"""
    d = np.array([1.0, 0.0])
    alpha = np.radians(60)
    assert np.allclose(g.rotate_direction(d, alpha), g.rot2(alpha) @ d)
    # 並進不変: 同じ方向は任意ピボットで同じ結果
    assert np.allclose(
        g.rotate_direction(d, alpha),
        g.rotate_about_pivot(d, (0, 0), alpha),  # ピボット原点なら点回転と一致
    )


def test_flush_only_affects_top_faces():
    """フラッシュは上向き面 (normal.y >= 0.707) のみ y を圧縮する。"""
    assert g.flush_y_multiplier(0.0, 1.0) == 1.0          # 側面: 影響なし
    assert g.flush_y_multiplier(0.706, 1.0) == 1.0        # 閾値直下: 影響なし
    assert g.flush_y_multiplier(1.0, 1.0) == 0.001        # 真上 + 全フラッシュ
    assert np.isclose(g.flush_y_multiplier(0.8, 0.5), 0.5)  # 上面 + 半フラッシュ


def _point_in_poly(x, y, poly):
    """レイキャスト法による点(x,y)の多角形内判定 (numpy のみ、非凸対応)。"""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
        ):
            inside = not inside
        j = i
    return inside


def _coverage_of(blades, grid=41):
    """与えた羽根群が単位円内を覆う割合 (0..1)。閉=1.0、開くほど小さい。"""
    total = 0
    covered = 0
    lin = np.linspace(-1.0, 1.0, grid)
    for x in lin:
        for y in lin:
            if x * x + y * y > 1.0:
                continue
            total += 1
            if any(_point_in_poly(x, y, b) for b in blades):
                covered += 1
    return covered / total


def _aperture_coverage(open_amount, grid=41):
    """単位円内が 6 枚の羽根で覆われる割合 (0..1)。閉=1.0、開くほど小さい。"""
    blades = [g.opened_blade_world(i, open_amount) for i in range(g.NUM_BLADES)]
    return _coverage_of(blades, grid)


def test_iris_opens_as_open_increases():
    """
    _Open を増やすとアパーチャが開く (= 単位円内の被覆率が下がる) こと。
    手系反転を無視すると被覆率が下がらず「閉じたまま」になるため、それを検出する回帰テスト。
    """
    cov0 = _aperture_coverage(0.0)
    cov_half = _aperture_coverage(0.5)
    cov1 = _aperture_coverage(1.0)
    assert cov0 > 0.98, f"_Open=0 は閉(被覆率~1)であるべき: {cov0:.3f}"
    assert cov1 < 0.75, f"_Open=1 でアパーチャが開く(被覆率低下)べき: {cov1:.3f}"
    assert cov0 > cov_half > cov1, (
        f"被覆率は単調減少すべき: {cov0:.3f} -> {cov_half:.3f} -> {cov1:.3f}"
    )


def test_runtime_sign_is_flipped():
    """open_angle_runtime が shader リテラルの open_angle に対し符号反転していること。"""
    for oa in [0.25, 0.5, 1.0]:
        assert np.isclose(g.open_angle_runtime(oa), -g.open_angle(oa))


def test_shader_frame_opens_with_positive_alpha():
    """
    shader フレームでは shader リテラルの +α (open_angle) で開く。
    生成座標版 (open_angle_runtime, -α) の v 鏡像に一致することを確認する
    (鏡像は被覆率を保つので、生成座標版が開くなら shader 版も同じだけ開く)。
    """
    mirror = np.array([1.0, -1.0])
    for i in range(g.NUM_BLADES):
        for oa in [0.0, 0.5, 1.0]:
            shader = g.opened_blade_world_shader(i, oa)
            blender_mirrored = g.opened_blade_world(i, oa) * mirror
            assert np.allclose(shader, blender_mirrored), f"blade {i}, open {oa}"


def test_shader_frame_coverage_matches_runtime():
    """shader フレームの被覆率は生成座標版と一致 (鏡像なので) し、開けば下がる。"""
    for oa in [0.0, 0.5, 1.0]:
        blades_s = [g.opened_blade_world_shader(i, oa) for i in range(g.NUM_BLADES)]
        blades_b = [g.opened_blade_world(i, oa) for i in range(g.NUM_BLADES)]
        cov_s = _coverage_of(blades_s)
        cov_b = _coverage_of(blades_b)
        assert np.isclose(cov_s, cov_b, atol=1e-9), f"open={oa}: {cov_s} vs {cov_b}"
    cov0 = _coverage_of([g.opened_blade_world_shader(i, 0.0) for i in range(g.NUM_BLADES)])
    cov1 = _coverage_of([g.opened_blade_world_shader(i, 1.0) for i in range(g.NUM_BLADES)])
    assert cov0 > 0.98 and cov1 < 0.75, f"shader 版も開くべき: {cov0:.3f} -> {cov1:.3f}"


def _run_all():
    import inspect

    mod = sys.modules[__name__]
    tests = [
        (name, fn)
        for name, fn in inspect.getmembers(mod, inspect.isfunction)
        if name.startswith("test_")
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)

"""
test_source_refs.py — 解説に表示するコード抜粋が、実シェーダー/スクリプトと
ズレていないことを検証する。

- 各名前付き抜粋のアンカーが references/ のスナップショットで見つかること
- references/ のスナップショットが兄弟リポジトリの実ファイルと一致すること
  (実ファイルが存在する場合のみ。CI 等で兄弟が無ければスキップ)

これにより「解説中の計算」と「実際のシェーダー」の乖離を機械的に防ぐ。
Manim/LaTeX には依存しない。

実行:  python tests/test_source_refs.py   /   python -m pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris_explainer import source_refs as sr  # noqa: E402


def test_all_excerpts_extract():
    """全ての名前付き抜粋がアンカーで抽出でき、行番号が妥当。"""
    for fn in sr.ALL_EXCERPTS:
        ex = fn()
        assert ex.text.strip(), f"{fn.__name__}: 空の抜粋"
        assert 1 <= ex.start_line <= ex.end_line, f"{fn.__name__}: 行番号が不正"
        assert ex.language in ("hlsl", "glsl", "c", "python")


def test_R_lines_match_geometry_formula():
    """シェーダーの R(α) 2 行が geometry の回転式と同じ形であること(目視ではなく文字列で)。"""
    ex = sr.shader_R_lines()
    code = ex.text.replace(" ", "")
    # newX = pos.x*cosA - pos.z*sinA  /  newZ = pos.x*sinA + pos.z*cosA
    assert "newX=pos.x*cosA-pos.z*sinA" in code
    assert "newZ=pos.x*sinA+pos.z*cosA" in code


def test_encode_matches_geometry():
    """シェーダー/スクリプトの encode が geometry.encode_pivot と同じ係数か。"""
    ex = sr.irisgen_encode()
    code = ex.text.replace(" ", "")
    assert "r=(pivot_world.x+2.0)/4.0" in code
    assert "g=(pivot_world.y+2.0)/4.0" in code


def test_decode_matches_geometry():
    ex = sr.shader_decode()
    code = ex.text.replace(" ", "")
    assert "pivot=(v.color.rg*4.0)-2.0" in code


def test_snapshots_match_real_sources():
    """references/ のスナップショットが兄弟リポジトリの実ファイルと一致 (存在時のみ)。"""
    checked = 0
    for snap, real in sr.SNAPSHOT_PAIRS:
        if not real.exists():
            continue
        checked += 1
        snap_text = snap.read_text(encoding="utf-8")
        real_text = real.read_text(encoding="utf-8")
        assert snap_text == real_text, (
            f"スナップショットが実ファイルと乖離: {snap.name}\n"
            f"  実ファイル: {real}\n  → references/ を更新してください。"
        )
    print(f"  (照合した実ファイル: {checked} 件)")


def _run_all():
    import inspect

    mod = sys.modules[__name__]
    tests = [
        (n, f) for n, f in inspect.getmembers(mod, inspect.isfunction) if n.startswith("test_")
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

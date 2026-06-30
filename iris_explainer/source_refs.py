"""
source_refs.py — 解説で表示する「実ソースコードの抜粋」を一元管理する。

解説中の数式が実際のシェーダー/スクリプトとズレないよう、コード断片は手書きせず
references/ に取り込んだ実ソースのスナップショットから **アンカー文字列で抽出** する。
各抜粋は実ファイル上の行番号を保持し、シーンではその行番号付きで表示する。

references/ のスナップショットが兄弟リポジトリの実ファイルと一致することは
tests/test_source_refs.py が検証する (乖離するとテストが落ちる)。

Manim には依存しない (純テキスト処理)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

_REPO = Path(__file__).resolve().parent.parent
_REF = _REPO / "references"

# 表示に使うスナップショット (このリポジトリ内)
SHADER_FILE = _REF / "MechanicalIris.shader"
FLOORMASK_FILE = _REF / "FloorMask.shader"
IRISGEN_FILE = _REF / "IrisGen_main.py"

# 乖離検出テスト用: 兄弟リポジトリ上の実ファイル
_DEV = _REPO.parent
REAL_SHADER = (
    _DEV / "Cafe-Horizon-World-Framework" / "Assets" / "Cafe-Horizon" / "World"
    / "LiveStage" / "Elevator" / "ElevatorCover" / "MechanicalIris" / "Shader"
    / "MechanicalIris.shader"
)
REAL_FLOORMASK = REAL_SHADER.with_name("FloorMask.shader")
REAL_IRISGEN = _DEV / "IrisGen" / "scripts" / "main.py"

# (スナップショット, 実ファイル) の対応 (テストで一致を検証)
SNAPSHOT_PAIRS = [
    (SHADER_FILE, REAL_SHADER),
    (FLOORMASK_FILE, REAL_FLOORMASK),
    (IRISGEN_FILE, REAL_IRISGEN),
]


@dataclass(frozen=True)
class Excerpt:
    """実ソースの抜粋。text は dedent 済み、行番号は実ファイル基準(1始まり)。"""

    text: str
    start_line: int
    end_line: int
    language: str
    source_name: str

    @property
    def caption(self) -> str:
        if self.start_line == self.end_line:
            return f"{self.source_name}  (L{self.start_line})"
        return f"{self.source_name}  (L{self.start_line}-{self.end_line})"

    def line_index(self, real_line_no: int) -> int:
        """実ファイル行番号 -> この抜粋内の 0 始まりインデックス。"""
        return real_line_no - self.start_line


def _extract(path: Path, first_anchor: str, last_anchor: str | None = None,
             language: str = "hlsl") -> Excerpt:
    raw = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, ln in enumerate(raw) if first_anchor in ln)
    except StopIteration as e:
        raise ValueError(f"{path.name}: アンカーが見つからない: {first_anchor!r}") from e
    if last_anchor is None:
        end = start
    else:
        try:
            end = next(i for i, ln in enumerate(raw) if last_anchor in ln and i >= start)
        except StopIteration as e:
            raise ValueError(f"{path.name}: 終端アンカーが見つからない: {last_anchor!r}") from e
    block = "\n".join(raw[start : end + 1])
    text = dedent(block).rstrip("\n")
    return Excerpt(text, start + 1, end + 1, language, path.name)


# ---------------------------------------------------------------------------
# 名前付き抜粋 (シーンから呼ぶ)
# ---------------------------------------------------------------------------
def shader_decode() -> Excerpt:
    """頂点カラーからピボットを復元 (decode)。"""
    return _extract(SHADER_FILE, "float2 pivot = (v.color.rg", language="hlsl")


def shader_angle() -> Excerpt:
    """開き量 _Open から回転角 angle を作る。"""
    return _extract(SHADER_FILE, "float angle = _Open", language="hlsl")


def shader_rotate_block() -> Excerpt:
    """ピボットまわりの回転 (T(-p) -> R -> T(+p)) のブロック。"""
    return _extract(SHADER_FILE, "pos.x -= pivot.x", "pos.z += pivot.y;", language="hlsl")


def shader_R_lines() -> Excerpt:
    """回転 R(α) の 2 行 (newX / newZ)。"""
    return _extract(SHADER_FILE, "float newX", "float newZ", language="hlsl")


def shader_clip() -> Excerpt:
    """アパーチャの円クリップ。"""
    return _extract(
        SHADER_FILE, "float distToCenter = length(IN.localPos", "clip(1.0 - distToCenter)",
        language="hlsl",
    )


def irisgen_place() -> Excerpt:
    """放射状配置: 配置角とピボットのワールド座標。"""
    return _extract(IRISGEN_FILE, "angle = i * (2.0", "pivot_world = rot_z @ pivot_local",
                    language="python")


def irisgen_encode() -> Excerpt:
    """ピボットを頂点カラーへ焼き込む (encode の r, g)。"""
    return _extract(IRISGEN_FILE, "r = (pivot_world.x", "g = (pivot_world.y", language="python")


ALL_EXCERPTS = [
    shader_decode, shader_angle, shader_rotate_block, shader_R_lines, shader_clip,
    irisgen_place, irisgen_encode,
]

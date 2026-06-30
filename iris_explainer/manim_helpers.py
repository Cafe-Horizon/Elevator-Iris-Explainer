"""
manim_helpers.py — 全シーン共通の Manim ヘルパー。

各シーンで重複していた処理 (色付き数式、羽根の Polygon、ヒンジ点、実コードの表示、
接続矢印) をここに集約し、定義の食い違いによるミスを減らす。

Manim に依存する (geometry.py / theme.py / source_refs.py は非依存)。
"""

from __future__ import annotations

from manim import (
    Annulus,
    Circle,
    Code,
    CurvedArrow,
    Dot,
    Intersection,
    MathTex,
    Paragraph,
    Polygon,
    SurroundingRectangle,
    Text,
    VGroup,
)

from . import geometry as g
from . import theme
from .source_refs import Excerpt

APERTURE_HOLE = "#18202C"  # 開口(穴)の色


# ---------------------------------------------------------------------------
# 数式 (色付き)
# ---------------------------------------------------------------------------
def isolate(tex: str, color_map: dict | None = None, scale: float = 1.0,
            color: str = theme.INK) -> MathTex:
    """MathTex を作り、color_map(部分文字列 -> 色)で部分式に色を付ける。"""
    color_map = color_map or {}
    m = MathTex(tex, substrings_to_isolate=list(color_map.keys()), color=color)
    for sub, col in color_map.items():
        m.set_color_by_tex(sub, col)
    if scale != 1.0:
        m.scale(scale)
    return m


def by_color(mobs, hexcol: str) -> list:
    """mobs 群から、指定色のグリフ部分集合を集める (同色の項をまとめて点滅させる用)。"""
    from manim import ManimColor

    out = []
    target = ManimColor(hexcol).to_hex().lower()
    for mob in mobs:
        for sm in mob.family_members_with_points():
            try:
                if sm.get_color().to_hex().lower() == target:
                    out.append(sm)
            except Exception:
                pass
    return out


# ---------------------------------------------------------------------------
# 羽根・ヒンジ (geometry を使った Polygon / Dot)
# ---------------------------------------------------------------------------
def _poly(ax, verts, **style) -> Polygon:
    return Polygon(
        *[ax.c2p(u, v) for u, v in verts],
        color=style.get("color", theme.BLADE_EDGE),
        fill_color=style.get("fill_color", theme.BLADE),
        fill_opacity=style.get("fill_opacity", theme.BLADE_FILL_OPACITY),
        stroke_width=style.get("stroke_width", 2),
    )


def blade_polygon(ax, i: int, open_amount: float = 0.0, **style) -> Polygon:
    """羽根 i を open_amount だけ開いた Polygon (実行時の開く向き = opened_blade_world)。"""
    return _poly(ax, g.opened_blade_world(i, open_amount), **style)


def blade_polygon_alpha(ax, i: int, alpha: float, **style) -> Polygon:
    """羽根 i を角 alpha (rad) だけヒンジまわりに回した Polygon。符号をそのまま使う(デモ用)。"""
    pivot = g.hinge_world(i)
    verts = [g.rotate_about_pivot(v, pivot, alpha) for v in g.blade_profile_world(i)]
    return _poly(ax, verts, **style)


def blade_polygon_verts(ax, verts, **style) -> Polygon:
    """明示した頂点列 (N,2) から羽根 Polygon を作る。
    生成座標とは別フレーム(例: shader フレーム)で描きたいシーン用。"""
    return _poly(ax, verts, **style)


def hinge_dot(ax, i: int, color: str = theme.PIVOT, radius: float = 0.07) -> Dot:
    """ヒンジ点 (shader フレーム)。aperture_group と同じ実行時フレームで描く。"""
    return Dot(ax.c2p(*g.hinge_world_shader(i)), color=color, radius=radius)


_cached_mask = {}

def get_bg_mask(ax, r, center):
    # 外径は r*3。羽根の頂点は開閉を通じて中心から最大 |p| + max|v - p| ≈ 2.56
    # (プロファイル半径換算) までしか届かないので r*3 で全て覆える。これ以上
    # 大きくすると、周囲のテキストやコードパネルまでマスクが覆ってしまう。
    key = (id(ax), r)
    if key not in _cached_mask:
        _cached_mask[key] = Annulus(
            inner_radius=r,
            outer_radius=r * 3.0,
            fill_color=theme.BG,
            fill_opacity=1.0,
            stroke_width=0,
        ).move_to(center)
    return _cached_mask[key].copy()


def aperture_group(ax, open_amount: float, ghost: bool = True) -> VGroup:
    """
    実シェーダーの clip(1 - ||q||) を再現した「実際に見えるアパーチャ」表示。
    Intersection 演算を避け、背景色の Annulus (円環マスク) で外側を隠すことで高速化する。
    """
    center = ax.c2p(0.0, 0.0)
    r = ax.c2p(g.PROFILE_RADIUS, 0.0)[0] - center[0]

    # 下地：アパーチャホールのディスク
    hole = Circle(radius=r, fill_color=APERTURE_HOLE, fill_opacity=1.0, stroke_width=0).move_to(center)
    grp = VGroup(hole)

    # 1. 羽根の塗りつぶしと境界線 (マスクの下)
    for i in range(g.NUM_BLADES):
        verts = g.opened_blade_world_shader(i, open_amount)
        pts = [ax.c2p(u, v) for u, v in verts]
        blade_fill = Polygon(
            *pts,
            fill_color=theme.BLADE,
            fill_opacity=theme.BLADE_FILL_OPACITY,
            stroke_width=0,
        )
        blade_stroke = Polygon(
            *pts,
            color=theme.BLADE_EDGE,
            fill_opacity=0,
            stroke_width=1.2,
        )
        grp.add(blade_fill, blade_stroke)

    # 2. 背景色のマスク (アパーチャの外側を隠す)
    bg_mask = get_bg_mask(ax, r, center)
    grp.add(bg_mask)

    # 3. 羽根の全体輪郭 (ゴースト) (マスクの上に重ねる)
    if ghost:
        for i in range(g.NUM_BLADES):
            verts = g.opened_blade_world_shader(i, open_amount)
            pts = [ax.c2p(u, v) for u, v in verts]
            grp.add(
                Polygon(
                    *pts,
                    color=theme.BLADE_EDGE,
                    fill_opacity=0,
                    stroke_width=1,
                    stroke_opacity=0.22,
                )
            )

    # アパーチャ外周枠線
    border = Circle(radius=r, color=theme.BLADE_EDGE, stroke_width=1.2, fill_opacity=0).move_to(center)
    grp.add(border)

    return grp


# ---------------------------------------------------------------------------
# 実ソースコードの表示 (行番号付き)
# ---------------------------------------------------------------------------
def code_block(excerpt: Excerpt, scale: float = 0.55, style: str = "monokai") -> Code:
    """source_refs.Excerpt を、実ファイルの行番号付きで描画する Code mobject にする。"""
    code = Code(
        code_string=excerpt.text,
        language=excerpt.language,
        add_line_numbers=True,
        line_numbers_from=excerpt.start_line,
        formatter_style=style,
        background="rectangle",
        background_config={
            "fill_color": "#11161D",
            "fill_opacity": 1.0,
            "stroke_color": theme.GUIDE,
            "stroke_width": 1.2,
            "corner_radius": 0.06,
            "buff": 0.22,
        },
        paragraph_config={"font": theme.FONT_MONO},
    )
    return code.scale(scale)


def code_caption(excerpt: Excerpt, scale: float = 0.32) -> Text:
    """コードブロックの出典 (ファイル名 + 行番号) ラベル。"""
    return Text(excerpt.caption, font=theme.FONT_MONO, color=theme.MUTED).scale(scale)


def highlight_code_line(code: Code, excerpt: Excerpt, real_line_no: int,
                        color: str = theme.HILITE) -> SurroundingRectangle:
    """実ファイル行番号で、コードブロック内の該当行を囲む矩形を返す。"""
    idx = excerpt.line_index(real_line_no)
    idx = max(0, min(idx, len(code.code_lines) - 1))
    return SurroundingRectangle(
        code.code_lines[idx], color=color, stroke_width=2.5, buff=0.04, corner_radius=0.03
    )


# ---------------------------------------------------------------------------
# 接続矢印
# ---------------------------------------------------------------------------
def connect(a, b, color: str = theme.MUTED, angle: float = -0.5, stroke_width: float = 2):
    """mobject a の下端から b の上端へ向かう曲線矢印。"""
    return CurvedArrow(a.get_bottom(), b.get_top(), color=color, stroke_width=stroke_width, angle=angle)


def create_safe_text(
    text: str,
    max_width: float = 5.2,
    max_chars_per_line: int = 24,
    font: str = theme.FONT_MAIN,
    color: str = theme.INK,
    font_size: float = 24,
    **kwargs
) -> Paragraph:
    """
    指定された文字数で自動的に改行を挿入し、かつ画面上の物理的な最大幅を超えないように
    自動でスケールダウンする Paragraph オブジェクトを生成する。
    """
    wrapped_lines = []
    for line in text.split("\n"):
        if not line:
            wrapped_lines.append("")
            continue
        chunks = [line[i:i + max_chars_per_line] for i in range(0, len(line), max_chars_per_line)]
        wrapped_lines.extend(chunks)
    
    # 複数行のレイアウトとアラインメントを安定させるため、Paragraph を使用する
    t = Paragraph(*wrapped_lines, font=font, color=color, font_size=font_size, alignment="left", **kwargs)
    
    if t.width > max_width:
        t.scale_to_fit_width(max_width)
        
    return t


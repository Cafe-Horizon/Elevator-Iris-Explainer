"""
mathlib.py — Manim の数式・行列表示ヘルパー。

行列計算の解説が主目的なので、数式は LaTeX (MathTex / Matrix) で組む。
全シーンが同じ見た目になるよう、色・フォント・括弧スタイルをここに集約する。

このモジュールは Manim と LaTeX に依存する (geometry.py / theme.py は非依存)。
"""

from __future__ import annotations

import numpy as np
from manim import (
    MathTex,
    Matrix,
    Tex,
    VGroup,
)

from . import theme

# MathTex 全体に効かせる LaTeX プリアンブル不要のシンプル運用。
# 行列は manim の Matrix mobject を使う。

_TEX_KW = dict()


def eq(*parts: str, color: str = theme.INK, scale: float = 1.0, **kwargs) -> MathTex:
    """テーマ色を適用した MathTex。複数文字列は部分式として分割される。"""
    m = MathTex(*parts, color=color, **kwargs)
    if scale != 1.0:
        m.scale(scale)
    return m


def label(text: str, color: str = theme.MUTED, scale: float = 0.7) -> Tex:
    """説明用の短いテキスト (LaTeX テキストモード)。日本語が必要なら Text を使うこと。"""
    return Tex(text, color=color).scale(scale)


def _fmt(x, places: int = 2) -> str:
    """数値を行列表示用の文字列へ。整数は整数、端数は places 桁で丸めて末尾0を除去。"""
    if isinstance(x, str):
        return x
    xf = float(x)
    if abs(xf - round(xf)) < 1e-9:
        return str(int(round(xf)))
    s = f"{xf:.{places}f}".rstrip("0").rstrip(".")
    # -0 を 0 に正規化
    return "0" if s in ("-0", "-0.0") else s


def matrix(
    rows,
    *,
    bracket: str = "[",
    color: str = theme.INK,
    bracket_color: str = theme.MATRIX_BRACKET,
    scale: float = 1.0,
    places: int = 2,
    h_buff: float = 1.3,
    v_buff: float = 0.8,
) -> Matrix:
    """
    2 次元リスト(文字列 or 数値)から Manim の Matrix を作る。
    数値は _fmt で整形、文字列は LaTeX 式としてそのまま使う。
    """
    str_rows = [[_fmt(v, places) for v in row] for row in rows]
    m = Matrix(
        str_rows,
        left_bracket=bracket,
        right_bracket="]" if bracket == "[" else bracket,
        bracket_h_buff=0.15,
        h_buff=h_buff,
        v_buff=v_buff,
        element_to_mobject_config={"color": color},
    )
    m.get_brackets().set_color(bracket_color)
    if scale != 1.0:
        m.scale(scale)
    return m


def num_matrix(arr: np.ndarray, **kwargs) -> Matrix:
    """numpy 配列をそのまま Matrix へ (geometry.py の出力可視化に便利)。"""
    arr = np.atleast_2d(np.asarray(arr, dtype=float))
    return matrix(arr.tolist(), **kwargs)


def rotation_matrix_tex(symbol: str = r"\theta", **kwargs) -> Matrix:
    """記号 θ の 2x2 回転行列  [[cosθ, -sinθ], [sinθ, cosθ]]。"""
    c, s = rf"\cos{symbol}", rf"\sin{symbol}"
    return matrix([[c, f"-{s}"], [s, c]], **kwargs)


def col_vec(*entries, **kwargs) -> Matrix:
    """縦ベクトル。"""
    return matrix([[e] for e in entries], **kwargs)


def brace_label(mobject, text: str, *, direction, color: str = theme.MUTED):
    """mobject に波括弧 + ラベルを付けた VGroup を返す。"""
    from manim import Brace

    br = Brace(mobject, direction=direction, color=color)
    lab = br.get_tex(text)
    lab.set_color(color)
    return VGroup(br, lab)

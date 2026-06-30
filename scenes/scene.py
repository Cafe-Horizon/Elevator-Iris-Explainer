"""
scene.py — メカニカルアイリス(エレベーターの蓋)の開閉を支える
「任意ピボット点まわりの回転」を、1 本のストーリーとして解説する。

構成 (9 アクト・一本道):
  ACT 1  フック ......... 実際の見た目(円形アパーチャ)が開閉する。種明かし:
                          動かしているのは数式 T(p)R(α)T(-p) だけ。なぜ数式なのか。
  ACT 2  準備 ........... 羽根 6 枚のうち 1 枚に注目。ピボット p・頂点 q・
                          開き量 _Open と角度 α = _Open×60° を導入し、目標の動きを見る。
  ACT 3  素朴な失敗 ..... R(α) をそのまま掛けると原点まわりに回って羽根が飛んでいく。
                          「回転行列の不動点は原点だけ」という障害を可視化。
  ACT 4  作戦 ........... 「p を原点へ運ぶ → 回す → 返す」の 3 ステップを、
                          実シェーダー (L70-79) の行ハイライトと同時に 1 回だけ演じる。
                          グリッドは累積で動かし、「合成すると p まわりの回転そのもの」
                          「p は行って帰ってくるだけ(不動点)」を 1 つの絵で見せる。
  ACT 5  ②の中身 ....... R(α)·q' の行×列の掛け算が、そのままシェーダー L73-74 の
                          2 行になっていることを同じ色で結ぶ。
  ACT 6  合成 ........... 3 ステップを代入で 1 本の式 q''' = R(α)(q-p)+p にまとめ、
                          並進部 t = p - R(α)p と行列 M を導き、M·p = p を検算する。
  ACT 7  頂点カラー ..... GPU は p をどこから知るのか。Blender でのエンコード
                          c=(p+2)/4 と、シェーダー L61 のデコード p=4c-2 の往復。
  ACT 8  フィナーレ ..... 6 枚が同時に開き、clip による円形アパーチャで
                          冒頭と同じ「本当の見た目」に戻る。
  ACT 9  まとめ ......... 焼き込み → 復元 → ピボット回転 → クリップ、の 1 枚カード。

フレーム規約:
  一貫して「shader フレーム」(羽根を -θ_i に配置した鏡像フレーム)で描く。
  このフレームではシェーダーリテラルの +α がそのまま「開く」向きになるため、
  画面の動きと表示する行列・コード(+α)が一致する。詳細は geometry.py と
  docs/MATH.md の付録を参照。

対応する実シェーダー (MechanicalIris.shader, L70-79):
    pos.x -= pivot.x;  pos.z -= pivot.y;          # T(-p)
    float newX = pos.x*cosA - pos.z*sinA;         # R(α)
    float newZ = pos.x*sinA + pos.z*cosA;
    pos.x += pivot.x;  pos.z += pivot.y;          # T(+p)

    →  M = T(p) R(α) T(-p) = [[R, p - R p], [0, 1]]

レンダリング:
    manim -ql scenes/scene.py RotateAboutPivot
"""

import os
import sys

import numpy as np
from manim import *  # noqa: F401,F403  (Manim シーンの定石)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris_explainer import geometry as g  # noqa: E402
from iris_explainer import manim_helpers as mh  # noqa: E402
from iris_explainer import source_refs as sr  # noqa: E402
from iris_explainer import theme  # noqa: E402

config.background_color = theme.BG

BLADE_INDEX = 0  # ヒンジが (1.2, 0) に来る、いちばん見やすい羽根

isolate = mh.isolate
C_COS, C_SIN, C_QX, C_QY = theme.TERM_COS, theme.TERM_SIN, theme.TERM_QX, theme.TERM_QY
C_P = theme.PIVOT

# 数式の色対応。dict の挿入順が set_color_by_tex の適用順になるため、
# 必ず "p" を先、"R(\alpha)" を後にする ("\alpha" は文字列として 'p' を含むので、
# 逆順にすると p の色付けが R(α) を上書きしてしまう)。
FORMULA_COLORS = {"p": C_P, r"R(\alpha)": C_COS}

NARR_SCALE = 0.46   # 画面下部ナレーションの標準スケール
NARR_BUFF = 0.5     # 同・下端からの距離

# ナレーションの読了時間の見積もり (全角 ≈ 9 文字/秒 + 固定オーバーヘッド)。
# 半角英数は全角より速く読めるので 0.5 文字ぶんと数える。
READ_BASE_SEC = 0.6
READ_SEC_PER_CHAR = 0.11


def reading_time(text: str) -> float:
    """テキストを読み切るのに必要な表示時間 (秒) の目安を返す。"""
    units = sum(
        0.0 if ch.isspace() else (0.5 if ord(ch) < 0x100 else 1.0)
        for ch in text
    )
    return READ_BASE_SEC + units * READ_SEC_PER_CHAR


def fmt1(v: float) -> str:
    """座標ラベル用に小数 1 桁で整形する。-0.0 は 0.0 に正規化。"""
    return f"{round(float(v), 1) + 0.0:.1f}"


class RotateAboutPivot(Scene):
    """メカニカルアイリスの開閉行列を 9 アクトで解説する単一シーン。"""

    def construct(self):
        self._narr = None   # 画面下部のナレーション (常に 1 つ)
        self._narr_min_until = 0.0  # 現ナレーションを保持すべきシーン時刻 (読了保証)
        self._head = None   # タイトル直下のセクション見出し (常に 1 つ)
        self.open_amt = ValueTracker(0.0)

        # shader フレーム (冒頭コメント参照)。ヒンジは x 軸上 (1.2, 0)、
        # q は羽根プロファイルの頂点のひとつ (0.4, -1.2)。
        self.pivot = g.hinge_world_shader(BLADE_INDEX)
        self.q0 = g.blade_profile_world_shader(BLADE_INDEX)[1]

        self.ax = self.make_base_plane()
        self.panel_left_x = -0.2  # 右側パネル (コード・数式) の基準左端

        self.act1_hook()
        self.act2_meet_the_blade()
        self.act3_naive_fail()
        self.act4_three_steps()
        self.act5_matrix_detail()
        self.act6_compose()
        self.act7_vertex_color()
        self.act8_finale()
        self.act9_summary()

    # ------------------------------------------------------------------
    # 共通ヘルパー
    # ------------------------------------------------------------------
    def make_base_plane(self):
        return (
            NumberPlane(
                x_range=[-2.5, 2.5, 1], y_range=[-2.5, 2.5, 1],
                x_length=4.4, y_length=4.4,
                background_line_style={"stroke_color": theme.GUIDE, "stroke_width": 1, "stroke_opacity": 0.15},
                axis_config={"color": theme.GUIDE, "stroke_width": 1.5, "stroke_opacity": 0.25},
            )
            .to_edge(LEFT, buff=0.5)
            .shift(DOWN * 0.2)
        )

    def make_temp_plane(self):
        """「空間全体の動き」を表す水色グリッド。base plane に重ねて使う。"""
        return (
            NumberPlane(
                x_range=[-2.5, 2.5, 1], y_range=[-2.5, 2.5, 1],
                x_length=4.4, y_length=4.4,
                background_line_style={"stroke_color": theme.CIRCLE, "stroke_width": 1.2, "stroke_opacity": 0.45},
                axis_config={"color": theme.CIRCLE, "stroke_width": 1.8, "stroke_opacity": 0.55},
            )
            .to_edge(LEFT, buff=0.5)
            .shift(DOWN * 0.2)
        )

    def hold_narration(self):
        """現在のナレーションの読了時間が経つまで待つ (足りない分だけ)。

        say() の合間に流れるアニメーションも表示時間に数えているので、
        アニメーションが十分長い箇所では何も待たない。
        """
        if self._narr is not None:
            deficit = self._narr_min_until - self.renderer.time
            if deficit > 0.05:
                # wait はフレーム数に量子化されるため、1 フレームぶん上乗せして
                # 丸めで読了時間を下回らないようにする
                self.wait(deficit + 1.0 / config.frame_rate)

    def say(self, text: str, color: str = theme.INK, wait: float = 0.0):
        """画面下部のナレーションを差し替える。全アクト共通の 1 スロット。

        直前のナレーションが読み切られていない場合は、差し替え前に
        自動で待つ (hold_narration)。wait は読了保証とは別の「間」で、
        パネルの数式やコードを追う時間が要る場面などに使う。
        """
        self.hold_narration()
        new = Text(text, font=theme.FONT_MAIN, color=color).scale(NARR_SCALE)
        if new.width > 12.8:
            new.scale_to_fit_width(12.8)
        new.to_edge(DOWN, buff=NARR_BUFF)
        if self._narr is None:
            self.play(FadeIn(new, shift=UP * 0.1))
        else:
            self.play(FadeTransform(self._narr, new))
        self._narr = new
        self._narr_min_until = self.renderer.time + reading_time(text)
        if wait:
            self.wait(wait)

    def clear_say(self):
        if self._narr is not None:
            self.hold_narration()
            self.play(FadeOut(self._narr))
            self._narr = None

    def head_in(self, text: str):
        """タイトル直下のセクション見出しを差し替える。"""
        h = Text(text, font=theme.FONT_MAIN, color=theme.INK).scale(0.48)
        h.next_to(self.title, DOWN, buff=0.26)
        if self._head is None:
            self.play(FadeIn(h))
        else:
            self.play(FadeTransform(self._head, h))
        self._head = h

    def head_out(self):
        if self._head is not None:
            self.play(FadeOut(self._head))
            self._head = None

    def panel_anchor(self):
        return np.array([self.panel_left_x, 0.0, 0.0])

    # ------------------------------------------------------------------
    # ACT 1 — フック: 本物の見た目 → 種明かし → なぜ数式か
    # ------------------------------------------------------------------
    def act1_hook(self):
        # 中央に「実際の見た目」(円形アパーチャ + clip) を出す。
        intro_ax = NumberPlane(
            x_range=[-2.5, 2.5, 1], y_range=[-2.5, 2.5, 1],
            x_length=7.0, y_length=7.0,
        ).move_to(UP * 0.55)  # 座標変換にだけ使う (画面には出さない)

        title_big = Text("メカニカルアイリスの数学", font=theme.FONT_MAIN, color=theme.INK).scale(0.85)
        title_sub = Text("エレベーターの蓋は、1つの数式で開く", font=theme.FONT_MAIN, color=theme.MUTED).scale(0.5)
        title_grp = VGroup(title_big, title_sub).arrange(DOWN, buff=0.28).to_edge(DOWN, buff=0.55)

        first = mh.aperture_group(intro_ax, 0.0, ghost=False)
        self.play(FadeIn(first), FadeIn(title_grp))

        iris = always_redraw(lambda: mh.aperture_group(intro_ax, self.open_amt.get_value(), ghost=False))
        self.add(iris)
        self.remove(first)
        self.bring_to_front(title_grp)  # アパーチャの背景マスクより手前に出す

        self.play(self.open_amt.animate.set_value(1.0), run_time=2.2,
                  rate_func=rate_functions.ease_in_out_sine)
        self.wait(0.3)
        self.play(self.open_amt.animate.set_value(0.0), run_time=1.8,
                  rate_func=rate_functions.ease_in_out_sine)
        self.wait(0.2)

        self.play(FadeOut(title_grp))
        self.say("この開閉、ボーンもキーフレームアニメーションも使っていない。", wait=1.2)

        formula = isolate(r"q''' = T(p)\,R(\alpha)\,T(-p)\; q", FORMULA_COLORS, scale=0.9)
        formula.move_to(DOWN * 1.55)
        f_box = SurroundingRectangle(formula, color=theme.HILITE, buff=0.18, corner_radius=0.06)
        f_cap = (
            Text("MechanicalIris.shader の頂点シェーダーがしていること", font=theme.FONT_MAIN, color=theme.MUTED)
            .scale(0.34).next_to(f_box, DOWN, buff=0.12)
        )
        self.say("動かしているのは、シェーダーに書かれたこの計算だけ。")
        self.play(Write(formula), Create(f_box), FadeIn(f_cap))
        self.wait(1.0)
        self.say("この動画では、この式をゼロから組み立てる。", wait=1.0)

        iris.clear_updaters()
        self.play(FadeOut(iris), FadeOut(formula), FadeOut(f_box), FadeOut(f_cap))
        self.clear_say()

        # なぜアニメーションではなく数式なのか (短く 1 ページ)
        why_head = (
            Text("なぜアニメーションではなく「数式」なのか", font=theme.FONT_MAIN, color=theme.INK)
            .scale(0.58).to_edge(UP, buff=1.1)
        )
        items = [
            ("CPU を使わない", "演出制御や音声同期など、CPU 側の重い処理と競合しない"),
            ("6 枚まとめて GPU が変形", "ドローコールは最小のまま、全頂点を並列に計算できる"),
            ("キーフレームデータが不要", "Transform アニメーションを持たないぶん、ワールドも軽い"),
        ]
        rows = VGroup(*[
            VGroup(
                Text("・" + t, font=theme.FONT_MAIN, color=theme.INK).scale(0.5),
                Text(d, font=theme.FONT_MAIN, color=theme.MUTED).scale(0.4),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
            for t, d in items
        ]).arrange(DOWN, aligned_edge=LEFT, buff=0.45).next_to(why_head, DOWN, buff=0.6)

        self.play(FadeIn(why_head))
        for row in rows:
            self.play(FadeIn(row, shift=UP * 0.12), run_time=0.7)
            self.wait(2.0)  # 見出し + 補足の 2 行 (約 35 文字) を読む時間
        self.wait(0.8)
        self.play(FadeOut(why_head), FadeOut(rows))

        # 常設タイトル
        self.title = (
            Text("メカニカルアイリスの仕組み — ピボットまわりの回転", font=theme.FONT_MAIN, color=theme.INK)
            .scale(0.52).to_edge(UP)
        )
        self.play(Write(self.title))

    # ------------------------------------------------------------------
    # ACT 2 — 準備: 羽根 1 枚・ピボット p・頂点 q・開き量 _Open
    # ------------------------------------------------------------------
    def act2_meet_the_blade(self):
        self.head_in("準備 — 羽根 1 枚とピボット p")
        self.play(Create(self.ax), run_time=1.0)

        blades6 = VGroup(*[
            mh.blade_polygon_verts(self.ax, g.opened_blade_world_shader(i, 0.0))
            for i in range(g.NUM_BLADES)
        ])
        hinges6 = VGroup(*[
            Dot(self.ax.c2p(*g.hinge_world_shader(i)), color=C_P, radius=0.055)
            for i in range(g.NUM_BLADES)
        ])
        self.say("羽根は 6 枚。どの羽根も、付け根にある「ヒンジ」を軸にして回る。")
        self.play(FadeIn(blades6), FadeIn(hinges6))
        self.play(*[Flash(d, color=C_P, flash_radius=0.25) for d in hinges6])
        self.wait(0.4)

        # 1 枚に注目 (他は薄くしてから消す)
        others = VGroup(*[blades6[i] for i in range(1, g.NUM_BLADES)])
        other_h = VGroup(*[hinges6[i] for i in range(1, g.NUM_BLADES)])
        self.say("仕組みは 6 枚とも同じなので、1 枚だけ取り出して考える。")
        self.play(others.animate.set_opacity(0.1), other_h.animate.set_opacity(0.12))

        self.blade_poly = blades6[0]
        self.pivot_dot = hinges6[0]
        self.play(self.pivot_dot.animate.scale(1.5))
        self.pivot_lbl = MathTex("p", color=C_P).scale(0.8).next_to(self.pivot_dot, DR, buff=0.07)
        # ラベルは羽根の明るい塗りの上に乗るため、背景色の縁取りで読みやすくする
        self.pivot_lbl.set_stroke(theme.BG, width=4, background=True)

        self.q_dot = Dot(self.ax.c2p(*self.q0), color=theme.HILITE, radius=0.07)
        self.q_lbl = MathTex("q", color=theme.HILITE).scale(0.7)
        self.q_lbl.set_stroke(theme.BG, width=4, background=True)
        self.q_lbl.add_updater(lambda m: m.next_to(self.q_dot, DL, buff=0.06))

        self.say("回転の中心をピボット p、羽根の上の点をひとつ選んで q と呼ぶ。")
        self.play(Write(self.pivot_lbl), FadeIn(self.q_dot), FadeIn(self.q_lbl))
        self.wait(0.3)

        # 開き量 _Open と角度 α (シェーダー L62 と対応づける)
        alpha_def = VGroup(
            Text("開き具合はマテリアルの数値 _Open (0〜1)", font=theme.FONT_MAIN, color=theme.INK).scale(0.42),
            isolate(r"\alpha = \texttt{\_Open} \times 60^\circ", {r"\alpha": theme.HILITE}, scale=0.7),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.25)
        alpha_def.align_to(self.panel_anchor(), LEFT).shift(UP * 1.7)

        ex_angle = sr.shader_angle()
        angle_code = VGroup(
            mh.code_block(ex_angle, scale=0.42),
            mh.code_caption(ex_angle),
        ).arrange(DOWN, buff=0.12)
        angle_code.next_to(alpha_def, DOWN, buff=0.4).align_to(alpha_def, LEFT)

        self.say("開き量 _Open が 0→1 と増えると、角度 α は 0°→60° に増える。")
        self.play(FadeIn(alpha_def), FadeIn(angle_code))
        self.wait(1.8)  # 定義 2 行 + コードブロックを読む時間

        # 目標の動きを先に見せる
        self.say("目標はただひとつ。「羽根全体を、p を中心に α だけ回す」こと。")
        alpha = g.open_angle(1.0)
        grp = VGroup(self.blade_poly, self.q_dot)
        self.play(Rotate(grp, angle=alpha, about_point=self.ax.c2p(*self.pivot)), run_time=1.4)
        self.wait(0.2)
        self.play(Rotate(grp, angle=-alpha, about_point=self.ax.c2p(*self.pivot)), run_time=1.2)
        self.wait(0.3)

        self.play(FadeOut(others), FadeOut(other_h), FadeOut(alpha_def), FadeOut(angle_code))

    # ------------------------------------------------------------------
    # ACT 3 — 素朴な失敗: R(α) をそのまま掛けると原点まわりに回る
    # ------------------------------------------------------------------
    def act3_naive_fail(self):
        self.head_in("まずは失敗してみる — R(α) をそのまま掛けると?")
        self.say("回転といえば回転行列 R(α)。まずは何も考えず、q にそのまま掛けてみる。")

        R_mat = Matrix(
            [[r"\cos\alpha", r"-\sin\alpha"], [r"\sin\alpha", r"\cos\alpha"]],
            h_buff=1.6, element_to_mobject_config={"color": theme.INK},
        ).scale(0.55)
        R_mat.get_brackets().set_color(theme.MATRIX_BRACKET)
        for e in R_mat.get_entries():
            e.set_color(C_COS if "cos" in e.get_tex_string() else C_SIN)
        r_def = VGroup(
            MathTex(r"R(\alpha)=", color=C_COS).scale(0.6), R_mat,
        ).arrange(RIGHT, buff=0.15)
        r_def.align_to(self.panel_anchor(), LEFT).shift(UP * 1.7)

        wrong_eq = (
            isolate(r"q \;\mapsto\; R(\alpha)\, q", {r"R(\alpha)": C_COS}, scale=0.6)
            .next_to(r_def, DOWN, buff=0.35).align_to(r_def, LEFT)
        )
        self.play(FadeIn(r_def), Write(wrong_eq))
        self.wait(0.4)

        origin_dot = Dot(self.ax.c2p(0, 0), color=C_SIN, radius=0.06)
        wrong_poly = Polygon(
            *[self.ax.c2p(u, v) for u, v in g.blade_profile_world_shader(BLADE_INDEX)],
            color=C_SIN, fill_color=C_SIN, fill_opacity=0.18, stroke_width=2,
        )
        temp = self.make_temp_plane()
        self.play(FadeIn(origin_dot), FadeIn(temp), TransformFromCopy(self.blade_poly, wrong_poly))

        alpha = g.open_angle(1.0)
        self.play(
            Rotate(VGroup(temp, wrong_poly), angle=alpha, about_point=self.ax.c2p(0, 0)),
            run_time=1.5,
        )
        self.say("羽根がヒンジから外れて、あらぬ場所へ飛んでいってしまった。")
        self.play(Wiggle(wrong_poly))

        # p 自身がどこへ連れて行かれたかを、破線で直接示す
        drifted = g.rot2(alpha) @ self.pivot
        drift_dot = Dot(self.ax.c2p(*drifted), color=C_SIN, radius=0.07)
        drift_line = DashedLine(
            self.ax.c2p(*self.pivot), self.ax.c2p(*drifted),
            color=C_SIN, stroke_width=2.5, dash_length=0.08,
        )
        self.say("原因: R(α) は「原点を中心に」空間全体を回す変換。動かずに残るのは原点だけ。")
        self.play(Indicate(origin_dot, color=C_SIN, scale_factor=1.8))
        self.say("回転の中心であるはずの p まで、一緒に連れて行かれる。")
        self.play(Create(drift_line), FadeIn(drift_dot))

        cross = Cross(wrong_poly, stroke_color=C_SIN, stroke_width=5).scale(0.6)
        self.play(Create(cross))
        self.wait(0.4)

        self.say("欲しいのは「p が動かない回転」。R(α) 単体では作れない。", wait=0.6)
        self.play(FadeOut(VGroup(temp, wrong_poly, cross, drift_dot, drift_line, wrong_eq, r_def)))
        self.origin_dot = origin_dot  # ACT 4 でも使う

    # ------------------------------------------------------------------
    # ACT 4 — 作戦: 運んで、回して、返す (3 ステップ × 実シェーダー行)
    # ------------------------------------------------------------------
    def act4_three_steps(self):
        self.head_in("作戦 — 運んで、回して、返す")
        self.say("回転の中心が原点しか選べないなら、p のほうを原点まで運んでしまえばいい。", wait=0.5)

        ex = sr.shader_rotate_block()
        code = mh.code_block(ex, scale=0.46)
        cap = mh.code_caption(ex)
        codegrp = VGroup(code, cap).arrange(DOWN, buff=0.15)
        codegrp.align_to(self.panel_anchor(), LEFT).shift(DOWN * 0.55)
        self.say("実際のシェーダーも、まさにこの作戦を 3 ステップで実行している。")
        self.play(FadeIn(codegrp))

        origin = self.ax.c2p(0.0, 0.0)
        shift_to_origin = origin - self.ax.c2p(*self.pivot)
        alpha = g.open_angle(1.0)

        # p の「元の位置」に印を残し、空間全体の動きを水色グリッドで表す
        home_ring = DashedVMobject(
            Circle(radius=0.16, color=C_P, stroke_width=2.0).move_to(self.ax.c2p(*self.pivot)),
            num_dashes=10,
        )
        temp = self.make_temp_plane()
        self.say("p の元の位置に印(点線リング)を置く。水色のグリッドは「空間全体」の動き。")
        self.play(Create(home_ring), FadeIn(temp))

        self.pivot_lbl.add_updater(lambda m: m.next_to(self.pivot_dot, DR, buff=0.06))
        space = VGroup(temp, self.blade_poly, self.q_dot, self.pivot_dot)

        banner = None

        def show_step(text, eq_tex, color, lines):
            nonlocal banner
            t = Text(text, font=theme.FONT_MAIN, color=color).scale(0.38)
            e = isolate(eq_tex, FORMULA_COLORS, scale=0.5)
            b = VGroup(t, e).arrange(RIGHT, buff=0.3)
            if b.width > 7.2:
                b.scale_to_fit_width(7.2)
            b.next_to(code, UP, buff=0.22)
            rects = VGroup(*[mh.highlight_code_line(code, ex, ln, color=color) for ln in lines])
            if banner is None:
                self.play(FadeIn(b), Create(rects))
            else:
                self.play(FadeTransform(banner, b), Create(rects))
            banner = b
            return rects

        # ① 空間全体を −p 並進 (ヒンジが原点へ) = L70-71
        r1 = show_step("① 全体を −p 平行移動: ピボットが原点へ", r"q' = q - p", C_P, [70, 71])
        self.play(space.animate.shift(shift_to_origin), run_time=1.4)
        self.play(FadeOut(r1))
        self.wait(0.2)

        # ② 原点まわりに α 回転 = L73-74
        r2 = show_step("② 原点まわりに α 回転: R(α) の出番", r"q'' = R(\alpha)\, q'", C_COS, [73, 74])
        self.play(Rotate(space, angle=alpha, about_point=origin), run_time=1.5)
        self.play(FadeOut(r2))
        self.wait(0.2)

        # ③ 空間全体を +p 並進 (元の場所へ返す) = L78-79
        r3 = show_step("③ 全体を +p 平行移動: 元の場所へ返す", r"q''' = q'' + p", C_P, [78, 79])
        self.play(space.animate.shift(-shift_to_origin), run_time=1.4)
        self.play(FadeOut(r3))

        # ペイオフ: p は行って帰ってきただけ = 不動点。全体は p まわりの回転そのもの。
        self.say("ピボット p は行って帰ってきただけ — 置いた印のリングとぴったり重なっている。")
        self.play(Indicate(self.pivot_dot, color=C_P, scale_factor=1.6))
        self.wait(0.3)
        self.say("グリッドを見ると、空間全体が「p を中心に α 回転」している。羽根は正しく開いた。", wait=0.8)

        self.pivot_lbl.clear_updaters()
        self.q_lbl.clear_updaters()
        self.play(FadeOut(VGroup(temp, home_ring, codegrp, banner, self.origin_dot)))
        self.say("あとはこの 3 ステップを、1 つの式に磨き上げるだけ。", wait=0.5)
        self.play(FadeOut(VGroup(
            self.ax, self.blade_poly, self.q_dot, self.q_lbl, self.pivot_dot, self.pivot_lbl,
        )))

    # ------------------------------------------------------------------
    # ACT 5 — ステップ②の中身: 行列の 2 行 = コードの 2 行 (L73-74)
    # ------------------------------------------------------------------
    def act5_matrix_detail(self):
        self.head_in("ステップ②の中身 — 行列の 2 行が、コードの 2 行")
        self.say("②で使った R(α)·q′ の掛け算を、成分まで開いてみる。")

        R = Matrix(
            [[r"\cos\alpha", r"-\sin\alpha"], [r"\sin\alpha", r"\cos\alpha"]],
            h_buff=1.9, element_to_mobject_config={"color": theme.INK},
        ).scale(0.72)
        R.get_brackets().set_color(theme.MATRIX_BRACKET)
        for e in R.get_entries():
            e.set_color(C_COS if "cos" in e.get_tex_string() else C_SIN)

        qv = Matrix([[r"q'_x"], [r"q'_y"]], element_to_mobject_config={"color": theme.INK}).scale(0.72)
        qv.get_brackets().set_color(theme.MATRIX_BRACKET)
        qv.get_entries()[0].set_color(C_QX)
        qv.get_entries()[1].set_color(C_QY)
        eq_sign = MathTex("=", color=theme.INK).scale(0.85)

        comp_colors = {r"q'_x": C_QX, r"q'_y": C_QY, r"\cos\alpha": C_COS, r"\sin\alpha": C_SIN}
        out1 = isolate(r"\cos\alpha\; q'_x - \sin\alpha\; q'_y", comp_colors, scale=0.66)
        out2 = isolate(r"\sin\alpha\; q'_x + \cos\alpha\; q'_y", comp_colors, scale=0.66)
        result = VGroup(out1, out2).arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        prod = VGroup(R, qv, eq_sign, result).arrange(RIGHT, buff=0.3).move_to(UP * 0.9)

        self.play(FadeIn(R), FadeIn(qv), Write(eq_sign))
        self.play(Indicate(R.get_rows()[0], color=C_COS), Indicate(qv, color=C_QX))
        self.play(TransformFromCopy(VGroup(R.get_rows()[0], qv.get_entries()), out1))
        self.play(Indicate(R.get_rows()[1], color=C_COS), Indicate(qv, color=C_QY))
        self.play(TransformFromCopy(VGroup(R.get_rows()[1], qv.get_entries()), out2))
        self.wait(0.3)

        ex = sr.shader_R_lines()
        codegrp = VGroup(
            mh.code_block(ex, scale=0.55),
            mh.code_caption(ex),
        ).arrange(DOWN, buff=0.12).next_to(prod, DOWN, buff=0.55)
        self.say("これがシェーダーの 2 行そのもの。1 行目が新しい x、2 行目が新しい z。")
        self.play(FadeIn(codegrp))

        pool = [R, out1, out2]
        self.play(*[Indicate(m, color=C_COS, scale_factor=1.35) for m in mh.by_color(pool, C_COS)], run_time=1.1)
        self.play(*[Indicate(m, color=C_SIN, scale_factor=1.35) for m in mh.by_color(pool, C_SIN)], run_time=1.1)
        self.say("cosα と sinα の並びまで、行列とコードは 1 対 1 に対応している。", wait=0.6)
        self.play(FadeOut(prod), FadeOut(codegrp))

    # ------------------------------------------------------------------
    # ACT 6 — 合成: 3 ステップ → 1 つの式 → 並進部 t → 行列 M → 検算 M·p = p
    # ------------------------------------------------------------------
    def act6_compose(self):
        self.head_in("3 つのステップを、1 つの式へ")

        steps = VGroup(
            isolate(r"q' = q - p", {"p": C_P}, scale=0.55),
            isolate(r"q'' = R(\alpha)\, q'", {r"R(\alpha)": C_COS}, scale=0.55),
            isolate(r"q''' = q'' + p", {"p": C_P}, scale=0.55),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.24).move_to(LEFT * 4.7 + UP * 1.35)
        self.say("さっきの 3 本の式を、下から順に代入してつなげる。")
        self.play(FadeIn(steps))
        self.wait(0.5)

        combined = isolate(r"q''' = R(\alpha)\,(q - p) + p", FORMULA_COLORS, scale=0.72)
        combined.move_to(RIGHT * 1.6 + UP * 1.35)
        arrow = Arrow(
            steps.get_right(), combined.get_left(),
            buff=0.3, color=theme.MUTED, stroke_width=3, max_tip_length_to_length_ratio=0.12,
        )
        self.play(GrowArrow(arrow), TransformFromCopy(steps, combined))

        c_box = SurroundingRectangle(combined, color=theme.HILITE, buff=0.16, corner_radius=0.05)
        c_cap = (
            Text("シェーダーが毎フレーム・全頂点に行っている計算", font=theme.FONT_MAIN, color=theme.MUTED)
            .scale(0.34).next_to(c_box, DOWN, buff=0.12)
        )
        self.play(Create(c_box), FadeIn(c_cap))
        self.say("引いて、回して、足す — 見た目どおりの式になった。", wait=0.6)

        # 展開して「回転 1 回 + 並進 1 回」に畳む
        self.say("展開して整理すると、この変換の正体が見えてくる。")
        expanded = isolate(r"q''' = R(\alpha)\,q - R(\alpha)\,p + p", FORMULA_COLORS, scale=0.62)
        expanded.move_to(RIGHT * 1.6 + UP * 0.1)
        self.play(TransformFromCopy(combined, expanded))
        self.wait(0.4)

        regrouped = isolate(r"q''' = R(\alpha)\,q + \big(p - R(\alpha)\,p\big)", FORMULA_COLORS, scale=0.62)
        regrouped.next_to(expanded, DOWN, buff=0.3).align_to(expanded, LEFT)
        self.play(TransformFromCopy(expanded, regrouped))
        self.wait(0.4)

        t_eq = isolate(r"t = p - R(\alpha)\,p", FORMULA_COLORS, scale=0.7)
        t_eq.next_to(regrouped, DOWN, buff=0.4).align_to(regrouped, LEFT)
        t_box = SurroundingRectangle(t_eq, color=C_P, buff=0.14, corner_radius=0.05)
        self.play(Write(t_eq), Create(t_box))
        self.say("正体は「原点まわりの回転 R(α) を 1 回 + 平行移動 t を 1 回」。", wait=0.7)

        t_grp = VGroup(t_eq, t_box)
        self.play(FadeOut(expanded), FadeOut(regrouped),
                  t_grp.animate.move_to(RIGHT * 1.6 + UP * 0.25))

        # 同次座標なら 1 枚の行列にまとまる
        M_eq = isolate(
            r"M = T(p)\,R(\alpha)\,T(-p) = \begin{bmatrix} R(\alpha) & p - R(\alpha)\,p \\ 0 & 1 \end{bmatrix}",
            FORMULA_COLORS, scale=0.6,
        ).move_to(DOWN * 0.85)
        self.say("同次座標で書けば、3 枚の行列の積は「回転と並進を並べた 1 枚の行列」M になる。")
        self.play(Write(M_eq))
        self.wait(1.0)

        # 検算: q = p を代入すると p がそのまま返る (不動点)
        self.say("最後に検算。この式は本当に p を動かさないのか — q に p を入れてみる。")
        self.play(FadeOut(M_eq))
        c1 = isolate(r"R(\alpha)\,(p - p) + p", FORMULA_COLORS, scale=0.62).move_to(RIGHT * 1.6 + DOWN * 0.7)
        c2 = isolate(r"= R(\alpha)\cdot 0 + p", FORMULA_COLORS, scale=0.62)
        c2.next_to(c1, DOWN, buff=0.22).align_to(c1, LEFT)
        c3 = isolate(r"= p", {"p": C_P}, scale=0.68)
        c3.next_to(c2, DOWN, buff=0.22).align_to(c2, LEFT)
        self.play(Write(c1))
        self.wait(0.3)
        self.play(TransformFromCopy(c1, c2))
        self.wait(0.3)
        self.play(TransformFromCopy(c2, c3))
        self.say("p を入れると p がそのまま返る。さっき画面で見た「p は動かない」の、数式による裏付け。", wait=1.0)

        self.play(FadeOut(VGroup(steps, arrow, combined, c_box, c_cap, t_grp, c1, c2, c3)))

    # ------------------------------------------------------------------
    # ACT 7 — 頂点カラー: GPU は p をどうやって知るのか
    # ------------------------------------------------------------------
    def act7_vertex_color(self):
        self.head_in("残る謎 — GPU は p をどうやって知るのか")
        self.say("式には各羽根のピボット p が要る。だが頂点シェーダーは「自分がどの羽根の頂点か」を知らない。")
        self.play(FadeIn(self.ax))

        def rgb_to_hex_str(rgb):
            r = int(max(0, min(255, rgb[0] * 255)))
            g_val = int(max(0, min(255, rgb[1] * 255)))
            b = int(max(0, min(255, rgb[2] * 255)))
            return f"#{r:02X}{g_val:02X}{b:02X}"

        blades = VGroup()
        pivot_dots = VGroup()
        coord_lbls = VGroup()
        lbl_positions = []  # 各ラベルの位置 (axes 座標)。色ラベル/復元ラベルでも再利用する。

        for i in range(g.NUM_BLADES):
            verts = g.opened_blade_world_shader(i, 0.0)
            blades.add(mh.blade_polygon_verts(self.ax, verts))

            p_pos = g.hinge_world_shader(i)
            pivot_dots.add(Dot(self.ax.c2p(*p_pos), color=C_P, radius=0.075))

            # ラベルはヒンジを通る動径方向に、羽根ポリゴンの最遠点より外側へ置く
            # (羽根形状から距離が自動で決まるため、どの羽根ともラベルが重ならない)。
            dir_vec = p_pos / np.linalg.norm(p_pos)
            reach = max(np.linalg.norm(p_pos), float(np.max(verts @ dir_vec)))
            lbl_pos = dir_vec * (reach + 0.3)
            lbl_positions.append(lbl_pos)
            coord_lbls.add(
                MathTex(f"({fmt1(p_pos[0])}, {fmt1(p_pos[1])})", color=C_P)
                .scale(0.48).move_to(self.ax.c2p(*lbl_pos))
            )

        self.play(FadeIn(blades), FadeIn(pivot_dots), Write(coord_lbls), run_time=1.5)
        self.say("6 つのヒンジは、半径 1.2 の円周上に 60° おきに並んでいる。", wait=0.6)

        # --- エンコード (Blender / メッシュ生成時) ---
        self.say("答え: メッシュを作る時点で、各頂点に「自分のピボット座標」を色として塗っておく。")
        ex_enc = sr.irisgen_encode()
        enc_code = mh.code_block(ex_enc, scale=0.46)
        enc_grp = VGroup(enc_code, mh.code_caption(ex_enc)).arrange(DOWN, buff=0.12)
        enc_grp.align_to(self.panel_anchor(), LEFT).shift(UP * 1.3)
        enc_rects = VGroup(
            mh.highlight_code_line(enc_code, ex_enc, 30, color=theme.HILITE),
            mh.highlight_code_line(enc_code, ex_enc, 31, color=theme.HILITE),
        )
        enc_eqs = VGroup(
            isolate(r"r = (p_x + 2)\,/\,4", {"p_x": C_P}, scale=0.62),
            isolate(r"g = (p_y + 2)\,/\,4", {"p_y": C_P}, scale=0.62),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        enc_eqs.next_to(enc_grp, DOWN, buff=0.35).align_to(enc_grp, LEFT)
        enc_note = (
            Text("座標の範囲 [-2, 2] を、色の範囲 [0, 1] に写すだけの 1 次変換", font=theme.FONT_MAIN, color=theme.MUTED)
            .scale(0.36).next_to(enc_eqs, DOWN, buff=0.25).align_to(enc_eqs, LEFT)
        )
        self.play(FadeIn(enc_grp), Create(enc_rects), Write(enc_eqs), FadeIn(enc_note))
        self.wait(1.8)  # コード + 式 2 本 + 注釈を読む時間

        # 点の色を実際のエンコード結果へ変え、ラベルも色値表示へ
        color_anims = []
        color_lbls = VGroup()
        for i, dot in enumerate(pivot_dots):
            p_pos = g.hinge_world_shader(i)
            enc = g.encode_pivot(p_pos)
            hexcol = rgb_to_hex_str([enc[0], enc[1], 0.0])
            color_anims.append(dot.animate.set_color(hexcol))
            color_lbls.add(
                MathTex(f"({enc[0]:.2f}, {enc[1]:.2f})", color=hexcol)
                .scale(0.48).move_to(self.ax.c2p(*lbl_positions[i]))
            )
        self.play(*color_anims, FadeOut(coord_lbls), FadeIn(color_lbls), run_time=1.8)
        self.say("ヒンジ座標が、そのまま「色」になった。色はメッシュと一緒に GPU まで運ばれる。", wait=1.0)

        # --- デコード (Unity / 頂点シェーダー) ---
        self.say("色を塗るのは Blender。読み出して羽根を回すのは、Unity 側のシェーダー。")
        self.play(FadeOut(VGroup(enc_grp, enc_rects, enc_eqs, enc_note)))

        ex_dec = sr.shader_decode()
        dec_code = mh.code_block(ex_dec, scale=0.46)
        dec_grp = VGroup(dec_code, mh.code_caption(ex_dec)).arrange(DOWN, buff=0.12)
        dec_grp.align_to(self.panel_anchor(), LEFT).shift(UP * 1.3)
        dec_rect = mh.highlight_code_line(dec_code, ex_dec, 61, color=theme.HILITE)
        dec_eqs = VGroup(
            isolate(r"p_x = 4r - 2", {"p_x": C_P}, scale=0.62),
            isolate(r"p_y = 4g - 2", {"p_y": C_P}, scale=0.62),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        dec_eqs.next_to(dec_grp, DOWN, buff=0.35).align_to(dec_grp, LEFT)
        dec_note = (
            Text("逆向きの 1 次変換で、元のピボット座標がそのまま戻る", font=theme.FONT_MAIN, color=theme.MUTED)
            .scale(0.36).next_to(dec_eqs, DOWN, buff=0.25).align_to(dec_eqs, LEFT)
        )
        self.say("シェーダーは頂点カラーから、逆向きの計算で p を復元する。")
        self.play(FadeIn(dec_grp), Create(dec_rect), Write(dec_eqs), FadeIn(dec_note))
        self.wait(1.6)  # コード + 式 2 本 + 注釈を読む時間

        # デコードのペイオフ: 色 → 座標に実際に戻して見せる
        restored_lbls = VGroup(*[
            MathTex(
                f"({fmt1(g.hinge_world_shader(i)[0])}, {fmt1(g.hinge_world_shader(i)[1])})", color=C_P,
            ).scale(0.48).move_to(self.ax.c2p(*lbl_positions[i]))
            for i in range(g.NUM_BLADES)
        ])
        self.play(
            pivot_dots.animate.set_color(C_P),
            FadeOut(color_lbls), FadeIn(restored_lbls),
            run_time=1.2,
        )
        self.say("色は見た目のためではなく、データの入れ物。各頂点が「自分の回転中心」を持ち歩いている。", wait=1.2)

        self.play(FadeOut(VGroup(dec_grp, dec_rect, dec_eqs, dec_note)))

        # ACT 8 で使う
        self.vc_blades = blades
        self.vc_dots = pivot_dots
        self.vc_lbls = restored_lbls
        self.lbl_positions = lbl_positions

    # ------------------------------------------------------------------
    # ACT 8 — フィナーレ: 6 枚同時に開き、clip で「本当の見た目」へ
    # ------------------------------------------------------------------
    def act8_finale(self):
        self.head_in("仕上げ — 6 枚同時に、本当の見た目へ")

        # 座標ラベル → p_i ラベル
        p_lbls = VGroup(*[
            MathTex(f"p_{i}", color=C_P).scale(0.6).move_to(self.ax.c2p(*self.lbl_positions[i]))
            for i in range(g.NUM_BLADES)
        ])
        self.play(*[
            ReplacementTransform(self.vc_lbls[i], p_lbls[i]) for i in range(g.NUM_BLADES)
        ])

        # 静的な羽根を、_Open 追従の羽根に差し替える (閉状態なので見た目は同一)
        dyn_blades = VGroup(*[
            always_redraw(lambda i=i: mh.blade_polygon_verts(
                self.ax, g.opened_blade_world_shader(i, self.open_amt.get_value()),
            ))
            for i in range(g.NUM_BLADES)
        ])
        self.add(dyn_blades)
        self.remove(self.vc_blades)
        self.bring_to_front(self.vc_dots, p_lbls)

        self.say("_Open を 0 から 1 へ。全頂点が同じ式・自分の p で、一斉に回る。")
        self.play(
            self.open_amt.animate.set_value(1.0),
            run_time=2.4, rate_func=rate_functions.ease_in_out_sine,
        )
        self.say("開いている間も、6 つのピボットは 1 ミリも動かない — すべて不動点。")
        self.play(*[Flash(d, color=C_P, flash_radius=0.3) for d in self.vc_dots])
        self.play(
            self.open_amt.animate.set_value(0.0),
            run_time=1.8, rate_func=rate_functions.ease_in_out_sine,
        )

        # clip による円形アパーチャ
        ex_clip = sr.shader_clip()
        clip_grp = VGroup(
            mh.code_block(ex_clip, scale=0.46),
            mh.code_caption(ex_clip),
        ).arrange(DOWN, buff=0.12)
        clip_grp.align_to(self.panel_anchor(), LEFT).shift(UP * 0.6)
        self.say("最後の仕上げ。中心から半径 1 の円の外側は、clip で描画を捨てる。")
        self.play(FadeIn(clip_grp))
        self.wait(1.2)  # コードブロックを読む時間

        for b in dyn_blades:
            b.clear_updaters()
        static_ap = mh.aperture_group(self.ax, 0.0, ghost=True)
        self.play(FadeOut(dyn_blades), FadeOut(self.vc_dots), FadeOut(p_lbls), FadeIn(static_ap))

        iris = always_redraw(lambda: mh.aperture_group(self.ax, self.open_amt.get_value(), ghost=True))
        self.add(iris)
        self.remove(static_ap)
        # アパーチャの背景マスクより手前に出す
        self.bring_to_front(clip_grp)
        self.bring_to_front(self.title)
        if self._head is not None:
            self.bring_to_front(self._head)
        if self._narr is not None:
            self.bring_to_front(self._narr)

        self.say("これで、冒頭に見た「丸い窓が開く」動きになる。薄い線は捨てられた羽根の続き。")
        self.play(
            self.open_amt.animate.set_value(1.0),
            run_time=2.4, rate_func=rate_functions.ease_in_out_sine,
        )
        self.wait(0.5)
        self.play(
            self.open_amt.animate.set_value(0.0),
            run_time=1.8, rate_func=rate_functions.ease_in_out_sine,
        )
        self.wait(0.3)

        iris.clear_updaters()
        self.play(FadeOut(iris), FadeOut(clip_grp), FadeOut(self.ax))

    # ------------------------------------------------------------------
    # ACT 9 — まとめ: 蓋が開くまでの全体像を 1 枚で
    # ------------------------------------------------------------------
    def act9_summary(self):
        # 前アクトのナレーションが空画面に残らないよう、先に消してから見出しを出す
        self.clear_say()
        self.head_in("まとめ — 蓋が開くまで")

        def row(tag, desc, math_mobs, tag_color):
            left = VGroup(
                Text(tag, font=theme.FONT_MAIN, color=tag_color).scale(0.42),
                Text(desc, font=theme.FONT_MAIN, color=theme.INK).scale(0.4),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
            r = VGroup(left, math_mobs).arrange(RIGHT, buff=0.7)
            if r.width > 12.5:
                r.scale_to_fit_width(12.5)
            return r

        rows = VGroup(
            row(
                "① 設計時 (Blender)",
                "ヒンジ p を円周上に置き、その座標を頂点カラーへ焼き込む",
                isolate(r"c = (p + 2)\,/\,4", {"p": C_P}, scale=0.58),
                theme.PROFILE,
            ),
            row(
                "② 実行時 (GPU) — 復元",
                "頂点カラーから p を戻し、開き量から角度を作る",
                VGroup(
                    isolate(r"p = 4c - 2", {"p": C_P}, scale=0.58),
                    isolate(r"\alpha = \texttt{\_Open} \times 60^\circ", {r"\alpha": theme.HILITE}, scale=0.58),
                ).arrange(RIGHT, buff=0.6),
                theme.HILITE,
            ),
            row(
                "③ 実行時 (GPU) — 回転",
                "全頂点を「自分の p」まわりに回し、円の外側を clip で捨てる",
                isolate(r"q''' = R(\alpha)\,(q - p) + p", FORMULA_COLORS, scale=0.58),
                C_P,
            ),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.55).move_to(UP * 0.35)

        for r in rows:
            self.play(FadeIn(r, shift=UP * 0.12), run_time=0.8)
            self.wait(1.8)  # タグ + 説明 + 数式の 1 行ぶんを読む時間
        self.wait(0.8)

        fin = VGroup(
            Text("アニメーションを再生しているのではなく、数式を評価している。",
                 font=theme.FONT_MAIN, color=theme.INK).scale(0.46),
            Text("それが、メカニカルアイリスの正体。",
                 font=theme.FONT_MAIN, color=theme.HILITE).scale(0.52),
        ).arrange(DOWN, buff=0.22).to_edge(DOWN, buff=0.7)
        self.play(FadeIn(fin[0]))
        self.wait(1.4)
        self.play(FadeIn(fin[1]))
        self.wait(2.4)

        self.head_out()
        self.play(FadeOut(rows), FadeOut(fin), FadeOut(self.title))
        self.wait(0.5)

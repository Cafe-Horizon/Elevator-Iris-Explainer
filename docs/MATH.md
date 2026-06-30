# メカニカルアイリス蓋の行列計算 — 導出ノート

このドキュメントは、エレベーターの蓋（メカニカルアイリス）の開閉機構が
**どの行列計算で実装されているか** を、生成（Blender）から実行時（Unity GPU）まで
一気通貫で導出する。各式は `iris_explainer/geometry.py` に 1:1 で実装され、
`tests/test_math_matches_shader.py` で元ソースとの一致を検証している。

参照ソース:

- 生成: `IrisGen/scripts/main.py`
- 実行時: `Cafe-Horizon-World-Framework/.../MechanicalIris/Shader/MechanicalIris.shader`
- マスク: 同 `Shader/FloorMask.shader`
- 制御: `.../Elevator/Script/Elevator.cs` と `Animation/ElevatorCover_Opening.anim`

---

## 0. 座標系の約束（Blender XY ↔ Unity XZ）

Blender では羽根は **XY 平面** に作られ、Z 軸まわりに配置される。FBX で Unity に
取り込むと Z-up → Y-up 変換が入り、羽根は Unity の **XZ 平面** に寝る。つまり

$$ \text{Blender}(x, y) \;\longleftrightarrow\; \text{Unity}(x, z) $$

本ノートでは平面座標を \((u, v)\) と書き、Blender では \((x,y)\)、Unity では
\((x,z)\) に読み替える。シェーダーが `pos.x` と `pos.z` を回している
（`pos.y` ではない）のはこのため。

### 可視化のフレーム規約（shader フレーム）

本ノートおよび解説動画（`scene.py`）は、一貫して **shader フレーム** で描く。
これは羽根の配置角を最初から \(-\theta_i\)（時計回り）に取ったフレームで、
シェーダーリテラルの \(+\alpha\)（`open_angle`）がそのまま「開く」向きになる。
画面の動きと、表示する行列・コード（\(+\alpha\)）が常に一致するので、
読者は符号の読み替えをせずに済む。

実装: `geometry.{hinge_world_shader, blade_profile_world_shader,
opened_blade_world_shader}`。

なお Blender 生成座標をそのまま使う場合は回転の符号を反転する必要がある
（`geometry.RUNTIME_ROTATION_SIGN`）。その事実関係と原因の考察（未検証の
仮説を含む）は本編の理解には不要なので、[付録 A](#付録-a-生成座標での回転符号補正)
にまとめた。

---

## 1. 羽根の放射状配置（生成 / Blender）

羽根は \(N=6\) 枚。羽根 \(i\) の配置角は

$$ \theta_i = i \cdot \frac{2\pi}{N}, \qquad i = 0,1,\dots,5 $$

Z 軸まわりの回転行列（Blender `Matrix.Rotation(θ, 4, 'Z')`）は

$$
R_z(\theta) =
\begin{bmatrix} \cos\theta & -\sin\theta & 0 & 0 \\ \sin\theta & \cos\theta & 0 & 0 \\ 0 & 0 & 1 & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}
$$

各羽根のヒンジ（ピボット）はローカルで \(p_\text{local} = (1.2, 0, 0)\)。
ワールドへ回すと

$$
p_i = R_z(\theta_i)\, p_\text{local} = \big(1.2\cos\theta_i,\; 1.2\sin\theta_i,\; 0\big)
$$

→ 6 個のヒンジは **半径 1.2 の円周上を 60° 刻み** で並ぶ。
羽根プロファイル（5 頂点の多角形）も同じ \(R_z(\theta_i)\) で各頂点を回す。
頂点 z には `z = y·0.03` の微小傾きを与え、隣り合う羽根の同一平面上の重なり
（z-fighting）を防ぐ。

実装: `geometry.blade_angle`, `hinge_world`, `blade_profile_world`。

---

## 2. ピボットの頂点カラー焼き込み（生成 → GPU）

GPU の頂点シェーダーには「自分がどの羽根か」という情報がない。そこで生成時に
**各頂点のヒンジ座標を頂点カラー (RG) に焼き込む**。座標範囲 \([-2, 2]\) を
カラー範囲 \([0, 1]\) へ写すアフィン変換:

$$
\text{encode}: \quad c = \frac{p + 2}{4}
\qquad\Longleftrightarrow\qquad
\text{decode}: \quad p = 4c - 2
$$

- 焼き込み (`main.py`): `r = (pivot.x + 2)/4`, `g = (pivot.y + 2)/4`
- 復元 (`shader`): `pivot = v.color.rg * 4 - 2`

`decode ∘ encode = id`（テスト `test_encode_decode_roundtrip` で確認）。
こうして各頂点は「自分が回るべきヒンジ」を色として運ぶ。

実装: `geometry.encode_pivot`, `decode_pivot`。

---

## 3. 任意ピボット点まわりの回転（実行時 / 機構の核心）

開き量 `_Open ∈ [0,1]` を回転角へ:

$$ \alpha = \texttt{\_Open} \cdot 60^\circ \cdot \frac{\pi}{180} $$

各頂点を**自分のヒンジ \(p\) を中心に** \(\alpha\) 回す。原点中心では駄目なので、
「ヒンジを原点へ移動 → 回す → 戻す」の 3 ステップに分解する:

$$
q' = q - p,\qquad
q'' = R(\alpha)\,q',\qquad
q''' = q'' + p
$$

ここで平面内 2D 回転は

$$
R(\alpha) = \begin{bmatrix} \cos\alpha & -\sin\alpha \\ \sin\alpha & \cos\alpha \end{bmatrix}
$$

シェーダーの該当行と完全一致する:

```hlsl
pos.x -= pivot.x;  pos.z -= pivot.y;                 // q - p
float newX = pos.x*cosA - pos.z*sinA;                // R(α) q'
float newZ = pos.x*sinA + pos.z*cosA;
pos.x = newX;  pos.z = newZ;
pos.x += pivot.x;  pos.z += pivot.y;                 // q'' + p
```

### 同次座標で 1 つの行列にまとめる

3 ステップは 3×3 同次アフィン行列の積になる:

$$
M = T(p)\, R(\alpha)\, T(-p) =
\begin{bmatrix} R(\alpha) & p - R(\alpha)p \\ 0 & 1 \end{bmatrix}
$$

すなわち線形部は \(R(\alpha)\)、**並進部は \(t = p - R(\alpha)\,p\)**。
展開すると

$$
M = \begin{bmatrix}
\cos\alpha & -\sin\alpha & p_u(1-\cos\alpha) + p_v\sin\alpha \\
\sin\alpha & \cos\alpha & p_v(1-\cos\alpha) - p_u\sin\alpha \\
0 & 0 & 1
\end{bmatrix}
$$

これがメカニカルアイリス開閉の**心臓部**。`_Open` が 0→1 に動くと 6 枚の羽根が
各自のヒンジを支点に同時に開く。

実装: `geometry.rotate_about_pivot`, `rotate_about_pivot_matrix`。
検証: `test_rotate_about_pivot_matches_explicit_shader_steps`,
`test_composite_matrix_equals_stepwise`, `test_translation_part_is_p_minus_Rp`。

---

## 4. 法線・接線の回転（方向ベクトルは線形部のみ）

頂点を回したらライティング用の法線・接線も回す必要がある。ただし方向ベクトルは
**並進を持たない**ので、適用するのは \(M\) の線形部 \(R(\alpha)\) だけ:

$$ n' = R(\alpha)\, n, \qquad \tau' = R(\alpha)\, \tau $$

シェーダーも `normal.xz` と `tangent.xz` に同じ 2D 回転を適用している。
（点には \(M\)、方向には \(R\) を使う、というアフィン変換の基本。）

実装: `geometry.rotate_direction`。検証: `test_direction_rotation_ignores_translation`。

---

## 5. フラッシュ（閉状態で床と面一にする y スケール）

閉じたときに蓋を床面と面一にするため、**上向きの面だけ** y を縮める:

$$
\text{mult} = \mathrm{lerp}\!\big(1,\; \max(0.001,\,1-\texttt{\_FlushAmount}),\; \mathrm{step}(0.707, n_y)\big)
$$

\(n_y \ge 0.707\)（上向き 45° 以上）の頂点のみ `v.y *= mult`。これは
y 方向だけのスケール行列 \(\mathrm{diag}(1, \text{mult}, 1)\) に相当し、回転とは独立。

実装: `geometry.flush_y_multiplier`。検証: `test_flush_only_affects_top_faces`。

---

## 6. アパーチャのクリップ（円形の開口を保つ）

回転で羽根が外へ退くと、開口を**単位円**で切り抜いて綺麗な円形アパーチャにする:

```hlsl
float distToCenter = length(localPos.xz);
clip(1.0 - distToCenter);     // 中心からの距離 > 1 の断片を捨てる
```

\(\lVert (u,v) \rVert > 1\) の領域を破棄。羽根の内縁が開くにつれ、見える部分が
中心から円形に開いていく。

---

## 7. ステンシルによる床穴マスク

蓋は床の丸穴の中だけに見せたい。`FloorMask.shader` が円（半径 `_CircleRadius`）を
**色を書かずに**ステンシルバッファへ書き込み（`Ref 2`, `Comp Always`, `Pass Replace`、
`ColorMask 0`, `ZWrite Off`, `Queue Geometry-1` で最初に描画）、アイリスは
`Stencil { Ref 2  Comp Equal }` でステンシル値が 2 の画素にだけ描画される。
→ アイリスは床穴の内側にのみ出現する。

---

## 8. 制御（アニメーションカーブ）

`_Open` と `_FlushAmount` は `ElevatorCover_Opening.anim` で時間駆動される:

- `_FlushAmount`: \(1 \to 0\)（\(t\in[0,\,0.167]\)）。まず面一を解除。
- `_Open`: \(t=0.25\) まで 0、その後 \(0 \to 1\)（\(t=1\)）。面一解除後に羽根が開く。

`Elevator.cs` が状態機械（OPENING → MOVING → CLOSING）で `ElevatorCover_Open`
フロートを `Mathf.MoveTowards` で 0↔1 に動かし、Animator がこのカーブを再生する。

---

## まとめ — 1 枚で言うと

$$
\underbrace{p_i = R_z(\theta_i)\,(1.2,0,0)}_{\text{1. 配置}}
\;\xrightarrow{\;c=(p+2)/4\;}\;
\underbrace{\text{頂点カラー}}_{\text{2. 焼き込み}}
\;\xrightarrow{\;p=4c-2\;}\;
\underbrace{q''' = T(p)R(\alpha)T(-p)\,q}_{\text{3. 開閉回転}}
\;\to\;
\underbrace{\mathrm{clip}(1-\lVert q'''_{uv}\rVert)}_{\text{6. 開口}}
$$

回転行列 \(R\) を「配置」と「開閉」の両方で使い、ヒンジ座標を色として運ぶことで、
GPU 上で羽根ごとの個別ヒンジ回転を頂点シェーダーだけで実現している。

---

## 付録 A: 生成座標での回転符号補正

本ライブラリが Blender 生成座標をそのまま使い、シェーダーの正の \(\alpha\)
（`_Open`>0）を素直に適用すると、アパーチャが**開かず閉じたまま**に見える
（`tests/test_math_matches_shader.py` の `test_iris_opens_as_open_increases` が
この症状を回帰テストとして検出する）。これを解消するため、本ライブラリは
Blender 生成座標では符号を反転した \(-\alpha\) を使う
（`geometry.open_angle_runtime` = \(-\,\)`open_angle`、`RUNTIME_ROTATION_SIGN`）。

符号を反転する**必要があること自体**は上記の回帰テストで裏付けられているが、
その**原因**を「Blender(右手系)→Unity(左手系) の FBX 変換で羽根が寝る平面の
向き(orientation)が反転するため」と説明しているのは、本解説プロジェクトが
この症状を発見した際に立てた**当時の仮説**であり、実際の Unity/VRChat 実機や
FBX の軸変換設定（例: `MechanicalIris.fbx.meta` の `bakeAxisConversion`）で
検証したものではない。原因は羽根プロファイルとヒンジの位置関係という単なる
2D 幾何の性質である可能性もあり、断定はできない。

本編の解説はこの符号補正を経由しない。shader フレーム（\(-\theta_i\) 配置）を
最初からの前提として扱うことで、\(+\alpha\) がそのまま「開く」向きになる。
この配置は数値的には生成座標を \(v\) 反転した鏡像と一致するが、
「生成座標を計算してから反転する」という工程を解説上は経由しない。

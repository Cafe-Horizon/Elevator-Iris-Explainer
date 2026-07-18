# Elevator-Iris-Explainer

[LiveStage-Elevator](https://github.com/Cafe-Horizon/LiveStage-Elevator) のエレベーターの開閉機構が、どういう行列計算で実装されているかを
Manim のアニメーションで解説するリポジトリ

<https://youtu.be/c4NOMRSOP0g>

<video src="https://github.com/user-attachments/assets/ae6c8ca9-8327-47a4-bcfe-6303ca7b94c2" width="50%" controls></video>

開閉機構のベースオブジェクトは [IrisGen](https://github.com/Cafe-Horizon/IrisGen)（Blender スクリプト）で生成しています。

開閉そのものは Unity の頂点シェーダー [MechanicalIris.shader](https://github.com/Cafe-Horizon/LiveStage-Elevator/blob/main/Assets/Cafe-Horizon/World/LiveStage/Elevator/ElevatorCover/MechanicalIris/Shader/MechanicalIris.shader) が行列計算で行っています。

本リポジトリはその中でも核心となる「GPU での開閉回転機構」について
数式とアニメーションで可視化しています。

## セットアップ

```powershell
# Python 3.11+ / ffmpeg / LaTeX(MiKTeX 等) が必要
# uv を用いた依存関係の同期（仮想環境の自動作成とパッケージのインストール）
uv sync

# 開発用（テスト実行時など、開発用依存関係も含めて同期する場合）
uv sync --all-extras
```

- **ffmpeg**: 動画書き出しに必要。
- **LaTeX**: 数式 (MathTex) の描画に必要。Windows は MiKTeX 推奨
  （`scoop install latex`）。MiKTeX は不足パッケージを自動取得する。

## レンダリング

```powershell
# シーンを低品質でプレビュー
uv run ./render.ps1

# 高品質
uv run ./render.ps1 -Quality h

# 直接 Manim で実行する場合
uv run manim -ql scenes/scene.py RotateAboutPivot
```

出力は `media/videos/...` に生成されます。

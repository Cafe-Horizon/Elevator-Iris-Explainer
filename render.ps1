<#
render.ps1 — Manim シーンを並列でレンダリングする補助スクリプト。

使い方:
  ./render.ps1                # デフォルトで全編通しシーン (RotateAboutPivot) を低品質 (-ql) でレンダリング
  ./render.ps1 -Quality h     # 全編通しシーンを高品質 (-qh) でレンダリング
  ./render.ps1 -Scene 04      # 特定の個別アクト (Act4) だけをレンダリング
  ./render.ps1 -Scene all     # 全個別アクト + 全編通しシーンをすべて並列レンダリング
  ./render.ps1 -Jobs 4        # 並列プロセス数を指定して実行
#>
param(
    [string]$Quality = "l",
    [string]$Scene = "",
    [int]$Jobs = 0
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$cmdArgs = @("-q", $Quality)

if ($Scene) {
    $cmdArgs += @("-s", $Scene)
}

if ($Jobs -gt 0) {
    $cmdArgs += @("-j", $Jobs)
}

& uv run python (Join-Path $root "render.py") $cmdArgs
if ($LASTEXITCODE -ne 0) { throw "render failed" }

Write-Host "done. Output is under ./media/videos/." -ForegroundColor Green

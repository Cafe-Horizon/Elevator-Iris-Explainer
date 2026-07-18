<#
render.ps1 — 全シーンを並列でまとめてレンダリングする補助スクリプト。

使い方:
  ./render.ps1                # 全シーンを低品質 (-ql) で並列レンダリング
  ./render.ps1 -Quality h     # 高品質 (-qh)
  ./render.ps1 -Scene 04      # scene04 (Act4) だけ
  ./render.ps1 -Jobs 4        # 並列プロセス数を指定して実行
  ./render.ps1 -NoCombine     # レンタリング完了後の自動結合を無効化
#>
param(
    [string]$Quality = "l",
    [string]$Scene = "",
    [int]$Jobs = 0,
    [switch]$NoCombine
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

if ($NoCombine) {
    $cmdArgs += "--no-combine"
}

& uv run python (Join-Path $root "render.py") $cmdArgs
if ($LASTEXITCODE -ne 0) { throw "render failed" }

Write-Host "done. Output is under ./media/videos/." -ForegroundColor Green

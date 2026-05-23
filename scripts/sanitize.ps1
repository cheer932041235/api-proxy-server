$repo = "E:\study\api-proxy-server"
$files = Get-ChildItem -Path $repo -Recurse -Include *.md, *.sh, *.py, *.service -File |
  Where-Object {
    $_.FullName -notmatch '\\\.git\\' -and
    $_.Name -ne 'local.secrets.md' -and
    $_.Name -ne 'LICENSE' -and
    $_.Name -ne '.env.example' -and
    $_.FullName -notmatch '\\homepage-designs\\'
  }

$pairs = @(
  @{ Old = 'OpenClaw\(龙虾\)-4KQB'; New = '<YOUR_VPS_INSTANCE_NAME>' },
  @{ Old = '170\.106\.65\.175'; New = '<YOUR_VPS_IP>' },
  @{ Old = 'api\.shujinxing777\.com'; New = '<YOUR_DOMAIN>' },
  @{ Old = '\?token=shujinxing777'; New = '?token=<YOUR_LOG_TOKEN>' },
  @{ Old = '\?key=shujinxing777'; New = '?key=<YOUR_LOG_TOKEN>' },
  @{ Old = '932041235@qq\.com'; New = '<YOUR_PLUS_EMAIL_A>' },
  @{ Old = 'cheershuyang@163\.com'; New = '<YOUR_PLUS_EMAIL_B>' },
  @{ Old = 'cheershuyang@qq\.com'; New = '<YOUR_ALERT_EMAIL>' },
  @{ Old = 'sk-MxTbv9KDEiD4OXTJgZ7pO6RgbmnVmUPs3PCiXpFqfcWsi8OL'; New = '<YOUR_NEW_API_KEY>' },
  @{ Old = 'sk-gpt2api-secret'; New = '<YOUR_CHATGPT2API_AUTH_KEY>' },
  @{ Old = 'Proxy2026!'; New = '<YOUR_NEW_API_ADMIN_PASS>' },
  @{ Old = '疏锦行'; New = '<YOUR_STUDIO_QUIZ_ANSWER>' },
  @{ Old = '课程老师是？'; New = '<YOUR_STUDIO_QUIZ_QUESTION>' },
  @{ Old = '课程老师是\?'; New = '<YOUR_STUDIO_QUIZ_QUESTION>' }
)

$totalChanged = 0
foreach ($f in $files) {
  $content = Get-Content $f.FullName -Raw -Encoding UTF8
  $original = $content
  foreach ($p in $pairs) {
    $content = $content -replace $p.Old, $p.New
  }
  if ($content -ne $original) {
    Set-Content -Path $f.FullName -Value $content -Encoding UTF8 -NoNewline
    Write-Host "  modified: $($f.FullName.Substring($repo.Length))"
    $totalChanged++
  }
}
Write-Host "Total files modified: $totalChanged"

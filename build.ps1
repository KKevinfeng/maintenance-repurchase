# Build script: 使用 Nuitka 打包为 exe
# 要求: Python 3.10+ 且已安装 Nuitka (pip install nuitka)
# 输出: dist\main.dist\main.exe

$ErrorActionPreference = "Stop"

# 优先查找 workbuddy 自带的 Python（已预装 Nuitka）
$workbuddyPython = "$env:USERPROFILE\.workbuddy\binaries\python\versions\3.14.3\python.exe"
if (Test-Path $workbuddyPython) {
    $python = $workbuddyPython
    Write-Host "使用 workbuddy Python: $python" -ForegroundColor Green
} else {
    $python = "python"
    Write-Host "使用系统 Python" -ForegroundColor Yellow
}

Write-Host "开始打包..." -ForegroundColor Cyan

& $python -m nuitka `
    --standalone `
    --windows-console-mode=disable `
    --enable-plugin=tk-inter `
    --include-package-data=customtkinter `
    --include-data-files="CHANGELOG.txt=CHANGELOG.txt" `
    --include-data-files="README.md=README.md" `
    --remove-output `
    --output-dir=dist `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "打包完成! 输出目录: dist\main.dist\" -ForegroundColor Green
} else {
    Write-Host "打包失败，请检查错误信息" -ForegroundColor Red
}

# Build script: 使用 Nuitka 打包为 exe
# 要求: Python 3.10+ 且已安装 Nuitka (pip install nuitka)
# 输出: dist\main.dist\main.exe
#
# 说明：本脚本会先复制源码到一个干净的临时目录，排除运行时自动生成的缓存文件，
#      避免把用户本地数据（industry_dict.json、续保明细等）打包进 exe。
#
# 注意：本脚本必须保存为 UTF-8 with BOM 编码，否则 PowerShell 5.x 会乱码。
#       VS Code 右下角编码 → "Save with Encoding" → UTF-8 with BOM

$ErrorActionPreference = "Stop"

# 强制控制台 UTF-8 编码，防止中文乱码
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 优先查找 workbuddy 自带的 Python（已预装 Nuitka）
$workbuddyPython = "$env:USERPROFILE\.workbuddy\binaries\python\versions\3.14.3\python.exe"
if (Test-Path $workbuddyPython) {
    $python = $workbuddyPython
    Write-Host "使用 workbuddy Python: $python" -ForegroundColor Green
} else {
    $python = "python"
    Write-Host "使用系统 Python" -ForegroundColor Yellow
}

# 项目根目录
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$buildDir = Join-Path $env:TEMP "maintenance-repurchase-build-$timestamp"

Write-Host "准备干净构建目录: $buildDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

# 复制源码文件到临时目录（排除运行时缓存/日志/版本控制/旧构建产物）
$sourceItems = @(
    "main.py",
    "data_processor.py",
    "utils.py",
    "requirements.txt",
    "CHANGELOG.txt",
    "README.md",
    "RELEASE.md",
    "ui"
)

foreach ($item in $sourceItems) {
    $src = Join-Path $projectDir $item
    $dst = Join-Path $buildDir $item
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
    } else {
        Write-Warning "源文件不存在，已跳过: $src"
    }
}

Write-Host "开始打包..." -ForegroundColor Cyan

Push-Location $buildDir

try {
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

    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka 打包失败，退出码: $LASTEXITCODE"
    }

    # 把生成的 dist 目录复制回项目根目录
    $srcDist = Join-Path $buildDir "dist"
    $dstDist = Join-Path $projectDir "dist"
    if (Test-Path $dstDist) {
        Remove-Item -Recurse -Force $dstDist
    }
    Copy-Item -Path $srcDist -Destination $dstDist -Recurse -Force

    Write-Host "打包完成! 输出目录: $dstDist\main.dist\" -ForegroundColor Green
} finally {
    Pop-Location
    Write-Host "清理临时构建目录..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
}

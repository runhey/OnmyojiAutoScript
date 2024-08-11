[CmdletBinding()]
param (
    [string] $archiveName, [string] $targetName
)
# 外部环境变量包括:
# archiveName: ${{ matrix.qt_ver }}-${{ matrix.qt_arch }}


# archiveName: 5.15.2-win64_mingw81

$scriptDir = $PSScriptRoot
$currentDir = Get-Location
Write-Host "currentDir" $currentDir
Write-Host "scriptDir" $scriptDir

function Main() {

    New-Item -ItemType Directory $archiveName
    # 拷贝exe
    Copy-Item bin\release\* $archiveName\ -Force -Recurse | Out-Null
    # 拷贝依赖
    windeployqt --qmldir . --plugindir $archiveName\plugins --no-translations --compiler-runtime $archiveName\$targetName
    # 删除不必要的文件
    $excludeList = @("*.qmlc", "*.ilk", "*.exp", "*.lib", "*.pdb")
    Remove-Item -Path $archiveName -Include $excludeList -Recurse -Force
    # 打包zip
    Compress-Archive -Path $archiveName $archiveName'.zip'
}

if ($null -eq $archiveName || $null -eq $targetName) {
    Write-Host "args missing, archiveName is" $archiveName ", targetName is" $targetName
    return
}
Main

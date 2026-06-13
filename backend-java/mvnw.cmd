@echo off
REM Maven Wrapper for Windows
REM 首次运行会自动从Apache下载Maven到用户目录

set MAVEN_OPTS=-Xmx1024m

set "MVNW_REPOURL=https://repo.maven.apache.org/maven2"
set "MVNW_VERSION=3.2.0"
set "MVN_VERSION=3.9.6"

set "BASE_DIR=%~dp0"
set "MVNW_DIR=%USERPROFILE%\.m2\wrapper\dists\apache-maven-%MVN_VERSION%-bin"

REM 如果Maven未下载，先下载
if not exist "%MVNW_DIR%\apache-maven-%MVN_VERSION%\bin\mvn.cmd" (
    echo [Maven Wrapper] 首次运行，正在下载 Apache Maven %MVN_VERSION%...
    powershell -Command "& {Invoke-WebRequest -Uri '%MVNW_REPOURL%/org/apache/maven/apache-maven/%MVN_VERSION%/apache-maven-%MVN_VERSION%-bin.zip' -OutFile '%TEMP%\maven.zip'; Expand-Archive -Path '%TEMP%\maven.zip' -DestinationPath '%MVNW_DIR%' -Force}"
    echo [Maven Wrapper] Maven下载完成
)

REM 运行Maven
set "MVN_CMD=%MVNW_DIR%\apache-maven-%MVN_VERSION%\bin\mvn.cmd"

if not exist "%MVN_CMD%" (
    echo [ERROR] Maven安装失败，请手动安装Maven并添加到PATH
    exit /b 1
)

call "%MVN_CMD%" %*

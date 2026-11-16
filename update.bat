@echo off
REM Refresh the Title IV-E job postings site and publish it to GitHub.
REM Double-click this file, or run it from a terminal.
cd /d "%~dp0"

py -m ivejobs.build %*
if errorlevel 1 (
    echo.
    echo The update failed, so nothing was sent to GitHub.
    pause
    exit /b 1
)

echo.
echo Sending the updated site to GitHub...
git add -A
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Update job postings %date% %time:~0,5%"
    git push
    if errorlevel 1 (
        echo.
        echo Push to GitHub FAILED. Check your internet connection or GitHub login.
    ) else (
        echo GitHub updated.
    )
) else (
    echo No changes since the last update. GitHub is already current.
)

echo.
echo Open docs\index.html to view the site.
pause

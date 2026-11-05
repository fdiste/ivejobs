@echo off
REM Refresh the Title IV-E job postings site. Double-click this file, or run it from a terminal.
cd /d "%~dp0"
py -m ivejobs.build %*
echo.
echo Open docs\index.html to view the site.
pause

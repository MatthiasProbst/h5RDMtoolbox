@ECHO OFF

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help

if "%1" == "clean" (
    echo "Removing jupyter_execute"
    rmdir %SOURCEDIR%\jupyter_execute
)

REM sphinx-build -b html . _build:
if "%1" == "html" (
    %SPHINXBUILD% -b html %SOURCEDIR% %BUILDDIR% %SPHINXOPTS%
    goto end
)

if "%1" == "github" (
    %SPHINXBUILD% -M html %SOURCEDIR% %BUILDDIR% %SPHINXOPTS%
    robocopy %BUILDDIR%/html ../docs /E /XF *.ipynb> nul
    echo.Generated files copied to ../docs
    goto end
)

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	exit /b 1
)

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%

:end
popd

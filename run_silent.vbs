' ── Skyra Vision Service Silent Launcher ────────────────────────────────────
' Launches skyra-vision-service using pythonw.exe with no visible terminal window.
' Double-click this file to start the vision service as a stealth background daemon.
'
' Usage: Double-click run_silent.vbs
' Dependencies: Python must be installed and pythonw.exe must be in PATH.

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Resolve the directory of this VBScript to build relative path to src/main.py
Dim strDir
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Build the command: pythonw.exe runs Python without any console window
Dim strCommand
strCommand = "pythonw.exe """ & strDir & "\src\main.py"""

' Run with window style 0 = hidden, bWaitOnReturn = False
WshShell.Run strCommand, 0, False

Set WshShell = Nothing

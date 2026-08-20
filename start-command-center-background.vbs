Option Explicit

Dim fileSystem
Dim shell
Dim projectRoot
Dim backendCommand
Dim frontendCommand

Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectRoot = fileSystem.GetParentFolderName(WScript.ScriptFullName)

backendCommand = "cmd.exe /d /c ""cd /d """ & projectRoot & "\backend"" && """ & projectRoot & "\.venv\Scripts\python.exe"" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"""
frontendCommand = "cmd.exe /d /c ""cd /d """ & projectRoot & "\frontend"" && npm run dev -- --host"""

shell.Run backendCommand, 0, False
shell.Run frontendCommand, 0, False

Set shell = Nothing
Set fileSystem = Nothing

Option Explicit

Dim fileSystem
Dim shell
Dim projectRoot
Dim backendCommand
Dim frontendCommand

Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectRoot = fileSystem.GetParentFolderName(WScript.ScriptFullName)

AttemptDatabaseBackup

backendCommand = "cmd.exe /d /c ""cd /d """ & projectRoot & "\backend"" && """ & projectRoot & "\.venv\Scripts\python.exe"" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"""
frontendCommand = "cmd.exe /d /c ""cd /d """ & projectRoot & "\frontend"" && npm run dev -- --host"""

shell.Run backendCommand, 0, False
shell.Run frontendCommand, 0, False

Set shell = Nothing
Set fileSystem = Nothing

Function AttemptDatabaseBackup()
	Dim databasePath
	Dim backupFolder
	Dim backupPath
	Dim timestamp
	Dim currentTime
	Dim errorDescription

	AttemptDatabaseBackup = False
	databasePath = projectRoot & "\database\actions.db"
	backupFolder = projectRoot & "\backups"

	On Error Resume Next
	Err.Clear

	If Not fileSystem.FileExists(databasePath) Then
		errorDescription = "Database file was not found: " & databasePath
		LogBackupFailure backupFolder, errorDescription
		On Error GoTo 0
		Exit Function
	End If

	If Not fileSystem.FolderExists(backupFolder) Then
		fileSystem.CreateFolder backupFolder
		If Err.Number <> 0 Then
			errorDescription = "Could not create backup folder: " & Err.Description
			LogBackupFailure backupFolder, errorDescription
			On Error GoTo 0
			Exit Function
		End If
	End If

	currentTime = Now()
	timestamp = Year(currentTime) & "-" & TwoDigits(Month(currentTime)) & "-" & TwoDigits(Day(currentTime)) & "_" & TwoDigits(Hour(currentTime)) & TwoDigits(Minute(currentTime)) & TwoDigits(Second(currentTime))
	backupPath = GetBackupPath(backupFolder, timestamp)

	Err.Clear
	fileSystem.CopyFile databasePath, backupPath, False

	If Err.Number <> 0 Then
		errorDescription = "Could not create database backup: " & Err.Description
		LogBackupFailure backupFolder, errorDescription
		On Error GoTo 0
		Exit Function
	End If

	DeleteOlderBackups backupFolder

	On Error GoTo 0
	AttemptDatabaseBackup = True
End Function

Function GetBackupPath(backupFolder, timestamp)
	Dim backupPath
	Dim suffix

	backupPath = backupFolder & "\actions_" & timestamp & ".db"
	suffix = 1

	Do While fileSystem.FileExists(backupPath)
		backupPath = backupFolder & "\actions_" & timestamp & "_" & suffix & ".db"
		suffix = suffix + 1
	Loop

	GetBackupPath = backupPath
End Function

Function TwoDigits(value)
	TwoDigits = Right("0" & CStr(value), 2)
End Function

Sub DeleteOlderBackups(backupFolder)
	Dim folder
	Dim item
	Dim oldestFile
	Dim backupCount

	On Error Resume Next
	Err.Clear

	backupCount = 0
	Set folder = fileSystem.GetFolder(backupFolder)

	If Err.Number <> 0 Then
		LogBackupFailure backupFolder, "Could not inspect database backups: " & Err.Description
		On Error GoTo 0
		Exit Sub
	End If

	For Each item In folder.Files
		If IsDatabaseBackup(item.Name) Then
			backupCount = backupCount + 1
		End If
	Next

	Do While backupCount > 30
		Set oldestFile = Nothing

		For Each item In folder.Files
			If IsDatabaseBackup(item.Name) Then
				If oldestFile Is Nothing Then
					Set oldestFile = item
				ElseIf item.DateLastModified < oldestFile.DateLastModified Then
					Set oldestFile = item
				End If
			End If
		Next

		If oldestFile Is Nothing Then
			Exit Do
		End If

		Err.Clear
		fileSystem.DeleteFile oldestFile.Path, False

		If Err.Number <> 0 Then
			LogBackupFailure backupFolder, "Could not delete an older database backup: " & Err.Description
			Exit Do
		End If

		backupCount = backupCount - 1
	Loop

	On Error GoTo 0
End Sub

Sub LogBackupFailure(backupFolder, message)
	Dim logPath
	Dim logFile

	On Error Resume Next
	Err.Clear

	If Not fileSystem.FolderExists(backupFolder) Then
		fileSystem.CreateFolder backupFolder
	End If

	If Err.Number = 0 Then
		logPath = backupFolder & "\backup-failures.log"
		Set logFile = fileSystem.OpenTextFile(logPath, 8, True)
		If Err.Number = 0 Then
			logFile.WriteLine Now() & " - " & message
			logFile.Close
		End If
	End If

	On Error GoTo 0
End Sub

Function IsDatabaseBackup(fileName)
	IsDatabaseBackup = (LCase(Left(fileName, 8)) = "actions_" And LCase(Right(fileName, 3)) = ".db")
End Function

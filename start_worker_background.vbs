' DistributedMesh AI - Silent Worker Launcher
' Runs completely in the background with zero visible windows
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

quote = Chr(34)
pythonw = "pythonw.exe"

' Check common installation paths if pythonw is not in PATH
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
userProfile = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")

Dim candidates(7)
candidates(0) = "C:\Program Files\Python313\pythonw.exe"
candidates(1) = "C:\Program Files\Python312\pythonw.exe"
candidates(2) = "C:\Program Files\Python311\pythonw.exe"
candidates(3) = "C:\Program Files\Python310\pythonw.exe"
candidates(4) = localAppData & "\Programs\Python\Python313\pythonw.exe"
candidates(5) = localAppData & "\Programs\Python\Python312\pythonw.exe"
candidates(6) = localAppData & "\Programs\Python\Python311\pythonw.exe"
candidates(7) = localAppData & "\Programs\Python\Python310\pythonw.exe"

For Each cand In candidates
    If fso.FileExists(cand) Then
        pythonw = quote & cand & quote
        Exit For
    End If
Next

' Run silently without console window (0 = Hide window completely)
WshShell.Run pythonw & " -m worker.watchdog", 0, False

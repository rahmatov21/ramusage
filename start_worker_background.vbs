' DistributedMesh AI - Silent Worker Launcher
' Runs completely in the background with zero visible windows
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(strDir & "\worker\worker_node.py") Then
    strDir = "c:\Users\Abdulaziz\Desktop\All codes\ramusage"
End If

WshShell.CurrentDirectory = strDir

quote = Chr(34)
pythonw = "pythonw.exe"
If fso.FileExists("C:\Program Files\Python313\pythonw.exe") Then
    pythonw = quote & "C:\Program Files\Python313\pythonw.exe" & quote
End If

' Run silently without console window (0 = Hide window completely)
WshShell.Run pythonw & " -m worker.watchdog", 0, False

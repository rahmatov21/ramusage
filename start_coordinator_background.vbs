' DistributedMesh AI - Silent Coordinator Launcher
' Runs completely in the background with zero visible windows
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' 0 = Hide window completely
WshShell.Run "cmd.exe /c pythonw.exe -m coordinator.watchdog", 0, False

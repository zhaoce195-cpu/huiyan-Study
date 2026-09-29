Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(Wscript.ScriptFullName)
cmdLine = "cmd /c ""cd /d """ & currentDir & "\backend"" && set ""JAVA_HOME=" & currentDir & "\jdk-17"" && set ""PATH=" & currentDir & "\jdk-17\bin;" & currentDir & "\maven\bin;%PATH%"" && """ & currentDir & "\jdk-17\bin\java.exe"" -jar """ & currentDir & "\backend\target\huiyan-backend-1.0.0.jar""""
ws.Run cmdLine, 0, False
WScript.Sleep 6000
ws.Run "http://localhost:8000"

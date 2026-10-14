[Setup]
AppName=GyanSutr
AppVersion=0.1
DefaultDirName={localappdata}\GyanSutr
OutputBaseFilename=GyanSutrSetup
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\GyanSutr\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\GyanSutr"; Filename: "{app}\GyanSutr.exe"
Name: "{autodesktop}\GyanSutr"; Filename: "{app}\GyanSutr.exe"

[Run]
Filename: "{app}\GyanSutr.exe"; Description: "Launch GyanSutr"; Flags: nowait postinstall skipifsilent
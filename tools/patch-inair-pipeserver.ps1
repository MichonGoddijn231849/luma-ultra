param(
    [Parameter(Mandatory = $true)]
    [string]$InputAssembly,

    [Parameter(Mandatory = $true)]
    [string]$HelperAssembly,

    [Parameter(Mandatory = $true)]
    [string]$OutputAssembly
)

$ErrorActionPreference = "Stop"

function Get-MonoCecilPath {
    $candidates = @(
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\Extensions\TestPlatform\Extensions\Mono.Cecil.dll",
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\Common7\IDE\Extensions\TestPlatform\Extensions\Mono.Cecil.dll"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Mono.Cecil.dll was not found in the expected Visual Studio Build Tools locations."
}

Add-Type -Path (Get-MonoCecilPath)

$resolver = New-Object Mono.Cecil.DefaultAssemblyResolver
$resolver.AddSearchDirectory((Split-Path -Parent $InputAssembly))
$resolver.AddSearchDirectory((Split-Path -Parent $HelperAssembly))

$readerParameters = New-Object Mono.Cecil.ReaderParameters
$readerParameters.AssemblyResolver = $resolver

$input = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($InputAssembly, $readerParameters)
$helper = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($HelperAssembly, $readerParameters)

$serverType = $input.MainModule.Types | Where-Object { $_.FullName -eq "inair.dotnet.pipeserver.InAirPipeServer" }
if (-not $serverType) {
    throw "Could not find inair.dotnet.pipeserver.InAirPipeServer in $InputAssembly"
}

$pushSetDistance = $serverType.Methods | Where-Object { $_.Name -eq "PushSetDistance" }
if (-not $pushSetDistance) {
    throw "Could not find PushSetDistance in $InputAssembly"
}

$helperType = $helper.MainModule.Types | Where-Object { $_.FullName -eq "LumaUltra.InairPatchSupport.DistanceCommandDebouncer" }
if (-not $helperType) {
    throw "Could not find DistanceCommandDebouncer in $HelperAssembly"
}

$helperMethod = $helperType.Methods | Where-Object { $_.Name -eq "PushSetDistance" -and $_.Parameters.Count -eq 1 }
if (-not $helperMethod) {
    throw "Could not find DistanceCommandDebouncer.PushSetDistance(float) in $HelperAssembly"
}

$importedHelperMethod = $input.MainModule.ImportReference($helperMethod)

$body = $pushSetDistance.Body
$body.InitLocals = $false
$body.Variables.Clear()
$body.ExceptionHandlers.Clear()
$body.Instructions.Clear()

$processor = $body.GetILProcessor()
$processor.Append([Mono.Cecil.Cil.Instruction]::Create([Mono.Cecil.Cil.OpCodes]::Ldarg_1))
$processor.Append([Mono.Cecil.Cil.Instruction]::Create([Mono.Cecil.Cil.OpCodes]::Call, $importedHelperMethod))
$processor.Append([Mono.Cecil.Cil.Instruction]::Create([Mono.Cecil.Cil.OpCodes]::Ret))

$writerParameters = New-Object Mono.Cecil.WriterParameters
$input.Write($OutputAssembly, $writerParameters)

Write-Host "Patched $InputAssembly -> $OutputAssembly" -ForegroundColor Green

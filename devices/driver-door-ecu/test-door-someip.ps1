param(
    [string]$DoorIp = "192.168.88.101",
    [int]$DoorPort = 30501
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-DoorFrame {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$IsOpen
    )

    # Minimal SOME/IP UDP frame expected by driver-door-ecu.ino
    [byte[]]$frame = 0x43,0x01,0x80,0x02,0x00,0x00,0x00,0x09,
                     0xD0,0x01,0x00,0x01,0x01,0x01,0x02,0x00,
                     0x00

    $frame[16] = if ($IsOpen) { 0x01 } else { 0x00 }
    return $frame
}

function Send-DoorCommand {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$IsOpen,
        [Parameter(Mandatory = $true)]
        [string]$TargetIp,
        [Parameter(Mandatory = $true)]
        [int]$TargetPort
    )

    $frame = New-DoorFrame -IsOpen:$IsOpen
    $udp = [System.Net.Sockets.UdpClient]::new()
    try {
        [void]$udp.Send($frame, $frame.Length, $TargetIp, $TargetPort)
        $state = if ($IsOpen) { "OPEN" } else { "CLOSED" }
        Write-Host "Sent $state command to ${TargetIp}:$TargetPort" -ForegroundColor Green
        Write-Host ("Payload: {0}" -f (($frame | ForEach-Object { $_.ToString("X2") }) -join " "))
    }
    finally {
        $udp.Dispose()
    }
}

function Show-Menu {
    Write-Host ""
    Write-Host "Door SOME/IP UDP Tester" -ForegroundColor Cyan
    Write-Host "Target: ${DoorIp}:$DoorPort"
    Write-Host "[1] Open door"
    Write-Host "[2] Close door"
    Write-Host "[3] Set target IP"
    Write-Host "[4] Set target port"
    Write-Host "[5] Send open then close (2s gap)"
    Write-Host "[q] Quit"
}

$running = $true
while ($running) {
    Show-Menu
    $choice = Read-Host "Choose"

    switch ($choice) {
        "1" { Send-DoorCommand -IsOpen:$true -TargetIp $DoorIp -TargetPort $DoorPort }
        "2" { Send-DoorCommand -IsOpen:$false -TargetIp $DoorIp -TargetPort $DoorPort }
        "3" {
            $newIp = Read-Host "Enter door ECU IP"
            if (-not [string]::IsNullOrWhiteSpace($newIp)) {
                $DoorIp = $newIp.Trim()
                Write-Host "Target IP updated to $DoorIp" -ForegroundColor Yellow
            }
        }
        "4" {
            $newPort = Read-Host "Enter door ECU UDP port"
            $parsed = 0
            if ([int]::TryParse($newPort, [ref]$parsed) -and $parsed -gt 0 -and $parsed -le 65535) {
                $DoorPort = $parsed
                Write-Host "Target port updated to $DoorPort" -ForegroundColor Yellow
            }
            else {
                Write-Host "Invalid port. Keep current value: $DoorPort" -ForegroundColor Red
            }
        }
        "5" {
            Send-DoorCommand -IsOpen:$true -TargetIp $DoorIp -TargetPort $DoorPort
            Start-Sleep -Seconds 2
            Send-DoorCommand -IsOpen:$false -TargetIp $DoorIp -TargetPort $DoorPort
        }
        "q" { $running = $false }
        "Q" { $running = $false }
        default { Write-Host "Unknown option: $choice" -ForegroundColor Red }
    }
}

Write-Host "Bye." -ForegroundColor Cyan

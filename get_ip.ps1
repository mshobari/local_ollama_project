# Get IP addresses for remote access
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   IP Addresses for Connection" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get all network interfaces
$interfaces = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }

Write-Host "Available IP addresses for connection:" -ForegroundColor Green
Write-Host ""

foreach ($interface in $interfaces) {
    $adapter = Get-NetAdapter | Where-Object { $_.InterfaceIndex -eq $interface.InterfaceIndex }
    Write-Host "$($interface.IPAddress)" -ForegroundColor Yellow
    Write-Host "   Adapter: $($adapter.Name)" -ForegroundColor Gray
    Write-Host "   URL: http://$($interface.IPAddress):5000" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Connection Instructions:" -ForegroundColor Green
Write-Host "1. Make sure devices are on the same network" -ForegroundColor White
Write-Host "2. Use any of the IP addresses above" -ForegroundColor White
Write-Host "3. Add port :5000 to the IP address" -ForegroundColor White
Write-Host "4. Example: http://192.168.1.100:5000" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

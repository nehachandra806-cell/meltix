$file = 'd:\meltix\templates\profile.html'
$lines = Get-Content $file -Encoding UTF8

# SVG left arrow icon — clean, no emoji
$arrowSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>'

# Line 20 (0-indexed: 19) — back to shop button
$lines[19] = "        <a href=""/shop"" class=""back-btn"">$arrowSvg Back to Shop</a>"

$lines | Set-Content $file -Encoding UTF8
Write-Host "Done."

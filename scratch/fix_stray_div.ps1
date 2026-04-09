$file = 'd:\meltix\templates\profile.html'
$lines = Get-Content $file

# Line 343 (0-indexed: 342) is the stray </div> — remove it
$before  = $lines[0..341]                          # lines 1-342
$after   = $lines[343..($lines.Length - 1)]        # lines 344 onward

$newLines = $before + $after

$newLines | Set-Content $file -Encoding UTF8
Write-Host "Done. New total lines: $($newLines.Length)"

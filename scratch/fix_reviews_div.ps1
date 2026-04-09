$file = 'd:\meltix\templates\profile.html'
$lines = Get-Content $file

# Lines 342-358 (0-indexed: 341-357) contain the Jinja for-loop inside reviews-list
# We replace them with just the empty div (line 342 stays, lines 343-358 are removed and replaced)
# Keep lines 0-341 (before the div), add the empty div, then lines 358 onward

$before  = $lines[0..340]           # lines 1-341 (0-indexed 0..340)
$emptyDiv = '                <div id="reviews-list" class="review-list"></div>'
$after   = $lines[357..($lines.Length - 1)]  # from old line 358 onward

$newLines = $before + $emptyDiv + $after

$newLines | Set-Content $file -Encoding UTF8
Write-Host "Done. New total lines: $($newLines.Length)"

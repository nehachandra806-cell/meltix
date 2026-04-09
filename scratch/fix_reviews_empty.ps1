$file = 'd:\meltix\templates\profile.html'
$lines = Get-Content $file

# Line 343 (0-indexed: 342) has Jinja condition on reviews-empty div
# Replace: <div id="reviews-empty" class="empty-state" {% if recent_reviews %}style="display:none;"{% endif %}>
# With:    <div id="reviews-empty" class="empty-state">
$lines[342] = '                <div id="reviews-empty" class="empty-state">'

$lines | Set-Content $file -Encoding UTF8
Write-Host "Done."

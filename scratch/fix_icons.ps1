$file = 'd:\meltix\templates\profile.html'
$lines = Get-Content $file -Encoding UTF8

# SVG close (X) button — clean, no emoji
$closeSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'

# Better lock icon — padlock with keyhole
$lockSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1C9.24 1 7 3.24 7 6v1H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2h-2V6c0-2.76-2.24-5-5-5zm0 2c1.66 0 3 1.34 3 3v1H9V6c0-1.66 1.34-3 3-3zm0 9a2 2 0 1 1 0 4 2 2 0 0 1 0-4z"/></svg>'

# Fix line 370 — avatar modal close
$lines[369] = "            <button class=""modal-close"" id=""close-avatar-modal"" type=""button"" aria-label=""Close avatar gallery"">$closeSvg</button>"

# Fix line 397 — level-up modal close
$lines[396] = "            <button class=""modal-close"" id=""close-level-up-modal"" type=""button"" aria-label=""Close level up modal"">$closeSvg</button>"

# Fix line 411 — tracking modal close
$lines[410] = "            <button class=""modal-close"" id=""close-tracking-modal"" type=""button"" aria-label=""Close order tracking"">$closeSvg</button>"

# Fix line 437 — scent quiz modal close
$lines[436] = "            <button class=""modal-close"" id=""close-scent-quiz"" type=""button"" aria-label=""Close scent quiz"">$closeSvg</button>"

# Fix line 385 — avatar lock indicator with better icon
$lines[384] = "                    <span class=""avatar-lock-indicator"" {% if profile and profile.level and profile.level >= avatar.required_level %}hidden{% endif %}>$lockSvg</span>"

$lines | Set-Content $file -Encoding UTF8
Write-Host "Done. All modals and lock icons updated."

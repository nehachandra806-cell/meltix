import re

html_path = 'd:/meltix/templates/profile.html'
css_path = 'd:/meltix/static/profile.css'

with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

new_ui = """                    <div class="empty-state vault-empty-state">
                        <div class="empty-icon-ring">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                            </svg>
                        </div>
                        <p>Your vault is secured.</p>
                        <span>Complete active missions and elevate your atelier level to unlock exclusive reward codes.</span>
                        <button type="button" class="secondary-btn compact-btn" style="margin-top: 18px; padding: 6px 14px; min-height: 36px; font-size: 0.85rem;" onclick="document.getElementById('missions-grid').scrollIntoView({behavior: 'smooth'})">View Missions</button>
                    </div>"""

pattern = r'\n[ \t]*<div class="premium-empty-state".*?</div>'

new_html = re.sub(pattern, '\n' + new_ui, html_content, flags=re.DOTALL)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_html)

with open(css_path, 'a', encoding='utf-8') as f:
    f.write('''\n\n/* --- Premium Empty Vault --- */
.vault-empty-state {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3.5rem 1.5rem;
    border: 1px dashed rgba(242, 201, 138, 0.25);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(10, 6, 4, 0.3));
    border-radius: 24px;
    box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.2);
}

.empty-icon-ring {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    margin-bottom: 24px;
    display: grid;
    place-items: center;
    background: radial-gradient(circle, rgba(212, 163, 115, 0.12), rgba(20, 15, 10, 0.6));
    border: 1px solid rgba(212, 163, 115, 0.2);
    color: var(--accent-gold);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.empty-icon-ring svg {
    filter: drop-shadow(0 2px 8px rgba(242, 201, 138, 0.4));
}
''')

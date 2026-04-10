import re

with open('d:/meltix/templates/profile.html', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """                    <div class="premium-empty-state" style="text-align: center; padding: 50px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                        <h3 style="font-family: 'Playfair Display', serif; font-size: 1.6rem; color: #eaddcf; margin-bottom: 12px; font-weight: 400; letter-spacing: 0.5px;">
                            Your reward vault is empty.
                        </h3>
                        <p style="font-family: 'Lato', sans-serif; font-size: 0.95rem; color: #a89f91; line-height: 1.5; max-width: 380px; margin: 0 auto;">
                            Complete missions and elevate your atelier level to unlock exclusive discount codes.
                        </p>
                    </div>"""

pattern = r'\n[ \t]*<article class="coupon-ticket coupon-ticket-empty">.*?</article>'

new_content = re.sub(pattern, '\n' + replacement, content, flags=re.DOTALL)

with open('d:/meltix/templates/profile.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

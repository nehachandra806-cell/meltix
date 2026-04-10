import re
import codecs

html_path = 'd:/meltix/templates/hidden_message.html'
with codecs.open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# 1. UI element injection
ui_chunk = """                        <div class="price-block">
                            <p class="price-label">Price</p>
                            <p class="product-price-premium">₹ 500</p>
                        </div>
                        
                        <div class="custom-order-section" style="margin: 25px 0; padding-top: 20px; border-top: 1px solid rgba(220, 220, 240, 0.1);">
                            <div style="margin-bottom: 20px;">
                                <label for="secretMessageInput" style="display: block; font-family: 'Playfair Display', serif; color: var(--accent-gold); font-size: 1.2rem; margin-bottom: 10px; font-style: italic;">
                                    Write Your Hidden Message
                                </label>
                                <textarea id="secretMessageInput" rows="2" placeholder="e.g., Will you marry me? / Happy Anniversary!" style="width: 100%; padding: 15px; background: rgba(20, 20, 25, 0.6); border: 1px solid rgba(220, 220, 240, 0.2); border-radius: 8px; color: #fff; font-family: 'Lato', sans-serif; font-size: 1rem; resize: none; transition: border 0.3s ease; box-sizing: border-box;" onfocus="this.style.borderColor='var(--accent-gold)'" onblur="this.style.borderColor='rgba(220, 220, 240, 0.2)'"></textarea>
                                <span style="font-size: 0.8rem; color: #a89f91; margin-top: 5px; display: block;">*This message will magically appear inside the wax as it melts.</span>
                            </div>

                            <div style="display: flex; align-items: center; justify-content: space-between;">
                                <label style="font-family: 'Lato', sans-serif; color: #eaddcf; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px;">Quantity</label>
                                <div style="display: flex; align-items: center; background: rgba(20, 20, 25, 0.6); border: 1px solid rgba(220, 220, 240, 0.2); border-radius: 6px; overflow: hidden;">
                                    <button type="button" id="qtyMinus" style="background: none; border: none; color: #fff; padding: 10px 15px; cursor: pointer; font-size: 1.2rem; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='none'">-</button>
                                    <input type="number" id="qtyInput" value="1" min="1" readonly style="background: none; border: none; color: var(--accent-gold); text-align: center; width: 40px; font-weight: bold; font-size: 1.1rem; pointer-events: none;">
                                    <button type="button" id="qtyPlus" style="background: none; border: none; color: #fff; padding: 10px 15px; cursor: pointer; font-size: 1.2rem; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='none'">+</button>
                                </div>
                            </div>
                        </div>"""

pattern_ui = re.compile(r'[ \t]*<div class="price-block">.*?<p class="product-price-premium">₹ 500</p>\s*</div>', re.DOTALL)
if pattern_ui.search(html_content):
    html_content = pattern_ui.sub(ui_chunk, html_content, count=1)
else:
    print("WARNING: UI target not found!")

# 2. JS injection
js_chunk = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('secretMessageInput');
    // Select the main Add to Cart button (adjusted to the actual class used on this page)
    const addToCartBtn = document.querySelector('.magic-cart-btn'); 
    
    const qtyMinus = document.getElementById('qtyMinus');
    const qtyPlus = document.getElementById('qtyPlus');
    const qtyInput = document.getElementById('qtyInput');

    if (!addToCartBtn || !messageInput) return; // safeguard

    // Store original button text/styles
    const originalBtnText = addToCartBtn.innerHTML;

    // Initial Locked State
    function lockButton() {
        addToCartBtn.disabled = true;
        addToCartBtn.style.opacity = '0.5';
        addToCartBtn.style.cursor = 'not-allowed';
        addToCartBtn.style.background = '#333';
        addToCartBtn.style.border = '1px solid #555';
        addToCartBtn.innerHTML = 'Write Message to Unlock 🔒';
    }

    // Unlocked State
    function unlockButton() {
        addToCartBtn.disabled = false;
        addToCartBtn.style.opacity = '1';
        addToCartBtn.style.cursor = 'pointer';
        addToCartBtn.style.background = ''; // Revert to CSS
        addToCartBtn.style.border = ''; // Revert to CSS
        addToCartBtn.innerHTML = originalBtnText; // Restore original 'Add to Cart' and stars
    }

    // Apply initial state
    lockButton();
    
    // Listen for typing
    messageInput.addEventListener('input', () => {
        if (messageInput.value.trim().length > 0) {
            unlockButton();
        } else {
            lockButton();
        }
    });

    // Quantity Counter Logic
    if (qtyPlus && qtyMinus && qtyInput) {
        qtyPlus.addEventListener('click', () => {
            qtyInput.value = parseInt(qtyInput.value) + 1;
        });

        qtyMinus.addEventListener('click', () => {
            if (parseInt(qtyInput.value) > 1) {
                qtyInput.value = parseInt(qtyInput.value) - 1;
            }
        });
    }
});
</script>
</body>"""

if "</body>" in html_content:
    parts = html_content.rsplit("</body>", 1)
    html_content = js_chunk.join(parts)
else:
    print("WARNING: </body> not found!")

with codecs.open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print("SCRIPT EXECUTION COMPLETE")

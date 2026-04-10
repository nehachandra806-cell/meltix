import codecs

html_path = 'd:/meltix/templates/hidden_message.html'
with codecs.open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    // Listen for typing
    messageInput.addEventListener('input', () => {
        if (messageInput.value.trim().length > 0) {
            unlockButton();
        } else {
            lockButton();
        }
    });"""

replacement = """    // Listen for typing
    const charCounter = document.getElementById('charCounter');
    const MAX_CHARS = 20;

    messageInput.addEventListener('input', () => {
        let currentText = messageInput.value;
        let textLength = currentText.length;
        
        // Update Counter Text
        charCounter.innerText = textLength + '/' + MAX_CHARS;

        // Change color if approaching limit
        if (textLength >= MAX_CHARS) {
            charCounter.style.color = '#ff4d4d'; // Red when full
        } else {
            charCounter.style.color = 'var(--accent-gold)'; // Normal gold
        }

        // Lock/Unlock Logic (must have at least 1 valid char)
        if (currentText.trim().length > 0 && textLength <= MAX_CHARS) {
            unlockButton();
        } else {
            lockButton();
        }
    });"""

if target in content:
    content = content.replace(target, replacement)
    with codecs.open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS")
else:
    print("TARGET NOT FOUND!")
    print("Printing context to inspect:")
    print(content[-500:])


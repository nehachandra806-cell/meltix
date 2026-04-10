import codecs

html_path = 'd:/meltix/templates/hidden_message.html'
with codecs.open(html_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = "addToCartBtn.innerHTML = 'Write Message to Unlock 🔒';"
replacement = "addToCartBtn.innerHTML = 'Enter Message to Unlock 🔒';"

if target in text:
    text = text.replace(target, replacement)
    with codecs.open(html_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("REPLACED")
else:
    print("NOT FOUND")

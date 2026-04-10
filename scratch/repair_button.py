import codecs

html_path = 'd:/meltix/templates/hidden_message.html'
with codecs.open(html_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The missing content to insert at index 184 (which is line 185)
missing_content = """                        </div>
                        <button class="magic-cart-btn">
                            ADD TO CART
                            <div class="star-1">
                                <svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" version="1.1" style="shape-rendering:geometricPrecision; text-rendering:geometricPrecision; image-rendering:optimizeQuality; fill-rule:evenodd; clip-rule:evenodd" viewBox="0 0 784.11 815.53" xmlns:xlink="http://www.w3.org/1999/xlink"><g id="Layer_x0020_1"><path class="fil0" d="M392.05 0c-20.9,210.08 -184.06,378.41 -392.05,407.78 207.96,29.37 371.12,197.68 392.05,407.74 20.93,-210.06 184.09,-378.37 392.05,-407.74 -207.98,-29.38 -371.16,-197.69 -392.06,-407.78z"></path></g></svg>
                            </div>
                            <div class="star-2">
                                <svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" version="1.1" style="shape-rendering:geometricPrecision; text-rendering:geometricPrecision; image-rendering:optimizeQuality; fill-rule:evenodd; clip-rule:evenodd" viewBox="0 0 784.11 815.53" xmlns:xlink="http://www.w3.org/1999/xlink"><g id="Layer_x0020_1"><path class="fil0" d="M392.05 0c-20.9,210.08 -184.06,378.41 -392.05,407.78 207.96,29.37 371.12,197.68 392.05,407.74 20.93,-210.06 184.09,-378.37 392.05,-407.74 -207.98,-29.38 -371.16,-197.69 -392.06,-407.78z"></path></g></svg>
                            </div>
                            <div class="star-3">
                                <svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" version="1.1" style="shape-rendering:geometricPrecision; text-rendering:geometricPrecision; image-rendering:optimizeQuality; fill-rule:evenodd; clip-rule:evenodd" viewBox="0 0 784.11 815.53" xmlns:xlink="http://www.w3.org/1999/xlink"><g id="Layer_x0020_1"><path class="fil0" d="M392.05 0c-20.9,210.08 -184.06,378.41 -392.05,407.78 207.96,29.37 371.12,197.68 392.05,407.74 20.93,-210.06 184.09,-378.37 392.05,-407.74 -207.98,-29.38 -371.16,-197.69 -392.06,-407.78z"></path></g></svg>
                            </div>
                            <div class="star-4">
                                <svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" version="1.1" style="shape-rendering:geometricPrecision; text-rendering:geometricPrecision; image-rendering:optimizeQuality; fill-rule:evenodd; clip-rule:evenodd" viewBox="0 0 784.11 815.53" xmlns:xlink="http://www.w3.org/1999/xlink"><g id="Layer_x0020_1"><path class="fil0" d="M392.05 0c-20.9,210.08 -184.06,378.41 -392.05,407.78 207.96,29.37 371.12,197.68 392.05,407.74 20.93,-210.06 184.09,-378.37 392.05,-407.74 -207.98,-29.38 -371.16,-197.69 -392.06,-407.78z"></path></g></svg>
                            </div>\n"""

# Delete line 185
del lines[184]

# Insert missing content
lines.insert(184, missing_content)

with codecs.open(html_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("REPAIR COMPLETE!")


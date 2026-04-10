import codecs
import re

html_path = 'd:/meltix/templates/hidden_message.html'
with codecs.open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# I will find the custom-order-section using a regex properly
# It spans from <div class="custom-order-section" ... to the matching closing div.
# Because there are internal divs, I'll extract it using a string find based on exact start/end chunks since I know the exact boundaries.

start_marker = '                        <div class="custom-order-section"'
end_marker = '                        </div>\n                        <button class="magic-cart-btn">'

# Let's cleanly split out the block
if start_marker in content and end_marker in content:
    start_index = content.find(start_marker)
    end_index = content.find(end_marker) + len('                        </div>\n')
    
    custom_block = content[start_index:end_index]
    
    # 1. Remove it from its current position
    content = content[:start_index] + content[end_index:]
    
    # 2. Insert it just above <div class="purchase-section">
    target_insert = '                    <div class="purchase-section">'
    insert_index = content.find(target_insert)
    
    if insert_index != -1:
        content = content[:insert_index] + custom_block + content[insert_index:]
        with codecs.open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS")
    else:
        print("FAILED: Target insert not found")
else:
    print("FAILED: start_marker or end_marker not found")

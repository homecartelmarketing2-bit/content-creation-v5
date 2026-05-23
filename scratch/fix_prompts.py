import os
with open('config/prompts.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_prompt = False
for line in lines:
    if line.startswith('PRODUCT_CLOSEUP_FEEDS_PROMPT = '):
        in_prompt = True
        new_lines.append('PRODUCT_CLOSEUP_FEEDS_PROMPT = "Use the first image strictly as a layout, composition, and crop reference. Extract the product (chandelier) from the second image and place it seamlessly into this exact layout style on a pure plain white background. [{caption}]"\n')
        continue
    
    if in_prompt:
        if '"""' in line:
            in_prompt = False
        continue
    
    new_lines.append(line)

with open('config/prompts.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
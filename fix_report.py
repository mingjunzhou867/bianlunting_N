import sys, re, copy
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document

doc = Document('作品报告.docx')

# Helper: replace text in a paragraph while preserving formatting
def replace_in_paragraph(para, old, new):
    """Replace text in paragraph, handling text split across runs."""
    full_text = para.text
    if old not in full_text:
        return False
    
    # Try simple single-run replacement first
    for run in para.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return True
    
    # If split across runs, rebuild
    new_text = full_text.replace(old, new)
    # Clear all runs and set text on first run
    if para.runs:
        para.runs[0].text = new_text
        for run in para.runs[1:]:
            run.text = ''
    return True

changes = []

for i, p in enumerate(doc.paragraphs):
    text = p.text
    
    # === Fix 1: Renumber figures 3->4 through 16->17 (reverse order to avoid conflicts) ===
    for old_num in range(16, 2, -1):  # 16, 15, 14, ..., 3
        new_num = old_num + 1
        # Figure captions: "图 N " at start of paragraph
        old_str = f'图 {old_num} '
        new_str = f'图 {new_num} '
        if text.startswith(old_str):
            replace_in_paragraph(p, old_str, new_str)
            changes.append(f'段落{i}: 图 {old_num} -> 图 {new_num}')
            text = p.text  # Update text after replacement
        
        # Inline references: "图N}" or "图N}" (no space)
        old_inline = f'图{old_num}'
        new_inline = f'图{new_num}'
        if old_inline in text and not text.startswith('图'):
            replace_in_paragraph(p, old_inline, new_inline)
            changes.append(f'段落{i}: inline 图{old_num} -> 图{new_num}')
            text = p.text

    # === Fix 2: Remove trailing 顿号 from captions ===
    if text.startswith('图') and text.endswith('、'):
        replace_in_paragraph(p, '、', '')
        changes.append(f'段落{i}: removed trailing 顿号 from figure caption')
    
    if text.startswith('表') and text.endswith('、'):
        replace_in_paragraph(p, '、', '')
        changes.append(f'段落{i}: removed trailing 顿号 from table caption')

    # === Fix 3: Fix extra spaces before commas ===
    if ' ,' in text or ' , ' in text:
        replace_in_paragraph(p, ' ,', ',')
        replace_in_paragraph(p, ' , ', ',')
        changes.append(f'段落{i}: fixed extra space before comma')

# Save
doc.save('作品报告_fixed.docx')

print('=== Changes made ===')
for c in changes:
    print(c)
print(f'\nTotal: {len(changes)} changes')
print('Saved to: 作品报告_fixed.docx')

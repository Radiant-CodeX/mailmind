"""Merge all 5 parts into final MailMind_Documentation.pdf."""
import os
from pypdf import PdfWriter, PdfReader

parts = [
    'part1_overview.pdf',
    'part2_diagrams.pdf',
    'part3_backend.pdf',
    'part4_services.pdf',
    'part5_reference.pdf',
]

base = os.path.dirname(__file__)
writer = PdfWriter()

for part in parts:
    path = os.path.join(base, part)
    if not os.path.exists(path):
        print(f'[MISSING] {path}')
        continue
    reader = PdfReader(path)
    for page in reader.pages:
        writer.add_page(page)
    print(f'[+] {part} ({len(reader.pages)} pages)')

out = os.path.join(base, 'MailMind_Documentation.pdf')
with open(out, 'wb') as f:
    writer.write(f)

print(f'\n[DONE] {out}')
total = sum(1 for _ in PdfReader(out).pages)
print(f'       Total pages: {total}')

import re

bib_file_path = 'arxivcdct/cdct_references.bib'

with open(bib_file_path, 'r') as f:
    bib_content = f.read()

bib_keys = re.findall(r'@\w+\s*\{\s*([^,]+),', bib_content)

print(f"Found {len(bib_keys)} keys:")
for key in bib_keys:
    print(key)

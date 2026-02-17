import re

tex_file_path = 'arxivcdct/CDCT_2_0_arxiv.tex'
bib_file_path = 'arxivcdct/cdct_references.bib'

with open(tex_file_path, 'r') as f:
    tex_content = f.read()

with open(bib_file_path, 'r') as f:
    bib_content = f.read()

print("--- BIB CONTENT ---")
print(bib_content)
print("--- END BIB CONTENT ---")

# Find all \citep{...} and \cite{...}
tex_citations = re.findall(r'\\cite[p|t]?{([^}]+)}', tex_content)
# Split citations like \citep{key1,key2}
tex_keys = set()
for citation in tex_citations:
    keys = [key.strip() for key in citation.split(',')]
    tex_keys.update(keys)

# Find all @...@{key, ...}
# I will use a more robust regex that handles different whitespace.
bib_keys = set(re.findall(r'@\\w+\s*{\s*([^,]+),', bib_content))

# Find duplicate bib keys
bib_keys_list = re.findall(r'@\\w+\s*{\s*([^,]+),', bib_content)
duplicates = set([key for key in bib_keys_list if bib_keys_list.count(key) > 1])

missing_in_bib = tex_keys - bib_keys
unused_in_tex = bib_keys - tex_keys

print(f"Citations in .tex file: {len(tex_keys)}")
print(f"References in .bib file: {len(bib_keys)}")
print("-" * 20)

if missing_in_bib:
    print(f"ERROR: Found {len(missing_in_bib)} citations in .tex file that are MISSING from .bib file:")
    for key in sorted(missing_in_bib):
        print(f"  - {key}")
else:
    print("OK: All citations in the .tex file are present in the .bib file.")

print("-" * 20)

if unused_in_tex:
    print(f"WARNING: Found {len(unused_in_tex)} UNUSED references in .bib file (defined but not cited):")
    for key in sorted(unused_in_tex):
        print(f"  - {key}")
else:
    print("OK: All references in the .bib file are cited in the paper.")

print("-" * 20)

if duplicates:
    print(f"ERROR: Found {len(duplicates)} DUPLICATE keys in .bib file:")
    for key in sorted(duplicates):
        print(f"  - {key}")
else:
    print("OK: No duplicate keys found in the .bib file.")

import fitz  # PyMuPDF
import re
import pandas as pd

# Extend this list if you have more known product prefixes
KNOWN_MODEL_PREFIXES = [
    "IDA8C", "IDA8S", "IDA8SAB", "IDA8SL",
    "IDA8SAB-SW", "DIVA-8MG2"
]

def extract_model_numbers(pdf_path, output_excel, custom_prefixes=None):
    # Use custom prefixes if provided
    prefixes = KNOWN_MODEL_PREFIXES.copy()
    if custom_prefixes:
        prefixes.extend(custom_prefixes)

    # Sort prefixes by length descending and escape special chars
    prefix_pattern = '|'.join(sorted(map(re.escape, prefixes), key=len, reverse=True))

    # Open PDF and extract all text
    with fitz.open(pdf_path) as doc:
        full_text = "".join(page.get_text() for page in doc)

    # Regex: matches full model numbers starting with exact prefixes
    model_pattern = rf'\b(?:{prefix_pattern})[0-9A-Z\-]*\b'
    matches = re.findall(model_pattern, full_text)

    # Clean: remove duplicates, too short, or all-digit
    models = {m.strip() for m in matches if len(m.strip()) > 4 and not m.strip().isdigit()}

    # Save to Excel
    df = pd.DataFrame(sorted(models), columns=['Model Number'])
    df.to_excel(output_excel, index=False)

    print(f"✅ Extracted {len(models)} model numbers → {output_excel}")
    return sorted(models)

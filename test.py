import fitz  # PyMuPDF
import pandas as pd
import os

# ==== CONFIGURATION ====
excel_path = "./uploads/PA_VA_test.xlsx"  # <-- Your Excel file
pdf_path = "E:/Projects/image ui project 1/image ui project 1/image ui project 1/uploads/PAVA_catalogue-_en_eu_v6.04_web.pdf"                       # <-- Your Product Catalog PDF
output_dir = "extracted_images"
output_excel_path = "Unstockit_Inventory_with_Images.xlsx"
os.makedirs(output_dir, exist_ok=True)

# ==== STEP 1: Read Excel ====
df = pd.read_excel(excel_path)
df["Image File"] = None  # Add column to store matched image filenames

# ==== STEP 2: Extract Images from PDF ====
doc = fitz.open(pdf_path)
image_map = []

for page_number in range(len(doc)):
    page = doc[page_number]
    images = page.get_images(full=True)
    
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        image_filename = f"page{page_number+1}_img{img_index+1}.{image_ext}"
        image_path = os.path.join(output_dir, image_filename)

        # Save image
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        
        image_map.append({
            "page": page_number + 1,
            "filename": image_filename,
            "width": base_image.get("width"),
            "height": base_image.get("height")
        })

print(f"✅ Extracted {len(image_map)} images.")

# ==== STEP 3: (Manual or Rule-Based) Matching ====
# Example: Match image from page 1 to part number 3400
matched_part = "3400"
matched_image = "page1_img1.jpeg"
df.loc[df["Part Number/SKU"] == int(matched_part), "Image File"] = matched_image

# ==== STEP 4: Save Updated Excel ====
df.to_excel(output_excel_path, index=False)
print(f"✅ Excel updated and saved to: {output_excel_path}")
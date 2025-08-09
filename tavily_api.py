import os
import re
import json
import requests
import pandas as pd
from io import BytesIO
from PIL import Image, ImageEnhance
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_API_URL = "https://api.tavily.com/search"
NUM_IMAGES = 1

def search_tavily_data(query):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}"
    }
    payload = {
        "query": query,
        "search_depth": "advanced",
        "include_images": True,
        "include_answer": True
    }
    try:
        res = requests.post(TAVILY_API_URL, json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()
        return data.get("images", []), data.get("answer", "")
    except Exception as e:
        print("❌ Tavily API Error:", e)
        return [], ""

def extract_price(text):
    if not text:
        return "N/A"
    
    matches = re.findall(r'[$₹€]\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?[$₹€]', text)
    return matches[0] if matches else "Price not found"

def download_image(url, model_name):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail((500, 500))
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        img = ImageEnhance.Contrast(img).enhance(1.1)

        # Only replace forward slashes for path safety, keep spaces
        filename = f"{model_name.replace('/', '_')}.jpg"
        # Ensure the downloaded_images directory exists
        os.makedirs("downloaded_images", exist_ok=True)
        # Save the image with the original filename (spaces preserved)
        img.save(os.path.join("downloaded_images", filename), quality=95)

    except Exception as e:
        print(f"❌ Failed to download image for {model_name}: {e}")

def scrape_images_for_models_get_options(excel_path, limit=5):
    df = pd.read_excel(excel_path)

    # Ensure required columns exist
    for col in ['Description', 'Price', 'Specifications']:
        if col not in df.columns:
            df[col] = ""

    image_options = {}
    limited_df = df.head(limit) if limit else df

    for index, row in limited_df.iterrows():
        model = str(row["Model Number"]).strip()
        current_desc = str(row.get("Description", "")).strip()
        current_price = str(row.get("Price", "")).strip()
        current_specs = str(row.get("Specifications", "")).strip()

        if not model:
            continue

        print(f"\n🔍 Fetching for: {model}")
        prompts = [
            f"{model} ceiling speaker product photo",
            f"{model} audio loudspeaker product image",
            f"{model} ceiling mount speaker image",
            f"{model} white commercial speaker photo",
            f"white ceiling loudspeaker like {model}"
        ]

        collected_urls = []
        filled_description = current_desc if current_desc and current_desc.lower() != "nan" else None
        filled_price = current_price if current_price and current_price.lower() != "nan" else None
        filled_spec = current_specs if current_specs and current_specs.lower() != "nan" else None

        for prompt in prompts:
            images, answer = search_tavily_data(prompt)
            urls = [img["url"] if isinstance(img, dict) else img for img in images]

            for url in urls:
                if url.startswith("http") and url not in collected_urls:
                    collected_urls.append(url)

            if not filled_description and answer:
                filled_description = answer.strip()

            if not filled_price and answer:
                filled_price = extract_price(answer)

            if not filled_spec and answer:
                spec_match = re.findall(r"(specifications?:|•|\n\s*[-*])(.{20,})", answer, flags=re.IGNORECASE)
                spec_text = ""
                if spec_match:
                    spec_text = "\n".join([s[1].strip() for s in spec_match])
                elif len(answer) > 300:
                    spec_text = answer.strip()[-300:]  # fallback
                filled_spec = spec_text.strip()

            if len(collected_urls) >= 5:
                break

        image_options[model] = collected_urls[:5]
        df.at[index, "Description"] = filled_description or "Description not available."
        df.at[index, "Price"] = filled_price or "N/A"
        df.at[index, "Specifications"] = filled_spec or "Not available"

    df.to_excel(excel_path, index=False)
    return image_options

def generate_prompt(brand, part, description):
    return f"{brand} {part} {description}. High resolution product photo, isolated on white background, no watermark, centered, e-commerce quality"

def search_images_with_tavily(query_text):
    url = 'https://api.tavily.com/search'
    payload = {
        'api_key': TAVILY_API_KEY,
        'query': query_text,
        'search_depth': 'advanced',
        'include_images': True,
        'num_images': NUM_IMAGES
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json().get('images', [])

def download_image_for_excel(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return BytesIO(response.content)

def run_scraper(input_file, output_file, data_excel_file, log_func=None):
    df = pd.read_excel(input_file)
    df.columns = df.columns.str.strip()
    
    # Dictionary to store scraped image data
    scraped_images = {}

    # Standardize column names
    col_map = {
        'id_col': 'Part Number',
        'price_col': 'Unit Price',
        'brand_col': 'Brand',
        'qty_col': 'Qty',
        'desc_col': 'Description'
    }

    # Auto-map columns if different names are found
    for col in df.columns:
        if 'manufacturer' in col.lower():
            col_map['brand_col'] = col
        elif 'part' in col.lower() and 'number' in col.lower():
            col_map['id_col'] = col
        elif 'cost' in col.lower() or 'price' in col.lower():
            col_map['price_col'] = col
        elif 'quantity' in col.lower() or 'qty' in col.lower():
            col_map['qty_col'] = col
        elif 'description' in col.lower():
            col_map['desc_col'] = col

    wb = Workbook()
    ws = wb.active
    ws.title = 'Products with Images'

    # Write headers
    headers = [
        col_map['id_col'],
        col_map['brand_col'],
        col_map['desc_col'],
        col_map['price_col'],
        col_map['qty_col'],
        'Image URL',
        'Image'
    ]
    
    for col_idx, col_name in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=col_name)

    # Process each row
    for idx, row in df.iterrows():
        row_num = idx + 2
        part = str(row[col_map['id_col']]).strip()
        brand = str(row[col_map['brand_col']]).strip()
        desc = str(row[col_map['desc_col']]).strip()
        price = str(row[col_map['price_col']]).strip()
        qty = str(row[col_map['qty_col']]).strip()

        # Write data to cells
        ws.cell(row=row_num, column=1, value=part)
        ws.cell(row=row_num, column=2, value=brand)
        ws.cell(row=row_num, column=3, value=desc)
        ws.cell(row=row_num, column=4, value=price)
        ws.cell(row=row_num, column=5, value=qty)

        if log_func:
            log_func(f"🔄 Scraping image for Part #{part}")

        try:
            urls = search_images_with_tavily(generate_prompt(brand, part, desc))
            if urls:
                img_url = urls[0]
                ws.cell(row=row_num, column=6, value=img_url)

                img_data = download_image_for_excel(img_url)
                img_data.seek(0)
                img_pil = Image.open(img_data)
                
                # Convert to RGB if the image has an alpha channel
                if img_pil.mode in ('RGBA', 'LA') or (img_pil.mode == 'P' and 'transparency' in img_pil.info):
                    img_pil = img_pil.convert('RGB')
                
                img_pil.thumbnail((500, 500))
                
                # Create the downloaded_images directory if it doesn't exist
                os.makedirs("downloaded_images", exist_ok=True)
                
                # Determine file extension from URL or content type
                file_ext = 'jpg'  # default
                if img_url.lower().endswith('.webp'):
                    file_ext = 'webp'
                elif img_url.lower().endswith(('.png', '.jpeg', '.gif')):
                    file_ext = img_url.lower().rsplit('.', 1)[1]
                
                # Save the image with the original filename (spaces preserved)
                filename = f"{part.replace('/', '_')}.{file_ext}"
                save_path = os.path.join("downloaded_images", filename)
                
                # Save in the appropriate format
                format_map = {
                    'jpg': 'JPEG',
                    'jpeg': 'JPEG',
                    'png': 'PNG',
                    'webp': 'WEBP',
                    'gif': 'GIF'
                }
                
                # Default to JPEG if format not recognized
                save_format = format_map.get(file_ext.lower(), 'JPEG')
                img_pil.save(save_path, format=save_format, quality=90)
                
                # Store image data for database
                if part not in scraped_images:
                    scraped_images[part] = []
                    
                # Read the saved file to get the final binary data
                with open(save_path, 'rb') as f:
                    img_binary = f.read()
                    
                scraped_images[part].append({
                    'url': img_url,
                    'data': img_binary,  # Use the actual saved binary data
                    'filename': filename
                })

                img_data.seek(0)
                xl_img = XLImage(img_data)
                xl_img.width = 150
                xl_img.height = 150
                ws.add_image(xl_img, f"G{row_num}")
                ws.row_dimensions[row_num].height = 180

        except Exception as e:
            if log_func:
                log_func(f"❌ Error scraping Part #{part}: {type(e).__name__} - {e}")

    wb.save(output_file)

    # Create simplified data Excel for frontend
    simplified_df = pd.DataFrame()
    simplified_df['Model Number'] = df[col_map['id_col']]
    simplified_df['Brand'] = df[col_map['brand_col']]
    simplified_df['Description'] = df[col_map['desc_col']]
    simplified_df['Price'] = df[col_map['price_col']]
    simplified_df['Qty'] = df[col_map['qty_col']]
    
    # Add image URLs to the simplified data
    image_urls = []
    for part in simplified_df['Model Number']:
        if part in scraped_images and scraped_images[part]:
            image_urls.append(scraped_images[part][0]['url'])
        else:
            image_urls.append('')
    simplified_df['Image URL'] = image_urls
    
    simplified_df.to_excel(data_excel_file, index=False)
    
    # Return the scraped images data
    return scraped_images
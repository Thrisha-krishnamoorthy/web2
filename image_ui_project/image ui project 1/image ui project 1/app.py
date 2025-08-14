import os
import pandas as pd
import pickle
from flask import Flask, render_template, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from urllib.parse import unquote
from dotenv import load_dotenv

from extractor import extract_model_numbers
from tavily_api import scrape_images_for_models_get_options, download_image, run_scraper
from final_excel_builder import create_final_excel

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
EXCEL_FOLDER = 'excels'
IMAGE_FOLDER = 'downloaded_images'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXCEL_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

@app.route('/')
def home():
    return redirect('/product-ui')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect('/upload-options')
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/product-ui')

@app.route('/upload-options')
def upload_options():
    if not session.get('logged_in'):
        return redirect('/login')
    return render_template('upload_options.html')

@app.route('/upload-pdf', methods=['GET', 'POST'])
def upload_pdf():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        file = request.files.get('pdf_file')
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            model_excel = os.path.join(EXCEL_FOLDER, 'models.xlsx')
            scraped_data_excel = os.path.join(EXCEL_FOLDER, 'scraped_data.xlsx')

            models = extract_model_numbers(file_path, model_excel)
            pd.DataFrame({'Model Number': models}).to_excel(scraped_data_excel, index=False)

            image_options = scrape_images_for_models_get_options(scraped_data_excel)
            with open('image_options.pkl', 'wb') as f:
                pickle.dump(image_options, f)

            session['excel_path'] = scraped_data_excel
            session['final_excel_path'] = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output.xlsx')
            session['data_excel_path'] = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')

            return redirect('/select-images')

    return render_template('upload_pdf.html')



@app.route('/upload-excel', methods=['GET', 'POST'])
def upload_excel():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file:
            filename = secure_filename(file.filename)
            excel_path = os.path.join(EXCEL_FOLDER, filename)
            file.save(excel_path)

            output_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output.xlsx')
            output_data_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')

            run_scraper(excel_path, output_excel, output_data_excel, log_func=print)
            return redirect('/product-ui')

    return render_template('upload_excel.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        pdf = request.files.get('pdf_file')
        excel = request.files.get('excel_file')

        if not pdf or not excel:
            return "Please upload both files."

        # Save files
        pdf_filename = secure_filename(pdf.filename)
        excel_filename = secure_filename(excel.filename)

        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
        excel_path = os.path.join(EXCEL_FOLDER, excel_filename)

        pdf.save(pdf_path)
        excel.save(excel_path)

        # Process PDF
        model_excel = os.path.join(EXCEL_FOLDER, 'models.xlsx')
        scraped_data_excel = os.path.join(EXCEL_FOLDER, 'scraped_data.xlsx')
        models = extract_model_numbers(pdf_path, model_excel)
        pd.DataFrame({'Model Number': models}).to_excel(scraped_data_excel, index=False)

        image_options = scrape_images_for_models_get_options(scraped_data_excel)
        with open('image_options.pkl', 'wb') as f:
            pickle.dump(image_options, f)

        # Process Excel
        output_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output.xlsx')
        output_data_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')
        run_scraper(excel_path, output_excel, output_data_excel, log_func=print)

        session['excel_path'] = scraped_data_excel
        session['final_excel_path'] = output_excel
        session['data_excel_path'] = output_data_excel

        return redirect('/select-images')

    return render_template('upload.html')


@app.route('/select-images', methods=['GET', 'POST'])
def select_images():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        excel_path = session.get('excel_path')
        output_excel = session.get('final_excel_path')
        data_excel = session.get('data_excel_path')

        with open('image_options.pkl', 'rb') as f:
            image_options = pickle.load(f)

        df = pd.read_excel(excel_path, engine='openpyxl')

        for model in image_options:
            selected_url = request.form.get(model)
            if selected_url and selected_url != "skip":
                df.loc[df['Model Number'] == model, 'Image URL'] = selected_url
                download_image(selected_url, model)

        df.to_excel(excel_path, index=False)
        create_final_excel(excel_path, output_excel, data_excel)

        return redirect('/product-ui')

    with open('image_options.pkl', 'rb') as f:
        image_options = pickle.load(f)

    return render_template('select_images.html', image_options=image_options)

@app.route('/product-ui')
def product_ui():
    query = request.args.get('q', '').strip().lower()
    excel_path = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')

    if not os.path.exists(excel_path):
        return render_template('product_ui.html', products=[], search_query=query, logged_in=session.get('logged_in', False))

    df = pd.read_excel(excel_path, engine='openpyxl')
    products = []

    # Standardized column names
    id_col = 'Model Number' if 'Model Number' in df.columns else 'Part Number'
    price_col = 'Price' if 'Price' in df.columns else 'Unit Price'
    brand_col = 'Brand'
    qty_col = 'Qty' if 'Qty' in df.columns else 'Quantity'

    for _, row in df.iterrows():
        model = str(row.get(id_col, '')).strip()
        price = str(row.get(price_col, '')).strip()
        brand = str(row.get(brand_col, '')).strip()
        qty = str(row.get(qty_col, '')).strip()

        if not model:
            continue

        if price.lower() in ['nan', '', 'none']:
            price = "Price not available"

        model_safe = model.replace('/', '_').replace(' ', '_')

        img_file = f"{model_safe}.jpg"
        if not os.path.exists(os.path.join(IMAGE_FOLDER, img_file)):
            img_file = f"{model_safe}.png"

        image_path = f"/{IMAGE_FOLDER}/{img_file}" if os.path.exists(os.path.join(IMAGE_FOLDER, img_file)) else "/static/default.jpg"

        if query and query not in model.lower() and query not in price.lower():
            continue

        products.append({
            "model": model,
            "image": image_path,
            "price": price,
            "brand": brand,
            "qty": qty
        })

    return render_template('product_ui.html', products=products, search_query=query, logged_in=session.get('logged_in', False))

@app.route('/product/<path:model>')
def product_detail(model):
    model = unquote(model)
    excel_path = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')

    if not os.path.exists(excel_path):
        return "❌ Excel file not found."

    df = pd.read_excel(excel_path, engine='openpyxl')
    
    # Standardized column names
    id_col = 'Model Number' if 'Model Number' in df.columns else 'Part Number'
    price_col = 'Price' if 'Price' in df.columns else 'Unit Price'
    brand_col = 'Brand'
    qty_col = 'Qty' if 'Qty' in df.columns else 'Quantity'
    desc_col = 'Description'
    specs_col = 'Specifications'

    matched = df[df[id_col] == model]
    if matched.empty:
        return "❌ Product not found."

    row = matched.iloc[0]

    model_safe = model.replace('/', '_').replace(' ', '_')
    img_file = f"{model_safe}.jpg"
    if not os.path.exists(os.path.join(IMAGE_FOLDER, img_file)):
        img_file = f"{model_safe}.png"

    image_path = f"/{IMAGE_FOLDER}/{img_file}" if os.path.exists(os.path.join(IMAGE_FOLDER, img_file)) else "/static/default.jpg"

    product = {
        'model': model,
        'price': row.get(price_col) or "Price not available",
        'description': row.get(desc_col, '') or "No description available.",
        'specifications': row.get(specs_col, '') or "Not available",
        'brand': row.get(brand_col, '') or "Unknown brand",
        'qty': row.get(qty_col, '') or "N/A",
        'image': image_path
    }

    return render_template('product_detail.html', product=product)

@app.route('/downloaded_images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True)
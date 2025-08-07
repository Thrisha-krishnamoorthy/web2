import os
import pandas as pd
import pickle
import json
from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify, url_for, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from admin_seller_app.models import db as seller_db, Seller, PDFDocument, ExcelDocument, Product, ExtractedImage, SelectedImage
from urllib.parse import unquote
from dotenv import load_dotenv

from extractor import extract_images_from_pdf
from tavily_api import scrape_images_for_models_get_options, download_image, run_scraper
from final_excel_builder import create_final_excel

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Configure seller database
import os

# Get the absolute path to the sellers.db file
db_path = os.path.join(os.path.dirname(__file__), 'admin_seller_app', 'instance', 'sellers.db')
db_uri = f'sqlite:///{os.path.abspath(db_path).replace(os.sep, "/")}'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_BINDS'] = {
    'sellers': db_uri
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize seller database
seller_db.init_app(app)

UPLOAD_FOLDER = 'uploads'
EXCEL_FOLDER = 'excel_files'
IMAGE_FOLDER = 'downloaded_images'

# Create necessary directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXCEL_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

@app.route('/product-catalog')
def product_catalog():
    if 'username' not in session or 'seller_id' not in session:
        return redirect('/login')

    # Get products from database for the current seller
    products = Product.query.filter_by(seller_id=session['seller_id']).all()
    
    # Format products for the template
    formatted_products = []
    for product in products:
        # Get the first image from image_options if available
        image_options = json.loads(product.image_options) if product.image_options else []
        image_url = image_options[0] if image_options else '/static/default.jpg'
        
        formatted_products.append({
            'id': product.id,
            'model': product.file_name or 'N/A',
            'brand': product.brand or 'N/A',
            'qty': product.quantity or 0,
            'image': image_url,
            'part_number': product.part_number or '',
            'description': product.description or ''
        })
    
    return render_template('product_ui.html', products=formatted_products, logged_in=session.get('logged_in', True))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    username = request.form['username']
    password = request.form['password']
    
    # Check against hardcoded admin first
    if username == "Admin" and password == "1234":
        session['logged_in'] = True
        session['is_admin'] = True
        return redirect('/upload-options')
    
    # Check against sellers database
    with app.app_context():
        seller = Seller.query.filter_by(username=username).first()
        if seller and seller.password == password:  # In production, use proper password hashing
            session['logged_in'] = True
            session['seller_id'] = seller.id
            session['username'] = seller.username
            return redirect('/upload-options')
    
    flash('Invalid username or password')
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/upload-options')
def upload_options():
    if not session.get('logged_in'):
        return redirect('/login')
    return render_template('upload_options.html')

import pandas as pd
from werkzeug.utils import secure_filename
import os

@app.route('/upload-pdf', methods=['GET', 'POST'])
def upload_pdf():
    if not session.get('logged_in'):
        return redirect('/login')
        
    if request.method == 'POST':
        pdf_files = request.files.getlist('pdf_file')
        excel_file = request.files.get('excel_file')

        if not pdf_files or not excel_file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please upload at least one PDF and one Excel file.'}), 400
            return "Please upload at least one PDF and one Excel file."

        # Get the current seller's ID
        seller_id = session.get('seller_id')
        if not seller_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Seller not authenticated. Please log in again.'}), 401
            return "Seller not authenticated. Please log in again."

        # Save and process Excel file
        excel_filename = secure_filename(excel_file.filename)
        excel_filename = excel_filename.replace('_', ' ')  # Restore spaces after secure_filename
        excel_path = os.path.join(UPLOAD_FOLDER, excel_filename)
        
        # Read Excel file content
        excel_content = excel_file.read()
        
        # Save Excel file info to database with content
        excel_doc = ExcelDocument(
            filename=excel_filename,
            file_content=excel_content,  # Store file content as BLOB
            seller_id=seller_id
        )
        seller_db.session.add(excel_doc)
        seller_db.session.commit()

        # Reset file pointer after reading content
        excel_file.seek(0)
        df = pd.read_excel(excel_file)

        if 'File Name' not in df.columns:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': "Excel is missing 'File Name' column."}), 400
            return "Excel is missing 'File Name' column."
            
        # Initialize image_options dictionary
        image_options = {}
        
        # Save PDFs and build mapping
        pdf_paths = {}
        
        # Create a response object to track success
        response_data = {
            'success': True,
            'message': 'Files uploaded and processed successfully',
            'redirect': '/select-images'  # Redirect to select-images after successful upload
        }

        for pdf_file in pdf_files:
            # Get secure filename and restore spaces
            filename = secure_filename(pdf_file.filename)
            filename = filename.replace('_', ' ')  # Restore spaces after secure_filename
            
        # Step 1: First create all products from Excel
        products_created = 0
        product_mapping = {}  # Store mapping of file_name to product_id
        
        for _, row in df.iterrows():
            try:
                file_name = str(row.get('File Name', '')).strip()
                if not file_name:
                    print("Skipping row with missing 'File Name'")
                    continue
                    
                # Clean and prepare product data
                pdf_name = os.path.splitext(file_name)[0]  # Remove extension for matching
                
                # Create product with all required fields
                product = Product(
                    part_number=str(row.get('Part Number', '')).strip(),
                    file_name=file_name,
                    brand_url=str(row.get('Brand URL', '')).strip(),
                    description=str(row.get('Description', '')).strip(),
                    brand=str(row.get('Brand', '')).strip(),
                    category=str(row.get('Category', '')).strip(),
                    original_price=float(row.get('Original Price (AED)', 0)) if pd.notna(row.get('Original Price (AED)')) else 0.0,
                    quantity=int(row.get('Quantity Available', 0)) if pd.notna(row.get('Quantity Available')) else 0,
                    physical_condition=str(row.get('Physical Condition', '')) if pd.notna(row.get('Physical Condition')) else '',
                    packaging_status=str(row.get('Packaging Status', '')) if pd.notna(row.get('Packaging Status')) else '',
                    completeness=str(row.get('Completeness', '')) if pd.notna(row.get('Completeness')) else '',
                    warranty_days=int(row.get('Warranty (Days)', 0)) if pd.notna(row.get('Warranty (Days)')) else 0,
                    warranty_type=str(row.get('Warranty Type', '')) if pd.notna(row.get('Warranty Type')) else '',
                    seller_id=seller_id,
                    pdf_path='',  # Will be updated after PDF processing
                    image_options=None  # Will be updated after image extraction
                )
                seller_db.session.add(product)
                seller_db.session.flush()  # Flush to get the product ID
                
                # Store the mapping of PDF name to product ID
                product_mapping[pdf_name] = product.id
                products_created += 1
                
            except Exception as e:
                print(f"Error creating product for {row.get('File Name', 'unknown')}: {str(e)}")
                seller_db.session.rollback()
        
        # Commit all products to database
        seller_db.session.commit()
        print(f"Successfully created {products_created} products in the database.")
        
        # Step 2: Now fetch all products to get their IDs and create a mapping
        # Order by created_at in descending order to prioritize recently created products
        products = Product.query.filter_by(seller_id=seller_id).order_by(Product.created_at.desc()).all()
        # Create a mapping of normalized file_name to product_id
        # This will automatically keep the highest product_id for each filename
        # since we're processing in descending order of creation (which typically correlates with higher IDs)
        file_to_product_id = {}
        for product in products:
            if product.file_name:
                # Normalize the filename for matching (lowercase and remove common extensions)
                file_name = str(product.file_name).strip().lower()
                # Remove common extensions if present
                for ext in ['.pdf', '.xlsx', '.xls', '.csv']:
                    if file_name.endswith(ext):
                        file_name = file_name[:-len(ext)]
                # Only add if we haven't seen this filename before
                # Since we're processing in descending order of creation (and typically ID),
                # the first occurrence will have the highest ID
                if file_name not in file_to_product_id:
                    file_to_product_id[file_name] = product.id
                print(f"Mapped file: {file_name} to product ID: {product.id}")
        
        if not file_to_product_id:
            print("Warning: No products found in database after creation")
        else:
            print(f"\nAvailable product mappings:")
            for fname, pid in file_to_product_id.items():
                print(f"- '{fname}' -> {pid}")
        
        # Initialize image options dictionary
        image_options = {}

        # Process PDFs and extract images, associating them with products
        pdf_paths = {}
        image_options = {}
        
        # Reset file pointer to read PDFs again
        for pdf_file in pdf_files:
            pdf_file.seek(0)
            
        # Process each PDF file
        for pdf_file in pdf_files:
            try:
                # Get secure filename and restore spaces
                filename = secure_filename(pdf_file.filename)
                filename = filename.replace('_', ' ')  # Restore spaces after secure_filename
                
                # Ensure the upload directory exists
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                # Read the PDF content
                pdf_content = pdf_file.read()
                
                # Save PDF file info to database with content
                pdf_doc = PDFDocument(
                    filename=filename,
                    file_content=pdf_content,  # Store file content as BLOB
                    seller_id=seller_id
                )
                seller_db.session.add(pdf_doc)
                seller_db.session.flush()  # Flush to get the ID if needed

                # Store the content in session with original spacing
                pdf_name = os.path.splitext(filename)[0]
                pdf_path = os.path.join(UPLOAD_FOLDER, filename)
                pdf_paths[pdf_name] = pdf_path
                session.setdefault('pdf_paths', {})[pdf_name] = pdf_path

                # Normalize the PDF name for matching (lowercase and remove .pdf if present)
                normalized_pdf_name = pdf_name.lower().strip()
                if normalized_pdf_name.endswith('.pdf'):
                    normalized_pdf_name = normalized_pdf_name[:-4]
                
                # Try to find a matching product ID using the normalized name
                product_id = None
                for file_pattern, pid in file_to_product_id.items():
                    if file_pattern in normalized_pdf_name or normalized_pdf_name in file_pattern:
                        product_id = pid
                        break
                        
                print(f"\nProcessing PDF: {pdf_name}")
                print(f"Normalized name: {normalized_pdf_name}")
                print(f"Matched product_id: {product_id}")
                
                if product_id is None:
                    print(f"Warning: No product found for PDF: {pdf_name}")
                    print("Available product mappings:", file_to_product_id)
                
                # Update the product's pdf_path if we found a matching product
                if product_id:
                    product = Product.query.get(product_id)
                    if product:
                        product.pdf_path = pdf_path
                        seller_db.session.commit()
                
                # Extract images from PDF and save to database with product_id
                extracted = extract_images_from_pdf(
                    pdf_path=pdf_path,  # Still pass path for reference
                    output_base_dir="",
                    db_session=seller_db.session,
                    seller_id=seller_id,
                    product_id=product_id,  # This will be None if no matching product found
                    pdf_content=pdf_content  # Pass content directly
                )
                
                if extracted:
                    image_options[pdf_name] = [
                        {'url': img['image_url'], 'selected': True, 'filename': img['image_filename']} 
                        for img in extracted if img['pdf_name'] == pdf_name
                    ]
                    print(f"Extracted {len(image_options[pdf_name])} images from {pdf_name}")
                else:
                    print(f"No images extracted from {pdf_name}")
                    image_options[pdf_name] = []
                    
            except Exception as e:
                print(f"Error processing PDF {pdf_file.filename}: {str(e)}")
                continue
        
        # Commit all PDF documents to database
        seller_db.session.commit()

        # Add pdf_path column to DataFrame
        def get_pdf_path(file_name):
            return pdf_paths.get(file_name.strip(), "")

        df['pdf_path'] = df['File Name'].astype(str).apply(get_pdf_path)

        # Save updated Excel file
        updated_excel_path = os.path.join(UPLOAD_FOLDER, 'updated_' + excel_filename)
        df.to_excel(updated_excel_path, index=False)
        session['excel_path'] = updated_excel_path
        
        # Save the extracted Excel data to a new file with all columns
        extracted_excel_path = os.path.join(UPLOAD_FOLDER, 'extracted_columns_' + excel_filename)
        df.to_excel(extracted_excel_path, index=False)
        
        # Also save the extracted Excel to the database
        with open(extracted_excel_path, 'rb') as f:
            extracted_excel_content = f.read()
            
        extracted_excel_doc = ExcelDocument(
            filename='extracted_columns_' + excel_filename,
            file_content=extracted_excel_content,
            seller_id=seller_id
        )
        seller_db.session.add(extracted_excel_doc)
        seller_db.session.commit()

        # Save the mapping of PDF names to their extracted images in the session
        session['image_options'] = image_options
        
        # Prepare the data for the template
        template_data = {}
        for pdf_name, images in image_options.items():
            if images:  # Only include PDFs that have images
                template_data[pdf_name] = {
                    'images': images,
                    'selected_count': len([img for img in images if img.get('selected', False)]),
                    'total_images': len(images)
                }
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'redirect': url_for('select_images')
            })
            
        return render_template('select_images.html', image_options=template_data)

    return render_template('upload_pdf.html')



@app.route('/upload-excel', methods=['GET', 'POST'])
def upload_excel():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        if 'excel_file' not in request.files:
            return "No file part"
        
        file = request.files['excel_file']
        
        if file.filename == '':
            return "No selected file"
            
        if file and file.filename.endswith(('.xlsx', '.xls')):
            # Get secure filename and then restore spaces
            filename = secure_filename(file.filename)
            filename = filename.replace('_', ' ')  # Restore spaces after secure_filename
            
            # Read the Excel file content
            excel_content = file.read()
            
            # Get current user
            seller = Seller.query.filter_by(username=session['username']).first()
            if not seller:
                return 'User not found', 404
            
            # Save Excel file to database
            excel_doc = ExcelDocument(
                filename=filename,
                file_content=excel_content,
                seller_id=seller.id
            )
            seller_db.session.add(excel_doc)
            seller_db.session.commit()
            
            # Save file temporarily for processing
            os.makedirs(EXCEL_FOLDER, exist_ok=True)
            filepath = os.path.join(EXCEL_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(excel_content)
                
            session['final_excel_path'] = filepath
            return redirect(url_for('product_ui'))
            
    return render_template('upload_excel.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect('/login')
    
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'excel_file' not in request.files or 'pdf_files' not in request.files:
            return 'No file part'
        
        excel = request.files['excel_file']
        pdfs = request.files.getlist('pdf_files')
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if excel.filename == '' or len(pdfs) == 0:
            return 'No selected file'
            
        if excel and excel.filename.endswith(('.xlsx', '.xls')):
            # Ensure the upload directory exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Get current user
            seller = Seller.query.filter_by(username=session['username']).first()
            if not seller:
                return 'User not found', 404
                
            # Process Excel file - preserve spaces in filename
            excel_filename = secure_filename(excel.filename)
            excel_filename = excel_filename.replace('_', ' ')  # Restore spaces after secure_filename
            excel_content = excel.read()
            
            # Save Excel to database
            excel_doc = ExcelDocument(
                filename=excel_filename,
                file_content=excel_content,
                seller_id=seller.id
            )
            seller_db.session.add(excel_doc)
            
            # Process PDF files - preserve spaces in filenames
            pdf_docs = []
            for pdf in pdfs:
                if pdf and pdf.filename.endswith('.pdf'):
                    # Get secure filename and then restore spaces
                    pdf_filename = secure_filename(pdf.filename)
                    pdf_filename = pdf_filename.replace('_', ' ')  # Restore spaces after secure_filename
                    pdf_content = pdf.read()
                    
                    # Save PDF to database
                    pdf_doc = PDFDocument(
                        filename=pdf_filename,
                        file_content=pdf_content,
                        seller_id=seller.id
                    )
                    seller_db.session.add(pdf_doc)
                    pdf_docs.append(pdf_doc)
            
            # Commit all database changes
            seller_db.session.commit()
            
            # Store the IDs in the session
            session['excel_id'] = excel_doc.id
            session['pdf_ids'] = [doc.id for doc in pdf_docs]
            
            # Process the Excel file to extract product data
            try:
                # Read the Excel file
                df = pd.read_excel(excel_content, engine='openpyxl')
                
                # Process each row in the Excel
                for _, row in df.iterrows():
                    # Get image options for this product if available
                    image_options = session.get('image_options', {}).get(row.get('File Name', '').strip(), [])
                    
                    # Create and save product
                    product = Product(
                        part_number=row.get('Part Number/SKU', '') or '',
                        file_name=row.get('File Name', '') or '',
                        brand_url=row.get('Brand URL', '') or '',
                        description=row.get('Product Description', '') or '',
                        brand=row.get('Brand/Manufacturer', '') or '',
                        category=row.get('Category', '') or '',
                        original_price=float(row.get('Original Price (AED)', 0)) if str(row.get('Original Price (AED)', '')).replace('.', '').isdigit() else 0.0,
                        quantity=int(row.get('Quantity Available', 0)) if str(row.get('Quantity Available', '0')).isdigit() else 0,
                        physical_condition=row.get('Physical Condition', '') or '',
                        packaging_status=row.get('Packaging Status', '') or '',
                        completeness=row.get('Completeness', '') or '',
                        warranty_days=int(row.get('Warranty Days Remaining', 0)) if str(row.get('Warranty Days Remaining', '0')).isdigit() else 0,
                        warranty_type=row.get('Warranty Type', '') or '',
                        seller_id=seller.id,
                        image_options=json.dumps(image_options) if image_options else None
                    )
                    seller_db.session.add(product)
                
                # Commit all product additions
                seller_db.session.commit()
                
            except Exception as e:
                print(f"Error processing Excel data: {e}")
                seller_db.session.rollback()
                flash('Error processing product data. Please try again.', 'error')
                return redirect('/upload')
            
            return redirect('/product-ui')
    
            pickle.dump(image_options, f)

        # Process Excel
        output_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output.xlsx')
        output_data_excel = os.path.join(EXCEL_FOLDER, 'excel_image_embedded_output_data.xlsx')
        run_scraper(excel_path, output_excel, output_data_excel, log_func=print)

        # Save paths in session
        session['excel_path'] = scraped_data_excel
        session['final_excel_path'] = output_excel
        session['data_excel_path'] = output_data_excel

        return redirect('/select-images')

    return render_template('upload.html')



@app.route('/select-images', methods=['GET', 'POST'])
def select_images():
    if request.method == 'GET':
        # Get the current seller's ID from session
        seller_id = session.get('seller_id')
        if not seller_id:
            return redirect('/login')
            
        # Get the PDF paths from the current session
        pdf_paths = session.get('pdf_paths', {})
        if not pdf_paths:
            return "No PDFs found in current session. Please upload PDFs first."
            
        # Get the PDF names from the current session
        current_pdf_names = [os.path.splitext(os.path.basename(pdf_path))[0] for pdf_path in pdf_paths.values()]
        
        # Get all images for the current PDFs
        images = ExtractedImage.query.filter(
            ExtractedImage.seller_id == seller_id,
            ExtractedImage.pdf_name.in_(current_pdf_names)
        ).order_by(ExtractedImage.pdf_name, ExtractedImage.product_id.desc()).all()
        
        # Group by pdf_name and get the highest product_id for each
        grouped_images = {}
        for img in images:
            if img.pdf_name not in grouped_images:
                grouped_images[img.pdf_name] = []
            # Only add images if they have the same product_id as the first image for this pdf_name
            # (which will be the highest due to the ordering above)
            if not grouped_images[img.pdf_name] or img.product_id == grouped_images[img.pdf_name][0].product_id:
                grouped_images[img.pdf_name].append(img)
        
        # Flatten the grouped images
        images = [img for img_list in grouped_images.values() for img in img_list]
        
        # Group images by PDF name
        image_options = {}
        for img in images:
            if img.pdf_name not in image_options:
                image_options[img.pdf_name] = {
                    'product_id': img.product_id,
                    'images': []
                }
                
            image_options[img.pdf_name]['images'].append({
                'id': img.id,
                'url': url_for('serve_extracted_image', image_id=img.id),
                'selected': True,
                'filename': img.image_filename
            })
        
        # Ensure all PDFs from the current session are in the options, even if they have no images
        for pdf_name in current_pdf_names:
            if pdf_name not in image_options:
                image_options[pdf_name] = {
                    'product_id': product_mapping.get(pdf_name),
                    'images': []
                }
        
        return render_template('select_images.html', image_options=image_options)
        
    elif request.method == 'POST':
        form_data = request.form.to_dict(flat=False)  # Get form data as MultiDict
        excel_path = session.get('excel_path')

        if not excel_path or not os.path.exists(excel_path):
            return "Excel file missing!"

        df = pd.read_excel(excel_path)
    
    # Create a dictionary to store selected images for each model
    model_images = {}
    
    # Process the form data to group images by model
    for key, values in form_data.items():
        if key.endswith('[]'):
            model = key[:-2]  # Remove '[]' from the key to get the model name
            model_images[model] = values
        elif key.endswith('_main'):
            # This is the main image, we'll handle it separately
            pass
    
    # Add selected images and main image columns
    def get_selected_images(file_name):
        # Get all selected images for this model
        images = model_images.get(file_name.strip(), [])
        return ', '.join(images) if images else ""
    
    def get_main_image(file_name):
        # Get the main image (first selected) for this model
        images = model_images.get(file_name.strip(), [])
        return images[0] if images else ""
    
    df['selected_images'] = df['File Name'].astype(str).apply(get_selected_images)
    df['selected_image'] = df['File Name'].astype(str).apply(get_main_image)

    # Save final version
    final_excel_path = excel_path.replace('updated_', 'final_')
    df.to_excel(final_excel_path, index=False)

    # Save for catalog rendering
    session['final_excel_path'] = final_excel_path

    return redirect('/product-catalog')


@app.route('/api/save-selected-images', methods=['POST'])
def save_selected_images():
    try:
        # Get the current seller's ID
        seller_id = session.get('seller_id')
        if not seller_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Get the JSON data from the request
        data = request.get_json()
        if not data or 'selections' not in data:
            return jsonify({'success': False, 'error': 'No selection data provided'}), 400

        # Process each selection with its own product_id
        for selection in data['selections']:
            image_id = selection.get('image_id')
            is_primary = selection.get('is_primary', False)
            product_id = selection.get('product_id')
            
            # Verify the image exists and belongs to the seller
            image = ExtractedImage.query.filter_by(
                id=image_id,
                seller_id=seller_id
            ).first()
            
            if not image:
                continue  # Skip if image not found or doesn't belong to seller
            
            # Clear any existing selections for this product if product_id is provided
            if product_id:
                # Only clear if this is the first selection for this product
                existing = SelectedImage.query.filter_by(product_id=product_id).first()
                if existing and is_primary:
                    SelectedImage.query.filter_by(product_id=product_id).delete()
            
            # Create new selected image record
            selected_image = SelectedImage(
                image_id=image_id,
                product_id=product_id,
                seller_id=seller_id,
                is_primary=is_primary
            )
            
            # If this is set as primary, ensure no other images are marked as primary
            if is_primary and product_id:
                # Update any existing primary images for this product to non-primary
                SelectedImage.query.filter(
                    SelectedImage.product_id == product_id,
                    SelectedImage.is_primary == True
                ).update({'is_primary': False})
            
            seller_db.session.add(selected_image)
        
        # Commit all changes
        seller_db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Image selections saved successfully',
            'product_id': product_id
        })
        
    except Exception as e:
        seller_db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/')
@app.route('/product-ui')
def product_ui():
    if 'username' not in session or 'seller_id' not in session:
        return redirect('/login')
    
    try:
        # Get products from database for the current seller
        products = Product.query.filter_by(seller_id=session['seller_id']).all()
        
        # Format products for the template
        formatted_products = []
        for product in products:
            # Get the first image from image_options if available
            image_options = json.loads(product.image_options) if product.image_options else []
            image_url = image_options[0] if image_options else '/static/default.jpg'

        for _, row in df.iterrows():
            # Safely get and clean values
            model = str(row.get(id_col, '')).strip()
            if not model or model.lower() in ['nan', 'none', '']:
                continue

            price = str(row.get(price_col, '')).strip()
            if price.lower() in ['nan', '', 'none']:
                price = "Price not available"

            brand = str(row.get(brand_col, '')).strip()
            qty = str(row.get(qty_col, '')).strip()

            # Find the first available image for this product
            image_path = "/static/default.jpg"
            
            # Look for image with original model name (with spaces preserved)
            for ext in ['.jpg', '.jpeg', '.png']:
                img_filename = f"{model}{ext}"
                img_path = os.path.join(IMAGE_FOLDER, img_filename)
                if os.path.exists(img_path):
                    image_path = f"/{IMAGE_FOLDER}/{img_filename}"
                    break

            # Filter by search query if provided
            if query and query not in model.lower() and query not in price.lower() and query not in brand.lower():
                continue

            products.append({
                "model": model,  # Keep original model name with spaces
                "image": image_path,
                "price": price,
                "brand": brand,
                "qty": qty
            })
            
    except Exception as e:
        app.logger.error(f"Error in product_ui: {str(e)}")
        return render_template('error.html',
                           message='An error occurred while loading products.',
                           back_url=url_for('home')), 500

    return render_template('product_ui.html', products=products, search_query=query, logged_in=session.get('logged_in', False))

@app.route('/product-detail/<int:product_id>')
def product_detail(product_id):
    if 'username' not in session or 'seller_id' not in session:
        return redirect('/login')

    # Get product from database
    product = Product.query.filter_by(id=product_id, seller_id=session['seller_id']).first()
    
    if not product:
        return "Product not found", 404
    
    # Get image options
    image_options = json.loads(product.image_options) if product.image_options else []
    
    # Format product data for the template
    product_data = {
        'id': product.id,
        'model': product.file_name or 'N/A',
        'brand': product.brand or 'N/A',
        'part_number': product.part_number or 'N/A',
        'description': product.description or 'No description available',
        'price': product.original_price or 'N/A',
        'quantity': product.quantity or 0,
        'condition': product.physical_condition or 'N/A',
        'packaging': product.packaging_status or 'N/A',
        'completeness': product.completeness or 'N/A',
        'warranty_days': product.warranty_days or 'N/A',
        'warranty_type': product.warranty_type or 'N/A',
        'image_options': image_options,
        'selected_image': image_options[0] if image_options else '/static/default.jpg',
        'brand_url': product.brand_url or '#',
        'category': product.category or 'Uncategorized'
    }
    
    return render_template('product_detail.html', product=product_data)


@app.route('/extracted-image/<int:image_id>')
def serve_extracted_image(image_id):
    """Serve an image directly from the database using its ID."""
    image = ExtractedImage.query.get(image_id)
    if not image or not image.image_content:
        abort(404, description="Image not found or has no content")
    
    # Infer MIME type from filename extension
    ext = image.image_filename.rsplit('.', 1)[-1].lower()
    if ext == 'png':
        mimetype = 'image/png'
    elif ext in ('jpg', 'jpeg'):
        mimetype = 'image/jpeg'
    elif ext == 'gif':
        mimetype = 'image/gif'
    elif ext == 'webp':
        mimetype = 'image/webp'
    else:
        mimetype = 'application/octet-stream'  # fallback
    
    # Create response with proper headers
    response = app.response_class(
        response=image.image_content,
        status=200,
        mimetype=mimetype
    )
    response.headers['Content-Disposition'] = f'inline; filename="{image.image_filename}"'
    response.headers['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year
    return response

@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/debug/images')
def debug_images():
    """Debug route to check stored images"""
    seller_id = session.get('seller_id')
    if not seller_id:
        return "Not logged in"
        
    images = ExtractedImage.query.filter_by(seller_id=seller_id).all()
    
    result = []
    for img in images:
        result.append({
            'id': img.id,
            'pdf_name': img.pdf_name,
            'image_filename': img.image_filename,
            'content_length': len(img.image_content) if img.image_content else 0,
            'created_at': img.created_at.isoformat(),
            'product_id': img.product_id
        })
    
    return jsonify({
        'count': len(images),
        'images': result
    })

if __name__ == '__main__':
    app.run(debug=True)
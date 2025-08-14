from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configure SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../image ui project 1/admin_seller_app/instance/sellers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Import models
class Seller(db.Model):
    __tablename__ = 'seller'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String)
    file_name = db.Column(db.String)
    brand_url = db.Column(db.String)
    description = db.Column(db.Text)
    brand = db.Column(db.String)
    category = db.Column(db.String)
    original_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    physical_condition = db.Column(db.String)
    packaging_status = db.Column(db.String)
    completeness = db.Column(db.String)
    warranty_days = db.Column(db.Integer)
    warranty_type = db.Column(db.String)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    pdf_path = db.Column(db.String, nullable=True)
    image_options = db.Column(db.Text, nullable=True)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PDFDocument(db.Model):
    __tablename__ = 'pdf_document'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_content = db.Column(db.LargeBinary, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)

    def __repr__(self):
        return f"<PDFDocument {self.filename}>"

class ExtractedImage(db.Model):
    __tablename__ = 'extracted_image'
    id = db.Column(db.Integer, primary_key=True)
    pdf_name = db.Column(db.String(255), nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    image_content = db.Column(db.LargeBinary, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    
    # Relationships
    product = db.relationship('Product', backref=db.backref('extracted_images', lazy=True))
    seller = db.relationship('Seller', backref=db.backref('extracted_images', lazy=True))

class SelectedImage(db.Model):
    __tablename__ = 'selected_image'
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('extracted_image.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

@app.route('/')
def home():
    # Get all distinct categories with at least one product that has an image
    categories = db.session.query(
        Product.category,
        db.func.count(Product.id).label('product_count')
    ).group_by(Product.category).all()
    
    # Prepare category data
    category_data = []
    for category, product_count in categories:
        if not category:  # Skip products without a category
            continue
            
        # Try to find a product in this category that has an image
        product_with_image = db.session.query(
            Product, ExtractedImage
        ).join(
            SelectedImage, 
            db.and_(
                SelectedImage.product_id == Product.id,
                db.or_(
                    SelectedImage.is_primary == True,
                    SelectedImage.is_primary.is_(None)
                )
            )
        ).join(
            ExtractedImage,
            ExtractedImage.id == SelectedImage.image_id
        ).filter(
            Product.category == category
        ).first()
        
        if product_with_image and hasattr(product_with_image[1], 'id'):
            image_url = url_for('serve_extracted_image', image_id=product_with_image[1].id)
            
            category_data.append({
                'name': category,
                'image_url': image_url,
                'product_count': product_count
            })
    
    print(f"Found {len(category_data)} categories")
    
    return render_template('index.html', categories=category_data)

@app.route('/product-detail/<int:product_id>')
def product_detail(product_id):
    try:
        # Get the product by ID
        product = Product.query.get_or_404(product_id)
        
        # Get all selected images for this product
        selected_images = db.session.query(ExtractedImage).join(
            SelectedImage,
            SelectedImage.image_id == ExtractedImage.id
        ).filter(
            SelectedImage.product_id == product_id
        ).all()
        
        # Get image URLs for the carousel
        image_urls = [url_for('serve_extracted_image', image_id=img.id) for img in selected_images]
        
        # If no images, use default
        if not image_urls:
            image_urls = [url_for('static', filename='images/default-product.jpg')]
        
        # Format product data for the template
        product_data = {
            'id': product.id,
            'name': product.part_number or 'N/A',
            'part_number': product.part_number or 'N/A',
            'title': product.part_number or 'No Part Number',
            'brand': product.brand or 'No Brand',
            'description': product.description or 'No description available',
            'price': product.original_price or 0,
            'quantity': product.quantity if product.quantity is not None else 0,
            'category': product.category or 'Uncategorized',
            'condition': product.physical_condition or 'Not specified',
            'packaging_status': product.packaging_status or 'Not specified',
            'completeness': product.completeness or 'Not specified',
            'warranty_days': product.warranty_days or 0,
            'warranty_type': product.warranty_type or 'Not specified',
            'created_at': product.created_at.strftime('%Y-%m-%d') if product.created_at else 'N/A',
            'image_urls': image_urls,
            'additional_info': {
                'Brand URL': product.brand_url or 'N/A',
                'PDF Available': 'Yes' if product.pdf_path else 'No',
                'Created At': product.created_at.strftime('%Y-%m-%d') if product.created_at else 'N/A'
            }
        }
        
        return render_template('product_detail.html', product=product_data)
        
    except Exception as e:
        print(f"Error in product_detail route: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"An error occurred: {str(e)}", 500

@app.route('/product')
def product_page():
    try:
        # Get filter parameters from query parameters
        category_filter = request.args.get('category')
        brand_filter = request.args.get('brand')
        condition_filter = request.args.get('condition')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        
        # Query all products with their selected images
        products_data = []
        
        # Get all categories for the filter sidebar
        categories = db.session.query(
            Product.category,
            db.func.count(Product.id).label('product_count')
        ).group_by(Product.category).all()
        
        # Get all brands for the brand filter
        brands = db.session.query(
            Product.brand,
            db.func.count(Product.id).label('product_count')
        ).group_by(Product.brand).all()
        
        # Get all conditions for the condition filter
        conditions = db.session.query(
            Product.physical_condition,
            db.func.count(Product.id).label('product_count')
        ).group_by(Product.physical_condition).all()
        
        # Get price range for the price filter
        price_range = db.session.query(
            db.func.min(Product.original_price).label('min_price'),
            db.func.max(Product.original_price).label('max_price')
        ).first()
        
        # First, get filtered product IDs
        product_query = db.session.query(Product.id)
        
        # Apply filters to the product query
        if category_filter:
            product_query = product_query.filter(Product.category == category_filter)
        if brand_filter:
            product_query = product_query.filter(Product.brand == brand_filter)
        if condition_filter:
            product_query = product_query.filter(Product.physical_condition == condition_filter)
        if min_price is not None:
            product_query = product_query.filter(Product.original_price >= min_price)
        if max_price is not None:
            product_query = product_query.filter(Product.original_price <= max_price)
            
        # Get the filtered product IDs
        filtered_product_ids = [p[0] for p in product_query.all()]
        
        if not filtered_product_ids:
            print("No products match the filter criteria")
            results = []
        else:
            # Now get the products with their images
            query = db.session.query(
                Product,
                SelectedImage,
                ExtractedImage
            ).filter(Product.id.in_(filtered_product_ids))
            
            # Left outer join with SelectedImage and ExtractedImage
            query = query.outerjoin(
                SelectedImage,
                db.and_(
                    SelectedImage.product_id == Product.id,
                    db.or_(
                        SelectedImage.is_primary == True,
                        SelectedImage.is_primary.is_(None)  # Include if is_primary is not set
                    )
                )
            ).outerjoin(
                ExtractedImage,
                ExtractedImage.id == SelectedImage.image_id
            )
            
            # Execute the query and get all results
            results = query.all()
        
        if not results:
            print("No products found matching the filters")
        else:
            print(f"Found {len(results)} product records matching the filters")
        
        # Dictionary to store products by ID
        products_dict = {}
        
        for product, selected_image, extracted_image in results:
            if not product:
                print("Warning: Found None product in results")
                continue
                
            if product.id not in products_dict:
                # Format the price
                price = f"${product.original_price:,.2f}" if product.original_price else "Price not available"
                
                # Initialize product data with all fields from the database
                product_data = {
                    'id': product.id,
                    'part_number': product.part_number or 'N/A',
                    'title': product.part_number or 'No Part Number',
                    'file_name': product.file_name or 'N/A',
                    'brand_url': product.brand_url or '#',
                    'description': product.description or 'No description available',
                    'desc': product.description or 'No description available',  # For backward compatibility
                    'brand': product.brand or 'No Brand',
                    'category': product.category or 'Uncategorized',
                    'original_price': product.original_price or 0,
                    'price': price,
                    'quantity': product.quantity if product.quantity is not None else 0,
                    'physical_condition': product.physical_condition or 'N/A',
                    'packaging_status': product.packaging_status or 'N/A',
                    'completeness': product.completeness or 'N/A',
                    'warranty_days': product.warranty_days or 0,
                    'warranty_type': product.warranty_type or 'N/A',
                    'pdf_path': product.pdf_path or 'N/A',
                    'image': None,
                    'image_id': None,
                    'original_image': None
                }
                products_dict[product.id] = product_data
            else:
                product_data = products_dict[product.id]
            
            # If we have an image and haven't set one yet, or if this is a primary image
            if extracted_image and (product_data['image_id'] is None or (selected_image and selected_image.is_primary)):
                product_data['image'] = f"/serve-extracted-image/{extracted_image.id}"
                product_data['image_id'] = extracted_image.id
                product_data['original_image'] = extracted_image.image_url
        
        # Convert dictionary values to list
        products_data = list(products_dict.values())
        
        # For debugging - print first few products to verify data
        print("\nFirst few products with complete data:")
        for p in products_data[:3]:  # Print first 3 products
            print(f"Product ID: {p['id']}")
            print(f"  Title: {p['title']}")
            print(f"  Brand: {p['brand']}")
            print(f"  Description: {p['description'][:50]}..." if p['description'] else "  No description")
            print(f"  Price: {p['price']}")
            print(f"  Image ID: {p.get('image_id', 'No image')}")
        
        return render_template('product_page.html', 
                           products=products_data,
                           categories=categories,
                           selected_category=category_filter,
                           brands=brands,
                           conditions=conditions,
                           price_range=price_range,
                           current_filters={
                               'brand': brand_filter,
                               'condition': condition_filter,
                               'min_price': min_price,
                               'max_price': max_price
                           })
        
    except Exception as e:
        print(f"Error in product_page route: {str(e)}")
        import traceback
        traceback.print_exc()
        return "An error occurred while loading products. Please check the server logs.", 500

@app.route('/serve-extracted-image/<int:image_id>')
def serve_extracted_image(image_id):
    # Get the image from the database
    image = ExtractedImage.query.get_or_404(image_id)
    
    # Get the image content directly from the database
    if hasattr(image, 'image_content') and image.image_content:
        # If we have binary image content, return it
        from flask import make_response
        response = make_response(image.image_content)
        # Set the content type based on the image URL or assume JPEG by default
        if hasattr(image, 'image_url') and image.image_url:
            if image.image_url.lower().endswith('.png'):
                response.headers['Content-Type'] = 'image/png'
            elif image.image_url.lower().endswith('.gif'):
                response.headers['Content-Type'] = 'image/gif'
            else:
                response.headers['Content-Type'] = 'image/jpeg'
        else:
            response.headers['Content-Type'] = 'image/jpeg'
        return response
    elif hasattr(image, 'image_url') and image.image_url:
        # Fallback to redirecting to the image URL if binary content is not available
        from flask import redirect
        return redirect(image.image_url)
    else:
        # If no image content or URL is available, return a 404
        from flask import abort
        abort(404)

@app.route('/download-pdf/<int:product_id>')
def download_pdf(product_id):
    """Serve the PDF file associated with a product."""
    try:
        # Get the product first to ensure it exists
        product = Product.query.get_or_404(product_id)
        
        # Get the PDF document for this product
        pdf_doc = PDFDocument.query.filter_by(
            product_id=product_id
        ).first()
        
        # If not found by product_id, try to find by filename
        if not pdf_doc and product.pdf_path:
            pdf_doc = PDFDocument.query.filter(
                (PDFDocument.filename == product.pdf_path) |
                (PDFDocument.filename == os.path.basename(product.pdf_path))
            ).first()
        
        if not pdf_doc:
            return "PDF not found. No PDF document is associated with this product.", 404
            
        if not pdf_doc.file_content:
            return "PDF content is empty or corrupted.", 500
            
        # Debug information
        print(f"Serving PDF: {pdf_doc.filename}, Size: {len(pdf_doc.file_content)} bytes")
        
        # Create a response with the PDF content
        response = make_response(pdf_doc.file_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_doc.filename)}"'
        return response
        
    except Exception as e:
        import traceback
        print(f"Error serving PDF for product {product_id}:")
        traceback.print_exc()
        return f"An error occurred while processing your request: {str(e)}", 500

# Buyer authentication routes

@app.route('/buyer/register', methods=['GET', 'POST'])
def buyer_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
            
        # Check if username already exists
        existing_buyer = db.session.execute(
            db.select(Buyer).filter_by(username=username)
        ).scalar_one_or_none()
        
        if existing_buyer:
            return jsonify({'error': 'Username already exists'}), 400
            
        # Create new buyer
        new_buyer = Buyer(username=username)
        new_buyer.set_password(password)
        
        db.session.add(new_buyer)
        db.session.commit()
        
        return jsonify({'message': 'Buyer registered successfully'}), 201
    
    return render_template('buyer_register.html')

@app.route('/buyer/login', methods=['GET', 'POST'])
def buyer_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
            
        # Find buyer by username
        buyer = db.session.execute(
            db.select(Buyer).filter_by(username=username)
        ).scalar_one_or_none()
        
        if not buyer or not buyer.check_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401
            
        # Set session
        session['buyer_id'] = buyer.id
        session['username'] = buyer.username
        session['is_buyer'] = True
        
        return jsonify({'message': 'Login successful', 'buyer_id': buyer.id}), 200
    
    return render_template('buyer_login.html')

@app.route('/buyer/logout')
def buyer_logout():
    session.pop('buyer_id', None)
    session.pop('username', None)
    session.pop('is_buyer', None)
    return redirect(url_for('home'))

def buyer_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'buyer_id' not in session:
            return redirect(url_for('buyer_login'))
        return f(*args, **kwargs)
    return decorated_function

# Add Buyer model
class Buyer(db.Model):
    __tablename__ = 'buyer'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Buyer {self.username}>'

if __name__ == '__main__':
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
    app.run(debug=True)

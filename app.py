from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

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

@app.route('/product')
def product_page():
    try:
        # Get category filter from query parameters
        category_filter = request.args.get('category')
        
        # Query all products with their selected images
        products_data = []
        
        # Get all categories for the filter sidebar
        categories = db.session.query(
            Product.category,
            db.func.count(Product.id).label('product_count')
        ).group_by(Product.category).all()
        
        # Build the base query
        query = db.session.query(
            Product,
            SelectedImage,
            ExtractedImage
        ).outerjoin(
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
        
        # Apply category filter if specified
        if category_filter:
            query = query.filter(Product.category == category_filter)
        
        # Execute the query and get all results
        results = query.all()
        
        if not results:
            print("No products found in the database")
        else:
            print(f"Found {len(results)} product records")
        
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
                           category=category_filter,
                           categories=categories)
        
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

if __name__ == '__main__':
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
    app.run(debug=True)

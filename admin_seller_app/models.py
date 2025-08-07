from flask_sqlalchemy import SQLAlchemy
import os
import json
from datetime import datetime

db = SQLAlchemy()

class Seller(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    pdf_documents = db.relationship('PDFDocument', backref='seller', lazy=True, cascade='all, delete-orphan')
    excel_documents = db.relationship('ExcelDocument', backref='seller', lazy=True, cascade='all, delete-orphan')

class PDFDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_content = db.Column(db.LargeBinary, nullable=False)  # Changed from file_path to store actual file content
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)

    def __repr__(self):
        return f"<PDFDocument {self.filename}>"

class ExcelDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_content = db.Column(db.LargeBinary, nullable=False)  # Changed from file_path to store actual file content
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)

    def __repr__(self):
        return f"<ExcelDocument {self.filename}>"


class Product(db.Model):
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

    def __repr__(self):
        return f"<Product {self.part_number} - {self.file_name}>"


class ExtractedImage(db.Model):
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
    
    def __repr__(self):
        return f"<ExtractedImage {self.image_filename} from {self.pdf_name}>"


class SelectedImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('extracted_image.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    image = db.relationship('ExtractedImage', backref=db.backref('selections', lazy=True))
    product = db.relationship('Product', backref=db.backref('selected_images', lazy=True))
    seller = db.relationship('Seller', backref=db.backref('selected_images', lazy=True))
    
    def __repr__(self):
        return f"<SelectedImage {self.id} - {'Primary' if self.is_primary else 'Secondary'}>"

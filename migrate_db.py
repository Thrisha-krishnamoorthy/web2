import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Set up the Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admin_seller_app/instance/sellers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_BINDS'] = {
    'sellers': 'sqlite:///admin_seller_app/instance/sellers.db'
}

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Import models after db initialization
from admin_seller_app.models import db as seller_db, ScrapedImage

def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    with app.app_context():
        seller_db.create_all()
    print("Database tables created successfully!")

def add_scraped_image_table():
    """Add the ScrapedImage table to the database."""
    print("Adding ScrapedImage table to the database...")
    with app.app_context():
        # This will create the table if it doesn't exist
        ScrapedImage.__table__.create(seller_db.engine)
    print("ScrapedImage table added successfully!")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        add_scraped_image_table()
    else:
        create_tables()

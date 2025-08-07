from admin_seller_app.models import db, Product
from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    
    # Configure the database URI
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'sellers.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath(db_path).replace(os.sep, "/")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    db.init_app(app)
    
    return app

def init_products():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    init_products()

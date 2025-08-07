import os
from app import app
from admin_seller_app.models import db as seller_db, Seller

def update_database():
    with app.app_context():
        # Drop all tables
        seller_db.drop_all()
        print("Dropped all tables")
        
        # Create all tables with updated schema
        seller_db.create_all()
        print("Created all tables with updated schema")
        
        # Create a test seller if none exists
        if not Seller.query.first():
            test_seller = Seller(username='test', password='test')
            seller_db.session.add(test_seller)
            seller_db.session.commit()
            print("Created test seller")
        
        print("Database update complete!")

if __name__ == '__main__':
    update_database()

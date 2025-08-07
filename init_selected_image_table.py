from admin_seller_app import create_app
from admin_seller_app.models import db, SelectedImage

def init_db():
    app = create_app()
    with app.app_context():
        # This will create the table if it doesn't exist
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    init_db()

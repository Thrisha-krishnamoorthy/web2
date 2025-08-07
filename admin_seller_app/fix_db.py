import os
import sqlite3

def fix_database():
    # Path to the SQLite database
    db_path = os.path.join('instance', 'sellers.db')
    
    # Connect to the SQLite database with proper binary handling
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA encoding="UTF-8"')
    conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
    cursor = conn.cursor()
    
    try:
        # Drop existing tables if they exist (in correct order due to foreign key constraints)
        cursor.execute("DROP TABLE IF EXISTS pdf_document")
        cursor.execute("DROP TABLE IF EXISTS excel_document")
        print("Dropped existing tables")
        
        # Create new tables with the updated schema and proper BLOB handling
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_content BLOB NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            seller_id INTEGER NOT NULL,
            FOREIGN KEY (seller_id) REFERENCES seller (id) ON DELETE CASCADE
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS excel_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_content BLOB NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            seller_id INTEGER NOT NULL,
            FOREIGN KEY (seller_id) REFERENCES seller (id) ON DELETE CASCADE
        )
        """)
        
        # Commit the changes
        conn.commit()
        print("Successfully updated database schema with BLOB support for both PDF and Excel files")
        print("Note: Make sure to use binary mode when reading files for storage")
        
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        # Close the connection
        conn.close()

if __name__ == '__main__':
    fix_database()

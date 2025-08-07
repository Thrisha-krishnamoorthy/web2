import fitz  # PyMuPDF
import os
from datetime import datetime

def extract_images_from_pdf(pdf_path, output_base_dir, db_session=None, seller_id=None, product_id=None, pdf_content=None):
    """
    Extract images from a PDF and optionally save them to the database.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_base_dir (str): Base directory to save extracted images
        db_session: SQLAlchemy database session
        seller_id (int): ID of the seller who owns the PDF
        product_id (int, optional): ID of the product associated with the PDF
        pdf_content (bytes, optional): PDF file content as bytes if already in memory
        
    Returns:
        list: List of dictionaries containing image information
    """
    # If pdf_content is provided, use it directly instead of reading from file
    if pdf_content:
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
        except Exception as e:
            print(f"Error opening PDF from memory: {str(e)}")
            return []
    else:
        # Otherwise, try to read from file
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file does not exist: {pdf_path}")
            return []
            
        if os.path.getsize(pdf_path) == 0:
            print(f"Error: PDF file is empty: {pdf_path}")
            return []
            
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"Error opening PDF file {pdf_path}: {str(e)}")
            return []

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir = os.path.join("static", output_base_dir, pdf_name)
    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []

    try:
        doc = fitz.open(pdf_path)
        
        for page_number in range(len(doc)):
            try:
                page = doc[page_number]
                images = page.get_images(full=True)

                for img_index, img in enumerate(images):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image.get("image")
                        image_ext = base_image.get("ext", "png")  # Default to png if extension not found
                        
                        if image_bytes:
                            image_filename = f"page{page_number+1}_img{img_index+1}.{image_ext}"
                            image_path = os.path.join(output_dir, image_filename)
                            image_url = f"/{output_dir}/{image_filename}"

                            # Save image to filesystem
                            with open(image_path, "wb") as f:
                                f.write(image_bytes)
                            
                            # Prepare image info for return
                            image_info = {
                                "pdf_name": pdf_name,
                                "image_url": image_url,
                                "image_filename": image_filename,
                                "image_content": image_bytes
                            }
                            extracted_paths.append(image_info)
                            
                            # Save to database if session and seller_id are provided
                            if db_session is not None and seller_id is not None:
                                from admin_seller_app.models import ExtractedImage
                                
                                # Debug log before creating ExtractedImage
                                print(f"Creating ExtractedImage for PDF: {pdf_name}, Image: {image_filename}")
                                print(f"  - Seller ID: {seller_id}, Product ID: {product_id}")
                                
                                # Create new ExtractedImage record
                                extracted_image = ExtractedImage(
                                    pdf_name=pdf_name,
                                    image_filename=image_filename,
                                    image_content=image_bytes,
                                    image_url=image_url,
                                    seller_id=seller_id,
                                    product_id=product_id,
                                    created_at=datetime.utcnow()
                                )
                                db_session.add(extracted_image)
                                
                                try:
                                    # Flush to get the ID if needed
                                    db_session.flush()
                                    print(f"  - Successfully saved image with ID: {extracted_image.id}")
                                except Exception as e:
                                    print(f"  - Error saving image to database: {str(e)}")
                                    raise
                                
                    except Exception as img_error:
                        print(f"Warning: Error processing image {img_index} on page {page_number}: {str(img_error)}")
                        continue
                        
            except Exception as page_error:
                print(f"Warning: Error processing page {page_number}: {str(page_error)}")
                continue
                
        # Commit all database changes
        if db_session is not None:
            try:
                db_session.commit()
            except Exception as commit_error:
                print(f"Error committing extracted images to database: {str(commit_error)}")
                db_session.rollback()
                
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {str(e)}")
        return []
        
    return extracted_paths

# Save the file temporarily for extraction
try:
    # Ensure the directory exists
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    # Write the file content
    with open(pdf_path, 'wb') as f:
        f.write(pdf_content)
    
    # Verify the file was written and has content
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        # Try to extract images if it's a valid PDF
        try:
            extracted = extract_images_from_pdf(pdf_path, "")
            image_options[pdf_name] = [img['image_url'] for img in extracted if img['pdf_name'] == pdf_name]
        except Exception as e:
            print(f"Warning: Could not extract images from {pdf_path}: {str(e)}")
            image_options[pdf_name] = []
    else:
        print(f"Warning: Failed to write PDF file or file is empty: {pdf_path}")
        image_options[pdf_name] = []
        
except Exception as e:
    print(f"Error processing PDF {pdf_path}: {str(e)}")
    image_options[pdf_name] = []

import fitz  # PyMuPDF

def cover_header_text(input_pdf, output_pdf, coordinates):
    # Open the PDF document
    doc = fitz.open(input_pdf)
    
    # Define the rectangle coordinates (x0, y0, x1, y1)
    # PDF coordinates start from the top-left corner (0,0)
    rect = fitz.Rect(coordinates)
    
    # Loop through every page in the PDF
    for page in doc:
        # Draw a solid white rectangle over the coordinates
        # fill=(1, 1, 1) means RGB white
        # color=(1, 1, 1) sets the border to white as well
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
        
    # Save the modified PDF
    doc.save(output_pdf)
    doc.close()
    print(f"Successfully processed all pages! Saved as {output_pdf}")

# --- CONFIGURATION ---
INPUT_FILE = "tst.pdf"
OUTPUT_FILE = "cleaned_document.pdf"

# Replace these with your exact coordinates: (left, top, right, bottom)
# Example: a box starting 50 points from the left, 20 points from the top,
# extending to 300 points wide and 50 points deep.
BOX_COORDINATES = (400, 30, 730, 75)

cover_header_text(INPUT_FILE, OUTPUT_FILE, BOX_COORDINATES)

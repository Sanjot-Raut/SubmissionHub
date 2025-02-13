import fitz  # PyMuPDF for PDF operations
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import VGG16
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input
import mysql.connector
from mysql.connector import Error
import io,os

base_model = VGG16(weights='imagenet', include_top=False, pooling='avg')

def extract_images_from_pdf(pdf_path, output_dir):
    """Extract images from each page of a PDF and save them as image files."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    pdf_document = fitz.open(pdf_path)
    image_paths = []
    
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_filename = os.path.join(output_dir, f"page_{page_number}_img_{img_index}.png")
            
            with open(image_filename, "wb") as img_file:
                img_file.write(image_bytes)
            
            image_paths.append(image_filename)
    
    pdf_document.close()
    return image_paths

def extract_features(img_path, model):
    """Extract features from an image using VGG16."""
    img = image.load_img(img_path, target_size=(224, 224))
    img_data = image.img_to_array(img)
    img_data = np.expand_dims(img_data, axis=0)
    img_data = preprocess_input(img_data)
    features = model.predict(img_data)
    return features

def store_image_features(assignment_id, image_paths):
    """Store the extracted features of images in the database."""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='submission_hub',
            user='root',
            password=''
        )
        cursor = connection.cursor()

        for page_number, img_path in enumerate(image_paths):
            features = extract_features(img_path, base_model)
            features_blob = io.BytesIO(features.tobytes())
            
            insert_query = """
            INSERT INTO image_features (assignment_id, page_number, features)
            VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (assignment_id, page_number+1, features_blob.getvalue()))
        
        connection.commit()
        print("Image features stored successfully.")

    except Error as e:
        print(f"Error: {e}")

    finally:
        if connection.is_connected():
            
            
            
            cursor.close()
            connection.close()

def process_pdf_and_store_features(pdf_path, assignment_id):
    output_dir = "extracted_images"
    image_paths = extract_images_from_pdf(pdf_path, output_dir)
    store_image_features(assignment_id, image_paths)

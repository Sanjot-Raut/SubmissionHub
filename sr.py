import fitz  # PyMuPDF for PDF operations
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import VGG16
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input
import mysql.connector
from mysql.connector import Error
import io, os
from sklearn.metrics.pairwise import cosine_similarity
import json

# Initialize MySQL connection
def get_connection():
    return mysql.connector.connect(
        host='localhost',
        database='submission_hub',
        user='root',
        password=''
    )

# Initialize VGG16 model
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
    return features.flatten()  # Ensure features are a 1D array

def store_image_features(assignment_id, image_paths, new_features):
    """Store the extracted features of images in the database."""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        for page_number, (img_path, features) in enumerate(zip(image_paths, new_features)):
            features_blob = io.BytesIO(features.tobytes())
            insert_query = """
            INSERT INTO image_features (assignment_id, page_number, features)
            VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (assignment_id, page_number + 1, features_blob.getvalue()))
        
        connection.commit()
        print("Image features stored successfully.")

    except Error as e:
        print(f"Error: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def retrieve_stored_features(student_assignment_id):
    """Retrieve stored image features from the database."""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        select_query = """
        SELECT assignment_id, features 
        FROM image_features 
        WHERE assignment_id != %s
        """
        cursor.execute(select_query, (student_assignment_id,))
        
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            assignment_id = row[0]
            features_blob = row[1]
            features = np.frombuffer(features_blob, dtype='float32')
            print(assignment_id,features)
            yield assignment_id, features

    except Error as e:
        print(f"Error: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def compare_features(new_features, stored_features_generator):
    """Compare new features with stored features to determine similarity."""
    similarities = []
    for new_feature in new_features:
        for assignment_id, stored_feature in stored_features_generator:
            similarity = cosine_similarity([new_feature], [stored_feature])
            similarities.append((assignment_id, similarity[0][0]))
   
    return similarities

def process_pdf_and_store_features(pdf_path, assignment_id):
    output_dir = "extracted_images"
    image_paths = extract_images_from_pdf(pdf_path, output_dir)
    new_features = [extract_features(img_path, base_model) for img_path in image_paths]
    store_image_features(assignment_id, image_paths, new_features)
    return new_features

def filter_ids_with_all_high_scores(data, threshold=0.80):
    from collections import defaultdict
    scores_dict = defaultdict(list)
    
    for id, score in data:
        scores_dict[id].append(score)
   
    result = []
    for id, scores in scores_dict.items():
        if all(score >= threshold for score in scores):
            result.append(id)
    
    return result

def check_assignment_similarity(new_features, student_assignment_id):
    stored_features_generator = retrieve_stored_features(student_assignment_id)
    similarities = compare_features(new_features, stored_features_generator)
    copied_assignments = filter_ids_with_all_high_scores(similarities)
    print(similarities)
    if copied_assignments:
        print(f"The new assignment is similar to the following assignments: {copied_assignments}")
        return copied_assignments
    else:
        print("The new assignment is unique.")
        return copied_assignments

# Example usage
assignment_id = 1
student_id = 1
file_path = "ass2.pdf"
comments = "This is My First Assignment"

try:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO student_assignments (assignment_id, student_id, file_path, comments) VALUES (%s, %s, %s, %s)",
        (assignment_id, student_id, file_path, comments)
    )
    connection.commit()
    student_assignment_id = cursor.lastrowid

except mysql.connector.Error as err:
    print(f"Database error: {err}")

finally:
    if connection.is_connected():
        cursor.close()
        connection.close()

new_features = process_pdf_and_store_features(file_path, student_assignment_id)
copied_assignments = check_assignment_similarity(new_features, student_assignment_id)

try:
    connection = get_connection()
    cursor = connection.cursor()
    status = "Copied" if copied_assignments else "Unique"
    similar_to_id = json.dumps(copied_assignments)
    
    insert_query = """
    INSERT INTO student_assignment_comparisons (assignment_id, status, similar_to_id)
    VALUES (%s, %s, %s)
    """
    cursor.execute(insert_query, (student_assignment_id, status, similar_to_id))
    
    connection.commit()
    print(f"The new assignment is {status}.")
    if copied_assignments:
        print(f"It is similar to the following assignments: {copied_assignments}")

except Error as e:
    print(f"Error: {e}")

finally:
    if connection.is_connected():
        cursor.close()
        connection.close()

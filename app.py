from flask import Flask, render_template, request, redirect, url_for, session, flash,send_file,send_from_directory
from flask import jsonify
import mysql.connector
from mysql.connector import pooling
from werkzeug.security import check_password_hash, generate_password_hash
import spacy
import fitz
import io
import os
from werkzeug.utils import secure_filename
import re
import pandas as pd
import spacy
import assignment_matching
import project_matching
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'sr123'  # Change this to a more secure secret key

# Define the base upload folder
BASE_UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Database connection pool configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "submission_hub",
    "pool_name": "mypool",
    "pool_size": 25,
}

connection_pool = pooling.MySQLConnectionPool(**db_config)

def get_db_connection():
    try:
        connection = connection_pool.get_connection()
        if connection.is_connected():
            return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash("Database connection failed. Please try again later.", "error")
        return None

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        login_by = request.form.get('login_by')
        login_id = request.form.get('login_id')
        password = request.form.get('password')

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            if login_by == 'username':
                cursor.execute("SELECT * FROM admin WHERE username = %s", (login_id,))
            elif login_by == 'email':
                cursor.execute("SELECT * FROM admin WHERE email = %s", (login_id,))
            else:   
                flash('Invalid login method selected.')
                return redirect(url_for('admin_login')) 

            admin = cursor.fetchone()
            cursor.close()
            conn.close()

            if admin and check_password_hash(admin['password'], password):
                session['username'] = admin['username']
                session['role'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid credentials. Please try again.')
                return redirect(url_for('admin_login'))

    return render_template('admin_login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session['role'] == 'admin':
        return render_template('admin_dashboard.html')
    return redirect(url_for('index'))









@app.route('/admin/delete_teacher/<int:teacher_id>', methods=['POST'])
def admin_delete_teacher(teacher_id):
    if 'username' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM teachers WHERE id = %s', (teacher_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Teacher deleted successfully.'})
    else:
        return jsonify({'status': 'error', 'message': 'Teacher not found.'})















@app.route('/admin_view_teachers')
def admin_view_teachers():
    if 'username' in session and session['role'] == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM teachers')
        teachers = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin_view_teachers.html', teachers=teachers)
    return redirect(url_for('admin_login'))

@app.route('/admin_add_teacher', methods=['GET', 'POST'])
def admin_add_teacher():
    if 'username' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['username']
            email = request.form['email']
            password = request.form['password']
            hashed_password = generate_password_hash(password)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO teachers (username, email, password) VALUES (%s, %s, %s)', 
                           (name, email, hashed_password))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Teacher added successfully!')
            return redirect(url_for('admin_view_teachers'))
        return render_template('admin_add_teacher.html')
    return redirect(url_for('admin_login'))














@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
       
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM teachers WHERE username = %s OR email = %s", (username, username))
                teacher = cursor.fetchone()
                cursor.close()

               
                
                if teacher and check_password_hash(teacher['password'], password):
                    session['username'] = username
                    session['role'] = 'teacher'
                    session['teacher_id'] = teacher['id'] 
                    return redirect(url_for('teacher_dashboard'))
                else:
                    flash('Invalid credentials', 'error')
            except mysql.connector.Error as err:
                print(f"Database error: {err}")  # Debugging line
                flash('Database error. Please try again later.', 'error')
            finally:
                conn.close()
        else:
            flash('Database connection failed. Please try again later.', 'error')

    return render_template('teacher_login.html')


@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'username' in session and session['role'] == 'teacher':
        teacher_id = session['teacher_id']
        conn=get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
        teacher = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('teacher_dashboard.html', teacher=teacher)

    return redirect(url_for('index'))

@app.route('/teacher_update_profile/<int:user_id>', methods=['GET', 'POST'])
def teacher_update_profile(user_id):
    if 'username' in session and session['role'] == 'teacher':
        # Fetch the teacher's data from the database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM teachers WHERE id=%s", (user_id,))
        teacher = cursor.fetchone()
        
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            department = request.form['department']
            phone_number = request.form['phone_number']
            
            # Update the teacher's information in the database
            update_query = """
                UPDATE teachers 
                SET username=%s, email=%s, department=%s, phone_number=%s 
            """
            update_data = [username, email, department, phone_number]
            
            # Check if the password field is filled, and if so, update the password
            password = request.form['password']
            if password:
                confirm_password = request.form['confirm_password']
                if password == confirm_password:
                    hashed_password = generate_password_hash(password)
                    update_query += ", password=%s"
                    update_data.append(hashed_password)
                else:
                    # Handle the case where passwords do not match
                    return render_template('teacher_update_profile.html', teacher=teacher, error="Passwords do not match.")
            
            update_query += " WHERE id=%s"
            update_data.append(user_id)
            
            cursor.execute(update_query, tuple(update_data))
            conn.commit()
            cursor.close()
            conn.close()
            
            return redirect(url_for('teacher_dashboard'))
        
        return render_template('teacher_update_profile.html', teacher=teacher)
    
    return redirect(url_for('index'))











@app.route('/teacher/view_submissions')
def teacher_view_submissions():
    # Logic to view submissions
    return render_template('teacher_view_submissions.html')




@app.route('/teacher/view_subjects')
def teacher_view_subjects():
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            teacher_id = session.get('teacher_id')  # Assuming teacher_id is stored in session
            cursor.execute("SELECT * FROM subjects WHERE teacher_id = %s", (teacher_id,))
            subjects = cursor.fetchall()
            cursor.close()
         
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while fetching subjects. Please try again later.', 'danger')
            subjects = []
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        subjects = []

    return render_template('teacher_view_subjects.html', subjects=subjects)

@app.route('/teacher/view-subject/<int:subject_id>')
def teacher_view_subject_details(subject_id):
    conn = get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:  # Use dictionary cursor
            # Fetch subject details
            cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
            subject = cursor.fetchone()

            # Fetch assignments related to the subject
            cursor.execute("SELECT * FROM assignments WHERE subject_id = %s", (subject_id,))
            assignments = cursor.fetchall()

        return render_template('teacher_view_subject_details.html', subject=subject, assignments=assignments)
    finally:
        conn.close()



@app.route('/teacher/add_subject', methods=['GET', 'POST'])
def teacher_add_subject():
    if request.method == 'POST':
        subject_name = request.form.get('subject_name')
        subject_code = request.form.get('subject_code')
        subject_description = request.form.get('subject_description')
        semester = request.form.get('semester')
        teacher_id = session.get('teacher_id')  # Assuming teacher_id is stored in session

        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                query = """
                INSERT INTO subjects(name, subject_code, description, semester, teacher_id)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (subject_name, subject_code, subject_description, semester, teacher_id))
                conn.commit()
                cursor.close()
                flash('Subject added successfully!', 'success')
                return redirect(url_for('teacher_view_subjects'))
            except mysql.connector.Error as err:
                print(f"Database error: {err}")
                flash('An error occurred while adding the subject. Please try again later.', 'danger')
            finally:
                conn.close()
        else:
            flash('Database connection failed. Please try again later.', 'danger')

    return render_template('teacher_add_subject.html')



@app.route('/teacher/subject/<int:subject_id>/create_assignment', methods=['GET', 'POST'])
def teacher_create_assignment(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM subjects WHERE id = %s', (subject_id,))
    subject = cursor.fetchone()

    if not subject:
        flash('Subject not found!', 'danger')
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']

        file_path = ''
        if 'assignment_file' in request.files:
            file = request.files['assignment_file']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                assignment_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'assignments', str(subject_id))
                os.makedirs(assignment_dir, exist_ok=True)
                file_path = os.path.join(assignment_dir, filename)
                file.save(file_path)
                file_path = os.path.join('assignments', str(subject_id), filename)

        cursor.execute(
            '''INSERT INTO assignments (subject_id, title, description, due_date, file_path) 
               VALUES (%s, %s, %s, %s, %s)''',
            (subject_id, title, description, due_date, file_path)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash('Assignment created successfully!', 'success')
        return redirect(url_for('teacher_view_subject_details', subject_id=subject_id))

    cursor.close()
    conn.close()
    
    return render_template('teacher_create_assignment.html', subject=subject)











# Fetch assignment details by ID
def get_assignment_by_id(assignment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = "SELECT * FROM assignments WHERE id = %s"
    cursor.execute(query, (assignment_id,))
    assignment = cursor.fetchone()
    cursor.close()
    connection.close()
    return assignment

# Fetch student responses for an assignment
def get_student_responses(assignment_id,subject_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
                SELECT name FROM subjects WHERE id=%s
            """, (subject_id,))
    subject = cursor.fetchone()
    if 'project' in subject['name'].lower():
        print(subject['name'].lower())
        query = "SELECT * FROM projects WHERE assignment_id = %s"
    else:
        query = "SELECT * FROM student_assignments WHERE assignment_id = %s"
    cursor.execute(query, (assignment_id,))
    responses = cursor.fetchall()
    cursor.close()
    connection.close()
    return responses,subject['name']

@app.route('/teacher/assignment/<int:assignment_id>', methods=['GET'])
def teacher_view_assignment(assignment_id):
    assignment = get_assignment_by_id(assignment_id)
    responses,subject = get_student_responses(assignment_id,assignment['subject_id'])
    return render_template('teacher_view_assignment.html', assignment=assignment, responses=responses,subject=subject)



import ast

@app.route('/teacher_view_plagiarism_report', methods=['GET'])
def teacher_view_plagiarism_report():
    subject = request.args.get('subject')
    if not subject:
        return "Subject not provided", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if 'project' in subject.lower():
        query = """
            SELECT p.id, p.title, p.description, p.submission_date, p.file_path, 
                   s.name as student_name, s.email as student_email, 
                   pc.status, pc.similar_to_id, pc.compared_at
            FROM projects p
            JOIN students s ON p.student_id = s.id
            LEFT JOIN project_comparisons pc ON p.id = pc.project_id
        """
    else:
        query = """
            SELECT sa.id, sa.submission_date, sa.file_path, 
                   s.name as student_name, s.email as student_email, 
                   sac.status, sac.similar_to_id, sac.compared_at
            FROM student_assignments sa
            JOIN students s ON sa.student_id = s.id
            LEFT JOIN student_assignment_comparisons sac ON sa.id = sac.assignment_id
        """

    cursor.execute(query)
    comparisons = cursor.fetchall()
    cursor.close()
    conn.close()

    print("Fetched comparisons:", comparisons)  # Debug: Print fetched comparisons

    # Group comparisons by unique assignments
    unique_assignments = {}
    for comparison in comparisons:
        similar_to_id = ast.literal_eval(comparison['similar_to_id']) if comparison['similar_to_id'] else []
        if not similar_to_id:
            unique_assignments[comparison['id']] = {
                'assignment': comparison,
                'copies': []
            }

    print("Unique assignments after initial grouping:", unique_assignments)  # Debug: Print unique assignments

    # Add copied assignments to their respective unique assignment
    for comparison in comparisons:
        similar_to_id = ast.literal_eval(comparison['similar_to_id']) if comparison['similar_to_id'] else []
        for original_id in similar_to_id:
            if original_id in unique_assignments:
                unique_assignments[original_id]['copies'].append(comparison)

    print("Final unique assignments with copies:", unique_assignments)  # Debug: Print final grouped assignments

    return render_template('teacher_view_plagiarism_report.html', comparisons=comparisons, unique_assignments=unique_assignments, subject=subject)






@app.route('/assignment/<int:assignment_id>/edit', methods=['GET', 'POST'])
def teacher_edit_assignment(assignment_id):
    assignment = get_assignment_by_id(assignment_id)
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE assignments 
            SET title = %s, description = %s, due_date = %s
            WHERE id = %s
        """, (title, description, due_date, assignment_id))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Assignment updated successfully!', 'success')
        return redirect(url_for('teacher_view_subject_details', subject_id=assignment['subject_id']))
    return render_template('teacher_edit_assignment.html', assignment=assignment)



@app.route('/assignment/<int:assignment_id>/delete', methods=['POST','GET'])
def teacher_delete_assignment(assignment_id):
    assignment = get_assignment_by_id(assignment_id)
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM assignments WHERE id = %s", (assignment_id,))
    connection.commit()
    cursor.close()
    connection.close()
    flash('Assignment deleted successfully!', 'success')
    return redirect(url_for('teacher_view_subject_details', subject_id=assignment['subject_id']))








@app.route('/teacher/add_single_student', methods=['POST'])
def teacher_add_single_student():
    student_name = request.form.get('student-name')
    student_email = request.form.get('student-email')
    student_id = request.form.get('student-id')
    student_pass = request.form.get('student-pass')
    teacher_id = session.get('teacher_id') 
    password = generate_password_hash(student_pass)
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT department FROM teachers WHERE id = %s', (teacher_id,))
    course = cursor.fetchone()[0]
    cursor.close()
    connection.close()
    if not student_name or not student_id:
        flash('Please fill out all fields', 'danger')
        return redirect(request.url)
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Check if student ID already exists
            cursor.execute('SELECT COUNT(*) FROM students WHERE userid = %s', (student_id,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                flash('Student ID already exists. Please use a different ID.', 'danger')
                return redirect(request.url)
        except:
            flash('Error adding student', 'danger')
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            query = """
            INSERT INTO students(name, userid,teacher_id,email,password,course)
            VALUES (%s, %s,%s,%s,%s,%s)
            """
            cursor.execute(query, (student_name, student_id,teacher_id,student_email,password,course))
            conn.commit()
            cursor.close()
            flash('Student added successfully!', 'success')
            return redirect(url_for('teacher_view_students'))
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while adding the student. Please try again later.', 'danger')
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
    
    
    return redirect(url_for('teacher_add_students'))











@app.route('/teacher/view_students')
def teacher_view_students():
    teacher_id = session.get('teacher_id') 
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            query = """
            SELECT 
                id,
                userid,
                name,
                email,
                course,
                roll_number
            FROM 
                students
            WHERE 
                teacher_id = %s;
            """
            cursor.execute(query, (teacher_id,))
            students = cursor.fetchall()
          
            cursor.close()
            return render_template('teacher_view_students.html', students=students)
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while retrieving students. Please try again later.', 'danger')
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
    
    return render_template('teacher_view_students.html', students=[])














    
@app.route('/get_profile_pic/<int:student_id>')
def get_profile_pic(student_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT profile_pic FROM students WHERE id = %s', (student_id,))
    profile_pic = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    if profile_pic:
        return send_file(io.BytesIO(profile_pic), mimetype='image/jpeg')
    return None





@app.route('/teacher/view_student/<int:student_id>')
def view_student_detail(student_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            query = """
            SELECT 
                id,
                userid,
                name,
                email,
                course,
                roll_number,
                phone_number,
                address,
                registered_at
            FROM 
                students
            WHERE
                id = %s;
            """
            cursor.execute(query, (student_id,))
            student = cursor.fetchone()
            cursor.close()
            if student:
                return render_template('teacher_view_student_detail.html', student=student)
            else:
                flash('Student not found.', 'danger')
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while retrieving student details. Please try again later.', 'danger')
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')

    return redirect(url_for('teacher_view_students'))



@app.route('/teacher/remove_student/<int:student_id>', methods=['POST'])
def remove_student(student_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        conn.commit()
        flash('Student removed successfully.', 'success')
    except mysql.connector.Error as err:
        flash('An error occurred while removing the student. Please try again later.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('teacher_view_students'))



@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))











def extract_text_from_pdf(file):
    # Ensure the file is a file-like object
    if hasattr(file, 'read'):
        file_path = 'temp.pdf'
        with open(file_path, 'wb') as temp_file:
            temp_file.write(file.read())
        
        # Now open the temporary file with PyMuPDF
        pdf_document = fitz.open(file_path)
        
        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text += page.get_text()

        pdf_document.close()
        return text
    else:
        raise ValueError("Provided file object is not valid.")



def extract_data_from_file(file):
    extension = file.filename.split('.')[-1].lower()
    data = []
    
    if extension == 'csv':
        df = pd.read_csv(file)
    elif extension == 'txt':
        content = file.read().decode('utf-8')
        data = extract_info_from_text(content)
        df = pd.DataFrame(data)
    elif extension == 'pdf':
        text = extract_text_from_pdf(file)
        data = extract_info_from_text(text)
        if not isinstance(data, list):
            raise ValueError("Extracted data is not in the expected format.")
        df = pd.DataFrame(data)
    elif extension == 'xlsx':
        df = pd.read_excel(file)
    else:
        raise ValueError("Unsupported file type")

    return df

def extract_info_from_text(text):
    # Define patterns for extracting information
    name_pattern = r'Name:\s*(.*)'
    email_pattern = r'Email:\s*(\S+@\S+\.\S+)'
    roll_number_pattern = r'Roll Number:\s*(\d+)'
    
    # Compile the patterns
    name_re = re.compile(name_pattern)
    email_re = re.compile(email_pattern)
    roll_number_re = re.compile(roll_number_pattern)
    
    # Extract information using the regular expressions
    names = name_re.findall(text)
    emails = email_re.findall(text)
    roll_numbers = roll_number_re.findall(text)
    
    # Create a list to hold student data
    data = []
    
    # Ensure that there is a corresponding name, email, and roll number
    for name, email, roll_number in zip(names, emails, roll_numbers):
        data.append({
            'Name': name,
            'Email': email,
            'Roll Number': roll_number
        })
    return data
def clean_data(df):
    # Strip whitespace from column names and values
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    
    # Ensure no empty values for required fields
    df = df.dropna(subset=['name', 'email', 'roll_number'])
      # Drop duplicates
    df = df.drop_duplicates(subset=['email'])
    # Rename columns for consistency
    df = df.rename(columns={'name': 'Name', 'email': 'Email', 'roll_number': 'Roll Number'})
    return df
def insert_students_into_db(df):
    conn = get_db_connection()
    cursor = conn.cursor()
    teacher_id = session.get('teacher_id')
   
    
    hashed_password = generate_password_hash("sr")
    add_student = ("INSERT INTO students "
                   "(name, email, roll_number, password,teacher_id) "
                   "VALUES (%s, %s, %s, %s,%s) "
                   "ON DUPLICATE KEY UPDATE "
                   "name=VALUES(name), email=VALUES(email), roll_number=VALUES(roll_number), password=VALUES(password), teacher_id=VALUES(teacher_id)")
    
    default_password = hashed_password
    
    for index, row in df.iterrows():
        try:
            cursor.execute(add_student, (row['Name'], row['Email'], row['Roll Number'], default_password,teacher_id))
            conn.commit()
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            conn.rollback()
    
    cursor.close()
    conn.close()



@app.route('/teacher/add_students_bulk', methods=['GET', 'POST'])
def teacher_add_students_bulk():
    if request.method == 'POST':
        if 'student_file' not in request.files:
            return "No file part"
        file = request.files['student_file']
        if file.filename == '':
            return "No selected file"
        if file:
            df = extract_data_from_file(file)
            df = clean_data(df)
            insert_students_into_db(df)
            
            return redirect(url_for('teacher_add_students_bulk'))

    return render_template('teacher_add_students.html')


@app.route('/teacher/add-students', methods=['GET'])
def teacher_add_students():
    return render_template('teacher_add_students.html')







@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['student_id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM students WHERE id = %s', (student_id,))
    student = cursor.fetchone()
    cursor.execute('SELECT * FROM subjects WHERE teacher_id = %s', (student['teacher_id'],))
    subjects = cursor.fetchall()
    cursor.close()
    connection.close()
   
    return render_template('student_dashboard.html', student=student, subjects=subjects)

















@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM students WHERE userid = %s OR email = %s OR id = %s", (username, username, username))
                student = cursor.fetchone()
                cursor.close()

            
                if student and check_password_hash(student['password'], password):
                    session['username'] = username
                    session['role'] = 'student'
                    session['student_id'] = student['id'] 
                    return redirect(url_for('student_dashboard'))
                else:
                    flash('Invalid credentials', 'error')
            except mysql.connector.Error as err:
                print(f"Database error: {err}")  # Debugging line
                flash('Database error. Please try again later.', 'error')
            finally:
                conn.close()
        else:
            flash('Database connection failed. Please try again later.', 'error')

    return render_template('student_login.html')




















@app.route('/student/view_subjects')
def student_view_subjects():
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            student_id = session.get('student_id')  # Assuming teacher_id is stored in session
            cursor.execute("""
                SELECT s.*
                FROM subjects s
                JOIN student_subjects ss ON s.id = ss.subject_id
                WHERE ss.student_id = %s
            """, (student_id,))
            subjects = cursor.fetchall()
            cursor.close()
         
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while fetching subjects. Please try again later.', 'danger')
            subjects = []
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        subjects = []

    return render_template('student_view_subjects.html', subjects=subjects)






@app.route('/student/view_subject/<int:subject_id>')
def student_view_subject_details(subject_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
            subject = cursor.fetchone()
            
            cursor.execute("SELECT * FROM assignments WHERE subject_id = %s", (subject_id,))
            assignment = cursor.fetchall()
            cursor.close()
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while fetching subject details. Please try again later.', 'danger')
            subject = None
            assignment = None
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        subject = None

    return render_template('student_view_subject_details.html', subject=subject,assignments=assignment)


@app.route('/student/assignment/<int:assignment_id>')
def student_view_assignment(assignment_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Fetch the assignment details
            cursor.execute("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
            assignment = cursor.fetchone()

            # Fetch the related subject details if assignment is found
            subject = None
            if assignment:
                cursor.execute("SELECT * FROM subjects WHERE id = %s", (assignment['subject_id'],))
                subject = cursor.fetchone()
            
            cursor.close()
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while fetching assignment details. Please try again later.', 'danger')
            assignment = None
            subject = None
        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        assignment = None
        subject = None

    return render_template('student_view_assignment.html', assignment=assignment, subject=subject)







@app.route('/student/submit_assignment/<int:assignment_id>', methods=['GET','POST'])
def student_submit_assignment(assignment_id):
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)

    comments = request.form.get('comments', '')
    project_title = request.form.get('project_title', '')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Create directory structure based on subject_id
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
             # Query to get the subject_id and assignment_name
            cursor.execute("""
                SELECT a.subject_id, s.name AS name
                FROM assignments a
                JOIN subjects s ON a.subject_id = s.id
                WHERE a.id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()
            cursor.close()
            conn.close()
        
        if assignment:
            subject_id = assignment['subject_id']
            assignment_name = assignment['name']
            assignment_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'assignments', str(subject_id), 'Submission')
            os.makedirs(assignment_dir, exist_ok=True)  # Ensure the directory exists
            
            file_path = os.path.join(assignment_dir, filename)
            
            # Check if the student has already submitted an assignment for this assignment_id
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                if "project" in assignment_name.lower():
                    cursor.execute("SELECT * FROM projects WHERE student_id = %s AND assignment_id = %s", (session['student_id'],assignment_id))
                else:
                    cursor.execute("SELECT * FROM student_assignments WHERE assignment_id = %s AND student_id = %s", (assignment_id, session['student_id']))
                    
                existing_submission = cursor.fetchone()
                if existing_submission:
                    flash('You have already submitted an assignment for this task.', 'danger')
                else:
                    file.save(file_path)
                    
                    
                    
                    if "project" in assignment_name.lower():
                        # Call project_process
                        project_matching.project_submission_process(project_title,comments,session['student_id'],assignment_id,file_path)
                        flash('Assignment submitted successfully!', 'success')
                    else:
                        # Call assignment_process
                        assignment_matching.assignment_submission_process(assignment_id,session['student_id'],file_path,comments)
                        flash('Assignment submitted successfully!', 'success')
    
            else:
                flash('Database connection failed. Please try again later.', 'danger')
        else:
            flash('Assignment not found or no associated subject', 'danger')
    else:
        flash('File type not allowed', 'danger')

    return redirect(url_for('student_view_assignment', assignment_id=assignment_id))



@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads/',filename)

@app.route('/<path:filename>')
def student_uploaded_file_assignments(filename):
    return send_from_directory('',filename)





def allowed_file(filename):
    allowed_extensions = {'pdf', 'docx', 'txt', 'jpg', 'pptx','png'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions



@app.route('/update_profile/<int:user_id>', methods=['GET', 'POST'])
def update_profile(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Handle profile picture upload
        profile_picture = request.files.get('profile_picture')
        if profile_picture:
            profile_pic_data = profile_picture.read()
            cursor.execute('UPDATE students SET profile_pic = %s WHERE id = %s', (profile_pic_data, user_id))

        # Handle other form data
        student_pass = request.form['password']
        confirm_pass = request.form['confirm_password']

        if student_pass:
            if student_pass != confirm_pass:
                flash('Passwords do not match!', 'danger')
                return redirect(url_for('update_profile', user_id=user_id))
            else:
                password = generate_password_hash(student_pass)
                cursor.execute('UPDATE students SET password = %s WHERE id = %s', (password, user_id))

        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone_number']
        address = request.form['address']
        print(username)
        cursor.execute('''
            UPDATE students
            SET userid = %s, name = %s, email = %s, phone_number = %s, address = %s
            WHERE id = %s
        ''', (username,name, email, phone, address, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_dashboard', user_id=user_id))

    cursor.execute('SELECT * FROM students WHERE id = %s', (user_id,))
    student = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('student_edit_profile.html', student=student)


@app.route('/profile_pic')
def profile_pic():
    student_id=session['student_id']
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT profile_pic FROM students WHERE id = %s', (student_id,))
    profile_pic = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    if profile_pic:
        return send_file(io.BytesIO(profile_pic), mimetype='image/jpeg')
    return None













@app.route('/teacher/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
def teacher_edit_subject(subject_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            if request.method == 'POST':
                # Get form data
                name = request.form['name']
                subject_code = request.form['subject_code']
                description = request.form['description']
                semester = request.form['semester']
                
                # Update the subject in the database
                cursor.execute("""UPDATE subjects
                                  SET name = %s, subject_code = %s, description = %s, semester = %s
                                  WHERE id = %s""",
                               (name, subject_code, description, semester, subject_id))
                
                # Handle addition and removal of students
                selected_students = request.form.getlist('selected_students')
                
                # Remove all current students associated with this subject
                cursor.execute("DELETE FROM student_subjects WHERE subject_id = %s", (subject_id,))
                
                # Add selected students back
                for student_id in selected_students:
                    cursor.execute("INSERT INTO student_subjects (subject_id, student_id) VALUES (%s, %s)", (subject_id, student_id))
                
                conn.commit()
                cursor.close()
                flash('Subject updated successfully!', 'success')
                return redirect(url_for('teacher_view_subject_details', subject_id=subject_id))
            
            else:
                # Get the current year and the past two years
                current_year = datetime.now().year
                past_year = current_year - 2
                print(past_year)
                print(current_year)
                # Fetch the subject for GET request
                cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
                subject = cursor.fetchone()

                      # Fetch distinct batch years
                cursor.execute("SELECT DISTINCT batch_year FROM students")
                distinct_years = [row['batch_year'] for row in cursor.fetchall()]
                print(distinct_years)
                # Fetch all students who registered between the calculated years
                cursor.execute("SELECT id, name, course, roll_number, batch_year FROM students WHERE registered_at >= %s", (past_year,))
                all_students = cursor.fetchall()  # Get students registered in the past 2 years

                # Fetching current student IDs associated with the subject
                cursor.execute("SELECT student_id FROM student_subjects WHERE subject_id = %s", (subject_id,))
                subject_student_ids = cursor.fetchall()
                subject_student_ids = [student['student_id'] for student in subject_student_ids]  # List of student IDs

                cursor.close()

                if not subject:
                    flash('Subject not found.', 'danger')
                    return redirect(url_for('teacher_view_subjects'))

                return render_template('teacher_edit_subject.html', subject=subject, all_students=all_students, subject_student_ids=subject_student_ids,current_year=current_year,distinct_years=distinct_years)

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred while updating the subject. Please try again later.', 'danger')
            return redirect(url_for('teacher_view_subjects'))

        finally:
            conn.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        return redirect(url_for('teacher_view_subjects'))
    
    
    
    
    

@app.route('/teacher_add_students_to_subject', methods=['POST'])
def add_students_to_subject():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')  # Get the subject ID
        student_ids = request.form.getlist('selected_students')  # Get the selected student IDs
        print(subject_id)
        print(student_ids)
        if not student_ids:
            flash('No students selected.')
            return redirect(url_for('teacher_view_subjects'))  # Redirect back to a relevant view
        
        conn = get_db_connection()
        cursor=conn.cursor()
        if conn:
            try:
                for student_id in student_ids:
                    sql = "INSERT INTO student_subjects (student_id, subject_id) VALUES (%s, %s)"
                    cursor.execute(sql, (student_id, subject_id))  # Execute the query
            except:
                flash('An error occurred while adding students to the subject. Please try again later.')
            finally:
                conn.commit()
                cursor.close()
        
        flash('Students added to subject successfully.')
        return redirect(url_for('teacher_view_subjects'))  # Redirect back to a relevant view
    
    

if __name__ == '__main__':
    app.run(debug=True)


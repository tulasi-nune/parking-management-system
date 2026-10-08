from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
import pymysql
import qrcode
import base64
from io import BytesIO
from datetime import datetime, timedelta
import os
import hashlib
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)

# Database configuration - MySQL ONLY
# Make sure you have MySQL server running with these credentials
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'parking_db',
    'charset': 'utf8mb4'
}

def get_db_connection():
    """Create and return a MySQL database connection"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"MySQL Database connection error: {e}")
        print("Please ensure MySQL server is running and credentials are correct")
        return None

def get_db_connection_no_db():
    """Create MySQL connection without specifying database (for initial setup)"""
    try:
        config = DB_CONFIG.copy()
        del config['database']  # Remove database from config
        connection = pymysql.connect(**config)
        return connection
    except Exception as e:
        print(f"MySQL Server connection error: {e}")
        return None

def test_database_connection():
    """Test MySQL database connection on startup"""
    print("Testing MySQL server connection...")
    connection = get_db_connection_no_db()
    if connection:
        print("✓ MySQL server connection successful")
        connection.close()
        return True
    else:
        print("✗ MySQL server connection failed")
        return False

def create_database_tables():
    """Create database tables if they don't exist"""
    # First connect without database to create it
    connection = get_db_connection_no_db()
    if not connection:
        print("Cannot connect to MySQL server")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS parking_db")
        print("✓ Database 'parking_db' created/verified")
        connection.close()
        
        # Now connect to the specific database
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        cursor.execute("USE parking_db")
        
        # Create tables from DB.txt schema
        with open('DB.txt', 'r') as f:
            sql_commands = f.read()
            # Execute each command separately
            commands = sql_commands.split(';')
            for command in commands:
                if command.strip() and not command.strip().startswith('CREATE DATABASE') and not command.strip().startswith('USE'):
                    try:
                        cursor.execute(command.strip())
                    except Exception as e:
                        print(f"Error executing command: {e}")
                        # Try to continue with other commands
                        continue
        
        connection.commit()
        print("✓ Database tables created/verified")
        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False
    finally:
        if connection:
            connection.close()

def generate_qr_code(data):
    """Generate QR code as base64 string"""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str
    except Exception as e:
        print(f"QR code generation error: {e}")
        return None

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format - accepts 10 digits with flexible formatting"""
    # Remove all non-digit characters
    cleaned_phone = re.sub(r'[^0-9]', '', phone)
    # Check if we have exactly 10 digits
    return len(cleaned_phone) == 10

def validate_vehicle_number(vehicle_no):
    """Validate vehicle number format - accepts alphanumeric with spaces and hyphens"""
    if not vehicle_no or len(vehicle_no.strip()) < 2:
        return False
    if len(vehicle_no.strip()) > 25:
        return False
    # Allow alphanumeric characters, spaces, and hyphens - very permissive
    cleaned = vehicle_no.strip()
    if not cleaned:
        return False
    return True  # Accept any non-empty string after stripping

# Initialize database on startup
print("=== Parking Management System Startup ===")
test_database_connection()
create_database_tables()
print("=== System Ready ===\n")

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt - Username: {username}, Password: {password}")  # Debug
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('admin_login.html')
        
        connection = get_db_connection()
        if not connection:
            print("No database connection for login")  # Debug
            flash('Database connection error', 'error')
            return render_template('admin_login.html')
        
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT id, username, password, email, contact_no, address FROM admin WHERE username = %s", (username,))
            admin = cursor.fetchone()
            
            print(f"Admin query result: {admin}")  # Debug
            
            if admin and admin[2] == password:  # Simple password check for now
                session['admin_id'] = admin[0]
                session['admin_username'] = admin[1]
                session['admin_logged_in'] = True
                session['user_type'] = 'admin'
                print(f"Login successful - Session set: {dict(session)}")  # Debug
                flash('Login successful', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                print("Invalid credentials")  # Debug
                flash('Invalid username or password', 'error')
        except Exception as e:
            print(f"Login exception: {str(e)}")  # Debug
            flash(f'Login error: {str(e)}', 'error')
        finally:
            connection.close()
    
    return render_template('admin_login.html')

@app.route('/resident_login', methods=['GET', 'POST'])
def resident_login():
    """Resident login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Resident login attempt - Username: {username}, Password: {password}")  # Debug
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('resident_login.html')
        
        connection = get_db_connection()
        if not connection:
            flash('Database connection error', 'error')
            return render_template('resident_login.html')
        
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT id, username, password FROM resident WHERE username = %s", (username,))
            resident = cursor.fetchone()
            
            print(f"Resident query result: {resident}")  # Debug
            
            if resident and resident[2] == password:
                session['resident_id'] = resident[0]
                session['resident_username'] = resident[1]
                session['resident_logged_in'] = True
                session['user_type'] = 'resident'
                print(f"Resident login successful - Session set: {dict(session)}")  # Debug
                flash('Login successful', 'success')
                return redirect(url_for('resident_dashboard'))
            else:
                print("Invalid resident credentials")  # Debug
                flash('Invalid username or password', 'error')
        except Exception as e:
            print(f"Resident login exception: {str(e)}")  # Debug
            flash(f'Login error: {str(e)}', 'error')
        finally:
            connection.close()
    
    return render_template('resident_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    """Admin dashboard with statistics"""
    print(f"Admin dashboard - Session: {dict(session)}")  # Debug
    if not session.get('admin_logged_in'):
        print("Admin not logged in - redirecting to login")  # Debug
        flash('Please login to access admin dashboard', 'error')
        return redirect(url_for('admin_login'))
    
    print("Admin logged in, getting connection...")  # Debug
    connection = get_db_connection()
    if not connection:
        print("No database connection")  # Debug
        flash('Database connection error', 'error')
        return redirect(url_for('admin_login'))
    
    try:
        print("Starting database queries...")  # Debug
        cursor = connection.cursor()
        
        # Get admin data
        cursor.execute("SELECT username, email, contact_no, address FROM admin WHERE id = %s", (session['admin_id'],))
        admin_result = cursor.fetchone()
        print(f"Admin result: {admin_result}")  # Debug
        admin_data = {
            'username': admin_result[0] if admin_result else session.get('admin_username', 'Admin'),
            'email': admin_result[1] if admin_result else '',
            'contact': admin_result[2] if admin_result else '',
            'address': admin_result[3] if admin_result else ''
        }
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM resident")
        total_residents = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM vehicle")
        total_vehicles = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parking WHERE status = 'Available'")
        available_slots = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parking WHERE status = 'Occupied'")
        occupied_slots = cursor.fetchone()[0]
        
        # Get recent activities - simplified query to avoid JOIN issues
        cursor.execute("""
            SELECT vehicle_no, entry_time, exit_time, status, 'Unknown' as name
            FROM gatelog 
            ORDER BY entry_time DESC 
            LIMIT 10
        """)
        recent_activities = cursor.fetchall()
        
        stats = {
            'total_residents': total_residents,
            'total_vehicles': total_vehicles,
            'available_slots': available_slots,
            'occupied_slots': occupied_slots,
            'recent_activities': recent_activities
        }
        
        print("Dashboard data prepared successfully")  # Debug
        return render_template('admin_dashboard.html', stats=stats, admin_data=admin_data)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")  # Debug
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('admin_login'))
    finally:
        connection.close()

@app.route('/resident_dashboard')
def resident_dashboard():
    """Resident dashboard"""
    if not session.get('resident_logged_in'):
        flash('Please login to access resident dashboard', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_login'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get resident details
        cursor.execute("SELECT * FROM resident WHERE id = %s", (resident_id,))
        resident = cursor.fetchone()
        
        # Get resident's vehicles
        cursor.execute("SELECT * FROM vehicle WHERE resident_id = %s", (resident_id,))
        vehicles = cursor.fetchall()
        
        # Get recent gate activities
        cursor.execute("""
            SELECT g.vehicle_no, g.entry_time, g.exit_time, g.status 
            FROM gatelog g 
            JOIN vehicle v ON g.vehicle_no = v.vehicle_no 
            WHERE v.resident_id = %s 
            ORDER BY g.entry_time DESC 
            LIMIT 10
        """, (resident_id,))
        recent_activities = cursor.fetchall()
        
        return render_template('resident_dashboard.html', 
                             resident=resident, 
                             vehicles=vehicles, 
                             recent_activities=recent_activities)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('resident_login'))
    finally:
        connection.close()

@app.route('/manage_residents')
def manage_residents():
    """Admin page to manage residents"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor()
        
        # Check if new columns exist in the table
        cursor.execute("SHOW COLUMNS FROM resident")
        columns = [column[0] for column in cursor.fetchall()]
        
        if 'floor' in columns and 'door_number' in columns and 'status' in columns:
            # New schema with all columns
            cursor.execute("SELECT id, name, email, phone, address, username, password, floor, door_number, status, created_at FROM resident ORDER BY name")
        elif 'floor' in columns and 'door_number' in columns:
            # Partial new schema (floor and door_number but no status)
            cursor.execute("SELECT id, name, email, phone, address, username, password, floor, door_number, 'Current Resident' as status, created_at FROM resident ORDER BY name")
        else:
            # Old schema - add default values for missing columns
            cursor.execute("SELECT id, name, email, phone, address, username, password, 'N/A' as floor, 'N/A' as door_number, 'Current Resident' as status, created_at FROM resident ORDER BY name")
        
        residents = cursor.fetchall()
        
        return render_template('manage_residents.html', residents=residents)
    except Exception as e:
        flash(f'Error loading residents: {str(e)}', 'error')
        print(f"Manage residents error: {str(e)}")  # Debug output
        return redirect(url_for('admin_dashboard'))
    finally:
        if connection:
            connection.close()

@app.route('/add_resident', methods=['GET', 'POST'])
def add_resident():
    """Add new resident"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        print(f"Add resident POST request - Form data: {request.form}")
        
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        username = request.form.get('username')
        password = request.form.get('password')
        floor = request.form.get('floor')
        door_number = request.form.get('door_number')
        
        # Clean phone number by removing all non-digit characters
        if phone:
            phone = re.sub(r'[^0-9]', '', phone)
        
        print(f"Received data - Name: {name}, Email: {email}, Phone: {phone}, Username: {username}, Floor: {floor}, Door Number: {door_number}")
        
        # Validation
        if not all([name, email, phone, address, username, password, floor, door_number]):
            flash('All fields are required', 'error')
            return render_template('add_resident.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'error')
            return render_template('add_resident.html')
        
        if not validate_phone(phone):
            flash('Phone number must be exactly 10 digits', 'error')
            return render_template('add_resident.html')
        
        connection = get_db_connection()
        if not connection:
            flash('Database connection error', 'error')
            return render_template('add_resident.html')
        
        try:
            cursor = connection.cursor()
            
            # Check if username already exists
            cursor.execute("SELECT id FROM resident WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                return render_template('add_resident.html')
            
            # Check if email already exists
            cursor.execute("SELECT id FROM resident WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already exists', 'error')
                return render_template('add_resident.html')
            
            # Insert new resident
            cursor.execute("""
                INSERT INTO resident (name, email, phone, address, username, password, floor, door_number) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, email, phone, address, username, password, floor, door_number))
            
            connection.commit()
            print(f"Resident added successfully: {name} ({username})")
            flash('Resident added successfully', 'success')
            return redirect(url_for('manage_residents'))
            
        except Exception as e:
            print(f"Error adding resident: {str(e)}")
            flash(f'Error adding resident: {str(e)}', 'error')
        finally:
            connection.close()
    
    return render_template('add_resident.html')

@app.route('/edit_resident/<int:resident_id>', methods=['GET', 'POST'])
def edit_resident(resident_id):
    """Edit resident details"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_residents'))
    
    try:
        cursor = connection.cursor()
        
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            address = request.form.get('address')
            username = request.form.get('username')
            password = request.form.get('password')
            
            # Validation
            if not all([name, email, phone, address, username, password]):
                flash('All fields are required', 'error')
                return redirect(url_for('edit_resident', resident_id=resident_id))
            
            if not validate_email(email):
                flash('Invalid email format', 'error')
                return redirect(url_for('edit_resident', resident_id=resident_id))
            
            if not validate_phone(phone):
                flash('Invalid phone number format', 'error')
                return redirect(url_for('edit_resident', resident_id=resident_id))
            
            # Update resident
            cursor.execute("""
                UPDATE resident 
                SET name = %s, email = %s, phone = %s, address = %s, username = %s, password = %s 
                WHERE id = %s
            """, (name, email, phone, address, username, password, resident_id))
            
            connection.commit()
            flash('Resident updated successfully', 'success')
            return redirect(url_for('manage_residents'))
        
        # Get resident details for editing
        cursor.execute("SELECT * FROM resident WHERE id = %s", (resident_id,))
        resident = cursor.fetchone()
        
        if not resident:
            flash('Resident not found', 'error')
            return redirect(url_for('manage_residents'))
        
        return render_template('edit_resident.html', resident=resident)
        
    except Exception as e:
        flash(f'Error editing resident: {str(e)}', 'error')
        return redirect(url_for('manage_residents'))
    finally:
        connection.close()

@app.route('/delete_resident/<int:resident_id>')
def delete_resident(resident_id):
    """Delete resident"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_residents'))
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM resident WHERE id = %s", (resident_id,))
        connection.commit()
        flash('Resident deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting resident: {str(e)}', 'error')
    finally:
        connection.close()
    
    return redirect(url_for('manage_residents'))

@app.route('/manage_vehicles')
def manage_vehicles():
    """Admin page to manage vehicles"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT v.id, v.vehicle_no, v.vehicle_type, v.vehicle_company, v.vehicle_color, r.name as resident_name
            FROM vehicle v
            JOIN resident r ON v.resident_id = r.id
            ORDER BY v.vehicle_no
        """)
        vehicles = cursor.fetchall()
        
        return render_template('manage_vehicles.html', vehicles=vehicles)
    except Exception as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        connection.close()

@app.route('/add_vehicle', methods=['GET', 'POST'])
def add_vehicle():
    """Add new vehicle"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor()
        
        if request.method == 'POST':
            vehicle_no = request.form.get('vehicle_no')
            vehicle_type = request.form.get('vehicle_type')
            vehicle_company = request.form.get('vehicle_company')
            vehicle_color = request.form.get('vehicle_color')
            resident_id = request.form.get('resident_id')
            
            # Normalize vehicle number
            if vehicle_no:
                vehicle_no = vehicle_no.strip().upper()
            
            # Validation
            if not all([vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id]):
                flash('All fields are required', 'error')
                return render_template('add_vehicle.html')
            
            # Validate vehicle number format
            if not validate_vehicle_number(vehicle_no):
                flash('Vehicle number must be between 2-25 characters.', 'error')
                return render_template('add_vehicle.html')
            
            # Check if vehicle number already exists
            cursor.execute("SELECT id FROM vehicle WHERE vehicle_no = %s", (vehicle_no,))
            if cursor.fetchone():
                flash('Vehicle number already exists', 'error')
                return render_template('add_vehicle.html')
            
            # Insert new vehicle
            cursor.execute("""
                INSERT INTO vehicle (vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id) 
                VALUES (%s, %s, %s, %s, %s)
            """, (vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id))
            
            connection.commit()
            flash('Vehicle added successfully', 'success')
            return redirect(url_for('manage_vehicles'))
        
        # Get residents for dropdown
        cursor.execute("SELECT id, name FROM resident ORDER BY name")
        residents = cursor.fetchall()
        
        return render_template('add_vehicle.html', residents=residents)
        
    except Exception as e:
        flash(f'Error adding vehicle: {str(e)}', 'error')
        return redirect(url_for('manage_vehicles'))
    finally:
        connection.close()

@app.route('/edit_vehicle/<int:vehicle_id>', methods=['GET', 'POST'])
def edit_vehicle(vehicle_id):
    """Edit vehicle details"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_vehicles'))
    
    try:
        cursor = connection.cursor()
        
        if request.method == 'POST':
            vehicle_no = request.form.get('vehicle_no')
            vehicle_type = request.form.get('vehicle_type')
            vehicle_company = request.form.get('vehicle_company')
            vehicle_color = request.form.get('vehicle_color')
            resident_id = request.form.get('resident_id')
            
            # Normalize vehicle number
            if vehicle_no:
                vehicle_no = vehicle_no.strip().upper()
            
            # Validation
            if not all([vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id]):
                flash('All fields are required', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))
            
            # Validate vehicle number format
            if not validate_vehicle_number(vehicle_no):
                flash('Invalid vehicle number format. Please enter 3-20 characters with letters, numbers, spaces, or hyphens only.', 'error')
                return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))
            
            # Update vehicle
            cursor.execute("""
                UPDATE vehicle 
                SET vehicle_no = %s, vehicle_type = %s, vehicle_company = %s, vehicle_color = %s, resident_id = %s 
                WHERE id = %s
            """, (vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id, vehicle_id))
            
            connection.commit()
            flash('Vehicle updated successfully', 'success')
            return redirect(url_for('manage_vehicles'))
        
        # Get vehicle details
        cursor.execute("SELECT * FROM vehicle WHERE id = %s", (vehicle_id,))
        vehicle = cursor.fetchone()
        
        # Get residents for dropdown
        cursor.execute("SELECT id, name FROM resident ORDER BY name")
        residents = cursor.fetchall()
        
        return render_template('edit_vehicle.html', vehicle=vehicle, residents=residents)
        
    except Exception as e:
        flash(f'Error editing vehicle: {str(e)}', 'error')
        return redirect(url_for('manage_vehicles'))
    finally:
        connection.close()

@app.route('/delete_vehicle/<int:vehicle_id>')
def delete_vehicle(vehicle_id):
    """Delete vehicle"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_vehicles'))
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM vehicle WHERE id = %s", (vehicle_id,))
        connection.commit()
        flash('Vehicle deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting vehicle: {str(e)}', 'error')
    finally:
        connection.close()
    
    return redirect(url_for('manage_vehicles'))

@app.route('/manage_parking')
def manage_parking():
    """Admin page to manage parking slots"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM parking ORDER BY slot_no")
        parking_slots = cursor.fetchall()
        
        return render_template('manage_parking.html', parking_slots=parking_slots)
    except Exception as e:
        flash(f'Error loading parking slots: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        connection.close()

@app.route('/add_parking_slot', methods=['GET', 'POST'])
def add_parking_slot():
    """Add new parking slot"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        slot_no = request.form.get('slot_no')
        location = request.form.get('location')
        status = request.form.get('status', 'Available')
        slot_type = request.form.get('slot_type')
        
        connection = get_db_connection()
        if not connection:
            flash('Database connection error', 'error')
            return render_template('add_parking_slot.html')
        
        try:
            cursor = connection.cursor()
            
            # Check if slot number already exists
            cursor.execute("SELECT id FROM parking WHERE slot_no = %s", (slot_no,))
            if cursor.fetchone():
                flash('Slot number already exists', 'error')
                return render_template('add_parking_slot.html')
            
            # Insert new parking slot
            cursor.execute("""
                INSERT INTO parking (slot_no, location, status, slot_type) 
                VALUES (%s, %s, %s, %s)
            """, (slot_no, location, status, slot_type))
            
            connection.commit()
            flash('Parking slot added successfully', 'success')
            return redirect(url_for('manage_parking'))
            
        except Exception as e:
            flash(f'Error adding parking slot: {str(e)}', 'error')
        finally:
            connection.close()
    
    return render_template('add_parking_slot.html')

@app.route('/edit_parking_slot/<int:slot_id>', methods=['GET', 'POST'])
def edit_parking_slot(slot_id):
    """Edit parking slot details"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_parking'))
    
    try:
        cursor = connection.cursor()
        
        if request.method == 'POST':
            slot_no = request.form.get('slot_no')
            location = request.form.get('location')
            status = request.form.get('status')
            slot_type = request.form.get('slot_type')
            
            # Update parking slot
            cursor.execute("""
                UPDATE parking 
                SET slot_no = %s, location = %s, status = %s, slot_type = %s 
                WHERE id = %s
            """, (slot_no, location, status, slot_type, slot_id))
            
            connection.commit()
            flash('Parking slot updated successfully', 'success')
            return redirect(url_for('manage_parking'))
        
        # Get parking slot details
        cursor.execute("SELECT * FROM parking WHERE id = %s", (slot_id,))
        slot = cursor.fetchone()
        
        return render_template('edit_parking_slot.html', slot=slot)
        
    except Exception as e:
        flash(f'Error editing parking slot: {str(e)}', 'error')
        return redirect(url_for('manage_parking'))
    finally:
        connection.close()

@app.route('/delete_parking_slot/<int:slot_id>')
def delete_parking_slot(slot_id):
    """Delete parking slot"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('manage_parking'))
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM parking WHERE id = %s", (slot_id,))
        connection.commit()
        flash('Parking slot deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting parking slot: {str(e)}', 'error')
    finally:
        connection.close()
    
    return redirect(url_for('manage_parking'))

@app.route('/update_parking_status/<int:slot_id>', methods=['POST'])
def update_parking_status(slot_id):
    """Update parking slot status"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    status = data.get('status')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE parking SET status = %s WHERE id = %s", (status, slot_id))
        connection.commit()
        return jsonify({'success': True, 'message': 'Status updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/get_residents_for_assignment')
def get_residents_for_assignment():
    """Get list of current residents for assignment dropdown"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        # Get current residents who don't have vehicles assigned to parking slots
        cursor.execute("""
            SELECT DISTINCT r.id, r.name, r.username, r.floor, r.door_number 
            FROM resident r 
            WHERE r.status = 'Current Resident'
            ORDER BY r.name
        """)
        residents = cursor.fetchall()
        
        # Convert to list of dicts for JSON response
        residents_list = []
        for resident in residents:
            residents_list.append({
                'id': resident[0],
                'name': resident[1],
                'username': resident[2],
                'floor': resident[3],
                'door_number': resident[4]
            })
        
        return jsonify({'success': True, 'residents': residents_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/get_resident_vehicles/<int:resident_id>')
def get_resident_vehicles(resident_id):
    """Get vehicles for a specific resident"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT vehicle_no, vehicle_type FROM vehicle WHERE resident_id = %s", (resident_id,))
        vehicles = cursor.fetchall()
        
        # Convert to list of dicts for JSON response
        vehicles_list = []
        for vehicle in vehicles:
            vehicles_list.append({
                'vehicle_no': vehicle[0],
                'vehicle_type': vehicle[1]
            })
        
        return jsonify({'success': True, 'vehicles': vehicles_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/assign_parking_slot', methods=['POST'])
def assign_parking_slot():
    """Assign a parking slot to a resident's vehicle with compatibility checking"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    slot_id = data.get('slot_id')
    resident_id = data.get('resident_id')
    vehicle_no = data.get('vehicle_no')
    
    if not all([slot_id, resident_id, vehicle_no]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Get slot information including type
        cursor.execute("SELECT status, slot_type FROM parking WHERE id = %s", (slot_id,))
        slot_result = cursor.fetchone()
        if not slot_result:
            return jsonify({'success': False, 'message': 'Parking slot not found'}), 400
        if slot_result[0] != 'Available':
            return jsonify({'success': False, 'message': 'Parking slot is not available'}), 400
        
        slot_type = slot_result[1]
        
        # Get vehicle information
        cursor.execute("SELECT vehicle_type FROM vehicle WHERE vehicle_no = %s AND resident_id = %s", (vehicle_no, resident_id))
        vehicle_result = cursor.fetchone()
        if not vehicle_result:
            return jsonify({'success': False, 'message': 'Vehicle not found or does not belong to selected resident'}), 400
        
        vehicle_type = vehicle_result[0]
        
        # Check vehicle type compatibility with slot type
        vehicle_compatibility = {
            'Car': ['Car', 'Sedan', 'Hatchback'],
            'SUV': ['SUV', 'Car'],
            'Bike': ['Bike', 'Scooter', 'Motorcycle'],
            'Handicapped': ['Car', 'SUV'],
            'Visitor': ['Car', 'SUV', 'Bike', 'Scooter', 'Motorcycle']
        }
        
        compatible_types = vehicle_compatibility.get(slot_type, [])
        if vehicle_type not in compatible_types:
            return jsonify({
                'success': False, 
                'message': f'Vehicle type "{vehicle_type}" is not compatible with slot type "{slot_type}". Compatible types: {", ".join(compatible_types)}'
            }), 400
        
        # Check if vehicle is already assigned to another slot
        cursor.execute("SELECT id FROM parking WHERE vehicle_no = %s AND status = 'Occupied'", (vehicle_no,))
        existing_assignment = cursor.fetchone()
        if existing_assignment:
            return jsonify({'success': False, 'message': 'Vehicle is already assigned to another parking slot'}), 400
        
        # Assign the slot
        cursor.execute("UPDATE parking SET status = 'Occupied', vehicle_no = %s WHERE id = %s", (vehicle_no, slot_id))
        connection.commit()
        
        return jsonify({'success': True, 'message': f'Parking slot assigned successfully! {vehicle_type} vehicle is compatible with {slot_type} slot.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/unassign_parking_slot', methods=['POST'])
def unassign_parking_slot():
    """Unassign a parking slot from a resident's vehicle"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    slot_id = data.get('slot_id')
    
    if not slot_id:
        return jsonify({'success': False, 'message': 'Missing slot ID'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if slot is occupied
        cursor.execute("SELECT status, vehicle_no FROM parking WHERE id = %s", (slot_id,))
        slot_result = cursor.fetchone()
        if not slot_result or slot_result[0] != 'Occupied':
            return jsonify({'success': False, 'message': 'Parking slot is not occupied'}), 400
        
        # Unassign the slot
        cursor.execute("UPDATE parking SET status = 'Available', vehicle_no = NULL WHERE id = %s", (slot_id,))
        connection.commit()
        
        return jsonify({'success': True, 'message': 'Parking slot unassigned successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

# Charges Management Routes
@app.route('/manage_charges')
def manage_charges():
    """Admin page to manage charges and payments"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor()
        
        # First, let's check if the required columns exist
        cursor.execute("SHOW COLUMNS FROM payments")
        payment_columns = [column[0] for column in cursor.fetchall()]
        
        # Build query based on available columns
        if 'due_date' in payment_columns:
            payment_query = """
                SELECT 
                    r.id,
                    r.name,
                    r.username,
                    r.floor,
                    r.door_number,
                    p.id as parking_id,
                    p.slot_no,
                    p.slot_type,
                    v.vehicle_no,
                    v.vehicle_type,
                    c.monthly_charge,
                    py.id as payment_id,
                    py.amount as payment_amount,
                    py.status as payment_status,
                    py.due_date,
                    py.payment_date
                FROM resident r
                LEFT JOIN vehicle v ON r.id = v.resident_id
                LEFT JOIN parking p ON v.vehicle_no = p.vehicle_no AND p.status = 'Occupied'
                LEFT JOIN charges c ON p.slot_type = c.slot_type AND v.vehicle_type = c.vehicle_type
                LEFT JOIN payments py ON r.id = py.resident_id AND py.parking_slot_id = p.id 
                    AND py.payment_type = 'Monthly'
                    AND py.id = (
                        SELECT MAX(py2.id) 
                        FROM payments py2 
                        WHERE py2.resident_id = r.id 
                        AND py2.parking_slot_id = p.id 
                        AND py2.payment_type = 'Monthly'
                    )
                WHERE r.status = 'Current Resident'
                ORDER BY r.name
            """
        else:
            # Fallback query without due_date
            payment_query = """
                SELECT 
                    r.id,
                    r.name,
                    r.username,
                    r.floor,
                    r.door_number,
                    p.id as parking_id,
                    p.slot_no,
                    p.slot_type,
                    v.vehicle_no,
                    v.vehicle_type,
                    c.monthly_charge,
                    py.id as payment_id,
                    py.amount as payment_amount,
                    py.status as payment_status,
                    NULL as due_date,
                    py.payment_date
                FROM resident r
                LEFT JOIN vehicle v ON r.id = v.resident_id
                LEFT JOIN parking p ON v.vehicle_no = p.vehicle_no AND p.status = 'Occupied'
                LEFT JOIN charges c ON p.slot_type = c.slot_type AND v.vehicle_type = c.vehicle_type
                LEFT JOIN payments py ON r.id = py.resident_id AND py.parking_slot_id = p.id 
                    AND py.payment_type = 'Monthly'
                    AND py.id = (
                        SELECT MAX(py2.id) 
                        FROM payments py2 
                        WHERE py2.resident_id = r.id 
                        AND py2.parking_slot_id = p.id 
                        AND py2.payment_type = 'Monthly'
                    )
                WHERE r.status = 'Current Resident'
                ORDER BY r.name
            """
        
        cursor.execute(payment_query)
        resident_charges = cursor.fetchall()
        
        # Get charge rates for different slot/vehicle combinations
        cursor.execute("SELECT * FROM charges ORDER BY slot_type, vehicle_type")
        charge_rates = cursor.fetchall()
        
        return render_template('charges.html', 
                             resident_charges=resident_charges, 
                             charge_rates=charge_rates)
    except Exception as e:
        flash(f'Error loading charges: {str(e)}', 'error')
        print(f"Charges error: {str(e)}")  # Debug output
        return redirect(url_for('admin_dashboard'))
    finally:
        if connection:
            connection.close()

@app.route('/assign_charges', methods=['POST'])
def assign_charges():
    """Assign charges to a resident for their parking slot"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    resident_id = data.get('resident_id')
    parking_slot_id = data.get('parking_slot_id')
    amount = data.get('amount')
    due_date = data.get('due_date')
    description = data.get('description', 'Monthly parking charges')
    
    if not all([resident_id, parking_slot_id, amount]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if due_date column exists
        cursor.execute("SHOW COLUMNS FROM payments")
        payment_columns = [column[0] for column in cursor.fetchall()]
        
        # Check if payment already exists for this resident and slot
        cursor.execute("""
            SELECT id FROM payments 
            WHERE resident_id = %s AND parking_slot_id = %s 
            AND payment_type = 'Monthly' AND status IN ('Pending', 'Not Assigned')
        """, (resident_id, parking_slot_id))
        
        existing_payment = cursor.fetchone()
        
        if existing_payment:
            # Update existing payment
            if 'due_date' in payment_columns:
                cursor.execute("""
                    UPDATE payments 
                    SET amount = %s, due_date = %s, description = %s, status = 'Pending'
                    WHERE id = %s
                """, (amount, due_date, description, existing_payment[0]))
            else:
                cursor.execute("""
                    UPDATE payments 
                    SET amount = %s, description = %s, status = 'Pending'
                    WHERE id = %s
                """, (amount, description, existing_payment[0]))
        else:
            # Create new payment record
            if 'due_date' in payment_columns:
                cursor.execute("""
                    INSERT INTO payments (resident_id, parking_slot_id, amount, description, 
                                        payment_type, payment_method, due_date, status)
                    VALUES (%s, %s, %s, %s, 'Monthly', 'Pending', %s, 'Pending')
                """, (resident_id, parking_slot_id, amount, description, due_date))
            else:
                cursor.execute("""
                    INSERT INTO payments (resident_id, parking_slot_id, amount, description, 
                                        payment_type, payment_method, status)
                    VALUES (%s, %s, %s, %s, 'Monthly', 'Pending', 'Pending')
                """, (resident_id, parking_slot_id, amount, description))
        
        connection.commit()
        
        # Get the payment ID to return for UI updates
        if existing_payment:
            payment_id = existing_payment[0]
        else:
            payment_id = cursor.lastrowid
            
        return jsonify({
            'success': True, 
            'message': 'Charges assigned successfully',
            'payment_id': payment_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/collect_payment', methods=['POST'])
def collect_payment():
    """Admin collects payment for a resident (mark as Completed)"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    payment_id = data.get('payment_id')
    payment_method = data.get('payment_method', 'Cash')
    notes = data.get('notes', '')
    
    if not payment_id:
        return jsonify({'success': False, 'message': 'Missing payment ID'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Get payment amount before updating
        cursor.execute("SELECT amount FROM payments WHERE id=%s", (payment_id,))
        payment_result = cursor.fetchone()
        payment_amount = payment_result[0] if payment_result else 0
        
        # Mark payment as completed with payment method and notes
        cursor.execute("""
            UPDATE payments 
            SET status='Completed', payment_date=NOW(), payment_method=%s, notes=%s 
            WHERE id=%s
        """, (payment_method, notes, payment_id))
        connection.commit()
        
        # Get the completion date for UI update
        current_date = datetime.now().strftime('%d/%m/%Y')
        
        return jsonify({
            'success': True, 
            'message': 'Payment collected and marked as Completed.',
            'completed_date': current_date,
            'amount': float(payment_amount)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/update_charge_rates', methods=['POST'])
def update_charge_rates():
    """Update charge rates for slot/vehicle combinations"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    charge_id = data.get('charge_id')
    monthly_charge = data.get('monthly_charge')
    guest_charge = data.get('guest_charge')
    penalty_charge = data.get('penalty_charge')
    
    if not all([charge_id, monthly_charge, guest_charge, penalty_charge]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE charges 
            SET monthly_charge = %s, guest_charge_per_day = %s, penalty_charge = %s
            WHERE id = %s
        """, (monthly_charge, guest_charge, penalty_charge, charge_id))
        
        connection.commit()
        return jsonify({'success': True, 'message': 'Charge rates updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

# Resident routes
@app.route('/resident_vehicles')
def resident_vehicles():
    """Resident's vehicles page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_dashboard'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        cursor.execute("SELECT * FROM vehicle WHERE resident_id = %s", (resident_id,))
        vehicles = cursor.fetchall()
        
        return render_template('resident_vehicles.html', vehicles=vehicles)
    except Exception as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return redirect(url_for('resident_dashboard'))
    finally:
        connection.close()

@app.route('/resident_add_vehicle', methods=['GET', 'POST'])
def resident_add_vehicle():
    """Resident add vehicle page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    if request.method == 'POST':
        vehicle_no = request.form.get('vehicle_no')
        vehicle_type = request.form.get('vehicle_type')
        vehicle_company = request.form.get('vehicle_company')
        vehicle_color = request.form.get('vehicle_color')
        resident_id = session['resident_id']
        
        # Normalize vehicle number
        if vehicle_no:
            vehicle_no = vehicle_no.strip().upper()
        
        # Validation
        if not all([vehicle_no, vehicle_type, vehicle_company, vehicle_color]):
            flash('All fields are required', 'error')
            return render_template('resident_add_vehicle.html')
        
        # Validate vehicle number format
        if not validate_vehicle_number(vehicle_no):
            flash('Invalid vehicle number format. Please enter 3-20 characters with letters, numbers, spaces, or hyphens only.', 'error')
            return render_template('resident_add_vehicle.html')
        
        connection = get_db_connection()
        if not connection:
            flash('Database connection error', 'error')
            return render_template('resident_add_vehicle.html')
        
        try:
            cursor = connection.cursor()
            
            # Check if vehicle number already exists
            cursor.execute("SELECT id FROM vehicle WHERE vehicle_no = %s", (vehicle_no,))
            if cursor.fetchone():
                flash('Vehicle number already exists', 'error')
                return render_template('resident_add_vehicle.html')
            
            # Insert new vehicle
            cursor.execute("""
                INSERT INTO vehicle (vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id) 
                VALUES (%s, %s, %s, %s, %s)
            """, (vehicle_no, vehicle_type, vehicle_company, vehicle_color, resident_id))
            
            connection.commit()
            flash('Vehicle added successfully', 'success')
            return redirect(url_for('resident_vehicles'))
            
        except Exception as e:
            flash(f'Error adding vehicle: {str(e)}', 'error')
        finally:
            connection.close()
    
    return render_template('resident_add_vehicle.html')

@app.route('/resident_edit_vehicle/<int:vehicle_id>', methods=['GET', 'POST'])
def resident_edit_vehicle(vehicle_id):
    """Resident edit vehicle page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_vehicles'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Check if vehicle belongs to the resident
        cursor.execute("SELECT * FROM vehicle WHERE id = %s AND resident_id = %s", (vehicle_id, resident_id))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            flash('Vehicle not found or access denied', 'error')
            return redirect(url_for('resident_vehicles'))
        
        if request.method == 'POST':
            vehicle_no = request.form.get('vehicle_no')
            vehicle_type = request.form.get('vehicle_type')
            vehicle_company = request.form.get('vehicle_company')
            vehicle_color = request.form.get('vehicle_color')
            
            # Update vehicle
            cursor.execute("""
                UPDATE vehicle 
                SET vehicle_no = %s, vehicle_type = %s, vehicle_company = %s, vehicle_color = %s 
                WHERE id = %s AND resident_id = %s
            """, (vehicle_no, vehicle_type, vehicle_company, vehicle_color, vehicle_id, resident_id))
            
            connection.commit()
            flash('Vehicle updated successfully', 'success')
            return redirect(url_for('resident_vehicles'))
        
        return render_template('resident_edit_vehicle.html', vehicle=vehicle)
        
    except Exception as e:
        flash(f'Error editing vehicle: {str(e)}', 'error')
        return redirect(url_for('resident_vehicles'))
    finally:
        connection.close()

@app.route('/resident_qr_codes')
def resident_qr_codes():
    """Resident QR codes page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_dashboard'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        cursor.execute("SELECT * FROM vehicle WHERE resident_id = %s", (resident_id,))
        vehicles = cursor.fetchall()
        
        return render_template('resident_qr_codes.html', vehicles=vehicles)
    except Exception as e:
        flash(f'Error loading QR codes: {str(e)}', 'error')
        return redirect(url_for('resident_dashboard'))
    finally:
        connection.close()

@app.route('/resident_payments')
def resident_payments():
    """Resident payments page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    return render_template('resident_payments.html')

@app.route('/resident_profile', methods=['GET', 'POST'])
def resident_profile():
    """Resident profile page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_dashboard'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            address = request.form.get('address')
            
            # Update resident profile
            cursor.execute("""
                UPDATE resident 
                SET name = %s, email = %s, phone = %s, address = %s 
                WHERE id = %s
            """, (name, email, phone, address, resident_id))
            
            connection.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('resident_profile'))
        
        # Get resident details
        cursor.execute("SELECT * FROM resident WHERE id = %s", (resident_id,))
        resident = cursor.fetchone()
        
        return render_template('resident_profile.html', resident=resident)
        
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(url_for('resident_dashboard'))
    finally:
        connection.close()

@app.route('/gate_entry')
def gate_entry():
    """QR code scanner page for gate entry/exit"""
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    return render_template('gate_entry.html')

@app.route('/api/scan_qr', methods=['POST'])
def scan_qr():
    """API endpoint to process QR code scan"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    qr_data = data.get('qr_data')
    log_type = data.get('log_type', 'ENTRY')
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR data provided'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        vehicle_no = None
        
        # Parse QR data - could be comprehensive format or simple vehicle number
        if 'RESIDENT_ID:' in qr_data:
            # Enhanced QR format: RESIDENT_ID:1|NAME:John|PHONE:123|VEHICLE:ABC123|SLOT:A1|LOCATION:Ground
            qr_parts = dict(item.split(':', 1) for item in qr_data.split('|') if ':' in item)
            vehicle_no = qr_parts.get('VEHICLE', '').replace('NONE', '') or None
            resident_id = qr_parts.get('RESIDENT_ID')
            
            if not vehicle_no and resident_id:
                # If no vehicle in QR, try to find resident's vehicle
                cursor.execute("SELECT vehicle_no FROM vehicle WHERE resident_id = %s LIMIT 1", (resident_id,))
                vehicle_result = cursor.fetchone()
                vehicle_no = vehicle_result[0] if vehicle_result else None
        else:
            # Simple format - just vehicle number or resident ID
            if qr_data.startswith('RESIDENT_'):
                resident_id = qr_data.replace('RESIDENT_', '')
                cursor.execute("SELECT vehicle_no FROM vehicle WHERE resident_id = %s LIMIT 1", (resident_id,))
                vehicle_result = cursor.fetchone()
                vehicle_no = vehicle_result[0] if vehicle_result else None
            else:
                vehicle_no = qr_data
        
        if not vehicle_no:
            return jsonify({'success': False, 'message': 'No valid vehicle found in QR data'}), 404
        
        # Get full vehicle and resident details
        cursor.execute("""
            SELECT v.id, v.vehicle_no, v.vehicle_type, v.vehicle_company, v.vehicle_color,
                   r.id as resident_id, r.name, r.email, r.phone, r.floor, r.door_number, r.status, r.address,
                   p.slot_no, p.location, p.slot_type, p.status as parking_status
            FROM vehicle v
            LEFT JOIN resident r ON v.resident_id = r.id
            LEFT JOIN parking p ON v.vehicle_no = p.vehicle_no AND p.status = 'Occupied'
            WHERE v.vehicle_no = %s
        """, (vehicle_no,))
        vehicle_data = cursor.fetchone()
        
        if not vehicle_data:
            return jsonify({'success': False, 'message': 'Vehicle not found in database'}), 404
        
        # Check if vehicle is currently inside
        cursor.execute("""
            SELECT id FROM gatelog 
            WHERE vehicle_no = %s AND exit_time IS NULL
        """, (qr_data,))
        active_entry = cursor.fetchone()
        
        current_time = datetime.now()
        
        if log_type == 'EXIT' or active_entry:
            # Vehicle is exiting
            if active_entry:
                cursor.execute("""
                    UPDATE gatelog 
                    SET exit_time = %s, status = 'Exited' 
                    WHERE id = %s
                """, (current_time, active_entry[0]))
                
                # Update parking slot to available if it's a guest slot
                cursor.execute("""
                    UPDATE parking 
                    SET status = 'Available', vehicle_no = NULL 
                    WHERE vehicle_no = %s AND slot_type LIKE '%Visitor%'
                """, (vehicle_no,))
            else:
                return jsonify({'success': False, 'message': 'Vehicle was not logged as entered'}), 400
            
            action = 'EXIT'
            message = f'Vehicle {vehicle_no} exited successfully'
        else:
            # Vehicle is entering
            cursor.execute("""
                INSERT INTO gatelog (vehicle_no, entry_time, status) 
                VALUES (%s, %s, 'Entered')
            """, (vehicle_no, current_time))
            
            action = 'ENTRY'
            message = f'Vehicle {vehicle_no} entered successfully'
        
        connection.commit()
        
        # Return detailed response
        response_data = {
            'success': True,
            'message': message,
            'log_type': action,
            'vehicle_no': vehicle_data[1],
            'vehicle_type': vehicle_data[2] or 'N/A',
            'vehicle_company': vehicle_data[3] or 'N/A',
            'vehicle_color': vehicle_data[4] or 'N/A',
            'vehicle_model': vehicle_data[5] or 'N/A',
            'resident_id': vehicle_data[6] or 'N/A',
            'resident_name': vehicle_data[7] or 'N/A',
            'resident_email': vehicle_data[8] or 'N/A',
            'resident_phone': vehicle_data[9] or 'N/A',
            'floor_no': vehicle_data[10] or 'N/A',
            'door_no': vehicle_data[11] or 'N/A',
            'resident_status': vehicle_data[12] or 'N/A',
            'parking_slot': vehicle_data[13] or 'N/A',
            'parking_location': vehicle_data[14] or 'N/A',
            'parking_type': vehicle_data[15] or 'N/A',
            'timestamp': current_time.isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing QR: {str(e)}'}), 500
    finally:
        connection.close()

@app.route('/generate_qr/<vehicle_no>')
def generate_qr_route(vehicle_no):
    """Generate QR code for a vehicle"""
    if not session.get('admin_logged_in') and not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('index'))
    
    qr_code = generate_qr_code(vehicle_no)
    if qr_code:
        return jsonify({'success': True, 'qr_code': qr_code})
    else:
        return jsonify({'success': False, 'message': 'Error generating QR code'})

@app.route('/generate_resident_qr/<int:resident_id>')
def generate_resident_qr(resident_id):
    """Generate QR code for a resident with all details"""
    if not session.get('admin_logged_in') and not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('index'))
    
    # Check if the logged-in resident is accessing their own QR or if admin
    if session.get('resident_logged_in') and session.get('resident_id') != resident_id:
        flash('Access denied', 'error')
        return redirect(url_for('resident_dashboard'))
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Get resident details with vehicle and parking info
        cursor.execute("""
            SELECT r.id, r.name, r.email, r.phone, r.floor, r.door_number, r.status, r.address,
                   v.vehicle_no, v.vehicle_type, v.vehicle_company, v.vehicle_color,
                   p.slot_no, p.location, p.slot_type, p.status as parking_status
            FROM resident r
            LEFT JOIN vehicle v ON r.id = v.resident_id
            LEFT JOIN parking p ON v.vehicle_no = p.vehicle_no AND p.status = 'Occupied'
            WHERE r.id = %s
            ORDER BY v.id DESC
            LIMIT 1
        """, (resident_id,))
        
        resident_data = cursor.fetchone()
        
        if not resident_data:
            return jsonify({'success': False, 'message': 'Resident not found'}), 404
        
        # Create comprehensive QR data with all details
        qr_info = {
            'type': 'resident_comprehensive',
            'resident_id': resident_data[0],
            'resident_name': resident_data[1],
            'resident_email': resident_data[2],
            'resident_phone': resident_data[3],
            'floor': resident_data[4],
            'door': resident_data[5],
            'resident_status': resident_data[6],
            'resident_address': resident_data[7] or 'N/A',
            'vehicle_no': resident_data[8] or 'No Vehicle Assigned',
            'vehicle_type': resident_data[9] or 'N/A',
            'vehicle_company': resident_data[10] or 'N/A',
            'vehicle_color': resident_data[11] or 'N/A',
            'parking_slot': resident_data[12] or 'No Slot Assigned',
            'parking_location': resident_data[13] or 'N/A',
            'parking_type': resident_data[14] or 'N/A',
            'parking_status': resident_data[15] or 'N/A',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create a comprehensive QR code data string
        qr_data_string = f"RESIDENT_ID:{resident_data[0]}|NAME:{resident_data[1]}|PHONE:{resident_data[3]}|VEHICLE:{resident_data[8] or 'NONE'}|SLOT:{resident_data[12] or 'NONE'}|LOCATION:{resident_data[13] or 'NONE'}"
        
        try:
            import qrcode
            import io
            import base64
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data_string)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64 for web display
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return jsonify({
                'success': True, 
                'qr_code': f"data:image/png;base64,{qr_code_base64}",
                'qr_data': qr_data_string,
                'resident_info': qr_info
            })
            
        except ImportError:
            return jsonify({'success': False, 'message': 'QR code library not installed'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error generating QR: {str(e)}'}), 500
    finally:
        connection.close()

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route('/resident_change_password', methods=['POST'])
def resident_change_password():
    """Resident change password"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All password fields are required', 'error')
        return redirect(url_for('resident_profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('resident_profile'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters', 'error')
        return redirect(url_for('resident_profile'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_profile'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Verify current password
        cursor.execute("SELECT password FROM resident WHERE id = %s", (resident_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != current_password:
            flash('Current password is incorrect', 'error')
            return redirect(url_for('resident_profile'))
        
        # Update password
        cursor.execute("UPDATE resident SET password = %s WHERE id = %s", (new_password, resident_id))
        connection.commit()
        
        flash('Password changed successfully', 'success')
        return redirect(url_for('resident_profile'))
        
    except Exception as e:
        flash(f'Error changing password: {str(e)}', 'error')
        return redirect(url_for('resident_profile'))
    finally:
        connection.close()

@app.route('/complaints')
def complaints():
    """Admin complaints management"""
    print(f"Complaints route - Session: {dict(session)}")  # Debug print
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    
    connection = get_db_connection()
    complaints_data = []
    
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT c.id, c.subject, c.complaint_text as description, 
                       c.status, c.complaint_date, 
                       r.name as resident_name, r.email as resident_email
                FROM complaints c
                JOIN resident r ON c.resident_id = r.id
                ORDER BY c.complaint_date DESC
            """)
            complaints_data = cursor.fetchall()
            print(f'Found {len(complaints_data)} complaints')  # Debug print
        except Exception as e:
            print(f'Error fetching complaints: {str(e)}')  # Debug print
            flash('Error loading complaints data', 'error')
        finally:
            connection.close()
    else:
        flash('Database connection error', 'error')
    
    return render_template('complaints.html', complaints=complaints_data)

@app.route('/resident_complaints', methods=['GET', 'POST'])
def resident_complaints():
    """Resident complaints page"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_dashboard'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        if request.method == 'POST':
            subject = request.form.get('subject')
            description = request.form.get('description')
            
            if not subject or not description:
                flash('Subject and description are required', 'error')
            else:
                cursor.execute("""
                    INSERT INTO complaints (resident_id, subject, complaint_text, complaint_date, status)
                    VALUES (%s, %s, %s, NOW(), 'Pending')
                """, (resident_id, subject, description))
                connection.commit()
                flash('Complaint submitted successfully', 'success')
                return redirect(url_for('resident_complaints'))
        
        cursor.execute("""
            SELECT id, subject, complaint_text as description, 
                   status, complaint_date
            FROM complaints
            WHERE resident_id = %s
            ORDER BY complaint_date DESC
        """, (resident_id,))
        complaints_data = cursor.fetchall()
        
        return render_template('resident_complaints.html', complaints=complaints_data)
    except Exception as e:
        flash(f'Error processing request: {str(e)}', 'error')
        return redirect(url_for('resident_dashboard'))
    finally:
        connection.close()

@app.route('/resident_charges')
def resident_charges():
    """Resident charges page with comprehensive real-time data"""
    if not session.get('resident_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('resident_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('resident_dashboard'))
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get comprehensive payment data with due dates and categories
        cursor.execute("""
            SELECT p.id, p.amount, p.description, p.status, p.payment_date, 
                   p.due_date, p.payment_type, p.payment_method,
                   CASE 
                       WHEN p.status = 'Pending' AND p.due_date < CURDATE() THEN 'Overdue'
                       WHEN p.status = 'Pending' THEN 'Pending'
                       WHEN p.status = 'Completed' THEN 'Paid'
                       ELSE p.status
                   END as display_status,
                   pk.slot_no, pk.slot_type, v.vehicle_no
            FROM payments p
            LEFT JOIN parking pk ON p.parking_slot_id = pk.id
            LEFT JOIN vehicle v ON pk.vehicle_no = v.vehicle_no
            WHERE p.resident_id = %s
            ORDER BY p.payment_date DESC, p.id DESC
        """, (resident_id,))
        charges_data = cursor.fetchall()
        
        # Calculate summary statistics
        total_pending = sum(float(charge[1]) for charge in charges_data if charge[8] == 'Pending')
        total_paid = sum(float(charge[1]) for charge in charges_data if charge[8] == 'Paid')
        total_overdue = sum(float(charge[1]) for charge in charges_data if charge[8] == 'Overdue')
        
        # Get resident's current parking details
        cursor.execute("""
            SELECT r.name, r.email, r.phone, r.floor, r.door_number,
                   v.vehicle_no, v.vehicle_type, p.slot_no, p.slot_type, p.location
            FROM resident r
            LEFT JOIN vehicle v ON r.id = v.resident_id
            LEFT JOIN parking p ON v.vehicle_no = p.vehicle_no AND p.status = 'Occupied'
            WHERE r.id = %s
            LIMIT 1
        """, (resident_id,))
        resident_info = cursor.fetchone()
        
        # Calculate monthly rate from charges table
        cursor.execute("""
            SELECT COALESCE(c.monthly_charge, 500) as monthly_rate
            FROM parking p 
            JOIN vehicle v ON p.vehicle_no = v.vehicle_no 
            LEFT JOIN charges c ON p.slot_type = c.slot_type AND v.vehicle_type = c.vehicle_type
            WHERE v.resident_id = %s AND p.status = 'Occupied' 
            LIMIT 1
        """, (resident_id,))
        monthly_rate_result = cursor.fetchone()
        monthly_rate = monthly_rate_result[0] if monthly_rate_result else 500
        
        summary_data = {
            'total_pending': total_pending,
            'total_paid': total_paid,
            'total_overdue': total_overdue,
            'monthly_rate': float(monthly_rate),
            'total_charges': len(charges_data)
        }
        
        return render_template('resident_charges.html', 
                             charges=charges_data, 
                             summary=summary_data,
                             resident_info=resident_info)
    except Exception as e:
        flash(f'Error fetching charges: {str(e)}', 'error')
        return redirect(url_for('resident_dashboard'))
    finally:
        connection.close()

@app.route('/api/resident_charges_data')
def get_resident_charges_data():
    """Get real-time charges data for logged-in resident (API endpoint)"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get comprehensive payment data with due dates and categories
        cursor.execute("""
            SELECT p.id, p.amount, p.description, p.status, p.payment_date, 
                   p.due_date, p.payment_type, p.payment_method,
                   CASE 
                       WHEN p.status = 'Pending' AND p.due_date < CURDATE() THEN 'Overdue'
                       WHEN p.status = 'Pending' THEN 'Pending'
                       WHEN p.status = 'Completed' THEN 'Paid'
                       ELSE p.status
                   END as display_status,
                   pk.slot_no, pk.slot_type, v.vehicle_no
            FROM payments p
            LEFT JOIN parking pk ON p.parking_slot_id = pk.id
            LEFT JOIN vehicle v ON pk.vehicle_no = v.vehicle_no
            WHERE p.resident_id = %s
            ORDER BY p.payment_date DESC, p.id DESC
        """, (resident_id,))
        charges_data = cursor.fetchall()
        
        # Convert to list of dictionaries for JSON response
        charges_list = []
        for charge in charges_data:
            charges_list.append({
                'id': charge[0],
                'amount': float(charge[1]) if charge[1] else 0,
                'description': charge[2] or 'Monthly parking charges',
                'status': charge[3] or 'Pending',
                'payment_date': charge[4].strftime('%Y-%m-%d %H:%M') if charge[4] else None,
                'due_date': charge[5].strftime('%Y-%m-%d') if charge[5] else None,
                'payment_type': charge[6] or 'Monthly',
                'payment_method': charge[7] or 'N/A',
                'display_status': charge[8] or 'Pending',
                'slot_no': charge[9] or 'N/A',
                'slot_type': charge[10] or 'N/A',
                'vehicle_no': charge[11] or 'N/A'
            })
        
        # Calculate summary statistics
        total_pending = sum(charge['amount'] for charge in charges_list if charge['display_status'] == 'Pending')
        total_paid = sum(charge['amount'] for charge in charges_list if charge['display_status'] == 'Paid')
        total_overdue = sum(charge['amount'] for charge in charges_list if charge['display_status'] == 'Overdue')
        
        # Get monthly rate
        cursor.execute("""
            SELECT COALESCE(c.monthly_charge, 500) as monthly_rate
            FROM parking p 
            JOIN vehicle v ON p.vehicle_no = v.vehicle_no 
            LEFT JOIN charges c ON p.slot_type = c.slot_type AND v.vehicle_type = c.vehicle_type
            WHERE v.resident_id = %s AND p.status = 'Occupied' 
            LIMIT 1
        """, (resident_id,))
        monthly_rate_result = cursor.fetchone()
        monthly_rate = monthly_rate_result[0] if monthly_rate_result else 500
        
        return jsonify({
            'success': True,
            'charges': charges_list,
            'summary': {
                'total_pending': total_pending,
                'total_paid': total_paid,
                'total_overdue': total_overdue,
                'monthly_rate': float(monthly_rate),
                'total_charges': len(charges_list)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

# Resident Payment Features
@app.route('/api/resident_payment_data')
def get_resident_payment_data():
    """Get real-time payment data for logged-in resident"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get current balance, monthly rate, and pending amount
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN status = 'Completed' THEN amount ELSE 0 END), 0) as paid_amount,
                COALESCE(SUM(CASE WHEN status = 'Pending' THEN amount ELSE 0 END), 0) as pending_amount
            FROM payments 
            WHERE resident_id = %s
        """, (resident_id,))
        
        payment_summary = cursor.fetchone()
        paid_amount = payment_summary[0] if payment_summary else 0
        pending_amount = payment_summary[1] if payment_summary else 0
        
        # Get monthly rate from charges table based on resident's parking assignment
        cursor.execute("""
            SELECT COALESCE(c.monthly_charge, 500) as monthly_rate
            FROM parking p 
            JOIN vehicle v ON p.vehicle_no = v.vehicle_no 
            LEFT JOIN charges c ON p.slot_type = c.slot_type AND v.vehicle_type = c.vehicle_type
            WHERE v.resident_id = %s AND p.status = 'Occupied' 
            LIMIT 1
        """, (resident_id,))
        
        monthly_rate_result = cursor.fetchone()
        monthly_rate = monthly_rate_result[0] if monthly_rate_result else 500
        
        # Get payment history
        cursor.execute("""
            SELECT id, amount, description, status, payment_date, payment_method, payment_type, due_date
            FROM payments
            WHERE resident_id = %s
            ORDER BY payment_date DESC, id DESC
            LIMIT 10
        """, (resident_id,))
        
        payment_history = []
        for payment in cursor.fetchall():
            payment_history.append({
                'id': payment[0],
                'amount': float(payment[1]) if payment[1] else 0,
                'description': payment[2] or 'Monthly parking charges',
                'status': payment[3] or 'Pending',
                'date': payment[4].strftime('%Y-%m-%d') if payment[4] else 'N/A',
                'method': payment[5] or 'N/A',
                'type': payment[6] or 'Monthly',
                'due_date': payment[7].strftime('%Y-%m-%d') if payment[7] else 'N/A'
            })
        
        # Get or set auto payment status (adding column if not exists)
        try:
            cursor.execute("SELECT auto_payment FROM resident WHERE id = %s", (resident_id,))
            auto_payment_result = cursor.fetchone()
            auto_payment = auto_payment_result[0] if auto_payment_result and auto_payment_result[0] is not None else False
        except Exception:
            # Column might not exist, add it
            try:
                cursor.execute("ALTER TABLE resident ADD COLUMN auto_payment BOOLEAN DEFAULT FALSE")
                connection.commit()
                auto_payment = False
            except Exception:
                auto_payment = False
        
        return jsonify({
            'success': True,
            'data': {
                'current_balance': float(paid_amount),
                'monthly_rate': float(monthly_rate),
                'pending_amount': float(pending_amount),
                'auto_payment': bool(auto_payment),
                'payment_history': payment_history
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/api/view_bill/<int:payment_id>')
def view_bill(payment_id):
    """Get bill details for viewing in modal"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get bill details with resident and parking info
        cursor.execute("""
            SELECT 
                p.id, p.amount, p.description, p.status, p.payment_date, p.due_date,
                r.name, r.email, r.phone, r.floor, r.door_number,
                pk.slot_no, pk.slot_type, v.vehicle_no, v.vehicle_type
            FROM payments p
            JOIN resident r ON p.resident_id = r.id
            LEFT JOIN parking pk ON p.parking_slot_id = pk.id
            LEFT JOIN vehicle v ON pk.vehicle_no = v.vehicle_no
            WHERE p.id = %s AND p.resident_id = %s
        """, (payment_id, resident_id))
        
        bill_data = cursor.fetchone()
        if not bill_data:
            return jsonify({'success': False, 'message': 'Bill not found'}), 404
        
        bill = {
            'id': bill_data[0],
            'amount': float(bill_data[1]) if bill_data[1] else 0,
            'description': bill_data[2] or 'Monthly parking charges',
            'status': bill_data[3] or 'Pending',
            'payment_date': bill_data[4].strftime('%Y-%m-%d %H:%M') if bill_data[4] else 'Not paid',
            'due_date': bill_data[5].strftime('%Y-%m-%d') if bill_data[5] else 'N/A',
            'resident_name': bill_data[6],
            'resident_email': bill_data[7],
            'resident_phone': bill_data[8],
            'resident_location': f"Floor {bill_data[9]}, Door {bill_data[10]}",
            'slot_no': bill_data[11] or 'N/A',
            'slot_type': bill_data[12] or 'N/A',
            'vehicle_no': bill_data[13] or 'N/A',
            'vehicle_type': bill_data[14] or 'N/A'
        }
        
        return jsonify({'success': True, 'bill': bill})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/api/download_receipt/<int:payment_id>')
def download_receipt(payment_id):
    """Generate and download PDF receipt"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get payment details
        cursor.execute("""
            SELECT 
                p.id, p.amount, p.description, p.status, p.payment_date, p.payment_method,
                r.name, r.email, r.phone, r.floor, r.door_number,
                pk.slot_no, pk.slot_type, v.vehicle_no, v.vehicle_type
            FROM payments p
            JOIN resident r ON p.resident_id = r.id
            LEFT JOIN parking pk ON p.parking_slot_id = pk.id
            LEFT JOIN vehicle v ON pk.vehicle_no = v.vehicle_no
            WHERE p.id = %s AND p.resident_id = %s AND p.status = 'Completed'
        """, (payment_id, resident_id))
        
        receipt_data = cursor.fetchone()
        if not receipt_data:
            return jsonify({'success': False, 'message': 'Receipt not found or payment not completed'}), 404
        
        # For now, return receipt data as JSON (can be enhanced to generate actual PDF)
        receipt = {
            'receipt_id': f"RCP-{receipt_data[0]:06d}",
            'payment_id': receipt_data[0],
            'amount': float(receipt_data[1]) if receipt_data[1] else 0,
            'description': receipt_data[2] or 'Monthly parking charges',
            'payment_date': receipt_data[4].strftime('%Y-%m-%d %H:%M') if receipt_data[4] else 'N/A',
            'payment_method': receipt_data[5] or 'Cash',
            'resident_name': receipt_data[6],
            'resident_email': receipt_data[7],
            'resident_phone': receipt_data[8],
            'resident_location': f"Floor {receipt_data[9]}, Door {receipt_data[10]}",
            'slot_no': receipt_data[11] or 'N/A',
            'slot_type': receipt_data[12] or 'N/A',
            'vehicle_no': receipt_data[13] or 'N/A',
            'vehicle_type': receipt_data[14] or 'N/A'
        }
        
        return jsonify({'success': True, 'receipt': receipt})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/api/toggle_auto_payment', methods=['POST'])
def toggle_auto_payment():
    """Toggle auto payment setting for resident"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Check if auto_payment column exists, if not add it
        cursor.execute("SHOW COLUMNS FROM resident")
        columns = [column[0] for column in cursor.fetchall()]
        
        if 'auto_payment' not in columns:
            cursor.execute("ALTER TABLE resident ADD COLUMN auto_payment BOOLEAN DEFAULT FALSE")
            connection.commit()
        
        # Get current auto payment status
        cursor.execute("SELECT auto_payment FROM resident WHERE id = %s", (resident_id,))
        current_status = cursor.fetchone()
        current_auto_payment = current_status[0] if current_status else False
        
        # Toggle the status
        new_status = not current_auto_payment
        cursor.execute("UPDATE resident SET auto_payment = %s WHERE id = %s", (new_status, resident_id))
        connection.commit()
        
        status_text = "enabled" if new_status else "disabled"
        return jsonify({
            'success': True, 
            'message': f'Auto payment {status_text} successfully',
            'auto_payment': new_status
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/resolve_complaint/<int:complaint_id>', methods=['POST'])
def resolve_complaint(complaint_id):
    """Mark a complaint as resolved"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE complaints SET status = 'resolved' WHERE id = %s", (complaint_id,))
        connection.commit()
        return jsonify({'success': True, 'message': 'Complaint marked as resolved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/gate_logs')
def gate_logs():
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT g.id, g.vehicle_no, v.vehicle_company, v.vehicle_type, v.vehicle_color, 'N/A' as vehicle_model, r.name, r.email, r.phone, r.floor, r.door_number, g.entry_time, g.exit_time, g.status
            FROM gatelog g
            LEFT JOIN vehicle v ON g.vehicle_no = v.vehicle_no
            LEFT JOIN resident r ON v.resident_id = r.id
            ORDER BY g.entry_time DESC
        ''')
        logs = cursor.fetchall()
        return render_template('gate_logs.html', logs=logs)
    except Exception as e:
        flash(f'Error loading gate logs: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        connection.close()

@app.route('/api/process_payment', methods=['POST'])
def process_payment():
    """Process payment for a resident"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        payment_type = data.get('payment_type', 'Monthly')
        payment_method = data.get('payment_method', 'Cash')
        description = data.get('description', 'Manual payment')
        payment_id_to_pay = data.get('payment_id', None)  # Specific payment to complete
        
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Invalid payment amount'}), 400
        
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get resident's parking slot if exists
        cursor.execute("""
            SELECT p.id FROM parking p 
            JOIN vehicle v ON p.vehicle_no = v.vehicle_no 
            WHERE v.resident_id = %s AND p.status = 'Occupied' 
            LIMIT 1
        """, (resident_id,))
        
        parking_slot_result = cursor.fetchone()
        parking_slot_id = parking_slot_result[0] if parking_slot_result else None
        
        payment_id = None
        
        # If specific payment ID is provided, update that payment
        if payment_id_to_pay:
            cursor.execute("""
                UPDATE payments 
                SET status = 'Completed', payment_method = %s, payment_date = NOW(),
                    amount = %s, description = %s
                WHERE id = %s AND resident_id = %s AND status = 'Pending'
            """, (payment_method, amount, description, payment_id_to_pay, resident_id))
            
            if cursor.rowcount > 0:
                payment_id = payment_id_to_pay
                connection.commit()
            else:
                return jsonify({'success': False, 'message': 'Payment not found or already completed'}), 404
        
        else:
            # Check if there are any pending payments that match the amount
            cursor.execute("""
                SELECT id FROM payments 
                WHERE resident_id = %s AND status = 'Pending' AND ABS(amount - %s) < 0.01
                ORDER BY id ASC LIMIT 1
            """, (resident_id, amount))
            
            pending_payment = cursor.fetchone()
            
            if pending_payment:
                # Update existing pending payment
                cursor.execute("""
                    UPDATE payments 
                    SET status = 'Completed', payment_method = %s, payment_date = NOW(),
                        description = CONCAT(COALESCE(description, ''), ' - ', %s)
                    WHERE id = %s
                """, (payment_method, description, pending_payment[0]))
                payment_id = pending_payment[0]
            else:
                # Create new payment record
                cursor.execute("""
                    INSERT INTO payments (resident_id, parking_slot_id, amount, description, 
                                        payment_type, payment_method, status, payment_date)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Completed', NOW())
                """, (resident_id, parking_slot_id, amount, description, payment_type, payment_method))
                payment_id = cursor.lastrowid
            
            connection.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Payment processed successfully',
            'payment_id': payment_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment processing error: {str(e)}'}), 500
    finally:
        connection.close()

@app.route('/api/get_pending_payments')
def get_pending_payments():
    """Get all pending payments for the logged-in resident"""
    if not session.get('resident_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = connection.cursor()
        resident_id = session['resident_id']
        
        # Get all pending payments
        cursor.execute("""
            SELECT id, amount, description, payment_type, due_date, created_at
            FROM payments
            WHERE resident_id = %s AND status = 'Pending'
            ORDER BY due_date ASC, created_at ASC
        """, (resident_id,))
        
        pending_payments = []
        for payment in cursor.fetchall():
            pending_payments.append({
                'id': payment[0],
                'amount': float(payment[1]) if payment[1] else 0,
                'description': payment[2] or 'Monthly parking charges',
                'type': payment[3] or 'Monthly',
                'due_date': payment[4].strftime('%Y-%m-%d') if payment[4] else 'N/A',
                'created_date': payment[5].strftime('%Y-%m-%d') if payment[5] else 'N/A'
            })
        
        return jsonify({
            'success': True,
            'pending_payments': pending_payments,
            'total_pending': sum(p['amount'] for p in pending_payments)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()

@app.route('/admin_profile_update', methods=['GET', 'POST'])
def admin_profile_update():
    if not session.get('admin_logged_in'):
        flash('Please login to access this page', 'error')
        return redirect(url_for('admin_login'))

    admin_id = session.get('admin_id')
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        cursor = connection.cursor()
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            contact = request.form.get('contact')
            address = request.form.get('address')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            # Update profile info
            cursor.execute("""
                UPDATE admin SET username=%s, email=%s, contact_no=%s, address=%s WHERE id=%s
            """, (username, email, contact, address, admin_id))

            # Change password if provided
            if new_password and new_password == confirm_password:
                # Verify current password
                cursor.execute("SELECT password FROM admin WHERE id=%s", (admin_id,))
                result = cursor.fetchone()
                if result and result[0] == current_password:
                    cursor.execute("UPDATE admin SET password=%s WHERE id=%s", (new_password, admin_id))
                    flash('Password updated successfully', 'success')
                else:
                    flash('Current password is incorrect', 'error')
            elif new_password:
                flash('New passwords do not match', 'error')

            connection.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('admin_profile_update'))

        # Get current admin info
        cursor.execute("SELECT username, email, contact_no, address FROM admin WHERE id=%s", (admin_id,))
        admin = cursor.fetchone()
        return render_template('admin_profile_update.html', admin=admin)
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)

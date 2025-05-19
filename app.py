from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
import datetime
from collections import deque
import time
import statistics
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Flask configuration
app.config['SECRET_KEY'] = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y521'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ccdb_6oq2_user:ssVlSjuLjLiH1Wrx50j8PqoNDSTKAkie@dpg-d0keg3ggjchc73abrbi0-a/ccdb_6oq2'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
admin = Admin(app, name='Cloud Crop Admin', template_mode='bootstrap4')

# Initialize deque for sensor data (max 24 hours * 60 minutes = 1440 entries)
sensor_data = deque(maxlen=1440)

# Placeholder initial values
temperature = 0.0
humidity = 0.0
water_temperature = 0.0  # Added for DS18B20
air_temperature = 0.0    # Added for DHT11
tds = 0.0               # Added for TDS sensor
last_updated = "No data received yet"

# User model for cc_users table
class User(UserMixin, db.Model):
    __tablename__ = 'cc_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Flask-Admin view for User
class UserAdmin(ModelView):
    column_list = ['id', 'username', 'email', 'first_name', 'last_name']
    form_columns = ['username', 'email', 'first_name', 'last_name', 'password_hash']
    
    def is_accessible(self):
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin.add_view(UserAdmin(User, db.session))

@app.route('/')
def index():
    return render_template('index.html', 
                          temperature=temperature, 
                          humidity=humidity,
                          water_temperature=water_temperature,
                          air_temperature=air_temperature,
                          tds=tds,
                          last_updated=last_updated)

@app.route('/api/sensor')
def get_sensor_data():
    global temperature, humidity, water_temperature, air_temperature, tds, last_updated
    now = time.time()
    one_day_ago = now - 24 * 60 * 60
    recent_data = [
        entry for entry in sensor_data
        if entry['timestamp'] >= one_day_ago
    ]

    interval = 5 * 60
    aggregated_data = []
    if recent_data:
        start_time = recent_data[0]['timestamp']
        end_time = recent_data[-1]['timestamp']
        current_time = start_time - (start_time % interval)
        
        temp_values = []
        hum_values = []
        water_temp_values = []
        air_temp_values = []
        tds_values = []
        current_interval = current_time + interval
        
        for entry in recent_data:
            if entry['timestamp'] < current_interval:
                temp_values.append(float(entry.get('temperature', 0)))
                hum_values.append(float(entry.get('humidity', 0)))
                water_temp_values.append(float(entry.get('water_temperature', 0)))
                air_temp_values.append(float(entry.get('air_temperature', 0)))
                tds_values.append(float(entry.get('tds', 0)))
            else:
                if any([temp_values, hum_values, water_temp_values, air_temp_values, tds_values]):
                    aggregated_data.append({
                        'timestamp': current_interval - interval / 2,
                        'temperature': round(statistics.mean(temp_values) if temp_values else 0, 1),
                        'humidity': round(statistics.mean(hum_values) if hum_values else 0, 1),
                        'water_temperature': round(statistics.mean(water_temp_values) if water_temp_values else 0, 1),
                        'air_temperature': round(statistics.mean(air_temp_values) if air_temp_values else 0, 1),
                        'tds': round(statistics.mean(tds_values) if tds_values else 0, 1)
                    })
                temp_values = [float(entry.get('temperature', 0))]
                hum_values = [float(entry.get('humidity', 0))]
                water_temp_values = [float(entry.get('water_temperature', 0))]
                air_temp_values = [float(entry.get('air_temperature', 0))]
                tds_values = [float(entry.get('tds', 0))]
                current_interval += interval
        
        if any([temp_values, hum_values, water_temp_values, air_temp_values, tds_values]):
            aggregated_data.append({
                'timestamp': current_interval - interval / 2,
                'temperature': round(statistics.mean(temp_values) if temp_values else 0, 1),
                'humidity': round(statistics.mean(hum_values) if hum_values else 0, 1),
                'water_temperature': round(statistics.mean(water_temp_values) if water_temp_values else 0, 1),
                'air_temperature': round(statistics.mean(air_temp_values) if air_temp_values else 0, 1),
                'tds': round(statistics.mean(tds_values) if tds_values else 0, 1)
            })

    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "water_temperature": water_temperature,
        "air_temperature": air_temperature,
        "tds": tds,
        "last_updated": last_updated,
        "history": aggregated_data
    })

@app.route('/update_sensor', methods=['POST'])
def update_sensor_data():
    global temperature, humidity, water_temperature, air_temperature, tds, last_updated
    
    try:
        data = request.get_json()
        
        if data:
            # Handle legacy and new sensor data formats
            temperature = data.get('temperature', data.get('water_temperature', 0))
            humidity = data.get('humidity', 0)
            
            # Store new sensor values if available
            water_temperature = data.get('water_temperature', data.get('temperature', 0))
            air_temperature = data.get('air_temperature', data.get('temperature', 0))
            tds = data.get('tds', 0)
            
            last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Store all data in history
            sensor_data.append({
                'timestamp': time.time(),
                'temperature': temperature,
                'humidity': humidity,
                'water_temperature': water_temperature,
                'air_temperature': air_temperature,
                'tds': tds
            })

            return jsonify({"message": "Data updated successfully!"}), 200
    except Exception as e:
        app.logger.error(f"Error updating sensor data: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 400
    
    return jsonify({"message": "Invalid data"}), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/user-management/')
def user_management():
    try:
        users = User.query.all()
        return render_template('user_management.html', users=users)
    except Exception as e:
        app.logger.error(f"Error loading user management: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/user', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password') or not data.get('email'):
        return jsonify({"message": "Username, email and password are required"}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"message": "Username already exists"}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Email already exists"}), 400
    
    try:
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', '')
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        app.logger.info(f"User {data['username']} created successfully")
        return jsonify({"message": "User added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating user: {str(e)}")
        return jsonify({"message": f"Failed to create user: {str(e)}"}), 500

@app.route('/api/user/<int:user_id>', methods=['PUT'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('email'):
        return jsonify({"message": "Username and email are required"}), 400
    
    if User.query.filter_by(username=data['username']).first() and data['username'] != user.username:
        return jsonify({"message": "Username already exists"}), 400
    
    if User.query.filter_by(email=data['email']).first() and data['email'] != user.email:
        return jsonify({"message": "Email already exists"}), 400
    
    try:
        user.username = data['username']
        user.email = data['email']
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        if data.get('password'):
            user.set_password(data['password'])
        db.session.commit()
        app.logger.info(f"User {user_id} updated successfully")
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating user: {str(e)}")
        return jsonify({"message": f"Failed to update user: {str(e)}"}), 500

@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        app.logger.info(f"User {user_id} deleted successfully")
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({"message": f"Failed to delete user: {str(e)}"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)


# Add these imports if not already present
import datetime
from flask import request, jsonify, render_template

# Global variables for light data
light_scheduled = False
light_detected = False
ldr_value = 0
light_threshold = 500
relay_state = "OFF"
light_feedback = "NOT_DETECTED"
light_last_updated = "No data received yet"
manual_override = False

@app.route('/update_light', methods=['POST'])
def update_light_data():
    global light_scheduled, light_detected, ldr_value, light_threshold
    global relay_state, light_feedback, light_last_updated
    
    try:
        data = request.get_json()
        
        if data:
            light_scheduled = data.get('light_scheduled', False)
            light_detected = data.get('light_detected', False)
            ldr_value = data.get('ldr_value', 0)
            light_threshold = data.get('light_threshold', 500)
            relay_state = data.get('relay_state', 'OFF')
            light_feedback = data.get('light_feedback', 'NOT_DETECTED')
            
            light_last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            app.logger.info(f"Light data updated - Scheduled: {light_scheduled}, Detected: {light_detected}, LDR: {ldr_value}")
            return jsonify({"message": "Light data updated successfully!"}), 200
    except Exception as e:
        app.logger.error(f"Error updating light data: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 400
    
    return jsonify({"message": "Invalid data"}), 400

@app.route('/api/light')
def get_light_data():
    return jsonify({
        "light_scheduled": light_scheduled,
        "light_detected": light_detected,
        "ldr_value": ldr_value,
        "light_threshold": light_threshold,
        "relay_state": relay_state,
        "light_feedback": light_feedback,
        "light_last_updated": light_last_updated,
        "status_match": light_scheduled == light_detected,
        "manual_override": manual_override
    })

# Add this endpoint to match what the front-end is expecting
@app.route('/api/light_status')
def get_light_status():
    # This endpoint should return the information the dashboard needs
    return jsonify({
        "is_on": relay_state == "ON",
        "scheduled": light_scheduled,
        "detected": light_detected,
        "ldr_value": ldr_value,
        "threshold": light_threshold,
        "last_updated": light_last_updated,
        "manual_override": manual_override
    })

# Add this endpoint to handle manual light control from the dashboard
@app.route('/api/manual_light_control', methods=['POST'])
def manual_light_control():
    global relay_state, manual_override, light_scheduled
    
    try:
        data = request.get_json()
        
        if data:
            action = data.get('action')
            manual_override = data.get('manual_override', False)
            
            # Handle the actions
            if action == 'turn_on':
                relay_state = "ON"
                app.logger.info("Manual light control: Turning lights ON")
            elif action == 'turn_off':
                relay_state = "OFF"
                app.logger.info("Manual light control: Turning lights OFF")
            elif action == 'auto_mode':
                manual_override = False
                # In auto mode, determine light state based on schedule
                now = datetime.datetime.now()
                hour = now.hour
                # Lights on from 6 AM to 9 PM
                light_scheduled = 6 <= hour < 21
                relay_state = "ON" if light_scheduled else "OFF"
                app.logger.info(f"Auto mode enabled, light state set to {relay_state}")
            else:
                return jsonify({"message": "Invalid action"}), 400
                
            return jsonify({
                "success": True,
                "relay_state": relay_state,
                "manual_override": manual_override
            }), 200
    except Exception as e:
        app.logger.error(f"Error in manual light control: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 400
    
    return jsonify({"message": "Invalid data"}), 400

# Add this route to display light control dashboard
@app.route('/lights')
def lights_dashboard():
    # Get sensor data for the template (assuming you have sensor data available)
    water_temperature = 22.5  # Example value - replace with actual sensor data
    air_temperature = 24.3  # Example value - replace with actual sensor data
    humidity = 65  # Example value - replace with actual sensor data
    
    return render_template('lights.html',
                          water_temperature=water_temperature,
                          air_temperature=air_temperature,
                          humidity=humidity,
                          light_scheduled=light_scheduled,
                          light_detected=light_detected,
                          ldr_value=ldr_value,
                          relay_state=relay_state,
                          light_feedback=light_feedback,
                          last_updated=light_last_updated)

# Add this to check if lights should be on based on schedule (for auto mode)
def should_lights_be_on():
    now = datetime.datetime.now()
    hour = now.hour
    # Lights on from 6 AM to 9 PM
    return 6 <= hour < 21

# Optional: Add a periodic task to update light status based on schedule in auto mode
# This could be implemented with a separate thread, scheduler, or cron job

```python
import os
import datetime
import time
import statistics
from collections import deque
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Flask configuration
app.config['SECRET_KEY'] = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y521'
# Use environment variable for database URL
if 'DATABASE_URL' in os.environ:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('?pgbouncer=true', '')
else:
    # Fallback to SQLite for local development
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
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
water_temperature = 0.0
air_temperature = 0.0
tds = 0.0
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

# SensorData model for sensor_data table
class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    water_temperature = db.Column(db.Float, nullable=False)
    air_temperature = db.Column(db.Float, nullable=False)
    tds = db.Column(db.Float, nullable=False)

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

# Flask-Admin view for SensorData
class SensorDataAdmin(ModelView):
    column_list = ['id', 'timestamp', 'temperature', 'humidity', 'water_temperature', 'air_temperature', 'tds']
    form_columns = ['timestamp', 'temperature', 'humidity', 'water_temperature', 'air_temperature', 'tds']
    
    def is_accessible(self):
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin.add_view(UserAdmin(User, db.session))
admin.add_view(SensorDataAdmin(SensorData, db.session))

@app.route('/home/')
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
            water_temperature = data.get('water_temperature', data.get('temperature', 0))
            air_temperature = data.get('air_temperature', data.get('temperature', 0))
            tds = data.get('tds', 0)
            
            last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Store in deque for in-memory history
            sensor_data.append({
                'timestamp': time.time(),
                'temperature': temperature,
                'humidity': humidity,
                'water_temperature': water_temperature,
                'air_temperature': air_temperature,
                'tds': tds
            })

            # Store in database every 30 minutes
            now = datetime.datetime.now()
            if now.minute in (0, 30):
                try:
                    sensor_entry = SensorData(
                        timestamp=now,
                        temperature=temperature,
                        humidity=humidity,
                        water_temperature=water_temperature,
                        air_temperature=air_temperature,
                        tds=tds
                    )
                    db.session.add(sensor_entry)
                    db.session.commit()
                    app.logger.info("Sensor data saved to database")
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error saving sensor data to database: {str(e)}")

            return jsonify({"message": "Data updated successfully!"}), 200
    except Exception as e:
        app.logger.error(f"Error updating sensor data: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 400
    
    return jsonify({"message": "Invalid data"}), 400

@app.route('/history/', methods=['GET', 'POST'])
def history():
    selected_date = request.form.get('selected_date') if request.method == 'POST' else datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        # Parse selected date
        selected_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d").date()
        # Query sensor data for the selected date
        start_time = datetime.datetime.combine(selected_date, datetime.time.min)
        end_time = datetime.datetime.combine(selected_date, datetime.time.max)
        data = SensorData.query.filter(
            SensorData.timestamp >= start_time,
            SensorData.timestamp <= end_time
        ).order_by(SensorData.timestamp).all()
        
        # Format data for template
        formatted_data = [
            {
                'timestamp': entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'temperature': round(entry.temperature, 1),
                'humidity': round(entry.humidity, 1),
                'water_temperature': round(entry.water_temperature, 1),
                'air_temperature': round(entry.air_temperature, 1),
                'tds': round(entry.tds, 1)
            } for entry in data
        ]
        
        return render_template('history.html', data=formatted_data, selected_date=selected_date.strftime("%Y-%m-%d"))
    except Exception as e:
        app.logger.error(f"Error loading history: {str(e)}")
        flash(f"Error loading history: {str(e)}")
        return render_template('history.html', data=[], selected_date=selected_date)

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
```

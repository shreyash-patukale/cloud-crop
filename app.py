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
app.config['SECRET_KEY'] = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y521'  # Replace with a strong secret key
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
last_updated = "No data received yet"

# User model for cc_users table
class User(UserMixin, db.Model):
    __tablename__ = 'cc_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
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
    column_list = ['id', 'username']
    form_columns = ['username', 'password_hash']
    
    def is_accessible(self):
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin.add_view(UserAdmin(User, db.session))

@app.route('/')
def index():
    return render_template('index.html', temperature=temperature, humidity=humidity, last_updated=last_updated)

@app.route('/api/sensor')
def get_sensor_data():
    global temperature, humidity, last_updated
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
        current_interval = current_time + interval
        
        for entry in recent_data:
            if entry['timestamp'] < current_interval:
                temp_values.append(float(entry['temperature']))
                hum_values.append(float(entry['humidity']))
            else:
                if temp_values and hum_values:
                    aggregated_data.append({
                        'timestamp': current_interval - interval / 2,
                        'temperature': round(statistics.mean(temp_values), 1),
                        'humidity': round(statistics.mean(hum_values), 1)
                    })
                temp_values = [float(entry['temperature'])]
                hum_values = [float(entry['humidity'])]
                current_interval += interval
        
        if temp_values and hum_values:
            aggregated_data.append({
                'timestamp': current_interval - interval / 2,
                'temperature': round(statistics.mean(temp_values), 1),
                'humidity': round(statistics.mean(hum_values), 1)
            })

    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "last_updated": last_updated,
        "history": aggregated_data
    })

@app.route('/update_sensor', methods=['POST'])
def update_sensor_data():
    global temperature, humidity, last_updated
    data = request.get_json()

    if data:
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sensor_data.append({
            'timestamp': time.time(),
            'temperature': temperature,
            'humidity': humidity
        })

        return jsonify({"message": "Data updated successfully!"}), 200
    else:
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create cc_users table if it doesn't exist
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/user-management/')
def user_management():
    users = User.query.all()
    return render_template('user_management.html', users=users)

@app.route('/api/user', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password are required"}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"message": "Username already exists"}), 400
    
    user = User(username=data['username'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User added successfully"}), 201

@app.route('/api/user/<int:user_id>', methods=['PUT'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if not data or not data.get('username'):
        return jsonify({"message": "Username is required"}), 400
    
    if User.query.filter_by(username=data['username']).first() and data['username'] != user.username:
        return jsonify({"message": "Username already exists"}), 400
    
    user.username = data['username']
    if data.get('password'):
        user.set_password(data['password'])
    
    db.session.commit()
    return jsonify({"message": "User updated successfully"}), 200

@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"}), 200

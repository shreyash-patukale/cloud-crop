from flask import Flask, jsonify, render_template, request
import datetime
from collections import deque
import time

app = Flask(__name__)

# Initialize deque to store sensor data (max 24 hours * 60 minutes = 1440 entries, assuming 1 entry per minute)
sensor_data = deque(maxlen=1440)

# Placeholder initial values
temperature = 0.0
humidity = 0.0
last_updated = "No data received yet"

@app.route('/')
def index():
    return render_template('index.html', temperature=temperature, humidity=humidity, last_updated=last_updated)

@app.route('/api/sensor')
def get_sensor_data():
    global temperature, humidity, last_updated
    # Filter data for the last 24 hours
    now = time.time()
    one_day_ago = now - 24 * 60 * 60
    recent_data = [
        entry for entry in sensor_data
        if entry['timestamp'] >= one_day_ago
    ]
    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "last_updated": last_updated,
        "history": recent_data  # Return historical data
    })

@app.route('/update_sensor', methods=['POST'])
def update_sensor_data():
    global temperature, humidity, last_updated
    data = request.get_json()

    if data:
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add new data to deque
        sensor_data.append({
            'timestamp': time.time(),
            'temperature': temperature,
            'humidity': humidity
        })

        return jsonify({"message": "Data updated successfully!"}), 200
    else:
        return jsonify({"message": "Invalid data"}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

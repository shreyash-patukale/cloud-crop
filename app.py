from flask import Flask, jsonify, render_template, request
import datetime
from collections import deque
import time
import statistics

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

    # Aggregate data into 5-minute intervals (288 points for 24 hours)
    interval = 5 * 60  # 5 minutes in seconds
    aggregated_data = []
    if recent_data:
        # Group data by 5-minute intervals
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
                        'timestamp': current_interval - interval / 2,  # Middle of interval
                        'temperature': round(statistics.mean(temp_values), 1),
                        'humidity': round(statistics.mean(hum_values), 1)
                    })
                temp_values = [float(entry['temperature'])]
                hum_values = [float(entry['humidity'])]
                current_interval += interval
        
        # Add the last interval if it has data
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
        "history": aggregated_data  # Return aggregated data
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

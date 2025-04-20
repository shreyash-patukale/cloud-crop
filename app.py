from flask import Flask, jsonify, render_template
import datetime

app = Flask(__name__)

# Placeholder values
temperature = 25.0
humidity = 60.0
last_updated = "No data received yet"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sensor')
def get_sensor_data():
    global temperature, humidity, last_updated
    # Simulate sensor data fetching
    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "last_updated": last_updated
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, jsonify, render_template, request
import datetime

app = Flask(__name__)

# Placeholder values
temperature = 00.0
humidity = 00.0
last_updated = "No data received yet"

@app.route('/')
def index():
    return render_template('index.html', temperature=temperature, humidity=humidity, last_updated=last_updated)

@app.route('/api/sensor')
def get_sensor_data():
    global temperature, humidity, last_updated
    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "last_updated": last_updated
    })

@app.route('/update_sensor', methods=['POST'])
def update_sensor_data():
    global temperature, humidity, last_updated
    data = request.get_json()  # Get data from POST request

    if data:
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({"message": "Data updated successfully!"}), 200
    else:
        return jsonify({"message": "Invalid data"}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

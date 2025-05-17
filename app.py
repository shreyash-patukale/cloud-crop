from flask import Flask, jsonify, render_template, request
import datetime
import time
import statistics
import os
import psycopg2
from psycopg2 import pool

app = Flask(__name__)

# PostgreSQL connection pool configuration
db_config = {
    "dbname": 'ccdb_6oq2',
    "user": 'ccdb_6oq2_user',
    "password": 'ssVlSjuLjLiH1Wrx50j8PqoNDSTKAkie',
    "host": 'dpg-d0keg3ggjchc73abrbi0-a',
    "port": 5432
}

# Create connection pool
connection_pool = None

def get_db_connection():
    global connection_pool
    if connection_pool is None:
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **db_config)
            print("Connection pool created successfully")
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            return None
    
    conn = connection_pool.getconn()
    if conn:
        print("Successfully got connection from pool")
        return conn
    else:
        print("Failed to get connection from pool")
        return None

def release_connection(conn):
    global connection_pool
    if connection_pool and conn:
        connection_pool.putconn(conn)
        print("Released connection back to pool")

def init_db():
    """Initialize database tables if they don't exist"""
    conn = get_db_connection()
    if not conn:
        print("Error: Could not connect to the database")
        return False
    
    try:
        with conn.cursor() as cur:
            # Create sensor_readings table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id SERIAL PRIMARY KEY,
                    temperature FLOAT NOT NULL,
                    humidity FLOAT NOT NULL,
                    notes TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("Database initialized successfully")
            return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
    finally:
        release_connection(conn)

# Routes
@app.route('/')
def index():
    # Get the latest reading from the database to show on the dashboard
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT temperature, humidity, timestamp 
                    FROM sensor_readings 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                result = cur.fetchone()
                
                if result:
                    temperature = result[0]
                    humidity = result[1]
                    last_updated = result[2].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    temperature = 0.0
                    humidity = 0.0
                    last_updated = "No data yet"
        except Exception as e:
            print(f"Error querying database: {e}")
            temperature = 0.0
            humidity = 0.0
            last_updated = "Error reading data"
        finally:
            release_connection(conn)
    else:
        temperature = 0.0
        humidity = 0.0
        last_updated = "Database connection error"
    
    return render_template('index.html', temperature=temperature, humidity=humidity, last_updated=last_updated)

@app.route('/data_entry')
def data_entry():
    """Render the data entry page"""
    return render_template('data_entry.html')

@app.route('/api/sensor')
def get_sensor_data():
    """Get sensor data for the dashboard"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cur:
            # Get the latest reading
            cur.execute("""
                SELECT temperature, humidity, extract(epoch from timestamp) as timestamp_epoch
                FROM sensor_readings 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            latest = cur.fetchone()
            
            if latest:
                temperature = latest[0]
                humidity = latest[1]
                last_updated = datetime.datetime.fromtimestamp(latest[2]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                temperature = 0.0
                humidity = 0.0
                last_updated = "No data yet"
            
            # Get historical data (last 24 hours)
            now = time.time()
            one_day_ago = now - 24 * 60 * 60
            
            cur.execute("""
                SELECT extract(epoch from timestamp) as timestamp_epoch, temperature, humidity
                FROM sensor_readings
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                ORDER BY timestamp ASC
            """)
            
            recent_data = cur.fetchall()
            history_data = []
            
            if recent_data:
                # Process data into 5-minute intervals
                interval = 5 * 60  # 5 minutes in seconds
                
                # Group data by 5-minute intervals
                intervals = {}
                
                for row in recent_data:
                    timestamp = float(row[0])
                    temp = float(row[1])
                    hum = float(row[2])
                    
                    interval_key = int(timestamp // interval) * interval
                    
                    if interval_key not in intervals:
                        intervals[interval_key] = {"temps": [], "hums": []}
                    
                    intervals[interval_key]["temps"].append(temp)
                    intervals[interval_key]["hums"].append(hum)
                
                # Calculate averages for each interval
                for interval_key, values in sorted(intervals.items()):
                    if values["temps"] and values["hums"]:
                        history_data.append({
                            "timestamp": interval_key,
                            "temperature": round(statistics.mean(values["temps"]), 1),
                            "humidity": round(statistics.mean(values["hums"]), 1)
                        })
            
            return jsonify({
                "temperature": temperature,
                "humidity": humidity,
                "last_updated": last_updated,
                "history": history_data
            })
            
    except Exception as e:
        print(f"Error retrieving sensor data: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        release_connection(conn)

@app.route('/api/readings', methods=['GET'])
def get_readings():
    """Get list of readings for the data entry page"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT extract(epoch from timestamp) as timestamp_epoch, 
                       temperature, humidity, notes
                FROM sensor_readings
                ORDER BY timestamp DESC
                LIMIT 20
            """)
            
            readings = []
            for row in cur.fetchall():
                readings.append({
                    "timestamp": float(row[0]),
                    "temperature": float(row[1]),
                    "humidity": float(row[2]),
                    "notes": row[3] if row[3] else ""
                })
            
            return jsonify({"readings": readings})
            
    except Exception as e:
        print(f"Error retrieving readings: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        release_connection(conn)

@app.route('/api/readings', methods=['POST'])
def add_reading():
    """Add a new sensor reading from the data entry page"""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    temperature = data.get('temperature')
    humidity = data.get('humidity')
    notes = data.get('notes', '')
    
    if temperature is None or humidity is None:
        return jsonify({"message": "Temperature and humidity are required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sensor_readings (temperature, humidity, notes)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (temperature, humidity, notes))
            
            reading_id = cur.fetchone()[0]
            conn.commit()
            
            return jsonify({
                "message": "Reading added successfully", 
                "id": reading_id
            }), 201
            
    except Exception as e:
        conn.rollback()
        print(f"Error adding reading: {e}")
        return jsonify({"message": f"Error adding reading: {str(e)}"}), 500
    finally:
        release_connection(conn)

@app.route('/update_sensor', methods=['POST'])
def update_sensor_data():
    """
    Legacy endpoint for updating sensor data (compatible with existing setup)
    Redirects to the new API endpoint
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    temperature = data.get('temperature')
    humidity = data.get('humidity')
    
    if temperature is None or humidity is None:
        return jsonify({"message": "Temperature and humidity are required"}), 400
    
    # Prepare data for the new endpoint
    new_data = {
        "temperature": temperature,
        "humidity": humidity,
        "notes": "Automated reading"
    }
    
    # Save to database
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sensor_readings (temperature, humidity, notes)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (temperature, humidity, "Automated reading"))
            
            reading_id = cur.fetchone()[0]
            conn.commit()
            
            return jsonify({
                "message": "Data updated successfully!", 
                "id": reading_id
            }), 200
            
    except Exception as e:
        conn.rollback()
        print(f"Error updating sensor data: {e}")
        return jsonify({"message": f"Error updating sensor data: {str(e)}"}), 500
    finally:
        release_connection(conn)

# Initialize the app
@app.before_first_request
def before_first_request():
    """Initialize database before first request"""
    init_db()

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

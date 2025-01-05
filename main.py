from flask import Flask, render_template, redirect, request, url_for
import RPi.GPIO as GPIO
import time
from threading import Thread
from mfrc522 import SimpleMFRC522
import firebase_admin
from firebase_admin import credentials, db

# Initialize Firebase Admin SDK
cred = credentials.Certificate('inventory-9756d-firebase-adminsdk-h2cgm-ef480640da.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://inventory-9756d-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Reference to the Firebase database nodes
firebase_ref_total_items = db.reference('Total Items')
firebase_ref_low_stock = db.reference('Low Stock')

# Initialize Low Stock data
initial_low_stock = {
    "Room 1": False,
    "Room 2": False,
    "Room 3": False
}
firebase_ref_low_stock.set(initial_low_stock)

# GPIO Setup
GPIO.setmode(GPIO.BOARD)

# Define LED Pins for Rooms and Warnings
room_leds = [38, 40, 26]  # Physical pins for room LEDs
warning_leds = [32, 33, 37]  # LEDs for warnings when item count < 5

# Define Pins for 7-Segment Display and Multiplexers
segments = [3, 5, 7, 11, 13, 15, 18]  # Pins for 7-segment segments
mux_pins = [35, 36]  # Pins for tens and ones multiplexer

# Initialize GPIO Pins
for pin in segments + mux_pins + room_leds + warning_leds:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Fetch data from Firebase
room_counts = [
    db.reference(f'Total Items/Room {i + 1}').get()
    for i in range(3)
]

# Flask App Setup
app = Flask(__name__)
current_room = -1  # No active room initially
reader = SimpleMFRC522()
valid_uid = ['85615652294', '0987654321']

# 7-Segment Encoding for Digits 0-9 (Common Anode)
seven_seg_encoding = [
    [0, 0, 0, 0, 0, 0, 1],  # 0
    [1, 0, 0, 1, 1, 1, 1],  # 1
    [0, 0, 1, 0, 0, 1, 0],  # 2
    [0, 0, 0, 0, 1, 1, 0],  # 3
    [1, 0, 0, 1, 1, 0, 0],  # 4
    [0, 1, 0, 0, 1, 0, 0],  # 5
    [0, 1, 0, 0, 0, 0, 0],  # 6
    [0, 0, 0, 1, 1, 1, 1],  # 7
    [0, 0, 0, 0, 0, 0, 0],  # 8
    [0, 0, 0, 0, 1, 0, 0]   # 9
]

# GPIO Pins for Buttons
button_add = 29
button_remove = 31
GPIO.setup(button_add, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(button_remove, GPIO.IN, pull_up_down=GPIO.PUD_UP)

debounce_time = 0.5

# Function to Synchronize Data with Firebase
def sync_to_firebase():
    firebase_ref_total_items.set({
        f"Room {i + 1}": room_counts[i] for i in range(3)
    })
    firebase_ref_low_stock.set({
        f"Room {i + 1}": room_counts[i] <= 5 for i in range(3)
    })

# Update Warning LEDs
def update_warning_led(room_id):
    GPIO.output(warning_leds[room_id], GPIO.HIGH if room_counts[room_id] <= 5 else GPIO.LOW)

# Monitor Buttons
def monitor_buttons():
    global current_room
    last_add_state, last_remove_state = GPIO.input(button_add), GPIO.input(button_remove)

    while True:
        current_add_state, current_remove_state = GPIO.input(button_add), GPIO.input(button_remove)

        if last_add_state == GPIO.HIGH and current_add_state == GPIO.LOW and current_room != -1:
            room_counts[current_room] = min(room_counts[current_room] + 1, 99)
            sync_to_firebase()
            update_warning_led(current_room)
            time.sleep(debounce_time)

        if last_remove_state == GPIO.HIGH and current_remove_state == GPIO.LOW and current_room != -1:
            if room_counts[current_room] > 0:
                room_counts[current_room] -= 1
                sync_to_firebase()
                update_warning_led(current_room)
                time.sleep(debounce_time)

        last_add_state, last_remove_state = current_add_state, current_remove_state
        time.sleep(0.01)

Thread(target=monitor_buttons, daemon=True).start()

# Refresh Display
def refresh_display():
    while True:
        if current_room == -1:
            for pin in segments:
                GPIO.output(pin, GPIO.HIGH)
            continue

        count = room_counts[current_room]
        tens, ones = divmod(count, 10)

        for digit, mux_pin in zip([tens, ones], mux_pins):
            for pin, val in zip(segments, seven_seg_encoding[digit]):
                GPIO.output(pin, GPIO.LOW if val == 0 else GPIO.HIGH)
            GPIO.output(mux_pin, GPIO.HIGH)
            time.sleep(0.005)
            GPIO.output(mux_pin, GPIO.LOW)

Thread(target=refresh_display, daemon=True).start()

# Flask Routes
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def rfid_login():
    global text
    try:
        rfid_id, text = reader.read()
        if str(rfid_id) in valid_uid:
            return render_template('index.html', user_name=text, rooms=room_counts)
        else:
            return render_template('login.html', error="Invalid RFID")
    except Exception as e:
        return render_template('login.html', error=f"Error reading RFID: {e}")

@app.route('/index')
def index():
    global current_room, text
    current_room = -1
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    return render_template('index.html', rooms=room_counts, user_name=text)

@app.route('/enter/<int:room_id>')
def enter_room(room_id):
    global current_room
    current_room = room_id
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    GPIO.output(room_leds[room_id], GPIO.HIGH)
    update_warning_led(room_id)
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

@app.route('/update', methods=['POST'])
def update():
    room_id = int(request.form['room_id'])
    action = request.form['action']
    if action == "add":
        room_counts[room_id] = min(room_counts[room_id] + 1, 99)
    elif action == "remove" and room_counts[room_id] > 0:
        room_counts[room_id] -= 1
    elif action == "set":
        new_quantity = int(request.form['quantity'])
        if 0 <= new_quantity <= 99:
            room_counts[room_id] = new_quantity

    sync_to_firebase()
    update_warning_led(room_id)
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

@app.route('/logout', methods=['POST'])
def logout():
    return redirect(url_for('login'))

@app.route('/leave/<int:room_id>')
def leave_room(room_id):
    global current_room
    current_room = -1
    GPIO.output(room_leds[room_id], GPIO.LOW)
    return index()

# Main Execution
if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        GPIO.cleanup()

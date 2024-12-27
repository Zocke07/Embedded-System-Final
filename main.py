from flask import Flask, render_template, redirect, request, url_for, session
import RPi.GPIO as GPIO
import time
from threading import Thread
from mfrc522 import SimpleMFRC522
import firebase_admin
from firebase_admin import credentials, db

# Initialize Firebase Admin SDK
cred = credentials.Certificate('inventory-9756d-firebase-adminsdk-h2cgm-9a0177ad34.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://inventory-9756d-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Reference to the Firebase database nodes
firebase_ref_total_items = db.reference('Total Items')
firebase_ref_low_stock = db.reference('Low Stock')

# Initialize Firebase data
initial_data = {
    "Room 1": 10,
    "Room 2": 10,
    "Room 3": 10
}
firebase_ref_total_items.set(initial_data)

# Initialize Low Stock data
initial_low_stock = {
    "Room 1": False,
    "Room 2": False,
    "Room 3": False
}
firebase_ref_low_stock.set(initial_low_stock)

# GPIO Setup
GPIO.setmode(GPIO.BOARD)

# LED Pins for Rooms (Adjusted to BOARD mode)
room_leds = [38, 40, 26]  # Physical pins for room LEDs
warning_leds = [32, 33, 37]  # Additional LEDs for warning when item count < 5

# 7-Segment Display Setup

segments = [3, 5, 7, 11, 13, 15, 18]  # Pins for 7-segment segments
mux_pins = [35, 36]  # Pins for tens and ones multiplexer

# Initialize GPIO Pins
for pin in segments + mux_pins + room_leds + warning_leds:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Flask App Setup
app = Flask(__name__)
current_room = -1  # No room is active initially
room_counts = [10, 10, 10]  # Initial counts for Room 1, Room 2, Room 3

reader = SimpleMFRC522()

# Function to synchronize room counts with Firebase
def sync_to_firebase():
    # Sync Total Items
    firebase_ref_total_items.set({
        "Room 1": room_counts[0],
        "Room 2": room_counts[1],
        "Room 3": room_counts[2]
    })
    # Sync Low Stock
    firebase_ref_low_stock.set({
        "Room 1": room_counts[0] <= 5,
        "Room 2": room_counts[1] <= 5,
        "Room 3": room_counts[2] <= 5
    })

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
button_add = 29  # Physical pin for Add button
button_remove = 31  # Physical pin for Remove button

# Setup Buttons
GPIO.setup(button_add, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use pull-up resistor
GPIO.setup(button_remove, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use pull-up resistor

# Button Debounce Time (in seconds)
debounce_time = 0.5

# Background Thread to Monitor Buttons
def monitor_buttons():
    global current_room

    last_add_state = GPIO.input(button_add)
    last_remove_state = GPIO.input(button_remove)

    while True:
        current_add_state = GPIO.input(button_add)
        current_remove_state = GPIO.input(button_remove)

        if last_add_state == GPIO.HIGH and current_add_state == GPIO.LOW:
            if current_room != -1:
                room_counts[current_room] = min(room_counts[current_room] + 1, 99)
                sync_to_firebase()  # Update Firebase
                update_warning_led(current_room)
                time.sleep(0.3)

        if last_remove_state == GPIO.HIGH and current_remove_state == GPIO.LOW:
            if current_room != -1 and room_counts[current_room] > 0:
                room_counts[current_room] -= 1
                sync_to_firebase()  # Update Firebase
                update_warning_led(current_room)
                time.sleep(0.3)

        last_add_state = current_add_state
        last_remove_state = current_remove_state
        time.sleep(0.01)

# Start the Button Monitoring Thread
button_thread = Thread(target=monitor_buttons, daemon=True)
button_thread.start()

# Background Thread to Continuously Refresh Display
def refresh_display():
    while True:
        if current_room == -1:
            # Turn off all segments when no room is active
            for pin in segments:
                GPIO.output(pin, GPIO.HIGH)  # Common anode turns off with HIGH signal
            continue

        # Get the value to display
        count = room_counts[current_room]
        tens = count // 10
        ones = count % 10

        # Show tens digit
        for pin, val in zip(segments, seven_seg_encoding[tens]):
            GPIO.output(pin, GPIO.LOW if val == 0 else GPIO.HIGH)  # Common Anode
        GPIO.output(mux_pins[0], GPIO.HIGH)  # Enable tens multiplexer
        time.sleep(0.005)
        GPIO.output(mux_pins[0], GPIO.LOW)   # Disable tens multiplexer

        # Show ones digit
        for pin, val in zip(segments, seven_seg_encoding[ones]):
            GPIO.output(pin, GPIO.LOW if val == 0 else GPIO.HIGH)  # Common Anode
        GPIO.output(mux_pins[1], GPIO.HIGH)  # Enable ones multiplexer
        time.sleep(0.005)
        GPIO.output(mux_pins[1], GPIO.LOW)   # Disable ones multiplexer

def update_warning_led(room_id):
    room_name = f"Room {room_id + 1}"
    is_low_stock = room_counts[room_id] <= 5
    firebase_ref_low_stock.child(room_name).set(is_low_stock)
    GPIO.output(warning_leds[room_id], GPIO.HIGH if is_low_stock else GPIO.LOW)


# Start the Display Refresh Loop in a Separate Thread
display_thread = Thread(target=refresh_display, daemon=True)
display_thread.start()

valid_uid = ['85615652294', '0987654321']

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def rfid_login():
    global text
    try:
        # Start reading RFID
        rfid_id, text = reader.read()  # Changed 'id' to 'rfid_id'
        print(f"Scanned RFID ID: {rfid_id}")  # Debugging

        # Check if RFID ID matches a known UID
        if str(rfid_id) in valid_uid:
            return render_template('index.html', user_name=text, rooms=room_counts)
        else:
            return render_template('login.html', error="Invalid RFID")
    except Exception as e:
        print(f"Error reading RFID: {e}")
        return render_template('login.html', error="Error reading RFID")

@app.route('/index')
def index():
    global current_room, text
    current_room = -1
    # No room is active
    # Turn off all LEDs
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    return render_template('index.html', rooms=room_counts, user_name=text)  # Main page after successful login


# Enter Room Route
@app.route('/enter/<int:room_id>')
def enter_room(room_id):
    global current_room
    current_room = room_id  
    # Set the active room

    # Turn off all LEDs first
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    
    # Turn on the selected room's LED
    GPIO.output(room_leds[room_id], GPIO.HIGH)
    
    # Check if the item count is below 5 for the warning LED
    if room_counts[room_id] <= 5:
        GPIO.output(warning_leds[room_id], GPIO.HIGH)  # Turn on the warning LED
    
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Update Room Inventory
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

    sync_to_firebase()  # Update Firebase
    update_warning_led(room_id)
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

@app.route('/logout', methods=['POST'])
def logout():
    #return render_template('login.html')
    return redirect(url_for('login'))

# Leave Room Route
@app.route('/leave/<int:room_id>')
def leave_room(room_id):
    global current_room
    current_room = -1  # No room is active
    GPIO.output(room_leds[room_id], GPIO.LOW)  # Turn off the LED for the room
    return index()
    
@app.route('/sync')
def sync():
    # Load data from Firebase
    global room_counts
    room_counts = firebase_ref.get()
    return redirect(url_for('index'))

# Main Execution
if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)  # Turn off debug for production
    except KeyboardInterrupt:
        GPIO.cleanup()

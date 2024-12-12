from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import time

# GPIO Setup
GPIO.setmode(GPIO.BOARD)

# LED Pins for Rooms (Adjusted to BOARD mode)
room_leds = [22, 24, 26]  # Physical pins for LEDs (ensure no overlap with 7-segment pins)

# 7-Segment Display Setup
segments = [3, 5, 7, 11, 13, 15, 19]  # Pins for 7-segment segments
mux_pins = [21, 23, 29]  # Pins for 7-segment

# Initialize GPIO Pins
for pin in segments + mux_pins + room_leds:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Flask App Setup
app = Flask(__name__)
room_counts = [0, 0, 0]  # Initial item counts for rooms

# 7-Segment Encoding for Digits 0-9
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

# Display a number on the 7-segment display
def display_number(room_id, number):
    if room_id not in range(3) or number not in range(10):
        return

    # Turn off all multiplexers
    for pin in mux_pins:
        GPIO.output(pin, GPIO.LOW)

    # Display number on segments
    for seg, val in zip(segments, seven_seg_encoding[number]):
        GPIO.output(seg, GPIO.LOW if val == 0 else GPIO.HIGH)  # Common Anode logic

    # Enable the correct multiplexer
    GPIO.output(mux_pins[room_id], GPIO.HIGH)


# Home Route
@app.route('/')
def index():
    # Turn off all LEDs and 7-segment displays
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    for pin in mux_pins:
        GPIO.output(pin, GPIO.LOW)
    return render_template('index.html', rooms=room_counts)

# Enter Room Route
@app.route('/enter/<int:room_id>')
def enter_room(room_id):
    # Turn off all LEDs first (only one LED will be turned on)
    for led in room_leds:
        GPIO.output(led, GPIO.LOW)
    
    # Turn on the selected room's LED
    GPIO.output(room_leds[room_id], GPIO.HIGH)
    
    # Display the item count on the 7-segment display
    display_number(room_id, room_counts[room_id])
    
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Update Room Inventory
@app.route('/update', methods=['POST'])
def update():
    room_id = int(request.form['room_id'])
    action = request.form['action']
    if action == "add":
        room_counts[room_id] = min(room_counts[room_id] + 1, 9)
    elif action == "remove" and room_counts[room_id] > 0:
        room_counts[room_id] -= 1

    # Update the 7-segment display without changing LED state
    display_number(room_id, room_counts[room_id])
    print(f"Room {room_id + 1}: {room_counts[room_id]}")
    
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Leave Room Route
@app.route('/leave/<int:room_id>')
def leave_room(room_id):
    GPIO.output(room_leds[room_id], GPIO.LOW)  # Turn off the LED for the room
    GPIO.output(mux_pins[room_id], GPIO.LOW)   # Turn off the 7-segment display for the room
    return index()

# Main Execution
if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)  # Turn off debug for production
    except KeyboardInterrupt:
        GPIO.cleanup()

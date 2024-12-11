from flask import Flask, render_template, request
from gpiozero import LED
import RPi.GPIO as GPIO
import time

# GPIO Setup
GPIO.setmode(GPIO.BCM)

# LED Pins for Rooms
room_leds = [LED(17), LED(27), LED(22)]

# 7-Segment Display Setup
segments = [2, 3, 4, 5, 6, 7, 8]  # Pins for 7-segment segments
mux_pins = [9, 10, 11]  # Pins for 7-segment common cathode

# 7-Segment Encoding for Digits 0-9
seven_seg_encoding = [
    [1, 1, 1, 1, 1, 1, 0],  # 0
    [0, 1, 1, 0, 0, 0, 0],  # 1
    [1, 1, 0, 1, 1, 0, 1],  # 2
    [1, 1, 1, 1, 0, 0, 1],  # 3
    [0, 1, 1, 0, 0, 1, 1],  # 4
    [1, 0, 1, 1, 0, 1, 1],  # 5
    [1, 0, 1, 1, 1, 1, 1],  # 6
    [1, 1, 1, 0, 0, 0, 0],  # 7
    [1, 1, 1, 1, 1, 1, 1],  # 8
    [1, 1, 1, 1, 0, 1, 1]   # 9
]

# Initialize GPIO Pins
for pin in segments + mux_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Flask App Setup
app = Flask(__name__)
room_counts = [0, 0, 0]

# Display a number on the 7-segment display
def display_number(room_id, number):
    if room_id not in range(3) or number not in range(10):
        return

    # Turn off all multiplexers
    for pin in mux_pins:
        GPIO.output(pin, GPIO.LOW)

    # Display number on segments
    for seg, val in zip(segments, seven_seg_encoding[number]):
        GPIO.output(seg, GPIO.HIGH if val else GPIO.LOW)

    # Enable the correct multiplexer
    GPIO.output(mux_pins[room_id], GPIO.HIGH)

# Home Route
@app.route('/')
def index():
    # Turn off all LEDs and 7-segment displays
    for led in room_leds:
        led.off()
    for pin in mux_pins:
        GPIO.output(pin, GPIO.LOW)
    return render_template('index.html', rooms=room_counts)

# Enter Room Route
@app.route('/enter/<int:room_id>')
def enter_room(room_id):
    room_leds[room_id].on()
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

    # Update display
    display_number(room_id, room_counts[room_id])
    print(f"Room {room_id + 1}: {room_counts[room_id]}")
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Leave Room Route
@app.route('/leave/<int:room_id>')
def leave_room(room_id):
    room_leds[room_id].off()
    GPIO.output(mux_pins[room_id], GPIO.LOW)
    return index()

# Main Execution
if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        GPIO.cleanup()
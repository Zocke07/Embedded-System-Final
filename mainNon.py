from flask import Flask, render_template, request

# Mock Data for Testing
room_counts = [0, 0, 0]  # Storage quantities

# Flask App Setup
app = Flask(__name__)

# Home Route
@app.route('/')
def index():
    return render_template('index.html', rooms=room_counts)

# Enter Room Route
@app.route('/enter/<int:room_id>')
def enter_room(room_id):
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Update Room Inventory
@app.route('/update', methods=['POST'])
def update():
    room_id = int(request.form['room_id'])
    action = request.form['action']
    if action == "add":
        room_counts[room_id] += 1
    elif action == "remove" and room_counts[room_id] > 0:
        room_counts[room_id] -= 1

    # Debug Output
    print(f"Room {room_id + 1}: {room_counts[room_id]}")
    return render_template('room.html', room_id=room_id, count=room_counts[room_id])

# Leave Room Route
@app.route('/leave/<int:room_id>')
def leave_room(room_id):
    return index()

# Main Execution
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
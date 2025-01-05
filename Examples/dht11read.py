import time
import board
import adafruit_dht

# Use GPIO23 (physical pin 16)
dht_sensor = adafruit_dht.DHT11(board.D23)

while True:
    try:
        temp = dht_sensor.temperature
        humidity = dht_sensor.humidity
        print(f"Temperature: {temp}°C, Humidity: {humidity}%")
    except RuntimeError as error:
        print(f"RuntimeError: {error}")
        time.sleep(2.0)  # Wait 2 seconds before retrying
    except Exception as error:
        dht_sensor.exit()
        raise error

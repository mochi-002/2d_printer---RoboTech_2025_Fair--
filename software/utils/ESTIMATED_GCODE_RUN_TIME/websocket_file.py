import websocket
import threading
import time

ESP_IP = "ws://13:24:01.145"  # The ESP IP u find in the serial

ws = websocket.WebSocket()

#timer to send the data each 2 seconds
last_sent_time = 0

def connect_ws(estimated):
    """Try to connect to the ESP8266 WebSocket server."""
    while True:
        try:
            ws.connect(ESP_IP)
            print("[✓] Connected to ESP8266 WebSocket")
            break
        except Exception as e:
            print(f"[!] WebSocket retrying... {e}")
            time.sleep(2)

# using multi threading
threading.Thread(target=connect_ws, daemon=True).start()

def sendTime(estimated):
    """Send the detected Estimated time to ESP8266 via WebSocket."""
    global last_sent_time

    # send every 2 seconds
    if time.time() - last_sent_time >= 2:
        try:
            ws.send(str(estimated))  # sending estimated time
            print(f"[→] Sent to ESP: {estimated}")
            last_sent_time = time.time()  # putting time at the current as the last sent time
        except Exception:
            print("[!] Connection lost. Reconnecting...")
            threading.Thread(target=connect_ws, daemon=True).start()
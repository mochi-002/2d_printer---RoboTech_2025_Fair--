#include <ESP8266WiFi.h>
#include <WebSocketsServer.h>

const char* ssid = "axshha"; //Make sure ur internet name is one word with no spaces   
const char* password = "axsha3245";

WebSocketsServer webSocket(81);


void setup() {
    Serial.begin(115200);
     
    
    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    Serial.println("\nConnected to WiFi");
   Serial.println(WiFi.localIP().toString());
    webSocket.begin();
    webSocket.onEvent(webSocketEvent);
    
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t *payload, size_t length) {
    if (type == WStype_TEXT) {
        int estimatedTime = atoi((char*)payload);     Serial.printf("Received: %d minutes\n", estimatedTime);
   
    }
}

void loop() {
    webSocket.loop();
}
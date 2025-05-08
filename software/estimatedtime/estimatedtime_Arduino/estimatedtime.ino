#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

String incomingLine = "";

unsigned long previousMillis = 0;
unsigned long totalSeconds = 0;
bool timerRunning = false;

void setup() {
  Serial.begin(9600);
  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("Waiting for Time");
}

void loop() {
  // Check for new data
  while (Serial.available()) {
    incomingLine = Serial.readStringUntil('\n');
    Serial.println(incomingLine);
    processLine(incomingLine);
  }

  // Timer logic
  if (timerRunning && totalSeconds > 0) {
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= 1000) {
      previousMillis = currentMillis;
      totalSeconds--;

      updateTimerDisplay();

      if (totalSeconds == 0) {
        timerRunning = false;
        lcd.setCursor(0, 0);
        lcd.print("   Time Complete   ");
      }
    }
  }
}

void processLine(String line) {
  if (line.startsWith("Received: ")) {
    int minutesStart = line.indexOf(": ") + 2;
    int minutesEnd = line.indexOf(" minutes");

    if (minutesStart > 0 && minutesEnd > minutesStart) {
      String timeStr = line.substring(minutesStart, minutesEnd);
      int receivedMinutes = timeStr.toInt();

      totalSeconds = receivedMinutes * 60UL;
      timerRunning = true;
      previousMillis = millis();

      lcd.setCursor(0, 0);
      lcd.print("Time Remaining");
      updateTimerDisplay(); // immediate update
    }
  }
}

void updateTimerDisplay() {
  int hours = totalSeconds / 3600;
  int minutes = (totalSeconds % 3600) / 60;
  int seconds = totalSeconds % 60;

  lcd.setCursor(0, 1);
  if (hours < 10) lcd.print("0");
  lcd.print(hours);
  lcd.print(":");

  if (minutes < 10) lcd.print("0");
  lcd.print(minutes);
  lcd.print(":");

  if (seconds < 10) lcd.print("0");
  lcd.print(seconds);
  lcd.print(" "); // clear leftover char if overwriting longer time
}

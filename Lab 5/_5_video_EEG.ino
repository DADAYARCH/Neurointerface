/*
EEG Dual Channel
Скетч для приёма сигналов с двух одноканальных ЭЭГ-датчиков, подключённых к A0 и A1.
Передаёт оба сигнала в Bitronics Studio для визуализации в полях A0 и A1.
*/

#include <TimerOne.h>

int valA0 = 0;
int valA1 = 0;

// функция, вызываемая по прерыванию таймера
void sendData() {
  // Чтение с первого датчика (A0)
  valA0 = analogRead(A0);
  Serial.write("A0");  // имя поля в Bitronics Studio
  Serial.write(map(valA0, 0, 1023, 0, 255));  // нормализация

  // Чтение со второго датчика (A1)
  valA1 = analogRead(A1);
  Serial.write("A1");  // имя поля для второго сигнала
  Serial.write(map(valA1, 0, 1023, 0, 255));
}

void setup() {
  Serial.begin(115200);      // скорость обмена
  Timer1.initialize(3000);   // интервал 3000 мкс (≈333 Гц)
  Timer1.attachInterrupt(sendData);  // функция, вызываемая таймером
}

void loop() {
  // Основной цикл пуст — всё делает таймер
}

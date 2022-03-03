#ifndef ULTRASONIC_SENSOR_H
#define ULTRASONIC_SENSOR_H

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_log.h"

#define SENSOR_TAG "Sensor Log"

void init_ultrasonic_sensor(int trig_pin, int echo_pin);
float get_distance(int trig_pin);

#endif /* ULTRASONIC_SENSOR_H */

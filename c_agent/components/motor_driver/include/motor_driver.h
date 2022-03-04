#ifndef MOTOR_DRIVER_H
#define MOTOR_DRIVER_H

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_log.h"

#define MOTOR_DRIVER_TAG    "Motor Driver Log"
#define WHEEL_RADIUS        21 //42mm wheel diameter
#define AXEL_LENGTH         90 //90mm wheel centre to wheel centre

void init_motor_driver();
void move_forward(float dist);
void turn_left(float angle);
void turn_right(float angle);

#endif /* MOTOR_DRIVER_H */

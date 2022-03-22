/* 
 * ultrasonic_sensor.h
 *
 * Author: Finn Middlton-Baird
 * 
 * Comments: file containing defines, includes and delarations required by ultrasonic sensor functions
 *      
 * Requires: none
 * 
 * Revision: 1.0
 *
 * In this file:
 *      Includes - line 26
 *      Defines - line 37
 *      Function Declarations - line 43
 *
 */

#ifndef ULTRASONIC_SENSOR_H
#define ULTRASONIC_SENSOR_H

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_log.h"

//-----------------------------------------------------------------------------------------------------------
// Defines 
//-----------------------------------------------------------------------------------------------------------

#define SENSOR_TAG "Sensor Log"

//-----------------------------------------------------------------------------------------------------------
// Function Declarations
//-----------------------------------------------------------------------------------------------------------

void init_ultrasonic_sensor(int trig_pin, int echo_pin);
float get_distance(int trig_pin);

#endif /* ULTRASONIC_SENSOR_H */

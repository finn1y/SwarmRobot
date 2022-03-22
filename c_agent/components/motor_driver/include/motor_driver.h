/* 
 * motor_driver.h
 *
 * Author: Finn Middlton-Baird
 * 
 * Comments: file containing defines, includes and delarations required by motor driver functions
 *      
 * Requires: none
 * 
 * Revision: 1.0
 *
 * In this file:
 *      Includes - line 25
 *      Defines - line 36
 *      Function Declarations - line 44
 *
 */

#ifndef MOTOR_DRIVER_H
#define MOTOR_DRIVER_H

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_log.h"

//-----------------------------------------------------------------------------------------------------------
// Defines
//-----------------------------------------------------------------------------------------------------------

#define MOTOR_DRIVER_TAG    "Motor Driver Log"
#define WHEEL_RADIUS        21 //42mm wheel diameter
#define AXEL_LENGTH         90 //90mm wheel centre to wheel centre

//-----------------------------------------------------------------------------------------------------------
// Function Declarations
//-----------------------------------------------------------------------------------------------------------

void init_motor_driver();
void move_forward(float dist);
void turn_left(float angle);
void turn_right(float angle);

#endif /* MOTOR_DRIVER_H */

/* 
 * ultrasonic_sensor.c
 *
 * Author: Finn Middlton-Baird
 * 
 * Comments: file containing all functionality for ultrasonic sensor hardware on the board
 *      
 * Requires: ultrasonic_sensor.h
 * 
 * Revision: 1.0
 *
 * In this file:
 *      Includes - line 25
 *      Global Variables - line 31
 *      Functions - line 45
 *      (Functions) echo_isr_handle - line 46
 *      (Functions) init_ultrasonic_sensor - line 62
 *      (Functions) get_distance - line 100
 *      
 */

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include "ultrasonic_sensor.h"

//-----------------------------------------------------------------------------------------------------------
// Global Variables
//-----------------------------------------------------------------------------------------------------------

//timer declared in main
extern gptimer_handle_t echo_tmr;

//variables for echo timer count value when echo pulse starts and ends
uint64_t echo_start = 0;
uint64_t echo_end = 0;

//echo flag set when receiving echo pulse, cleared otherwise
uint8_t echo_flag = 0;

//-----------------------------------------------------------------------------------------------------------
// Functions
//-----------------------------------------------------------------------------------------------------------

static void IRAM_ATTR echo_isr_handler(void* arg) {
    gptimer_handle_t echo_tmr = (gptimer_handle_t)arg;

    if (! echo_flag) {
        gptimer_get_raw_count(echo_tmr, &echo_start);

        //echo flag set for echo pulse started
        echo_flag = 1;
    } else if (echo_flag) {
        gptimer_get_raw_count(echo_tmr, &echo_end);
        
        //echo flag cleared for echo pulse ended
        echo_flag = 0;
    }
}

void init_ultrasonic_sensor(int trig_pin, int echo_pin) {
    gpio_config_t io_conf = {};

    //GPIO output pin config
    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.pull_down_en = 0;
    io_conf.pull_up_en = 0;
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pin_bit_mask = (1ULL << trig_pin);
    gpio_config(&io_conf);

    //GPIO input pin config
    io_conf.intr_type = GPIO_INTR_ANYEDGE;
    io_conf.pull_down_en = 1;
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pin_bit_mask = (1ULL << echo_pin);
    gpio_config(&io_conf);

    //echo timer config
    gptimer_config_t echo_tmr_conf = {
        .clk_src = GPTIMER_CLK_SRC_APB,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000, //1MHz => 1us tick period timer
    };

    //timer to time echo pulse width
    gptimer_new_timer(&echo_tmr_conf, &echo_tmr);
    //timer runs indefinitely
    gptimer_start(echo_tmr);

    //isr to record timer count value on pos edge (echo pulse start) and neg edge (echo pulse end)
    gpio_install_isr_service(ESP_INTR_FLAG_LEVEL1);
    //add isr to echo pin
    gpio_isr_handler_add(echo_pin, echo_isr_handler, (void*)echo_tmr);

    ESP_LOGI(SENSOR_TAG, "Ulatrasonic Sensor initialised with trigger on pin %u and echo on pin %u", trig_pin, echo_pin);
}

float get_distance(int trig_pin) {
    //send trig pulse
    gpio_set_level(trig_pin, 1);
    vTaskDelay(0.01 / portTICK_PERIOD_MS);
    gpio_set_level(trig_pin, 0);

    //wait for end of echo pulse
    for (uint16_t i = 0; i < 2500; i++) { //only wait until max val to prevent watchdog timer not reset
        if (echo_end > 0) {
            break;
        }

        //pulse timed out (dist larger than max val)
        if (i >= 2499) {
            //set echo end to val which provides max dist
            echo_end = echo_start + 2500;

            ESP_LOGI(SENSOR_TAG, "Echo timed out");
            break;    
        }

        //delay one tick period of echo timer
        vTaskDelay(0.001 / portTICK_PERIOD_MS);
    }

    float dist = ((((echo_end - echo_start) * 1e-6) * 340) / 2) * 1e3; //dist in mm

    //limit distance measurements to hardware capability
    if (dist > 400) {
        //max distance is 40cm (400mm)
        dist = 400.00;
    } else if (dist < 20.00) {
        //min distance is 20mm 
        dist = 2.00;
    }

    ESP_LOGI(SENSOR_TAG, "Measured %.3fmm", dist);

    echo_end = 0;
    echo_start = 0;

    return dist;
}

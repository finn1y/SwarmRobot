/* 
 * motor_driver.c
 *
 * Author: Finn Middlton-Baird
 * 
 * Comments: file containing all functionality for motor driver hardware on the board
 *      
 * Requires: motor_driver.h
 * 
 * Revision: 1.0
 *
 * In this file:
 *      Includes - line 27
 *      Global Variables - line 33
 *      Functions - line 53
 *      (Functions) motor_timer_alarm_cb - line 54
 *      (Functions) init_motor_driver - line 64
 *      (Functions) move_forward - line 96
 *      (Functions) turn_left - line 129
 *      (Functions) turn_right - line 162
 *      
 */

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include "motor_driver.h"

//-----------------------------------------------------------------------------------------------------------
// Global Variables
//-----------------------------------------------------------------------------------------------------------

//timer declared in main
extern gptimer_handle_t motor_tmr;

//alarm config
gptimer_alarm_config_t motor_alarm_conf = {
    .reload_count = 0,
    .flags.auto_reload_on_alarm = true
};

//flag to stop the motor if set
uint8_t motor_flag = 0;

//velocities of motor
static const float linear_vel = 0.3;
static const float angular_vel = 6.6;

//-----------------------------------------------------------------------------------------------------------
// Functions
//-----------------------------------------------------------------------------------------------------------

static bool IRAM_ATTR motor_timer_alarm_cb(gptimer_handle_t motor_tmr, const gptimer_alarm_event_data_t *edata, void *user_data) {
    BaseType_t high_task_awoken = pdFALSE;
    // stop timer immediately
    gptimer_stop(motor_tmr);

    motor_flag = 1;
    // return whether we need to yield at the end of ISR
    return (high_task_awoken == pdTRUE);
}

void init_motor_driver(int motor1pin1, int motor1pin2, int motor2pin1, int motor2pin2) {
    const unsigned long long pin_bit_mask = (1ULL << motor1pin1 | 1ULL << motor1pin2 | 1ULL << motor2pin1 | 1ULL << motor2pin2);
    gpio_config_t io_conf = {};

    //GPIO output pin config
    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.pull_down_en = 0;
    io_conf.pull_up_en = 0;
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pin_bit_mask = pin_bit_mask;
    gpio_config(&io_conf);

    //timer config
    gptimer_config_t motor_tmr_conf = {
        .clk_src = GPTIMER_CLK_SRC_APB,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000, //1MHz => 1us period
    };

    //callback for alarm
    gptimer_event_callbacks_t cb = {
        .on_alarm = motor_timer_alarm_cb
    };

    //create timer 
    gptimer_new_timer(&motor_tmr_conf, &motor_tmr);
    //assign alarm to timer
    gptimer_register_event_callbacks(motor_tmr, &cb, NULL);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Motor driver initialised with motor 1 on pins %u and %u and motor 2 on pins %u and %u", motor1pin1, motor1pin2, motor2pin1, motor2pin2);
}

void move_forward(float dist) {
    //dist in mm
    //calculate time to run motor for
    uint64_t time = ((dist * 1e-3) / linear_vel) * 1e6; //time in us 

    //set alarm counter for time
    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Move forward %.2fmm", dist);
    //start timer
    gptimer_start(motor_tmr);
    //start motors
    gpio_set_level(12, 1);
    gpio_set_level(13, 0);

    gpio_set_level(21, 1);
    gpio_set_level(22, 0);

    //wait for motor to complete
    while (! motor_flag) {
        vTaskDelay((time * 1e-3) / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    //stop motors
    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}

void turn_left(float angle) {
    //angle in rads
    //calculate time to run motor for
    uint64_t time = (angle / angular_vel) * 1e6; //time in us 

    //set alarm counter for time
    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Turn left %.2frads", angle);
    //start timer
    gptimer_start(motor_tmr);
    //start motors
    gpio_set_level(12, 1);
    gpio_set_level(13, 0);

    gpio_set_level(21, 0);
    gpio_set_level(22, 1);

    //wait for motor to complete
    while (! motor_flag) {
        vTaskDelay((time * 1e-3) / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    //stop motors
    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}

void turn_right(float angle) {
    //angle in rads
    //calculate time to run motor for
    uint64_t time = (angle / angular_vel) * 1e6; //time in us 

    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Turn right %.2frads", angle);
    //start timer
    gptimer_start(motor_tmr);
    //start motors
    gpio_set_level(12, 0);
    gpio_set_level(13, 1);

    gpio_set_level(21, 1);
    gpio_set_level(22, 0);

    //wait for motor to complete
    while (! motor_flag) {
        vTaskDelay((time * 1e-3) / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    //stop motors
    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}



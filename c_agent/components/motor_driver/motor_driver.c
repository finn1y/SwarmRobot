#include "motor_driver.h"

extern gptimer_handle_t motor_tmr;

gptimer_alarm_config_t motor_alarm_conf = {
    .reload_count = 0,
    .flags.auto_reload_on_alarm = true
};

uint8_t motor_flag = 0;

static const float linear_vel = 0.5;
static const float angular_vel = 0.5;

/*
typedef struct {
    uint64_t event_count;
} example_queue_element_t;
example_queue_element_t ele;
QueueHandle_t queue = NULL;
*/

static bool IRAM_ATTR motor_timer_alarm_cb(gptimer_handle_t tmr, const gptimer_alarm_event_data_t *edata, void *user_data)
{
    BaseType_t high_task_awoken = pdFALSE;
//    QueueHandle_t queue = (QueueHandle_t)user_data;
    // stop timer immediately
    gptimer_stop(motor_tmr);
    // Retrieve count value and send to queue
/*    example_queue_element_t ele = {
        .event_count = edata->count_value
    };
    xQueueSendFromISR(queue, &ele, &high_task_awoken);*/
    motor_flag = 1;
    // return whether we need to yield at the end of ISR
    return (high_task_awoken == pdTRUE);
}

void init_motor_driver(int motor1pin1, int motor1pin2, int motor2pin1, int motor2pin2) {
    const unsigned long long pin_bit_mask = (1ULL << motor1pin1 | 1ULL << motor1pin2 | 1ULL << motor2pin1 | 1ULL << motor2pin2);
    gpio_config_t io_conf = {};

    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.pull_down_en = 0;
    io_conf.pull_up_en = 0;
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pin_bit_mask = pin_bit_mask;
    gpio_config(&io_conf);

    gptimer_config_t motor_tmr_conf = {
        .clk_src = GPTIMER_CLK_SRC_APB,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000, //1MHz => 1us
    };

    gptimer_event_callbacks_t cb = {
        .on_alarm = motor_timer_alarm_cb
    };
//    queue = xQueueCreate(1, sizeof(example_queue_element_t));
    gptimer_new_timer(&motor_tmr_conf, &motor_tmr);
//    gptimer_register_event_callbacks(motor_tmr, &cb, queue);
    gptimer_register_event_callbacks(motor_tmr, &cb, NULL);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Motor driver initialised with motor 1 on pins %u and %u and motor 2 on pins %u and %u", motor1pin1, motor1pin2, motor2pin1, motor2pin2);
}

void move_forward(float dist) {
    //dist in mm
    uint64_t time = ((dist * 1e-3) / linear_vel) * 1e6; //time in us 

    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Move forward %.2fmm", dist);
    gptimer_start(motor_tmr);
    gpio_set_level(12, 0);
    gpio_set_level(13, 1);

    gpio_set_level(21, 0);
    gpio_set_level(22, 1);

/*    if (xQueueReceive(queue, &ele, pdMS_TO_TICKS(((time * 1e-3) + 1e3) / portTICK_PERIOD_MS))) {
        ESP_LOGI(MOTOR_DRIVER_TAG, "Timer stopped, count=%llu", ele.event_count);
        gpio_set_level(12, 0);
        gpio_set_level(13, 0);
        
        gpio_set_level(21, 0);
        gpio_set_level(22, 0);
    } else {
        ESP_LOGW(MOTOR_DRIVER_TAG, "Missed one count event");
    }*/

    while (! motor_flag) {
        vTaskDelay(100 / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}

void turn_left(float angle) {
    //angle in rads
    uint64_t time = (angle / angular_vel) * 1e6; //time in us 

    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Turn left %.2frads", angle);
    gptimer_start(motor_tmr);
    gpio_set_level(12, 0);
    gpio_set_level(13, 1);

    gpio_set_level(21, 1);
    gpio_set_level(22, 0);

/*    if (xQueueReceive(queue, &ele, pdMS_TO_TICKS(((time * 1e-3) + 1e3) / portTICK_PERIOD_MS))) {
        ESP_LOGI(MOTOR_DRIVER_TAG, "Timer stopped, count=%llu", ele.event_count);
        gpio_set_level(12, 0);
        gpio_set_level(13, 0);
        
        gpio_set_level(21, 0);
        gpio_set_level(22, 0);
    } else {
        ESP_LOGW(MOTOR_DRIVER_TAG, "Missed one count event");
    }*/

    while (! motor_flag) {
        vTaskDelay(100 / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}

void turn_right(float angle) {
    //angle in rads
    uint64_t time = (angle / linear_vel) * 1e6; //time in us 

    motor_alarm_conf.alarm_count = time;
    gptimer_set_alarm_action(motor_tmr, &motor_alarm_conf);

    ESP_LOGI(MOTOR_DRIVER_TAG, "Turn right %.2frads", angle);
    gptimer_start(motor_tmr);
    gpio_set_level(12, 1);
    gpio_set_level(13, 0);

    gpio_set_level(21, 0);
    gpio_set_level(22, 1);

/*    if (xQueueReceive(queue, &ele, pdMS_TO_TICKS(((time * 1e-3) + 1e3) / portTICK_PERIOD_MS))) {
        ESP_LOGI(MOTOR_DRIVER_TAG, "Timer stopped, count=%llu", ele.event_count);
        gpio_set_level(12, 0);
        gpio_set_level(13, 0);
        
        gpio_set_level(21, 0);
        gpio_set_level(22, 0);
    } else {
        ESP_LOGW(MOTOR_DRIVER_TAG, "Missed one count event");
    }*/

    while (! motor_flag) {
        vTaskDelay(100 / portTICK_PERIOD_MS);
    }
    motor_flag = 0;

    gpio_set_level(12, 0);
    gpio_set_level(13, 0);
        
    gpio_set_level(21, 0);
    gpio_set_level(22, 0);
}

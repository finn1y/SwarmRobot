/* 
 * main.c
 *
 * Author: Finn Middlton-Baird
 * 
 * Comments: main file for agent of swarm robot designed for esp32 devkitM-1 board, use sdkconfig to define
 *      hardware options (e.g. pin connections) and wireless credentials
 *      
 * Requires: mqtt.c, wifi.c, motor_driver component and ultrasonic_sensor component
 * 
 * Revision: 1.0
 *
 * In this file:
 *      Includes - line 26
 *      Defines - line 46
 *      Global Variables - line 60
 *      main - line 87
 *      (main) init - line 89
 *      (main) main loop - line 196
 *      
 */

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_event.h"

#include "wifi.h"
#include "mqtt.h"

#include "ultrasonic_sensor.h"
#include "motor_driver.h"

//-----------------------------------------------------------------------------------------------------------
// Defines
//-----------------------------------------------------------------------------------------------------------

#define PI                  3.14

#define ULTRASONIC_TRIG     CONFIG_ULTRASONIC_SENSOR_TRIG
#define ULTRASONIC_ECHO     CONFIG_ULTRASONIC_SENSOR_ECHO

#define MOTOR_DRIVER_IN1    CONFIG_MOTOR_DRIVER_IN1
#define MOTOR_DRIVER_IN2    CONFIG_MOTOR_DRIVER_IN2
#define MOTOR_DRIVER_IN3    CONFIG_MOTOR_DRIVER_IN3
#define MOTOR_DRIVER_IN4    CONFIG_MOTOR_DRIVER_IN4

//-----------------------------------------------------------------------------------------------------------
// Global Variables
//-----------------------------------------------------------------------------------------------------------

//MQTT client
esp_mqtt_client_handle_t client;

//agent flags
uint8_t n_flag = 0;
uint8_t start_flag = 0;
uint8_t action_flag = 0;
uint8_t status_flag = 0;

//MQTT message buffers
char start_buffer[5];
char action_buffer[5];
char n_buffer[5];
char status_buffer[5];

//variable MQTT topics
char start_topic[25];
char action_topic[25];

//timers
gptimer_handle_t echo_tmr = NULL;
gptimer_handle_t motor_tmr = NULL;


//-----------------------------------------------------------------------------------------------------------
// main
//-----------------------------------------------------------------------------------------------------------

void app_main() {
    //init variables
    uint16_t n; //agent number (index)

    //RL env vars
    float dist_front = 0; //distance to front obstacle
    int reward = 0; 
    bool done = false; //bool if reached goal state

    //MQTT publish buffers
    char pub_topic_buffer[25];
    char pub_data_buffer[10];

    //init NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      ret = nvs_flash_init();
    }

    //init WiFi
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(WIFI_TAG, "ESP_WIFI_MODE_STA");

    init_wifi_sta();

    //init MQTT
    init_mqtt();

    ESP_LOGV(MQTT_TAG, "SUBSCRIBE TOPIC=%s", master_status_topic);

    esp_mqtt_client_subscribe(client, master_status_topic, 1);

    ESP_LOGI(AGENT_TAG, "Waiting for master...");

    //wait for master to be connected to broker before checking received messages and publishing
    do {
        process_messages();
        vTaskDelay(50 / portTICK_PERIOD_MS);
    } while (! status_flag); 

    ESP_LOGV(MQTT_TAG, "SUBSCRIBE TOPIC=%s", index_topic);

    esp_mqtt_client_subscribe(client, index_topic, 1);

    ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", add_topic);
    ESP_LOGV(MQTT_TAG, "PUBLISH DATA=1");

    esp_mqtt_client_publish(client, add_topic, "1", 0, 1, 0);

    //init components
    init_ultrasonic_sensor(ULTRASONIC_TRIG, ULTRASONIC_ECHO); //trigger pin, echo pin
    init_motor_driver(MOTOR_DRIVER_IN1, MOTOR_DRIVER_IN2, MOTOR_DRIVER_IN3, MOTOR_DRIVER_IN4); //motor1 pin1, pin2, motor2 pin1, pin2

    ESP_LOGI(AGENT_TAG, "Waiting for index...");

    //wait for init message to be received
    do {
        process_messages();
        vTaskDelay(50 / portTICK_PERIOD_MS);
    } while (! n_flag); 
    n_flag = 0;

    ESP_LOGV(AGENT_TAG, "N_FLAG Cleared");
    
    n = str_to_int(n_buffer);

    ESP_LOGI(AGENT_TAG, "Agent index: %u", n);

    //unsubscribe from index topic once this agent has an index
    esp_mqtt_client_unsubscribe(client, index_topic);

    sprintf(start_topic, "/agents/%u/start", n);
    sprintf(action_topic, "/agents/%u/action", n);

    ESP_LOGV(MQTT_TAG, "SUBSCRIBE TOPIC=%s", start_topic);
    ESP_LOGV(MQTT_TAG, "SUBSCRIBE TOPIC=%s", action_topic);

    esp_mqtt_client_subscribe(client, start_topic, 1);
    esp_mqtt_client_subscribe(client, action_topic, 1);

    //publish status message
    sprintf(pub_topic_buffer, "/agents/%u/status", n);

    ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", pub_topic_buffer);
    ESP_LOGV(MQTT_TAG, "PUBLISH DATA=1");

    esp_mqtt_client_publish(client, pub_topic_buffer, "1", 0, 1, 1);

    //wait for master to initialise this agent's coroutine
    ESP_LOGI(AGENT_TAG, "Waiting for start...");
    do {
        process_messages();
        vTaskDelay(50 / portTICK_PERIOD_MS);
    } while (! start_flag); 

    //get initial distance
    dist_front = get_distance(18);
    //publish initial obv
    sprintf(pub_data_buffer, "[%.4f]", dist_front);
    sprintf(pub_topic_buffer, "/agents/%u/obv", n);

    ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", pub_topic_buffer);
    ESP_LOGV(MQTT_TAG, "PUBLISH DATA=%s", pub_data_buffer);
    
    esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

    //main loop
    while (1) {
        if (action_flag) {
            switch (str_to_int(action_buffer)) {
                case 0:
                    //check if collision would occur
                    if (dist_front <= 200) {
                        ESP_LOGI(MOTOR_DRIVER_TAG, "Object detected ahead %.2fmm away, not performing action 'move forward' preventing collision", dist_front);

                        reward = -50;
                    } else {
                        //move forward
                        move_forward(200);
                        reward = -1;
                    }

                    break;

                case 1:
                    //turn right (pi/2 rads)
                    turn_right(PI/2); 
                    reward = -1;
                    break;

                case 2:
                    //turn around (pi rads)
                    turn_right(PI);
                    reward = -1;
                    break;

                case 3:
                    //turn left (pi/2 rads)
                    turn_left(PI/2);
                    reward = -1;
                    break;
            }

            //clear action flag after processing action
            action_flag = 0;
            ESP_LOGV(AGENT_TAG, "ACTION_FLAG Cleared");

            dist_front = get_distance(18);

            //wait for master to be connected to broker before publishing messages
            while (! status_flag) {
                process_messages();
                vTaskDelay(500 / portTICK_PERIOD_MS);
            } 

            //publish obv
            sprintf(pub_data_buffer, "[%.4f]", dist_front);
            sprintf(pub_topic_buffer, "/agents/%u/obv", n);

            ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", pub_topic_buffer);
            ESP_LOGV(MQTT_TAG, "PUBLISH DATA=%s", pub_data_buffer);
    
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //publish reward
            sprintf(pub_data_buffer, "%i", reward);
            sprintf(pub_topic_buffer, "/agents/%u/reward", n);

            ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", pub_topic_buffer);
            ESP_LOGV(MQTT_TAG, "PUBLISH DATA=%s", pub_data_buffer);
    
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //publish done
            sprintf(pub_data_buffer, "%s", done ? "True" : "False");
            sprintf(pub_topic_buffer, "/agents/%u/done", n);

            ESP_LOGV(MQTT_TAG, "PUBLISH TOPIC=%s", pub_topic_buffer);
            ESP_LOGV(MQTT_TAG, "PUBLISH DATA=%s", pub_data_buffer);
    
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //delay
            vTaskDelay(500 / portTICK_PERIOD_MS);
        }

        process_messages();
        //delay
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
}




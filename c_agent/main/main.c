#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "nvs_flash.h"
#include "lwip/err.h"
#include "lwip/sys.h"

#include "ultrasonic_sensor.h"
#include "motor_driver.h"

#define PI                  3.14
#define WIFI_TAG            "WiFi Log"
#define MQTT_TAG            "MQTT Log"
#define AGENT_TAG           "Agent Log"
#define WIFI_SSID           CONFIG_WIFI_SSID 
#define WIFI_PASSWORD       CONFIG_WIFI_PASSWORD
#define WIFI_MAX_RETRY      CONFIG_WIFI_MAX_RETRY
#define MQTT_URI            CONFIG_MQTT_URI
#define MQTT_USERNAME       CONFIG_MQTT_USERNAME
#define MQTT_PASSWORD       CONFIG_MQTT_PASSWORD
#define WIFI_CONNECTED_BIT  BIT0
#define WIFI_FAIL_BIT       BIT1
#define ULTRASONIC_TRIG     CONFIG_ULTRASONIC_SENSOR_TRIG
#define ULTRASONIC_ECHO     CONFIG_ULTRASONIC_SENSOR_ECHO
#define MOTOR_DRIVER_IN1    CONFIG_MOTOR_DRIVER_IN1
#define MOTOR_DRIVER_IN2    CONFIG_MOTOR_DRIVER_IN2
#define MOTOR_DRIVER_IN3    CONFIG_MOTOR_DRIVER_IN3
#define MOTOR_DRIVER_IN4    CONFIG_MOTOR_DRIVER_IN4

extern const uint8_t mqtt_pem_start[] asm("_binary_mqtt_pem_start");
extern const uint8_t mqtt_pem_end[] asm("_binary_mqtt_pem_end");

//FreeRTOS event group to signal when connected
static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;

static esp_mqtt_client_handle_t client;

const esp_mqtt_client_config_t mqtt_cfg = {
    .uri = MQTT_URI,
    .username = MQTT_USERNAME,
    .password = MQTT_PASSWORD,
    .cert_pem = (const char*)mqtt_pem_start
};

uint8_t n_flag = 0;
uint8_t start_flag = 0;
uint8_t action_flag = 0;
uint8_t status_flag = 0;

char start_buffer[5];
char action_buffer[5];
char n_buffer[5];
char status_buffer[5];

QueueHandle_t msg_q = NULL;
typedef struct {
    int topic_len;
    char* topic;
    int data_len;
    char* data;
} msg_q_element_t;

//topics
char start_topic[25];
char action_topic[25];
static const char index_topic[] = "/agents/index";
static const char master_status_topic[] = "/master/status";
static const char add_topic[] = "/agents/add";

gptimer_handle_t echo_tmr = NULL;
gptimer_handle_t motor_tmr = NULL;

int str_to_int(char* str) {
    int val = 0;

    while (*str != 0) {
        uint8_t char_val = (int)*str - 48; //48 is the ASCII value for the number 0
        val = (val * 10) + char_val;
        str++;
    }

    return val;
}

static void event_handler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < WIFI_MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(WIFI_TAG, "retry to connect to the AP");
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }

        ESP_LOGI(WIFI_TAG,"connect to the AP fail");
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(WIFI_TAG, "got ip:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void wifi_init_sta(void) {
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());

    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASSWORD,
	        .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable = true,
                .required = false
            },
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA) );
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config) );
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(WIFI_TAG, "wifi_init_sta finished.");

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(WIFI_TAG, "Connected to ap WIFI_SSID:%s password:%s", WIFI_SSID, WIFI_PASSWORD);
    } else if (bits & WIFI_FAIL_BIT) {
        ESP_LOGI(WIFI_TAG, "Failed to connect to WIFI_SSID:%s, password:%s", WIFI_SSID, WIFI_PASSWORD);
    } else {
        ESP_LOGE(WIFI_TAG, "UNEXPECTED EVENT");
    }

    //do not process event after unregister
    ESP_ERROR_CHECK(esp_event_handler_instance_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP, instance_got_ip));
    ESP_ERROR_CHECK(esp_event_handler_instance_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID, instance_any_id));
    vEventGroupDelete(s_wifi_event_group);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    ESP_LOGD(MQTT_TAG, "Event dispatched from event loop base=%s, event_id=%d", base, event_id);

    esp_mqtt_event_handle_t event = event_data;

    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(MQTT_TAG, "MQTT_CONNECTED");
            break;

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGI(MQTT_TAG, "MQTT_DISCONNECTED");
            break;

        case MQTT_EVENT_SUBSCRIBED:
            ESP_LOGI(MQTT_TAG, "MQTT_SUBSCRIBED, msg_id=%d", event->msg_id);
            break;
            
        case MQTT_EVENT_UNSUBSCRIBED:
            ESP_LOGI(MQTT_TAG, "MQTT_UNSUBSCRIBED, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_PUBLISHED:
            ESP_LOGI(MQTT_TAG, "MQTT_PUBLISHED, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_DATA:
            ESP_LOGI(MQTT_TAG, "MQTT_DATA_RECEIVED");
        
            printf("%.*s received from ", event->data_len, event->data); //debug
            printf("topic %.*s\r\n", event->topic_len, event->topic); //debug
            ESP_LOGV(MQTT_TAG, "TOPIC=%.*s", event->topic_len, event->topic);
            ESP_LOGV(MQTT_TAG, "DATA=%.*s", event->data_len, event->data);

            msg_q_element_t element = {
                .topic_len = event->topic_len,
                .topic = event->topic,
                .data_len = event->data_len,
                .data = event->data
            };

            xQueueSend(msg_q, &element, 100 / portTICK_PERIOD_MS);
            
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGI(MQTT_TAG, "MQTT_ERROR");
            break;

        default:
            ESP_LOGI(MQTT_TAG, "Other event id: %d", event->event_id);
            break;
    }
}

void process_messages() {
    msg_q_element_t element;
    char topic_buffer[30];
    char msg_buffer[30];

    if (xQueueReceive(msg_q, &element, pdMS_TO_TICKS(100 / portTICK_PERIOD_MS))) {
        sprintf(topic_buffer, "%.*s", element.topic_len, element.topic);

        sprintf(msg_buffer, "%.*s", element.data_len, element.data);
        printf("Received %s, ", msg_buffer); //debug
        printf("From topic: %s\r\n", topic_buffer); //debug

        if (! strcmp(topic_buffer, index_topic)) {
            sprintf(n_buffer, "%.*s", element.data_len, element.data);
            n_flag = 1;

            ESP_LOGV(AGENT_TAG, "N_FLAG Set");

        } else if (! strcmp(topic_buffer, start_topic)) {
            sprintf(start_buffer, "%.*s", element.data_len, element.data);
            //start flag is set by master over MQTT once agent is initialised at master
            start_flag = str_to_int(start_buffer);

            if (start_flag) {
                ESP_LOGV(AGENT_TAG, "START_FLAG Set");
            } else if (! start_flag){
                ESP_LOGV(AGENT_TAG, "START_FLAG Cleared");
            }

        } else if (! strcmp(topic_buffer, action_topic)) {
            sprintf(action_buffer, "%.*s", element.data_len, element.data);
            action_flag = 1;

            ESP_LOGV(AGENT_TAG, "ACTION_FLAG Set");

        } else if (! strcmp(topic_buffer, master_status_topic)) {
            sprintf(status_buffer, "%.*s", element.data_len, element.data);
            //status flag is set when master is connected to broker
            status_flag = str_to_int(status_buffer);

            if (status_flag) {
                ESP_LOGV(AGENT_TAG, "STATUS_FLAG Set");
            } else if (! status_flag) {
                ESP_LOGV(AGENT_TAG, "STATUS_FLAG Cleared");
            }
        }
    }
}

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

    wifi_init_sta();

    //init MQTT
    msg_q = xQueueCreate(10, sizeof(msg_q_element_t));

    client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);

    esp_mqtt_client_start(client);

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
                    //move forward
                    move_forward(200);
                    reward = -1;
                    break;

                case 1:
                    //turn right (pi/2 rads)
                    turn_right(PI/2); 
                    reward = -1;
                    break;

                case 2:
                    //turn around (pi rads)
                    turn_right(PI/2);
                    reward = -1;
                    break;

                case 3:
                    //turn left (pi/2 rads)
                    turn_left(PI/2);
                    reward = -1;
                    break;
            }

            action_flag = 0;
            ESP_LOGV(AGENT_TAG, "ACTION_FLAG Cleared");

            //get from env
            dist_front = get_distance(18);

            //wait for master to be connected to broker before publishing messages
            while (! status_flag) {
                process_messages();
                vTaskDelay(500 / portTICK_PERIOD_MS);
            } 

            //publish obv
            sprintf(pub_data_buffer, "[%.4f]", dist_front);
            sprintf(pub_topic_buffer, "/agents/%u/obv", n);
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //publish reward
            sprintf(pub_data_buffer, "%i", reward);
            sprintf(pub_topic_buffer, "/agents/%u/reward", n);
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //publish done
            sprintf(pub_data_buffer, "%s", done ? "True" : "False");
            sprintf(pub_topic_buffer, "/agents/%u/done", n);
            esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

            //delay
            vTaskDelay(500 / portTICK_PERIOD_MS);
        }

        process_messages();
        //delay
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
}




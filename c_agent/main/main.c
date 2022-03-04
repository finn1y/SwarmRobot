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
#define PI                  3.14

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
uint8_t msg_flag = 0;

char start_buffer[5];
char action_buffer[5];
char n_buffer[5];
char status_buffer[5];
char msg_buffer[30];
char topic_buffer[30];

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
        char char_val = (int)*str - 48; //48 is the ASCII value for the number 0
        val = (val * 10) + char_val;
        str++;
    }

    return val;
}

void slice_str(char* in_str, uint8_t start, uint8_t end, char* out_str) {
    for (uint8_t i = start; i < end; i++) {
        out_str[i - start] = in_str[i];
    }

    out_str[end + 1] = 0;
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
        ESP_LOGI(WIFI_TAG, "connected to ap WIFI_SSID:%s password:%s", WIFI_SSID, WIFI_PASSWORD);
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

            if (! strcmp(event->topic, index_topic)) {
                slice_str(event->data, 0, event->data_len, n_buffer);
                n_flag = 1;
                printf("%.*s received from ", event->data_len, event->data); //debug
                printf("topic %.*s\r\n", event->topic_len, event->topic); //debug

            } else if (! strcmp(event->topic, start_topic)) {
                slice_str(event->data, 0, event->data_len, start_buffer);
                //start flag is set by master over MQTT once agent is initialised at master
                start_flag = str_to_int(start_buffer);
                printf("%.*s received from ", event->data_len, event->data); //debug
                printf("topic %.*s\r\n", event->topic_len, event->topic); //debug

            } else if (! strcmp(event->topic, action_topic)) {
                slice_str(event->data, 0, event->data_len, action_buffer);
                action_flag = 1;
                printf("%.*s received from ", event->data_len, event->data); //debug
                printf("topic %.*s\r\n", event->topic_len, event->topic); //debug

            } else if (! strcmp(event->topic, master_status_topic)) {
                slice_str(event->data, 0, event->data_len, status_buffer);
                status_flag = 1;
                printf("%.*s received from ", event->data_len, event->data); //debug
                printf("topic %.*s\r\n", event->topic_len, event->topic); //debug

            } else {
                slice_str(event->data, 0, event->data_len, msg_buffer);
                slice_str(event->topic, 0, event->topic_len, topic_buffer);
                msg_flag = 1;
                printf("%.*s received from ", event->data_len, event->data); //debug
                printf("topic %.*s\r\n", event->topic_len, event->topic); //debug
            }

            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGI(MQTT_TAG, "MQTT_ERROR");
            break;

        default:
            ESP_LOGI(MQTT_TAG, "Other event id: %d", event->event_id);
            break;
    }
}

void app_main() {
    //init variables
    uint16_t n; //agent number (index)
    float dist_front = 0; //distance to front obstacle
    int reward = 0; 
    bool done = false; //bool if reached goal state
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
    client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(client);

    esp_mqtt_client_subscribe(client, master_status_topic, 1);
    esp_mqtt_client_subscribe(client, index_topic, 1);
    esp_mqtt_client_publish(client, add_topic, "1", 0, 1, 0);

    //init components
    init_ultrasonic_sensor(18, 5); //trigger pin, echo pin
    init_motor_driver(12, 13, 21, 22); //motor1 pin1, pin2, motor2 pin1, pin2

    //wait for init message to be received
    ESP_LOGI(AGENT_TAG, "Waiting for index...");
    while (! n_flag) {
        vTaskDelay(500 / portTICK_PERIOD_MS);
    } 
    n_flag = 0;
    
    n = str_to_int(n_buffer);
    ESP_LOGI(AGENT_TAG, "This is agent %u", n);

    sprintf(start_topic, "/agents/%u/start", n);
    sprintf(action_topic, "/agents/%u/action", n);
    esp_mqtt_client_subscribe(client, start_topic, 1);
    esp_mqtt_client_subscribe(client, action_topic, 1);

    //wait for subscribe before sending messages
    while (! start_flag) {
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
    start_flag = 0;

    //get initial distance
    dist_front = get_distance(18);
    //publish initial obv
    sprintf(pub_data_buffer, "[%.4f]", dist_front);
    sprintf(pub_topic_buffer, "/agents/%u/obv", n);
    printf("PUB_TOPIC=%s, ", pub_topic_buffer);
    printf("PUB_DATA=%s\r\n", pub_data_buffer);
    esp_mqtt_client_publish(client, pub_topic_buffer, pub_data_buffer, 0, 1, 0);

    //main loop
    while (1) {
        if (action_flag) {
            action_flag = 0;

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

            //get from env
            dist_front = get_distance(18);

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
        } else {
            vTaskDelay(500 / portTICK_PERIOD_MS);
        }
    }
}




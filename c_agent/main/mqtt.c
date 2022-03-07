//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include "mqtt.h"

//-----------------------------------------------------------------------------------------------------------
// Global Variables
//-----------------------------------------------------------------------------------------------------------

extern const uint8_t mqtt_pem_start[] asm("_binary_mqtt_pem_start");
extern const uint8_t mqtt_pem_end[] asm("_binary_mqtt_pem_end");

extern esp_mqtt_client_handle_t client;

//agent flags
extern uint8_t n_flag;
extern uint8_t start_flag;
extern uint8_t action_flag;
extern uint8_t status_flag;

//MQTT message buffers
extern char start_buffer[5];
extern char action_buffer[5];
extern char n_buffer[5];
extern char status_buffer[5];

//variable MQTT topics
extern char start_topic[25];
extern char action_topic[25];

//MQTT message queue
QueueHandle_t msg_q = NULL;

typedef struct {
    int topic_len;
    char* topic;
    int data_len;
    char* data;
} msg_q_element_t;

//-----------------------------------------------------------------------------------------------------------
// Functions
//-----------------------------------------------------------------------------------------------------------

int str_to_int(char* str) {
    int val = 0;

    //loop through string until NULL character
    while (*str != 0) {
        //convert each char into an int
        uint8_t char_val = (int)*str - 48; //48 is the ASCII value for the number 0
        //add int to total integer value
        val = (val * 10) + char_val;
        str++;
    }

    return val;
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

            //init element to put into queue
            msg_q_element_t element = {
                .topic_len = event->topic_len,
                .topic = event->topic,
                .data_len = event->data_len,
                .data = event->data
            };

            //send element to queue for later processing
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

void init_mqtt() {
    //message queue with size for 5 elements
    msg_q = xQueueCreate(5, sizeof(msg_q_element_t));

    esp_mqtt_client_config_t mqtt_cfg = {
        .uri = MQTT_URI,
        .username = MQTT_USERNAME,
        .password = MQTT_PASSWORD,
        .cert_pem = (const char*)mqtt_pem_start
    };

    client = esp_mqtt_client_init(&mqtt_cfg);
    //start mqtt event handler
    esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);

    esp_mqtt_client_start(client);
}

void process_messages() {
    msg_q_element_t element;
    char topic_buffer[30];

    if (xQueueReceive(msg_q, &element, pdMS_TO_TICKS(100 / portTICK_PERIOD_MS))) {
        sprintf(topic_buffer, "%.*s", element.topic_len, element.topic);

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

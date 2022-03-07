#ifndef MQTT_H
#define MQTT_h

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_event.h"
#include "mqtt_client.h"

//-----------------------------------------------------------------------------------------------------------
// Defines
//-----------------------------------------------------------------------------------------------------------

#define MQTT_TAG        "MQTT Log"
#define AGENT_TAG       "Agent Log"

#define MQTT_URI        CONFIG_MQTT_URI
#define MQTT_USERNAME   CONFIG_MQTT_USERNAME
#define MQTT_PASSWORD   CONFIG_MQTT_PASSWORD

//-----------------------------------------------------------------------------------------------------------
// Global Variables
//-----------------------------------------------------------------------------------------------------------

//constant MQTT topics
static const char index_topic[] = "/agents/index";
static const char master_status_topic[] = "/master/status";
static const char add_topic[] = "/agents/add";

//-----------------------------------------------------------------------------------------------------------
// Function Declarations
//-----------------------------------------------------------------------------------------------------------

int str_to_int(char* str);
void init_mqtt();
void process_messages();

#endif /* MQTT_H */

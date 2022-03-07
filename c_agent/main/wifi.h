#ifndef WIFI_H
#define WIFI_H

//-----------------------------------------------------------------------------------------------------------
// Includes
//-----------------------------------------------------------------------------------------------------------

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "lwip/err.h"
#include "lwip/sys.h"

//-----------------------------------------------------------------------------------------------------------
// Defines
//-----------------------------------------------------------------------------------------------------------

#define WIFI_TAG            "WiFi Log"

#define WIFI_SSID           CONFIG_WIFI_SSID 
#define WIFI_PASSWORD       CONFIG_WIFI_PASSWORD
#define WIFI_MAX_RETRY      CONFIG_WIFI_MAX_RETRY

#define WIFI_CONNECTED_BIT  BIT0
#define WIFI_FAIL_BIT       BIT1

//-----------------------------------------------------------------------------------------------------------
// Function Declarations
//-----------------------------------------------------------------------------------------------------------

void init_wifi_sta();

#endif /* WIFI_H */

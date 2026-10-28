/*
 * Mimamori Test - Child safety GPS tracker prototype (M5StickC Plus2)
 *
 * Prototype firmware for M5StickC Plus2 (ESP32).
 * GPS and cellular communication are NOT connected yet.
 * Simulated GPS mode generates test coordinates every GPS_UPDATE_INTERVAL_MS.
 *
 * Build: Arduino IDE or PlatformIO. See README.md.
 */

#include <M5StickCPlus2.h>

// ===================== Configuration (edit here) =====================
#define DEVICE_ID "M5STICK-001"          // Unique device id (no secrets here)
#define GPS_UPDATE_INTERVAL_MS 5000UL     // Position update interval
#define STALE_THRESHOLD_MS 30000UL        // Show STALE after this long without a fix

// GPS data source mode. Use simulated mode until a real GPS unit is connected.
#define USE_SIMULATED_GPS 1               // 1 = simulated test data, 0 = real GPS
#define USE_REAL_GPS 0                    // 1 = enable real GPS implementation (requires TinyGPS++)

// Real GPS UART settings (used only when USE_REAL_GPS == 1).
// Adjust to the actual module; do not hard-code in production without review.
#define GPS_UART_NUM 2
#define GPS_UART_RX_PIN 33                // GROVE RX (configurable)
#define GPS_UART_TX_PIN 32                // GROVE TX (configurable)
#define GPS_UART_BAUD 9600

// Simulated movement parameters
#define SIM_INITIAL_LAT 35.681236
#define SIM_INITIAL_LON 139.767125
#define SIM_STEP_MAX_M 15.0f              // max step per update (~meters)

// Serial output
#define SERIAL_BAUD 115200

// ===================== Common data structures =====================
enum DataSource {
    DATA_SOURCE_UNKNOWN = 0,
    DATA_SOURCE_SIMULATED,
    DATA_SOURCE_GPS
};

enum SystemState {
    STATE_INIT = 0,
    STATE_SIMULATING,
    STATE_GPS_SEARCHING,
    STATE_FIX_OK,
    STATE_GPS_ERROR,
    STATE_COMM_ERROR,
    STATE_RECONNECT_WAIT
};

struct LocationFix {
    char deviceId[32];
    double latitude;
    double longitude;
    // millis() at acquisition (monotonic). The device has no RTC, so this is
    // NOT a Unix timestamp: when network transport is added, send
    // "timestamp": null and let the server stamp received_at.
    uint32_t uptime_ms;
    float accuracy_m;        // meters; valid only if accuracy_valid
    bool accuracy_valid;
    bool fix_valid;
    DataSource data_source;
};

// ===================== Utility =====================
static bool isValidCoordinate(double lat, double lon) {
    if (lat < -90.0 || lat > 90.0) return false;
    if (lon < -180.0 || lon > 180.0) return false;
    // reject (0,0) as likely invalid/no-fix sentinel
    if (lat == 0.0 && lon == 0.0) return false;
    return true;
}

static const char* dataSourceName(DataSource s) {
    switch (s) {
        case DATA_SOURCE_SIMULATED: return "SIMULATED";
        case DATA_SOURCE_GPS: return "GPS";
        default: return "UNKNOWN";
    }
}

static const char* stateName(SystemState s) {
    switch (s) {
        case STATE_INIT: return "INIT";
        case STATE_SIMULATING: return "SIMULATING";
        case STATE_GPS_SEARCHING: return "GPS_SEARCH";
        case STATE_FIX_OK: return "FIX_OK";
        case STATE_GPS_ERROR: return "GPS_ERROR";
        case STATE_COMM_ERROR: return "COMM_ERROR";
        case STATE_RECONNECT_WAIT: return "RECONNECT_WAIT";
        default: return "UNKNOWN";
    }
}

// ===================== GPS provider interface =====================
class IGpsProvider {
public:
    virtual ~IGpsProvider() {}
    virtual bool begin() = 0;
    virtual bool update(LocationFix& out, uint32_t now_ms) = 0; // true if new valid fix
    virtual const char* name() const = 0;
};

// ===================== Simulated GPS provider =====================
class SimulatedGpsProvider : public IGpsProvider {
public:
    SimulatedGpsProvider() : _lat(SIM_INITIAL_LAT), _lon(SIM_INITIAL_LON), _step(0) {}

    bool begin() override {
        _lat = SIM_INITIAL_LAT;
        _lon = SIM_INITIAL_LON;
        _step = 0;
        return true;
    }

    bool update(LocationFix& out, uint32_t now_ms) override {
        // random walk around initial coordinate
        _step++;
        float dLat = (random(-100, 101) / 100.0f) * (SIM_STEP_MAX_M / 111000.0f);
        float dLon = (random(-100, 101) / 100.0f) * (SIM_STEP_MAX_M / (111000.0f * cosf(_lat * 0.0174533f)));
        _lat += dLat;
        _lon += dLon;
        // keep near initial (clamp to ~500m box)
        if (_lat < SIM_INITIAL_LAT - 0.005) _lat = SIM_INITIAL_LAT - 0.005;
        if (_lat > SIM_INITIAL_LAT + 0.005) _lat = SIM_INITIAL_LAT + 0.005;
        if (_lon < SIM_INITIAL_LON - 0.005) _lon = SIM_INITIAL_LON - 0.005;
        if (_lon > SIM_INITIAL_LON + 0.005) _lon = SIM_INITIAL_LON + 0.005;

        if (!isValidCoordinate(_lat, _lon)) {
            return false;
        }

        strncpy(out.deviceId, DEVICE_ID, sizeof(out.deviceId) - 1);
        out.deviceId[sizeof(out.deviceId) - 1] = '\0';
        out.latitude = _lat;
        out.longitude = _lon;
        out.uptime_ms = now_ms;
        out.accuracy_m = NAN;           // not measured
        out.accuracy_valid = false;     // do not fabricate accuracy
        out.fix_valid = true;
        out.data_source = DATA_SOURCE_SIMULATED;
        return true;
    }

    const char* name() const override { return "SimulatedGps"; }

private:
    double _lat;
    double _lon;
    uint32_t _step;
};

// ===================== Real GPS provider (optional) =====================
#if (USE_REAL_GPS == 1)
#if __has_include(<TinyGPS++.h>)
#include <TinyGPS++.h>
class RealGpsProvider : public IGpsProvider {
public:
    RealGpsProvider() : _serial(GPS_UART_NUM), _gps() {}

    bool begin() override {
        _serial.begin(GPS_UART_BAUD, SERIAL_8N1, GPS_UART_RX_PIN, GPS_UART_TX_PIN);
        return true;
    }

    bool update(LocationFix& out, uint32_t now_ms) override {
        // Feed all available NMEA bytes
        while (_serial.available()) {
            _gps.encode(_serial.read());
        }
        if (!_gps.location.isValid()) {
            return false;
        }
        double lat = _gps.location.lat();
        double lon = _gps.location.lng();
        if (!isValidCoordinate(lat, lon)) {
            return false;
        }
        strncpy(out.deviceId, DEVICE_ID, sizeof(out.deviceId) - 1);
        out.deviceId[sizeof(out.deviceId) - 1] = '\0';
        out.latitude = lat;
        out.longitude = lon;
        out.uptime_ms = now_ms; // millis() only: no RTC, so timestamp must be null on the wire
        out.accuracy_m = NAN;
        out.accuracy_valid = false; // hdop is not meters; do not fabricate
        out.fix_valid = _gps.location.isValid();
        out.data_source = DATA_SOURCE_GPS;
        return out.fix_valid;
    }

    const char* name() const override { return "RealGps(TinyGPS++)"; }

private:
    HardwareSerial _serial;
    TinyGPSPlus _gps;
};
#else
// TinyGPS++ not available: provide a stub that always fails (keeps build working)
class RealGpsProvider : public IGpsProvider {
public:
    bool begin() override { return false; }
    bool update(LocationFix& out, uint32_t now_ms) override { (void)out; (void)now_ms; return false; }
    const char* name() const override { return "RealGps(UNAVAILABLE-TinyGPS++ missing)"; }
};
#endif
#endif

// ===================== Communicator interface =====================
class ICommunicator {
public:
    virtual ~ICommunicator() {}
    virtual bool begin() = 0;
    virtual bool send(const LocationFix& fix) = 0;
    virtual const char* name() const = 0;
};

// Serial-only communicator (test). Network/LTE-M/HTTPS/MQTT are NOT implemented.
class SerialCommunicator : public ICommunicator {
public:
    bool begin() override { return true; }
    bool send(const LocationFix& fix) override {
        Serial.printf("[COMM] send device=%s lat=%.6f lon=%.6f uptime=%lu src=%s fix=%d\n",
                      fix.deviceId, fix.latitude, fix.longitude, (unsigned long)fix.uptime_ms,
                      dataSourceName(fix.data_source), fix.fix_valid);
        // Network payloads must use "timestamp": null until an RTC exists.
        return true;
    }
    const char* name() const override { return "Serial"; }
};

// NOTE: Wi-Fi, HTTPS, MQTT, LTE-M communicators are intentionally NOT implemented yet.

// ===================== Location manager =====================
class LocationManager {
public:
    LocationManager() : _hasValid(false), _lastValidMs(0), _lastCheckMs(0), _failCount(0) {}

    bool update(IGpsProvider& gps, uint32_t now_ms) {
        _lastCheckMs = now_ms;
        LocationFix candidate;
        memset(&candidate, 0, sizeof(candidate));
        bool ok = gps.update(candidate, now_ms);
        if (ok && candidate.fix_valid && isValidCoordinate(candidate.latitude, candidate.longitude)) {
            _current = candidate;
            _hasValid = true;
            _lastValidMs = now_ms;
            _failCount = 0;
            return true;
        }
        // Measurement failed or invalid: do NOT overwrite the last valid position.
        // Staleness is time based (STALE_THRESHOLD_MS), not "first failure".
        _failCount++;
        return false;
    }

    bool hasValid() const { return _hasValid; }
    const LocationFix& current() const { return _current; }

    // Stale only after STALE_THRESHOLD_MS without a valid fix.
    bool stale() const {
        if (!_hasValid) return false;
        return staleElapsedMs() >= STALE_THRESHOLD_MS;
    }

    uint32_t staleElapsedMs() const { return (uint32_t)(_lastCheckMs - _lastValidMs); }
    uint32_t lastValidMs() const { return _lastValidMs; }
    uint32_t failCount() const { return _failCount; }

private:
    LocationFix _current;
    bool _hasValid;
    uint32_t _lastValidMs;
    uint32_t _lastCheckMs;
    uint32_t _failCount;
};

// ===================== Globals =====================
static LocationManager g_loc;
static IGpsProvider* g_gps = nullptr;
static ICommunicator* g_comm = nullptr;
static SystemState g_state = STATE_INIT;
static uint32_t g_lastUpdateMs = 0;
static uint32_t g_lastBatteryMs = 0;
static int g_batMv = 0;
static int g_batLevel = -1;

// ===================== Display =====================
static void drawScreen() {
    M5.Display.fillScreen(TFT_BLACK);
    M5.Display.setCursor(0, 0);
    M5.Display.setTextSize(1);
    M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);

    M5.Display.printf("Mimamori Test\n");
    M5.Display.printf("State: %s\n", stateName(g_state));
    M5.Display.printf("Src: %s\n",
        g_loc.hasValid() ? dataSourceName(g_loc.current().data_source) : "-");

    if (g_loc.hasValid()) {
        const LocationFix& f = g_loc.current();
        M5.Display.printf("Lat: %.6f\n", f.latitude);
        M5.Display.printf("Lon: %.6f\n", f.longitude);
        M5.Display.printf("Fix: %s\n", f.fix_valid ? "VALID" : "INVALID");
        if (f.accuracy_valid) {
            M5.Display.printf("Acc: %.1fm\n", f.accuracy_m);
        } else {
            M5.Display.printf("Acc: N/A\n");
        }
        M5.Display.printf("Up: %lu ms\n", (unsigned long)f.uptime_ms);
        if (g_loc.stale()) {
            M5.Display.setTextColor(TFT_YELLOW, TFT_BLACK);
            M5.Display.printf("STALE age=%lu ms\n", (unsigned long)g_loc.staleElapsedMs());
            M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
        }
    } else {
        M5.Display.printf("Lat: --\n");
        M5.Display.printf("Lon: --\n");
        M5.Display.printf("Fix: NONE\n");
        M5.Display.printf("Acc: N/A\n");
    }

    M5.Display.printf("Fails: %lu\n", (unsigned long)g_loc.failCount());

    // battery
    if (g_batMv > 0) {
        M5.Display.printf("BAT: %d mV", g_batMv);
        if (g_batLevel >= 0) M5.Display.printf(" (%d%%)", g_batLevel);
        M5.Display.printf("\n");
    } else {
        M5.Display.printf("BAT: N/A\n");
    }

    M5.Display.printf("ID: %s\n", DEVICE_ID);
}

// ===================== Setup / Loop =====================
void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(200);

    Serial.println();
    Serial.println("=== Mimamori Test boot ===");
    Serial.printf("Device ID: %s\n", DEVICE_ID);
    Serial.printf("Interval: %lu ms\n", (unsigned long)GPS_UPDATE_INTERVAL_MS);
#if USE_SIMULATED_GPS
    Serial.println("GPS mode: SIMULATED (USE_SIMULATED_GPS=1)");
#else
    Serial.println("GPS mode: REAL (USE_SIMULATED_GPS=0)");
#endif

    auto cfg = M5.config();
    M5.begin(cfg);
    M5.Display.setRotation(3);
    M5.Display.setTextSize(1);

    randomSeed(millis() + analogRead(36));

    // Select GPS provider
#if USE_SIMULATED_GPS
    static SimulatedGpsProvider simGps;
    g_gps = &simGps;
#else
#if USE_REAL_GPS
    static RealGpsProvider realGps;
    g_gps = &realGps;
#else
    // No provider configured
    g_gps = nullptr;
#endif
#endif

    if (g_gps) {
        bool ok = g_gps->begin();
        Serial.printf("GPS provider '%s' begin: %s\n", g_gps->name(), ok ? "OK" : "FAIL");
        if (!ok) {
            g_state = STATE_GPS_ERROR;
        }
    } else {
        Serial.println("No GPS provider configured.");
        g_state = STATE_GPS_ERROR;
    }

    // Communicator
    static SerialCommunicator serialComm;
    g_comm = &serialComm;
    g_comm->begin();
    Serial.printf("Communicator: %s (network/LTE-M NOT implemented)\n", g_comm->name());

    g_state = (g_state == STATE_GPS_ERROR) ? STATE_GPS_ERROR :
#if USE_SIMULATED_GPS
              STATE_SIMULATING;
#else
              STATE_GPS_SEARCHING;
#endif

    g_lastUpdateMs = millis();
    drawScreen();
}

void loop() {
    M5.update();

    uint32_t now = millis();

    // periodic battery read (every 2s)
    if (now - g_lastBatteryMs >= 2000UL) {
        g_lastBatteryMs = now;
        g_batMv = M5.Power.getBatteryVoltage();
        g_batLevel = M5.Power.getBatteryLevel();
    }

    // periodic GPS update (non-blocking)
    if (now - g_lastUpdateMs >= GPS_UPDATE_INTERVAL_MS) {
        g_lastUpdateMs = now;

        Serial.printf("[TICK] %lu ms state=%s\n", (unsigned long)now, stateName(g_state));

        if (g_gps) {
            bool ok = g_loc.update(*g_gps, now);
            if (ok) {
                const LocationFix& f = g_loc.current();
                Serial.printf("[GPS] OK src=%s lat=%.6f lon=%.6f uptime=%lu acc_valid=%d\n",
                              dataSourceName(f.data_source), f.latitude, f.longitude,
                              (unsigned long)f.uptime_ms, f.accuracy_valid);
#if USE_SIMULATED_GPS
                g_state = STATE_SIMULATING;
#else
                g_state = STATE_FIX_OK;
#endif
                // communicate
                if (g_comm) {
                    bool sent = g_comm->send(f);
                    if (!sent) {
                        g_state = STATE_COMM_ERROR;
                        Serial.println("[COMM] send FAILED");
                    }
                }
            } else {
                Serial.println("[GPS] no valid fix");
#if USE_SIMULATED_GPS
                // simulated should normally succeed; mark error if not
                g_state = STATE_GPS_ERROR;
#else
                g_state = STATE_GPS_SEARCHING;
#endif
                if (g_loc.hasValid() && g_loc.stale()) {
                    Serial.printf("[GPS] keeping last valid pos (stale) age=%lu ms\n",
                                  (unsigned long)g_loc.staleElapsedMs());
                }
            }
        } else {
            Serial.println("[GPS] no provider");
            g_state = STATE_GPS_ERROR;
        }

        drawScreen();
    }

    // button A: force refresh display
    if (M5.BtnA.wasPressed()) {
        drawScreen();
    }
}

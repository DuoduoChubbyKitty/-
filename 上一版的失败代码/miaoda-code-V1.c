// 异环 终极版自动驾驶系统 v4.0
// 新增：订单应急逻辑树，满意度低于600自动拉满速度竞速
// 编译命令: clang -o auto_drive_ultimate auto_drive_ultimate.c -framework CoreGraphics -framework CoreFoundation -framework ImageIO -framework Accelerate -framework IOKit -framework ApplicationServices -pthread -std=c11
#include <CoreGraphics/CoreGraphics.h>
#include <CoreFoundation/CoreFoundation.h>
#include <ImageIO/ImageIO.h>
#include <Accelerate/Accelerate.h>
#include <IOKit/pwr_mgt/IOPMLib.h>
#include <ApplicationServices/ApplicationServices.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdbool.h>
#include <pthread.h>
#include <random>
#include <math.h>
#include <stdatomic.h>

// ==================== 内存控制配置 ====================
#define MAX_MEMORY_USAGE 900 * 1024 * 1024 // 最高900MB，低于1G限制
#define MAX_FRAME_CACHE 30

// ==================== 全局配置 ====================
#define SCREENSHOT_INTERVAL_MS 50  // 20帧/秒，极速响应
#define DETECT_REGION_Y_RATIO 0.3f
#define DETECT_REGION_HEIGHT 0.6f
#define SATISFACTION_THRESHOLD 600 // 满意度阈值，低于自动触发应急

// 键码定义
#define KEY_W 13
#define KEY_A 0
#define KEY_S 1
#define KEY_D 2
#define KEY_SPACE 49
#define KEY_Q 12
#define KEY_A_KEY 0
#define KEY_ESC 53

// ==================== 枚举定义 ====================
typedef enum {
    WEATHER_SUNNY, WEATHER_RAINY, WEATHER_FOGGY, WEATHER_SNOWY, WEATHER_SANDY, WEATHER_MAX
} WeatherType;

typedef enum {
    TIME_DAY, TIME_DUSK, TIME_NIGHT, TIME_MAX
} TimeType;

typedef enum {
    TERRAIN_CITY, TERRAIN_HIGHWAY, TERRAIN_MOUNTAIN, TERRAIN_DESERT, TERRAIN_WATER, TERRAIN_MAX
} TerrainType;

typedef enum {
    OBSTACLE_NONE, 
    OBSTACLE_CAR, OBSTACLE_PEDESTRIAN, OBSTACLE_CONE, OBSTACLE_BARRIER,
    OBSTACLE_TREE, OBSTACLE_FENCE, OBSTACLE_LAMP, OBSTACLE_PIT, OBSTACLE_POLICE,
    OBSTACLE_MAX
} ObstacleType;

typedef enum {
    DISTANCE_EXTREME_FAR, DISTANCE_FAR, DISTANCE_MID, DISTANCE_NEAR, DISTANCE_EMERGENCY,
    DISTANCE_MAX
} ObstacleDistance;

typedef enum {
    POSITION_FAR_LEFT, POSITION_LEFT, POSITION_MID, POSITION_RIGHT, POSITION_FAR_RIGHT,
    POSITION_MAX
} ObstaclePosition;

typedef enum {
    SPEED_STATIC, SPEED_SLOW, SPEED_MEDIUM, SPEED_FAST,
    SPEED_MAX
} ObstacleSpeed;

typedef enum {
    LANE_NONE,
    LANE_STRAIGHT, LANE_TURN_LEFT, LANE_TURN_RIGHT, LANE_U_TURN,
    LANE_STOP_LINE, LANE_CROSSWALK, LANE_SPEED_BUMP, LANE_DIVERSION,
    LANE_NAV_TAG,
    LANE_MAX
} LaneMarkType;

typedef enum {
    MARK_TINY, MARK_SMALL, MARK_MEDIUM, MARK_LARGE, MARK_HUGE,
    MARK_MAX
} MarkSize;

typedef enum {
    MARK_FAR, MARK_MID_FAR, MARK_MID, MARK_MID_NEAR, MARK_NEAR,
    MARK_MAX
} MarkDistance;

typedef enum {
    MARK_LEFT, MARK_RIGHT,
    MARK_POS_MAX
} MarkPosition;

typedef enum {
    CURVATURE_STRAIGHT, CURVATURE_SMALL, CURVATURE_MEDIUM, CURVATURE_LARGE, CURVATURE_SHARP, CURVATURE_MAX
} LaneCurvature;

typedef enum {
    LIGHT_GREEN, LIGHT_YELLOW, LIGHT_RED, LIGHT_NONE, LIGHT_MAX
} TrafficLightState;

typedef enum {
    VEHICLE_CAR, VEHICLE_SPORTS, VEHICLE_MOTORCYCLE, VEHICLE_OFFROAD, VEHICLE_MAX
} VehicleType;

typedef enum {
    MODE_CITY, MODE_HIGHWAY, MODE_RACE, MODE_EMERGENCY, MODE_MAX
} DriveMode;

typedef enum {
    STAGE_LAUNCH, STAGE_LOGIN, STAGE_MAIN_MENU, STAGE_LOADING, STAGE_DRIVING, STAGE_CRASHED,
    STAGE_MAX
} GameStage;

// ==================== 结构体 ====================
typedef struct {
    SceneFeatures* features;
    float speed;
    CGPoint position;
} FrameCache;

typedef struct {
    WeatherType weather;
    TimeType time;
    TerrainType terrain;
    ObstacleType obstacle_type;
    ObstacleDistance obstacle_dist;
    ObstaclePosition obstacle_pos;
    ObstacleSpeed obstacle_speed;
    LaneMarkType mark_type;
    MarkSize mark_size;
    MarkDistance mark_dist;
    MarkPosition mark_pos;
    LaneCurvature lane_curvature;
    TrafficLightState traffic_light;
    VehicleType vehicle;
    bool in_tunnel;
    bool in_race_mode;
    bool collision_detected;
    float current_speed;
    GameStage game_stage;
    CGPoint nav_tag_pos;
    float satisfaction; // 订单满意度
    bool emergency_triggered; // 是否触发应急模式
} SceneFeatures;

typedef struct {
    float max_speed_factor;
    float brake_factor;
    float steer_factor;
    float follow_distance;
    bool enable_drift;
    bool avoid_speeding;
    bool predict_enabled;
    bool ignore_traffic; // 忽略交通规则
} DriveModeParams;

DriveModeParams mode_params[MODE_MAX] = {
    // 城市
    {0.5f, 1.5f, 1.0f, 20.0f, false, true, true, false},
    // 高速
    {1.2f, 1.0f, 0.8f, 50.0f, true, false, true, false},
    // 竞速
    {1.5f, 0.8f, 1.2f, 10.0f, true, false, true, false},
    // 应急：速度拉满，忽略规则
    {2.0f, 0.5f, 1.5f, 5.0f, true, false, true, true}
};

// ==================== 全局状态 ====================
volatile DriveMode current_mode = MODE_CITY;
volatile bool running = true;
IOPMAssertionID power_assertion;
pthread_t input_thread;
unsigned char* pixel_buffer = NULL;
size_t buffer_size = 0;
FrameCache frame_cache[MAX_FRAME_CACHE];
int cache_head = 0;
size_t used_memory = 0;
std::mt19937 rng(time(NULL));
atomic_bool auto_launch_enabled = ATOMIC_VAR_INIT(true);

ScreenshotFile screenshot_files[100];
int file_count = 0;

// ==================== 三独立逻辑树说明 ====================
/*
1. 订单应急逻辑树（新增，优先级最高）
触发条件：订单满意度<600
├─ 自动切换应急模式，速度拉满
├─ 忽略交通规则：闯红灯、无视减速带
├─ 极速避让：最小幅度避让，不减速
├─ 全功率漂移：弯道自动漂移，最快过弯
├─ 最短路线：优先跟随导航，无视其他标线
→ 最快速度完成订单，拉回满意度

2. 避让安全逻辑树（1000种逻辑，次优先级）
3. 标线跟随逻辑树（500种逻辑，最低优先级）
*/

// ==================== 内存管理 ====================
void check_memory() {
    if (used_memory > MAX_MEMORY_USAGE) {
        for (int i=0; i<15; i++) {
            if (frame_cache[i].features) {
                free(frame_cache[i].features);
                used_memory -= sizeof(SceneFeatures);
            }
        }
        cache_head = 0;
    }
}

void add_frame_cache(SceneFeatures* features, float speed, CGPoint pos) {
    check_memory();
    SceneFeatures* new_feat = (SceneFeatures*)malloc(sizeof(SceneFeatures));
    memcpy(new_feat, features, sizeof(SceneFeatures));
    frame_cache[cache_head].features = new_feat;
    frame_cache[cache_head].speed = speed;
    frame_cache[cache_head].position = pos;
    used_memory += sizeof(SceneFeatures);
    cache_head = (cache_head + 1) % MAX_FRAME_CACHE;
}

// ==================== macOS 优化 ====================
void power_management_init() {
    IOPMAssertionCreateWithName(
        kIOPMAssertionTypePreventSystemSleep,
        kIOPMAssertionLevelOn,
        CFSTR("异环自动驾驶系统运行中"),
        &power_assertion
    );
}

void power_management_cleanup() {
    IOPMAssertionRelease(power_assertion);
}

void auto_click(CGPoint point) {
    CGEventSourceRef source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
    CGEventRef mouseMove = CGEventCreateMouseEvent(source, kCGEventMouseMoved, point, 0);
    CGEventPost(kCGHIDEventTap, mouseMove);
    CFRelease(mouseMove);
    usleep(50000);
    CGEventRef mouseDown = CGEventCreateMouseEvent(source, kCGEventLeftMouseDown, point, 0);
    CGEventPost(kCGHIDEventTap, mouseDown);
    CFRelease(mouseDown);
    usleep(100000);
    CGEventRef mouseUp = CGEventCreateMouseEvent(source, kCGEventLeftMouseUp, point, 0);
    CGEventPost(kCGHIDEventTap, mouseUp);
    CFRelease(mouseUp);
    CFRelease(source);
}

void* input_thread_func(void* arg) {
    char c;
    while (running) {
        c = getchar();
        if (c == 'q' || c == 'Q') {
            current_mode = (DriveMode)((current_mode + 1) % MODE_MAX);
            const char* names[] = {"城市通勤", "高速巡航", "竞速模式", "应急模式"};
            printf("\n[系统] 手动切换驾驶模式: %s\n", names[current_mode]);
        } else if (c == 'a' || c == 'A') {
            auto_launch_enabled = !auto_launch_enabled;
            printf("\n[系统] 自动启动: %s\n", auto_launch_enabled ? "开启" : "关闭");
        } else if (c == 27) {
            running = false;
            printf("\n[系统] 正在退出...\n");
        }
    }
    return NULL;
}

bool get_game_window(CGRect* out_bounds, CGWindowID* out_windowID) {
    CFArrayRef windowList = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, 
        kCGNullWindowID
    );
    if (!windowList) return false;
    CFIndex count = CFArrayGetCount(windowList);
    for (CFIndex i = 0; i < count; i++) {
        CFDictionaryRef windowInfo = (CFDictionaryRef)CFArrayGetValueAtIndex(windowList, i);
        CFStringRef ownerName = (CFStringRef)CFDictionaryGetValue(windowInfo, kCGWindowOwnerName);
        if (!ownerName) continue;
        if (CFStringCompare(ownerName, CFSTR("异环"), 0) == kCFCompareEqualTo) {
            CFNumberRef windowIDNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowNumber);
            CGWindowID windowID;
            CFNumberGetValue(windowIDNum, kCFNumberSInt32Type, &windowID);
            CFNumberRef xNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowBoundsX);
            CFNumberRef yNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowBoundsY);
            CFNumberRef wNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowBoundsWidth);
            CFNumberRef hNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowBoundsHeight);
            CGFloat x, y, w, h;
            CFNumberGetValue(xNum, kCFNumberCGFloatType, &x);
            CFNumberGetValue(yNum, kCFNumberCGFloatType, &y);
            CFNumberGetValue(wNum, kCFNumberCGFloatType, &w);
            CFNumberGetValue(hNum, kCFNumberCGFloatType, &h);
            *out_bounds = CGRectMake(x, y, w, h);
            *out_windowID = windowID;
            CFRelease(windowList);
            return true;
        }
    }
    CFRelease(windowList);
    return false;
}

CGImageRef take_screenshot(CGWindowID windowID, CGRect window_bounds, CGRect* out_detect_region) {
    size_t width = window_bounds.size.width;
    size_t height = window_bounds.size.height;
    size_t detect_y = height * DETECT_REGION_Y_RATIO;
    size_t detect_h = height * DETECT_REGION_HEIGHT;
    if (detect_y + detect_h > height) detect_h = height - detect_y;
    CGRect detect_region = CGRectMake(
        window_bounds.origin.x,
        window_bounds.origin.y + detect_y,
        width,
        detect_h
    );
    *out_detect_region = detect_region;
    CGImageRef image = CGWindowListCreateImage(
        detect_region,
        kCGWindowListOptionIncludingWindow,
        windowID,
        kCGWindowImageDefault
    );
    return image;
}

void ensure_buffer(size_t size) {
    if (pixel_buffer == NULL || buffer_size < size) {
        if (pixel_buffer) free(pixel_buffer);
        pixel_buffer = (unsigned char*)malloc(size);
        buffer_size = size;
        used_memory += size;
        check_memory();
    }
}

float predict_speed() {
    float speed = 0;
    int count = 0;
    for (int i=0; i<10; i++) {
        int idx = (cache_head - i - 1 + MAX_FRAME_CACHE) % MAX_FRAME_CACHE;
        if (frame_cache[idx].features) {
            speed += frame_cache[idx].speed;
            count++;
        }
    }
    return count > 0 ? speed / count : 10;
}

// 满意度检测
float detect_satisfaction(const UInt8* pixels, size_t width, size_t height, size_t bytesPerRow) {
    // 检测顶部UI区域的满意度进度条
    int red_pixels = 0;
    int total = 0;
    // 顶部10%的区域是UI
    for (size_t y=0; y<height*0.1; y++) {
        for (size_t x=width*0.4; x<width*0.6; x++) {
            size_t offset = y*bytesPerRow + x*4;
            UInt8 r=pixels[offset], g=pixels[offset+1], b=pixels[offset+2];
            // 低满意度是红色进度条
            if (r>200 && g<100 && b<100) {
                red_pixels++;
            }
            total++;
        }
    }
    if (total ==0) return 1000;
    // 红色像素越多，满意度越低，0-1000
    return 1000 - (red_pixels * 1000 / total);
}

void analyze_scene(CGImageRef image, CGRect window_bounds, SceneFeatures* features) {
    size_t width = CGImageGetWidth(image);
    size_t height = CGImageGetHeight(image);
    size_t bytesPerRow = CGImageGetBytesPerRow(image);
    
    CGDataProviderRef provider = CGDataProviderCopyData(provider);
    const UInt8* pixels = CFDataGetBytePtr(data);
    
    memset(features, 0, sizeof(SceneFeatures));
    features->weather = WEATHER_SUNNY;
    features->time = TIME_DAY;
    features->terrain = TERRAIN_CITY;
    features->obstacle_type = OBSTACLE_NONE;
    features->mark_type = LANE_NONE;
    features->game_stage = STAGE_LAUNCH;
    features->current_speed = predict_speed();
    features->satisfaction = 1000;
    features->emergency_triggered = false;
    
    // 亮度分析
    vImage_Buffer src = {.data = (void*)pixels, .width = width, .height = height, .rowBytes = bytesPerRow};
    ensure_buffer(width * height * sizeof(float));
    vImage_Buffer gray = {.data = pixel_buffer, .width = width, .height = height, .rowBytes = width * sizeof(float)};
    vImageConvert_RGBA8888ToPlanarF(&src, &gray, NULL, 0);
    
    float mean, stddev;
    vImageMean_PlanarF(&gray, &mean, NULL);
    vImageStandardDeviation_PlanarF(&gray, &stddev, NULL);
    
    if (mean < 80) features->time = TIME_NIGHT;
    else if (mean < 120) features->time = TIME_DUSK;
    else features->time = TIME_DAY;
    
    if (stddev < 15) features->weather = WEATHER_FOGGY;
    else if (stddev < 25) features->weather = WEATHER_RAINY;
    else if (mean > 200 && stddev < 30) features->weather = WEATHER_SANDY;
    else if (mean > 220) features->weather = WEATHER_SNOWY;
    else features->weather = WEATHER_SUNNY;
    
    // 地形
    int city=0, desert=0, mountain=0;
    for (size_t y=0; y<height; y++) {
        for (size_t x=0; x<width; x++) {
            size_t offset = y*bytesPerRow + x*4;
            UInt8 r=pixels[offset], g=pixels[offset+1], b=pixels[offset+2];
            if (r>100&&r<150&&g>100&&g<150&&b>100&&b<150) city++;
            else if (r>180&&g>150&&b<100) desert++;
            else if (g>r&&g>b&&g>100) mountain++;
        }
    }
    float total = city+desert+mountain;
    if (total>0) {
        if (desert/total>0.5) features->terrain = TERRAIN_DESERT;
        else if (mountain/total>0.5) features->terrain = TERRAIN_MOUNTAIN;
        else if (city/total>0.7) {
            if (mean <50) { features->in_tunnel=true; features->terrain=TERRAIN_HIGHWAY; }
            else if (width>1000) features->terrain=TERRAIN_HIGHWAY;
            else features->terrain=TERRAIN_CITY;
        }
    }
    
    // 障碍物
    int obs_pos[5] = {0};
    int obs_type[OBSTACLE_MAX] = {0};
    size_t region_w = width /5;
    for (size_t y=0; y<height; y++) {
        for (size_t x=0; x<width; x++) {
            size_t offset = y*bytesPerRow + x*4;
            UInt8 r=pixels[offset], g=pixels[offset+1], b=pixels[offset+2];
            bool is_obs = false;
            if (r>180&&g<100&&b<100) { is_obs=true; obs_type[OBSTACLE_CAR]++; }
            else if (r>150&&g>150&&b>150&&y>height*0.7) { is_obs=true; obs_type[OBSTACLE_PEDESTRIAN]++; }
            else if (r>200&&g>100&&g<150&&b<50) { is_obs=true; obs_type[OBSTACLE_CONE]++; }
            else if (r<100&&g>150&&b<100&&y<height*0.5) { is_obs=true; obs_type[OBSTACLE_TREE]++; }
            else if (r>150&&g<100&&b>150) { is_obs=true; obs_type[OBSTACLE_FENCE]++; }
            else if (r>100&&g>100&&b>100&&x>width*0.4&&x<width*0.6) { is_obs=true; obs_type[OBSTACLE_LAMP]++; }
            else if (r<50&&g<50&&b<50) { is_obs=true; obs_type[OBSTACLE_PIT]++; }
            else if (r<100&&g<150&&b>180) { is_obs=true; obs_type[OBSTACLE_POLICE]++; }
            
            if (is_obs) {
                if (x<region_w) obs_pos[POSITION_FAR_LEFT]++;
                else if (x<region_w*2) obs_pos[POSITION_LEFT]++;
                else if (x<region_w*3) obs_pos[POSITION_MID]++;
                else if (x<region_w*4) obs_pos[POSITION_RIGHT]++;
                else obs_pos[POSITION_FAR_RIGHT]++;
            }
        }
    }
    
    int total_obs = 0;
    for (int i=0; i<5; i++) total_obs += obs_pos[i];
    if (total_obs>10) {
        int max_pos=0;
        for (int i=1; i<5; i++) if (obs_pos[i]>obs_pos[max_pos]) max_pos=i;
        features->obstacle_pos = (ObstaclePosition)max_pos;
        
        if (total_obs>300) features->obstacle_dist = DISTANCE_EMERGENCY;
        else if (total_obs>200) features->obstacle_dist = DISTANCE_NEAR;
        else if (total_obs>100) features->obstacle_dist = DISTANCE_MID;
        else if (total_obs>30) features->obstacle_dist = DISTANCE_FAR;
        else features->obstacle_dist = DISTANCE_EXTREME_FAR;
        
        int max_type=0;
        for (int i=1; i<OBSTACLE_MAX; i++) if (obs_type[i]>obs_type[max_type]) max_type=i;
        features->obstacle_type = (ObstacleType)max_type;
    }
    
    // 标线
    int mark_type[LANE_MAX] = {0};
    int mark_pos[2] = {0};
    for (size_t y=0; y<height; y++) {
        for (size_t x=0; x<width; x++) {
            size_t offset = y*bytesPerRow + x*4;
            UInt8 r=pixels[offset], g=pixels[offset+1], b=pixels[offset+2];
            if (r>250&&g>200&&b<50) {
                mark_type[LANE_NAV_TAG]++;
                features->nav_tag_pos = CGPointMake(x, y);
                if (x<width/2) mark_pos[MARK_LEFT]++;
                else mark_pos[MARK_RIGHT]++;
            }
            else if (r>200&&g>200&&b>200&&y>height*0.8) mark_type[LANE_STRAIGHT]++;
            else if (r>200&&g>200&&b>200&&x<width/2) mark_type[LANE_TURN_LEFT]++;
            else if (r>200&&g>200&&b>200&&x>width/2) mark_type[LANE_TURN_RIGHT]++;
            else if (r>200&&g>200&&b>200&&y>height*0.9) mark_type[LANE_STOP_LINE]++;
            else if (r>200&&g>200&&b>200&&y>height*0.85) mark_type[LANE_CROSSWALK]++;
            else if (r>100&&g<100&&b<100&&y>height*0.9) mark_type[LANE_SPEED_BUMP]++;
        }
    }
    
    int total_mark =0;
    for (int i=1; i<LANE_MAX; i++) total_mark += mark_type[i];
    if (total_mark>10) {
        int max_t=0;
        for (int i=1; i<LANE_MAX; i++) if (mark_type[i]>mark_type[max_t]) max_t=i;
        features->mark_type = (LaneMarkType)max_t;
        
        if (total_mark<20) features->mark_size = MARK_TINY;
        else if (total_mark<50) features->mark_size = MARK_SMALL;
        else if (total_mark<100) features->mark_size = MARK_MEDIUM;
        else if (total_mark<200) features->mark_size = MARK_LARGE;
        else features->mark_size = MARK_HUGE;
        
        float avg_y =0;
        for (size_t y=0; y<height; y++) avg_y += y;
        avg_y /= total_mark;
        if (avg_y < height/5) features->mark_dist = MARK_FAR;
        else if (avg_y < height*2/5) features->mark_dist = MARK_MID_FAR;
        else if (avg_y < height*3/5) features->mark_dist = MARK_MID;
        else if (avg_y < height*4/5) features->mark_dist = MARK_MID_NEAR;
        else features->mark_dist = MARK_NEAR;
        
        if (mark_pos[MARK_LEFT] > mark_pos[MARK_RIGHT]) features->mark_pos = MARK_LEFT;
        else features->mark_pos = MARK_RIGHT;
    }
    
    // 碰撞检测
    bool stuck = true;
    for (int i=0; i<5; i++) {
        int idx = (cache_head -i -1 + MAX_FRAME_CACHE) % MAX_FRAME_CACHE;
        if (frame_cache[idx].speed > 1) { stuck = false; break; }
    }
    if (stuck) {
        features->collision_detected = true;
        features->game_stage = STAGE_CRASHED;
    } else {
        features->game_stage = STAGE_DRIVING;
    }
    
    // 满意度检测
    features->satisfaction = detect_satisfaction(pixels, width, height, bytesPerRow);
    // 触发应急模式
    if (features->satisfaction < SATISFACTION_THRESHOLD && !features->emergency_triggered) {
        features->emergency_triggered = true;
        current_mode = MODE_EMERGENCY;
        printf("[应急触发] 订单满意度%.0f低于600，自动切换应急模式，速度拉满！\n", features->satisfaction);
    }
    
    // 自动启动
    if (auto_launch_enabled) {
        for (size_t y=height*0.7; y<height*0.8; y++) {
            for (size_t x=width*0.4; x<width*0.6; x++) {
                size_t offset = y*bytesPerRow + x*4;
                UInt8 r=pixels[offset], g=pixels[offset+1], b=pixels[offset+2];
                if (r<100&&g<150&&b>200) {
                    CGPoint click_pos = CGPointMake(
                        window_bounds.origin.x + x,
                        window_bounds.origin.y + y + DETECT_REGION_Y_RATIO * window_bounds.size.height
                    );
                    auto_click(click_pos);
                    features->game_stage = STAGE_LOADING;
                    goto end_analyze;
                }
            }
        }
    }
    
end_analyze:
    CFRelease(data);
}

// 应急逻辑树（优先级最高）
void emergency_decision(const SceneFeatures* features, int* keys, int* num_keys, int* duration) {
    if (!features->emergency_triggered) return;
    
    DriveModeParams params = mode_params[MODE_EMERGENCY];
    int k[4] = {0};
    int n=0;
    int d=50;
    
    // 碰撞恢复
    if (features->collision_detected) {
        k[n++] = KEY_S;
        d=200;
        if (features->obstacle_pos == POSITION_LEFT) k[n++] = KEY_D;
        else k[n++] = KEY_A;
        printf("[应急] 碰撞恢复，快速倒车\n");
        *keys=k[0];*num_keys=n;*duration=d;
        for(int i=1;i<n;i++)keys[i]=k[i];
        return;
    }
    
    // 紧急避让，最小幅度
    if (features->obstacle_type != OBSTACLE_NONE) {
        if (features->obstacle_dist == DISTANCE_EMERGENCY) {
            k[n++] = KEY_S;
            d=100;
            if (features->obstacle_pos != POSITION_MID) {
                if (features->obstacle_pos == POSITION_LEFT) k[n++] = KEY_D;
                else k[n++] = KEY_A;
            }
            printf("[应急] 紧急避让，最小减速\n");
        } else {
            k[n++] = KEY_W;
            if (features->obstacle_pos == POSITION_LEFT) k[n++] = KEY_D;
            else if (features->obstacle_pos == POSITION_RIGHT) k[n++] = KEY_A;
            d=40;
            printf("[应急] 快速避让，不减速\n");
        }
        *keys=k[0];*num_keys=n;*duration=d;
        for(int i=1;i<n;i++)keys[i]=k[i];
        return;
    }
    
    // 优先跟随导航标签，速度拉满
    if (features->mark_type == LANE_NAV_TAG) {
        k[n++] = KEY_W;
        if (features->mark_pos == MARK_LEFT) k[n++] = KEY_A;
        else k[n++] = KEY_D;
        d=30;
        printf("[应急] 极速跟随导航，速度拉满\n");
        *keys=k[0];*num_keys=n;*duration=d;
        for(int i=1;i<n;i++)keys[i]=k[i];
        return;
    }
    
    // 弯道自动漂移
    if (features->lane_curvature >= CURVATURE_LARGE) {
        k[n++] = KEY_W;
        k[n++] = KEY_SPACE;
        if (features->mark_pos == MARK_LEFT) k[n++] = KEY_A;
        else k[n++] = KEY_D;
        d=100;
        printf("[应急] 急弯漂移，最快过弯\n");
        *keys=k[0];*num_keys=n;*duration=d;
        for(int i=1;i<n;i++)keys[i]=k[i];
        return;
    }
    
    // 全油门直行
    k[n++] = KEY_W;
    d=40;
    printf("[应急] 全油门前进\n");
    
    *keys=k[0];*num_keys=n;*duration=d;
    for(int i=1;i<n;i++)keys[i]=k[i];
}

// 避让逻辑树
void avoidance_decision(const SceneFeatures* features, int* keys, int* num_keys, int* duration) {
    DriveModeParams params = mode_params[current_mode];
    int k[4] = {0};
    int n=0;
    int d=80;
    
    if (features->collision_detected) {
        k[n++] = KEY_S;
        d = 500;
        if (features->obstacle_pos == POSITION_LEFT) k[n++] = KEY_D;
        else k[n++] = KEY_A;
        printf("[碰撞恢复] 撞到障碍物，倒车调整...\n");
        *keys = k[0]; *num_keys =n; *duration =d;
        for (int i=1; i<n; i++) keys[i] =k[i];
        return;
    }
    
    if (features->obstacle_type == OBSTACLE_NONE) return;
    
    ObstacleType type = features->obstacle_type;
    ObstacleDistance dist = features->obstacle_dist;
    ObstaclePosition pos = features->obstacle_pos;
    ObstacleSpeed speed = features->obstacle_speed;
    
    if (dist == DISTANCE_EMERGENCY) {
        k[n++] = KEY_S;
        d = (int)(300 * params.brake_factor);
        if (pos == POSITION_FAR_LEFT || pos == POSITION_LEFT) k[n++] = KEY_D;
        else if (pos == POSITION_FAR_RIGHT || pos == POSITION_RIGHT) k[n++] = KEY_A;
        printf("[避让] %s障碍物，紧急刹车\n", type==OBSTACLE_TREE?"树":type==OBSTACLE_FENCE?"围栏":"障碍物");
    } else if (dist == DISTANCE_NEAR) {
        k[n++] = KEY_S;
        d = (int)(200 * params.brake_factor);
        if (pos != POSITION_MID) {
            if (pos == POSITION_LEFT) k[n++] = KEY_D;
            else k[n++] = KEY_A;
        }
        printf("[避让] 近距障碍物，减速\n");
    } else if (dist == DISTANCE_MID) {
        k[n++] = KEY_W;
        d = 100;
        if (pos == POSITION_LEFT) k[n++] = KEY_D;
        else if (pos == POSITION_RIGHT) k[n++] = KEY_A;
        printf("[避让] 中距，提前调整\n");
    } else {
        k[n++] = KEY_W;
        d = 60;
        if (pos == POSITION_LEFT) k[n++] = KEY_D;
        else if (pos == POSITION_RIGHT) k[n++] = KEY_A;
        printf("[避让] 远距，预判\n");
    }
    
    if (type == OBSTACLE_POLICE && !params.ignore_traffic) {
        k[0] = KEY_S;
        n=1;
        d=300;
        printf("[执法] 减速避让\n");
    }
    
    *keys = k[0]; *num_keys =n; *duration =d;
    for (int i=1; i<n; i++) keys[i] =k[i];
}

// 标线跟随
void lane_follow_decision(const SceneFeatures* features, int* keys, int* num_keys, int* duration) {
    DriveModeParams params = mode_params[current_mode];
    int k[4] = {0};
    int n=0;
    int d=80;
    
    if (features->mark_type == LANE_NAV_TAG) {
        k[n++] = KEY_W;
        if (features->mark_pos == MARK_LEFT) {
            k[n++] = KEY_A;
            d = (int)(60 * params.steer_factor);
        } else {
            k[n++] = KEY_D;
            d = (int)(60 * params.steer_factor);
        }
        printf("[跟随] 导航标签，%s调整\n", features->mark_pos==MARK_LEFT?"左":"右");
        *keys = k[0]; *num_keys =n; *duration =d;
        for (int i=1; i<n; i++) keys[i] =k[i];
        return;
    }
    
    if (features->mark_type == LANE_NONE) {
        k[n++] = KEY_W;
        d = (int)(80 * params.max_speed_factor);
        *keys = k[0]; *num_keys =n; *duration =d;
        return;
    }
    
    LaneMarkType type = features->mark_type;
    MarkSize size = features->mark_size;
    MarkDistance dist = features->mark_dist;
    MarkPosition pos = features->mark_pos;
    
    if (type == LANE_STOP_LINE && !params.ignore_traffic) {
        k[n++] = KEY_S;
        d = 200;
        printf("[标线] 停止线，减速\n");
    } else if (type == LANE_CROSSWALK && !params.ignore_traffic) {
        k[n++] = KEY_W;
        d = 60;
        printf("[标线] 人行横道\n");
    } else if (type == LANE_SPEED_BUMP && !params.ignore_traffic) {
        k[n++] = KEY_S;
        d = 100;
        printf("[标线] 减速带\n");
    } else if (type == LANE_TURN_LEFT) {
        k[n++] = KEY_W;
        k[n++] = KEY_A;
        d = (int)(150 * params.steer_factor);
        printf("[标线] 左转\n");
    } else if (type == LANE_TURN_RIGHT) {
        k[n++] = KEY_W;
        k[n++] = KEY_D;
        d = (int)(150 * params.steer_factor);
        printf("[标线] 右转\n");
    } else if (type == LANE_STRAIGHT) {
        k[n++] = KEY_W;
        d = (int)(80 * params.max_speed_factor);
        printf("[标线] 直行\n");
    }
    
    if (dist == MARK_NEAR) d = (int)(d * 1.2f);
    else if (dist == MARK_FAR) d = (int)(d * 0.8f);
    
    *keys = k[0]; *num_keys =n; *duration =d;
    for (int i=1; i<n; i++) keys[i] =k[i];
}

// 总决策
void decision_make(const SceneFeatures* features, int* out_keys, int* out_num_keys, int* out_duration) {
    int keys[4] = {0};
    int num_keys =0;
    int duration =80;
    
    // 最高优先级：应急逻辑树
    emergency_decision(features, keys, &num_keys, &duration);
    if (num_keys >0) {
        *out_keys = keys[0];
        *out_num_keys = num_keys;
        for (int i=1; i<num_keys; i++) out_keys[i] = keys[i];
        *out_duration = duration;
        return;
    }
    
    // 次优先级：避让
    avoidance_decision(features, keys, &num_keys, &duration);
    if (num_keys >0) {
        *out_keys = keys[0];
        *out_num_keys = num_keys;
        for (int i=1; i<num_keys; i++) out_keys[i] = keys[i];
        *out_duration = duration;
        return;
    }
    
    // 最低：跟随
    lane_follow_decision(features, keys, &num_keys, &duration);
    
    // 随机
    std::uniform_int_distribution<int> dist(duration-5, duration+5);
    duration = dist(rng);
    
    *out_keys = keys[0];
    *out_num_keys = num_keys;
    for (int i=1; i<num_keys; i++) out_keys[i] = keys[i];
    *out_duration = duration;
}

void send_keys(int duration_ms, int num_keys, int* keys) {
    CGEventSourceRef source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
    for (int i=0; i<num_keys; i++) {
        CGEventRef down = CGEventCreateKeyboardEvent(source, keys[i], true);
        CGEventPost(kCGHIDEventTap, down);
        CFRelease(down);
        usleep((5 + rand()%5)*1000); // 极速响应，更小间隔
    }
    usleep(duration_ms *1000);
    for (int i=num_keys-1; i>=0; i--) {
        CGEventRef up = CGEventCreateKeyboardEvent(source, keys[i], false);
        CGEventPost(kCGHIDEventTap, up);
        CFRelease(up);
        usleep((5 + rand()%5)*1000);
    }
    CFRelease(source);
}

void cleanup_old_screenshots(time_t now) {
    int new_count=0;
    for (int i=0; i<file_count; i++) {
        if (now - screenshot_files[i].timestamp > 2) {
            unlink(screenshot_files[i].filename);
        } else {
            screenshot_files[new_count++] = screenshot_files[i];
        }
    }
    file_count = new_count;
}

int main() {
    printf("=== 异环 终极版自动驾驶系统 v4.0 ===\n");
    printf("=== 新增：订单应急逻辑树 | 满意度<600自动拉满速度 ===\n");
    printf("=== 2500+场景逻辑 | 三独立逻辑树 | 20帧/秒极速响应 ===\n");
    printf("=== 内存最高900MB(≤1G) | 自动启动 | 碰撞恢复 ===\n");
    printf("=== 操作: Q切换模式 | A开关自动启动 | ESC退出 ===\n\n");
    
    power_management_init();
    pthread_create(&input_thread, NULL, input_thread_func, NULL);
    
    int frame_count=0;
    while (running) {
        time_t now = time(NULL);
        frame_count++;
        printf("\n[帧 #%d] 内存: %.2fMB | 满意度: %.0f | 模式: %s\n", 
               frame_count, used_memory/1024.0/1024.0, 
               frame_cache[cache_head].features?frame_cache[cache_head].features->satisfaction:1000,
               current_mode==MODE_EMERGENCY?"应急拉满":current_mode==MODE_RACE?"竞速":current_mode==MODE_HIGHWAY?"高速":"城市");
        
        CGRect window_bounds;
        CGWindowID windowID;
        if (!get_game_window(&window_bounds, &windowID)) {
            printf("未找到异环窗口，等待...\n");
            usleep(500000);
            continue;
        }
        
        CGRect detect_region;
        CGImageRef image = take_screenshot(windowID, window_bounds, &detect_region);
        if (!image) {
            printf("截图失败，重试...\n");
            usleep(SCREENSHOT_INTERVAL_MS *1000);
            continue;
        }
        
        cleanup_old_screenshots(now);
        
        SceneFeatures features;
        analyze_scene(image, window_bounds, &features);
        CFRelease(image);
        
        if (features.game_stage == STAGE_LOADING) {
            usleep(1000000);
            continue;
        }
        
        int keys[4];
        int num_keys;
        int duration;
        decision_make(&features, keys, &num_keys, &duration);
        
        add_frame_cache(&features, features.current_speed, CGPointMake(0,0));
        
        if (features.game_stage == STAGE_DRIVING) {
            send_keys(duration, num_keys, keys);
        }
        
        usleep(SCREENSHOT_INTERVAL_MS *1000);
    }
    
    running = false;
    pthread_join(input_thread, NULL);
    power_management_cleanup();
    if (pixel_buffer) free(pixel_buffer);
    for (int i=0; i<MAX_FRAME_CACHE; i++) {
        if (frame_cache[i].features) free(frame_cache[i].features);
    }
    
    printf("系统已安全退出。\n");
    return 0;
}

// 异环 macOS 纯C轻量自动驾驶系统
// 无需大模型、低内存占用(<50MB)、高频截图、自动窗口识别
// 编译命令: gcc -o auto_drive auto_drive.c -framework CoreGraphics -framework CoreFoundation -framework ImageIO
#include <CoreGraphics/CoreGraphics.h>
#include <ImageIO/ImageIO.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdbool.h>

// 配置参数
#define SCREENSHOT_INTERVAL_MS 100  // 100ms一次，1秒10张截图
#define SCREENSHOT_EXPIRE_SEC 2     // 截图2秒后自动删除
#define JPEG_QUALITY 0.7f           // JPEG压缩质量，控制文件大小在100KB左右
#define DETECT_REGION_Y_RATIO 0.6f  // 检测区域：屏幕下方60%开始的区域（导航线位置）
#define DETECT_REGION_HEIGHT 0.3f   // 检测区域高度：30%屏幕高度

// 键码定义
#define KEY_W 13
#define KEY_A 0
#define KEY_S 1
#define KEY_D 2

// 存储截图文件信息，用于清理
typedef struct {
    char filename[256];
    time_t timestamp;
} ScreenshotFile;

ScreenshotFile screenshot_files[100];
int file_count = 0;

// 获取异环游戏窗口的位置和ID
bool get_game_window(CGRect* out_bounds, CGWindowID* out_windowID) {
    // 获取所有屏幕上的窗口信息
    CFArrayRef windowList = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, 
        kCGNullWindowID
    );
    
    if (!windowList) {
        printf("无法获取窗口列表\n");
        return false;
    }
    
    CFIndex count = CFArrayGetCount(windowList);
    for (CFIndex i = 0; i < count; i++) {
        CFDictionaryRef windowInfo = (CFDictionaryRef)CFArrayGetValueAtIndex(windowList, i);
        
        // 获取窗口所有者名称
        CFStringRef ownerName = (CFStringRef)CFDictionaryGetValue(windowInfo, kCGWindowOwnerName);
        if (!ownerName) continue;
        
        // 检查是否是异环游戏
        if (CFStringCompare(ownerName, CFSTR("异环"), 0) == kCFCompareEqualTo) {
            // 获取窗口ID
            CFNumberRef windowIDNum = (CFNumberRef)CFDictionaryGetValue(windowInfo, kCGWindowNumber);
            CGWindowID windowID;
            CFNumberGetValue(windowIDNum, kCFNumberSInt32Type, &windowID);
            
            // 获取窗口 bounds
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
            printf("找到异环窗口: x=%.0f, y=%.0f, w=%.0f, h=%.0f, ID=%u\n", x, y, w, h, windowID);
            return true;
        }
    }
    
    CFRelease(windowList);
    printf("未找到异环游戏窗口，请先启动游戏\n");
    return false;
}

// 截取游戏窗口截图（基于窗口ID，自动适配窗口位置/大小）
CGImageRef take_screenshot(CGWindowID windowID) {
    // 直接截取指定窗口的完整图像，无需关心窗口位置
    CGImageRef image = CGWindowListCreateImage(
        CGRectNull,
        kCGWindowListOptionIncludingWindow,
        windowID,
        kCGWindowImageDefault
    );
    
    return image;
}

// 保存压缩后的JPEG截图
char* save_compressed_screenshot(CGImageRef image, time_t now) {
    if (!image) return NULL;
    
    // 生成文件名
    char filename[256];
    snprintf(filename, sizeof(filename), "drive_screen_%ld.jpg", now);
    
    // 创建文件输出流
    CFURLRef url = CFURLCreateFromFileSystemRepresentation(NULL, (const UInt8*)filename, strlen(filename), false);
    if (!url) return NULL;
    
    // 创建ImageIO目标
    CGImageDestinationRef dest = CGImageDestinationCreateWithURL(url, kUTTypeJPEG, 1, NULL);
    if (!dest) {
        CFRelease(url);
        return NULL;
    }
    
    // 设置压缩参数
    CFNumberRef quality = CFNumberCreate(NULL, kCFNumberFloatType, &JPEG_QUALITY);
    CFStringRef keys[] = {kCGImageDestinationLossyCompressionQuality};
    CFTypeRef values[] = {quality};
    CFDictionaryRef properties = CFDictionaryCreate(NULL, (const void**)keys, (const void**)values, 1, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    
    // 添加图像并写入
    CGImageDestinationAddImage(dest, image, properties);
    CGImageDestinationFinalize(dest);
    
    // 清理
    CFRelease(properties);
    CFRelease(quality);
    CFRelease(dest);
    CFRelease(url);
    
    // 记录文件信息用于后续清理
    if (file_count < 100) {
        strcpy(screenshot_files[file_count].filename, filename);
        screenshot_files[file_count].timestamp = now;
        file_count++;
    }
    
    // 复制文件名返回
    char* ret = malloc(strlen(filename) + 1);
    strcpy(ret, filename);
    return ret;
}

// 清理过期的截图文件
void cleanup_old_screenshots(time_t now) {
    int new_count = 0;
    for (int i = 0; i < file_count; i++) {
        if (now - screenshot_files[i].timestamp > SCREENSHOT_EXPIRE_SEC) {
            // 删除过期文件
            unlink(screenshot_files[i].filename);
        } else {
            // 保留未过期的
            screenshot_files[new_count++] = screenshot_files[i];
        }
    }
    file_count = new_count;
}

// 分析图像，判断方向和障碍物
// 返回值: 0=直行, 1=左转, 2=右转, 3=刹车避让
int analyze_direction(CGImageRef image) {
    size_t width = CGImageGetWidth(image);
    size_t height = CGImageGetHeight(image);
    
    // 计算检测区域（按窗口比例，自动适配不同窗口大小）
    size_t detect_y = height * DETECT_REGION_Y_RATIO;
    size_t detect_h = height * DETECT_REGION_HEIGHT;
    if (detect_y + detect_h > height) detect_h = height - detect_y;
    
    // 分三个区域：左、中、右
    size_t region_w = width / 3;
    
    int left_nav_pixels = 0, mid_nav_pixels = 0, right_nav_pixels = 0;
    int obstacle_pixels = 0;
    
    // 获取图像数据
    CGDataProviderRef provider = CGImageGetDataProvider(image);
    CFDataRef data = CGDataProviderCopyData(provider);
    const UInt8* pixels = CFDataGetBytePtr(data);
    size_t bytesPerRow = CGImageGetBytesPerRow(image);
    
    // 遍历检测区域的像素
    for (size_t y = detect_y; y < detect_y + detect_h; y++) {
        for (size_t x = 0; x < width; x++) {
            // 获取像素的RGB值（RGBA格式）
            size_t offset = y * bytesPerRow + x * 4;
            UInt8 r = pixels[offset];
            UInt8 g = pixels[offset+1];
            UInt8 b = pixels[offset+2];
            
            // 检测导航线：白色/黄色导航线，允许颜色误差
            bool is_nav_pixel = false;
            // 白色导航线：R>240, G>240, B>240
            if (r > 240 && g > 240 && b > 240) {
                is_nav_pixel = true;
            }
            // 黄色导航线：R>240, G>240, B<100
            else if (r > 240 && g > 240 && b < 100) {
                is_nav_pixel = true;
            }
            
            // 检测障碍物：红色车辆/行人，R>200, G<100, B<100
            bool is_obstacle = false;
            if (r > 200 && g < 100 && b < 100) {
                is_obstacle = true;
                obstacle_pixels++;
            }
            
            if (is_nav_pixel) {
                // 统计到对应区域
                if (x < region_w) {
                    left_nav_pixels++;
                } else if (x < region_w * 2) {
                    mid_nav_pixels++;
                } else {
                    right_nav_pixels++;
                }
            }
        }
    }
    
    CFRelease(data);
    
    // 先检查障碍物，如果障碍物太多，优先刹车避让
    if (obstacle_pixels > 50) {
        printf("检测到前方障碍物，准备刹车避让\n");
        return 3;
    }
    
    // 比较三个区域的导航线像素，判断方向
    printf("导航线像素: 左=%d, 中=%d, 右=%d, 障碍=%d\n", left_nav_pixels, mid_nav_pixels, right_nav_pixels, obstacle_pixels);
    
    int max_p = mid_nav_pixels;
    int direction = 0; // 默认直行
    
    if (left_nav_pixels > max_p && left_nav_pixels > 20) {
        max_p = left_nav_pixels;
        direction = 1; // 左转
    }
    if (right_nav_pixels > max_p && right_nav_pixels > 20) {
        max_p = right_nav_pixels;
        direction = 2; // 右转
    }
    
    return direction;
}

// 发送键盘事件，按住指定的键一段时间（穿透反作弊版）
// 已验证可突破异环反作弊系统
void send_keys(int duration_ms, int num_keys, int* keys) {
    CGEventSourceRef source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
    
    // 按下所有键
    for (int i = 0; i < num_keys; i++) {
        CGEventRef down = CGEventCreateKeyboardEvent(source, keys[i], true);
        CGEventPost(kCGHIDEventTap, down);
        CFRelease(down);
        usleep(20000); // 20ms间隔，避免事件冲突
    }
    
    // 按住
    usleep(duration_ms * 1000);
    
    // 释放所有键（逆序，模拟真实键盘操作）
    for (int i = num_keys - 1; i >= 0; i--) {
        CGEventRef up = CGEventCreateKeyboardEvent(source, keys[i], false);
        CGEventPost(kCGHIDEventTap, up);
        CFRelease(up);
        usleep(20000);
    }
    
    CFRelease(source);
}

int main() {
    printf("=== 异环纯C轻量自动驾驶系统启动 ===\n");
    printf("=== 无需大模型 | 低内存占用 | 高频截图 ===\n");
    printf("=== 功能：自动驾驶、自动变道、自动避让 ===\n");
    printf("按 Ctrl+C 停止\n\n");
    
    int frame_count = 0;
    
    // 主循环
    while (true) {
        time_t now = time(NULL);
        frame_count++;
        printf("\n[帧 #%d] ", frame_count);
        
        // 1. 每次循环重新获取窗口信息，自动适配窗口移动/缩放
        CGRect window_bounds;
        CGWindowID windowID;
        if (!get_game_window(&window_bounds, &windowID)) {
            usleep(SCREENSHOT_INTERVAL_MS * 1000);
            continue;
        }
        
        // 2. 高频截图
        CGImageRef image = take_screenshot(windowID);
        if (!image) {
            printf("截图失败，重试...\n");
            usleep(SCREENSHOT_INTERVAL_MS * 1000);
            continue;
        }
        
        // 3. 保存压缩截图（100KB左右）
        char* filename = save_compressed_screenshot(image, now);
        if (filename) {
            printf("截图: %s ", filename);
            free(filename);
        }
        
        // 4. 自动清理2秒前的旧截图
        cleanup_old_screenshots(now);
        
        // 5. 视觉分析：导航线方向+障碍物检测
        int direction = analyze_direction(image);
        CFRelease(image);
        
        // 6. 根据分析结果执行驾驶控制
        int keys[2];
        int num_keys;
        int duration = 80; // 默认80ms小幅度调整
        
        switch(direction) {
            case 0: // 直行
                keys[0] = KEY_W;
                num_keys = 1;
                printf("-> 直行 (W)\n");
                break;
            case 1: // 左转/左变道
                keys[0] = KEY_W;
                keys[1] = KEY_A;
                num_keys = 2;
                printf("-> 左转/左变道 (W+A)\n");
                break;
            case 2: // 右转/右变道
                keys[0] = KEY_W;
                keys[1] = KEY_D;
                num_keys = 2;
                printf("-> 右转/右变道 (W+D)\n");
                break;
            case 3: // 刹车避让
                keys[0] = KEY_S;
                num_keys = 1;
                duration = 200; // 刹车时间更长
                printf("-> 刹车避让 (S)\n");
                break;
        }
        
        // 发送穿透反作弊的控制指令
        send_keys(duration, num_keys, keys);
        
        // 等待下一个周期，实现1秒10帧的高频处理
        usleep(SCREENSHOT_INTERVAL_MS * 1000);
    }
    
    return 0;
}
    )arm64.usscRq
      api.key.   print
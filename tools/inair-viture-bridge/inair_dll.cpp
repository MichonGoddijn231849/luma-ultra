#include <windows.h>

#include <array>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>

extern "C" IMAGE_DOS_HEADER __ImageBase;

namespace
{
using CreateProviderFn = void* (*)(int);
using DestroyProviderFn = void (*)(void*);
using InitializeProviderFn = int (*)(void*, const char*, const char*);
using StartProviderFn = int (*)(void*);
using StopProviderFn = int (*)(void*);
using ShutdownProviderFn = int (*)(void*);
using IsProductValidFn = bool (*)(int);
using RegisterCallbacksFn = int (*)(void*, void*, void*, void*, void*);
using GetPoseFn = int (*)(void*, float*, double, int*);
using GetMarketNameFn = int (*)(int, char*, int*);
using SetLogLevelFn = void (*)(int);
using SetLogHookFn = void (*)(void*);

constexpr int kPoseBufferSize = 7;
constexpr int kOffsetBufferSize = 3;

struct VitureApi
{
    HMODULE module = nullptr;
    CreateProviderFn create = nullptr;
    DestroyProviderFn destroy = nullptr;
    InitializeProviderFn initialize = nullptr;
    StartProviderFn start = nullptr;
    StopProviderFn stop = nullptr;
    ShutdownProviderFn shutdown = nullptr;
    IsProductValidFn is_product_valid = nullptr;
    RegisterCallbacksFn register_callbacks = nullptr;
    GetPoseFn get_pose = nullptr;
    GetMarketNameFn get_market_name = nullptr;
    SetLogLevelFn set_log_level = nullptr;
    SetLogHookFn set_log_hook = nullptr;
};

struct BridgeState
{
    std::mutex mutex;
    VitureApi api;
    void* provider = nullptr;
    int product_id = 0;
    int immersion_level = 0;
    bool started = false;
    bool logging_enabled = false;
};

BridgeState g_state;
std::mutex g_log_mutex;

std::filesystem::path GetModuleDirectory()
{
    wchar_t buffer[MAX_PATH] = {};
    GetModuleFileNameW(reinterpret_cast<HMODULE>(&__ImageBase), buffer, static_cast<DWORD>(std::size(buffer)));
    return std::filesystem::path(buffer).parent_path();
}

void Log(const char* format, ...)
{
    if (!g_state.logging_enabled)
    {
        return;
    }

    std::lock_guard<std::mutex> lock(g_log_mutex);
    if (!g_state.logging_enabled)
    {
        return;
    }

    char buffer[1024] = {};
    va_list args;
    va_start(args, format);
    std::vsnprintf(buffer, std::size(buffer), format, args);
    va_end(args);

    OutputDebugStringA("[luma-inair-bridge] ");
    OutputDebugStringA(buffer);
    OutputDebugStringA("\n");
}

template <typename T>
T LoadSymbol(HMODULE module, const char* name)
{
    return reinterpret_cast<T>(GetProcAddress(module, name));
}

void PoseCallback(const float* /*values*/, double /*timestamp*/)
{
}

void VsyncCallback(double /*timestamp*/)
{
}

void ImuCallback(const float* /*values*/, double /*timestamp*/)
{
}

void CameraCallback(
    const void* /*image_left0*/,
    const void* /*image_right0*/,
    const void* /*image_left1*/,
    const void* /*image_right1*/,
    double /*timestamp*/,
    int /*width*/,
    int /*height*/
)
{
}

bool EnsureApiLoaded()
{
    if (g_state.api.module)
    {
        return true;
    }

    std::filesystem::path dir = GetModuleDirectory();
    SetDllDirectoryW(dir.c_str());
    HMODULE module = LoadLibraryW((dir / L"glasses.dll").c_str());
    if (!module)
    {
        return false;
    }

    g_state.api.module = module;
    g_state.api.create = LoadSymbol<CreateProviderFn>(module, "xr_device_provider_create");
    g_state.api.destroy = LoadSymbol<DestroyProviderFn>(module, "xr_device_provider_destroy");
    g_state.api.initialize = LoadSymbol<InitializeProviderFn>(module, "xr_device_provider_initialize");
    g_state.api.start = LoadSymbol<StartProviderFn>(module, "xr_device_provider_start");
    g_state.api.stop = LoadSymbol<StopProviderFn>(module, "xr_device_provider_stop");
    g_state.api.shutdown = LoadSymbol<ShutdownProviderFn>(module, "xr_device_provider_shutdown");
    g_state.api.is_product_valid = LoadSymbol<IsProductValidFn>(module, "xr_device_provider_is_product_id_valid");
    g_state.api.register_callbacks = LoadSymbol<RegisterCallbacksFn>(module, "xr_device_provider_register_callbacks_carina");
    g_state.api.get_pose = LoadSymbol<GetPoseFn>(module, "xr_device_provider_get_gl_pose_carina");
    g_state.api.get_market_name = LoadSymbol<GetMarketNameFn>(module, "xr_device_provider_get_market_name");
    g_state.api.set_log_level = LoadSymbol<SetLogLevelFn>(module, "xr_device_provider_set_log_level");
    g_state.api.set_log_hook = LoadSymbol<SetLogHookFn>(module, "xr_device_provider_set_log_hook");

    const bool loaded = g_state.api.create && g_state.api.destroy && g_state.api.initialize && g_state.api.start &&
        g_state.api.stop && g_state.api.shutdown && g_state.api.is_product_valid && g_state.api.register_callbacks &&
        g_state.api.get_pose && g_state.api.get_market_name && g_state.api.set_log_level && g_state.api.set_log_hook;
    return loaded;
}

std::filesystem::path GetCacheDirectory()
{
    wchar_t local_app_data[MAX_PATH] = {};
    DWORD length = GetEnvironmentVariableW(L"LOCALAPPDATA", local_app_data, static_cast<DWORD>(std::size(local_app_data)));
    std::filesystem::path base = length > 0 ? std::filesystem::path(local_app_data) : GetModuleDirectory();
    std::filesystem::path cache_dir = base / "INAIR" / "viture-bridge-cache";
    std::error_code ignored;
    std::filesystem::create_directories(cache_dir, ignored);
    return cache_dir;
}

std::vector<int> CandidateProductIds()
{
    return { 0x1104, 0x1312 };
}

bool StartProviderUnlocked()
{
    if (!EnsureApiLoaded())
    {
        Log("Failed to load glasses.dll or one of the required SDK symbols.");
        return false;
    }

    if (g_state.started && g_state.provider)
    {
        return true;
    }

    for (int product_id : CandidateProductIds())
    {
        if (!g_state.api.is_product_valid(product_id))
        {
            continue;
        }

        void* provider = g_state.api.create(product_id);
        if (!provider)
        {
            continue;
        }

        const int callback_result = g_state.api.register_callbacks(
            provider,
            reinterpret_cast<void*>(PoseCallback),
            reinterpret_cast<void*>(VsyncCallback),
            reinterpret_cast<void*>(ImuCallback),
            reinterpret_cast<void*>(CameraCallback)
        );
        if (callback_result != 0)
        {
            Log("Callback registration failed for product 0x%04X with code %d.", product_id, callback_result);
            g_state.api.destroy(provider);
            continue;
        }

        std::string cache = GetCacheDirectory().string();
        int init_result = g_state.api.initialize(provider, nullptr, cache.c_str());
        if (init_result != 0)
        {
            Log("Provider initialization failed for product 0x%04X with code %d.", product_id, init_result);
            g_state.api.destroy(provider);
            continue;
        }

        int start_result = g_state.api.start(provider);
        if (start_result != 0)
        {
            Log("Provider start failed for product 0x%04X with code %d.", product_id, start_result);
            g_state.api.shutdown(provider);
            g_state.api.destroy(provider);
            continue;
        }

        g_state.provider = provider;
        g_state.product_id = product_id;
        g_state.started = true;
        Log("Started VITURE bridge with product id 0x%04X.", product_id);
        return true;
    }

    Log("No supported VITURE device could be started.");
    return false;
}

void StopProviderUnlocked()
{
    if (!g_state.provider)
    {
        g_state.started = false;
        return;
    }

    g_state.api.stop(g_state.provider);
    g_state.api.shutdown(g_state.provider);
    g_state.api.destroy(g_state.provider);
    g_state.provider = nullptr;
    g_state.product_id = 0;
    g_state.started = false;
}

bool QueryPoseUnlocked(double prediction_seconds, std::array<float, kPoseBufferSize>& pose)
{
    if (!StartProviderUnlocked())
    {
        return false;
    }

    int status = 0;
    if (g_state.api.get_pose(g_state.provider, pose.data(), prediction_seconds, &status) != 0)
    {
        Log("xr_device_provider_get_gl_pose_carina failed.");
        return false;
    }

    if (status == 0)
    {
        Log("Pose status is 0.");
        return false;
    }

    return true;
}

void CopyQuaternionToInairFormat(const std::array<float, kPoseBufferSize>& pose, float* imu)
{
    if (!imu)
    {
        return;
    }

    // ImuManager reconstructs Unity quaternion as (-imu[0], -imu[2], -imu[1], imu[3]).
    // Mapping VITURE's (x, y, z, w) into that format preserves the original quaternion.
    const float x = pose[3];
    const float y = pose[4];
    const float z = pose[5];
    const float w = pose[6];

    imu[0] = -x;
    imu[1] = -z;
    imu[2] = -y;
    imu[3] = w;
}
}

extern "C"
{
__declspec(dllexport) int start_glasses_engine()
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    return StartProviderUnlocked() ? 0 : -1;
}

__declspec(dllexport) int stop_glasses_engine()
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    StopProviderUnlocked();
    return 0;
}

__declspec(dllexport) int start_display_3d()
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    return StartProviderUnlocked() ? 0 : -1;
}

__declspec(dllexport) int stop_display_3d()
{
    return 0;
}

__declspec(dllexport) void getIMU(float* imu, long long* ts)
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    std::array<float, kPoseBufferSize> pose = {};
    if (!QueryPoseUnlocked(0.0, pose))
    {
        if (imu)
        {
            for (int i = 0; i < 4; ++i)
            {
                imu[i] = 0.0f;
            }
        }
        if (ts)
        {
            *ts = 0;
        }
        return;
    }

    CopyQuaternionToInairFormat(pose, imu);
    if (ts)
    {
        *ts = static_cast<long long>(
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now().time_since_epoch()
            ).count()
        );
    }
}

__declspec(dllexport) void getIMUPredicted(float delay, float* imu)
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    std::array<float, kPoseBufferSize> pose = {};
    if (!QueryPoseUnlocked(static_cast<double>(delay), pose))
    {
        if (imu)
        {
            for (int i = 0; i < 4; ++i)
            {
                imu[i] = 0.0f;
            }
        }
        return;
    }

    CopyQuaternionToInairFormat(pose, imu);
}

__declspec(dllexport) void getIMUOffset(float* data)
{
    if (!data)
    {
        return;
    }

    for (int i = 0; i < kOffsetBufferSize; ++i)
    {
        data[i] = 0.0f;
    }
}

__declspec(dllexport) void setSmooth(float /*smooth*/, float /*trend*/, float /*filter*/)
{
}

__declspec(dllexport) long long GetCurrentTimeMsec()
{
    return static_cast<long long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()
        ).count()
    );
}

__declspec(dllexport) long long GetCurrentTimeNsec()
{
    return static_cast<long long>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()
        ).count()
    );
}

__declspec(dllexport) void enableLog(bool enable)
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.logging_enabled = enable;
}

__declspec(dllexport) void SetImmersionLevel(int level)
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.immersion_level = level;
}

__declspec(dllexport) int GetImmersionLevel()
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    return g_state.immersion_level;
}

__declspec(dllexport) int GetGlassesVersion()
{
    std::lock_guard<std::mutex> lock(g_state.mutex);
    return g_state.product_id;
}
}

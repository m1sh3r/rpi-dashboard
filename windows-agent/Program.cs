using System.Net.Http.Headers;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using LibreHardwareMonitor.Hardware;
using Microsoft.Win32;

const int successLogIntervalMs = 5_000;

EnvironmentConfig.Load();

var settings = AgentSettings.Load(args);
using var sampler = new NativeMetricsSampler(settings);
using var httpClient = new HttpClient
{
  Timeout = TimeSpan.FromSeconds(5),
};

var jsonOptions = new JsonSerializerOptions
{
  DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull,
  PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
};

var lastSuccessLogAt = DateTimeOffset.MinValue;

await sampler.InitializeAsync();
await TickAsync();

if (!settings.Once)
{
  var timer = new PeriodicTimer(TimeSpan.FromMilliseconds(settings.IntervalMs));

  try
  {
    while (await timer.WaitForNextTickAsync())
    {
      await TickAsync();
    }
  }
  finally
  {
    timer.Dispose();
  }
}

return;

async Task TickAsync()
{
  try
  {
    var payload = sampler.CollectStatus();
    await SendStatusAsync(payload);
  }
  catch (Exception exception)
  {
    Console.Error.WriteLine($"Не удалось отправить состояние ПК: {exception.Message}");
  }
}

async Task SendStatusAsync(StatusPayload payload)
{
  var body = JsonSerializer.SerializeToUtf8Bytes(payload, jsonOptions);
  var errors = new List<string>();

  await Task.WhenAll(settings.Endpoints.Select(async (endpoint) =>
  {
    try
    {
      using var request = new HttpRequestMessage(HttpMethod.Post, endpoint)
      {
        Content = new ByteArrayContent(body),
      };
      request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
      request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", settings.Token);

      using var response = await httpClient.SendAsync(request);

      if (!response.IsSuccessStatusCode)
      {
        var text = await response.Content.ReadAsStringAsync();
        throw new InvalidOperationException($"HTTP {(int)response.StatusCode}: {text}");
      }
    }
    catch (Exception exception)
    {
      lock (errors)
      {
        errors.Add($"{endpoint}: {exception.Message}");
      }
    }
  }));

  if (errors.Count == settings.Endpoints.Count)
  {
    throw new InvalidOperationException(string.Join("; ", errors));
  }

  if (
    settings.LogSuccess &&
    DateTimeOffset.UtcNow - lastSuccessLogAt > TimeSpan.FromMilliseconds(successLogIntervalMs)
  )
  {
    lastSuccessLogAt = DateTimeOffset.UtcNow;
    Console.WriteLine($"Отправлено состояние {payload.Host} на {string.Join(", ", settings.Endpoints)}");
  }

  if (errors.Count > 0)
  {
    Console.Error.WriteLine($"Часть endpoint недоступна: {string.Join("; ", errors)}");
  }
}

internal sealed class AgentSettings
{
  public required IReadOnlyList<string> Endpoints { get; init; }
  public required string Token { get; init; }
  public required int IntervalMs { get; init; }
  public required bool LogNetworkDiagnostics { get; init; }
  public required bool LogSuccess { get; init; }
  public required bool LogTemperatureDiagnostics { get; init; }
  public required bool Once { get; init; }

  public static AgentSettings Load(string[] args)
  {
    var endpoints = (Environment.GetEnvironmentVariable("PC_STATUS_ENDPOINT") ?? string.Empty)
      .Split(new[] {';', ','}, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

    return new AgentSettings
    {
      Endpoints = endpoints.Length > 0
        ? endpoints
        : new[]
          {
            "http://localhost:7777/api/pc-status",
            "http://localhost:5173/api/pc-status",
          },
      IntervalMs = Math.Max(100, ReadInt("PC_STATUS_INTERVAL_MS", 1_000)),
      LogNetworkDiagnostics = ReadBool("PC_STATUS_LOG_NETWORK_DIAGNOSTICS", false),
      LogSuccess = ReadBool("PC_STATUS_LOG_SUCCESS", false),
      LogTemperatureDiagnostics = ReadBool("PC_STATUS_LOG_TEMPERATURE_DIAGNOSTICS", false),
      Once = args.Contains("--once", StringComparer.OrdinalIgnoreCase),
      Token = Environment.GetEnvironmentVariable("PC_STATUS_TOKEN") ?? "change-me",
    };
  }

  private static bool ReadBool(string key, bool fallback)
  {
    return bool.TryParse(Environment.GetEnvironmentVariable(key), out var value)
      ? value
      : fallback;
  }

  private static int ReadInt(string key, int fallback)
  {
    return int.TryParse(Environment.GetEnvironmentVariable(key), out var value)
      ? value
      : fallback;
  }
}

internal static class EnvironmentConfig
{
  public static void Load()
  {
    foreach (var filePath in EnumerateCandidateFiles())
    {
      if (!File.Exists(filePath))
      {
        continue;
      }

      foreach (var line in File.ReadAllLines(filePath, Encoding.UTF8))
      {
        var trimmed = line.Trim();

        if (trimmed.Length == 0 || trimmed.StartsWith('#'))
        {
          continue;
        }

        var separatorIndex = trimmed.IndexOf('=');

        if (separatorIndex <= 0)
        {
          continue;
        }

        var key = trimmed[..separatorIndex].Trim();
        var value = trimmed[(separatorIndex + 1)..].Trim().Trim('"');

        if (!string.IsNullOrWhiteSpace(key))
        {
          Environment.SetEnvironmentVariable(key, value);
        }
      }
    }
  }

  private static IEnumerable<string> EnumerateCandidateFiles()
  {
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var paths = new[]
    {
      Path.Combine(Directory.GetCurrentDirectory(), ".env"),
      Path.Combine(AppContext.BaseDirectory, ".env"),
    };

    foreach (var path in paths)
    {
      if (seen.Add(path))
      {
        yield return path;
      }
    }
  }
}

internal sealed class NativeMetricsSampler : IDisposable
{
  private readonly CpuUsageSampler cpuSampler = new();
  private readonly HardwareTemperatureMonitor hardwareTemperatureMonitor = new();
  private readonly DiskSnapshotProvider diskProvider = new();
  private readonly DiskActivitySampler diskActivitySampler = new();
  private readonly NetworkSnapshotProvider networkProvider;
  private readonly SystemSnapshot systemSnapshot = SystemSnapshot.Load();
  private readonly bool logTemperatureDiagnostics;

  public NativeMetricsSampler(AgentSettings settings)
  {
    logTemperatureDiagnostics = settings.LogTemperatureDiagnostics;
    networkProvider = new NetworkSnapshotProvider(settings);
    hardwareTemperatureMonitor.SetDiagnosticsEnabled(settings.LogTemperatureDiagnostics);
  }

  public Task InitializeAsync()
  {
    cpuSampler.Initialize();
    diskActivitySampler.Initialize();
    networkProvider.Initialize();

    if (logTemperatureDiagnostics)
    {
      hardwareTemperatureMonitor.WriteDiagnosticsSnapshot();
    }

    return Task.CompletedTask;
  }

  public StatusPayload CollectStatus()
  {
    hardwareTemperatureMonitor.Refresh();
    diskActivitySampler.Collect();
    var memory = MemorySnapshot.Read();
    var swap = SwapSnapshot.Read(memory);
    var disks = diskProvider.GetSnapshot(diskActivitySampler);
    var network = networkProvider.GetSnapshot();
    var gpu = hardwareTemperatureMonitor.CollectGpuStatus();

    return new StatusPayload
    {
      Cpu = new CpuPayload
      {
        Cores = Environment.ProcessorCount,
        TemperatureC = hardwareTemperatureMonitor.TryReadCpuTemperatureC(),
        UsagePercent = cpuSampler.GetUsagePercent(),
      },
      Disk = disks.FirstOrDefault(),
      Disks = disks,
      Gpu = gpu,
      Host = Environment.MachineName,
      Memory = memory,
      Network = network,
      Swap = swap,
      System = systemSnapshot,
      Timestamp = DateTimeOffset.UtcNow.ToString("O"),
      UptimeSeconds = Environment.TickCount64 / 1000,
    };
  }

  public void Dispose()
  {
    cpuSampler.Dispose();
    diskActivitySampler.Dispose();
    hardwareTemperatureMonitor.Dispose();
  }
}

internal sealed class CpuUsageSampler : IDisposable
{
  private FileTimeSnapshot previous = FileTimeSnapshot.Read();
  private double lastUsagePercent;
  private PdhQuery? query;
  private IntPtr cpuCounter;

  public void Initialize()
  {
    previous = FileTimeSnapshot.Read();
    lastUsagePercent = 0;

    try
    {
      query = new PdhQuery();
      // Пробуем получить "% Processor Utility" (соответствует Диспетчеру задач)
      cpuCounter = query.TryAddEnglishCounter(@"\Processor Information(_Total)\% Processor Utility");
      
      // Резервный вариант: традиционный "% Processor Time"
      if (cpuCounter == IntPtr.Zero)
      {
        cpuCounter = query.TryAddEnglishCounter(@"\Processor(_Total)\% Processor Time");
      }

      if (cpuCounter != IntPtr.Zero)
      {
        query.Collect();
      }
    }
    catch
    {
      CleanupPdh();
    }
  }

  public double GetUsagePercent()
  {
    if (query is not null && cpuCounter != IntPtr.Zero)
    {
      try
      {
        query.Collect();
        var values = query.GetDoubleArray(cpuCounter);
        if (values.Count > 0)
        {
          var totalValue = values.FirstOrDefault(v => v.Name.Equals("_Total", StringComparison.OrdinalIgnoreCase));
          if (totalValue.Name is null)
          {
            totalValue = values[0];
          }
          lastUsagePercent = Math.Round(Math.Clamp(totalValue.Value, 0, 100), 1);
          return lastUsagePercent;
        }
      }
      catch
      {
        CleanupPdh();
      }
    }

    // Резервный расчет через GetSystemTimes (fallback)
    var current = FileTimeSnapshot.Read();
    var idleDelta = current.Idle - previous.Idle;
    var kernelDelta = current.Kernel - previous.Kernel;
    var userDelta = current.User - previous.User;
    var totalDelta = kernelDelta + userDelta;

    if (totalDelta > 0)
    {
      var busy = Math.Clamp(totalDelta - idleDelta, 0, totalDelta);
      lastUsagePercent = Math.Round(busy * 100d / totalDelta, 1);
    }

    previous = current;
    return lastUsagePercent;
  }

  private void CleanupPdh()
  {
    query?.Dispose();
    query = null;
    cpuCounter = IntPtr.Zero;
  }

  public void Dispose()
  {
    CleanupPdh();
  }
}

internal readonly record struct FileTimeSnapshot(ulong Idle, ulong Kernel, ulong User)
{
  public static FileTimeSnapshot Read()
  {
    if (!Kernel32.GetSystemTimes(out var idle, out var kernel, out var user))
    {
      return default;
    }

    return new FileTimeSnapshot(ToUInt64(idle), ToUInt64(kernel), ToUInt64(user));
  }

  private static ulong ToUInt64(FILETIME fileTime)
  {
    return ((ulong)fileTime.dwHighDateTime << 32) | fileTime.dwLowDateTime;
  }
}

internal sealed class GpuSampler : IDisposable
{
  private PdhQuery? query;
  private IntPtr gpuUsageCounter;
  private IntPtr gpuMemoryCounter;
  private GpuStaticInfo staticInfo = GpuStaticInfo.Load();

  public void Initialize()
  {
    staticInfo = GpuStaticInfo.Load();

    try
    {
      query = new PdhQuery();
      gpuUsageCounter = query.TryAddEnglishCounter(@"\GPU Engine(*)\Utilization Percentage");
      gpuMemoryCounter = query.TryAddEnglishCounter(@"\GPU Adapter Memory(*)\Dedicated Usage");
      query.Collect();
    }
    catch
    {
      query?.Dispose();
      query = null;
      gpuUsageCounter = IntPtr.Zero;
      gpuMemoryCounter = IntPtr.Zero;
    }
  }

  public GpuPayload GetSnapshot()
  {
    query?.Collect();

    var usagePercent = 0d;
    var memoryUsedBytes = 0L;

    if (query is not null && gpuUsageCounter != IntPtr.Zero)
    {
      var usageValues = query.GetDoubleArray(gpuUsageCounter)
        .Where(item => !item.Name.Contains("_Total", StringComparison.OrdinalIgnoreCase))
        .Select(item => item.Value)
        .ToArray();

      if (usageValues.Length > 0)
      {
        usagePercent = Math.Round(usageValues.Max(), 1);
      }
    }

    if (query is not null && gpuMemoryCounter != IntPtr.Zero)
    {
      memoryUsedBytes = query.GetLongArray(gpuMemoryCounter)
        .Where(item => !item.Name.Contains("_Total", StringComparison.OrdinalIgnoreCase))
        .Sum(item => item.Value);
    }

    return new GpuPayload
    {
      DriverVersion = string.Empty,
      MemoryTotalBytes = staticInfo.MemoryTotalBytes,
      MemoryUsedBytes = Math.Max(memoryUsedBytes, 0),
      Name = staticInfo.Name,
      UsagePercent = usagePercent,
      Vendor = staticInfo.Vendor,
      VideoProcessor = string.Empty,
    };
  }

  public void Dispose()
  {
    query?.Dispose();
  }
}



internal sealed class HardwareTemperatureMonitor : IDisposable
{
  private readonly object syncRoot = new();
  private readonly IVisitor updateVisitor = new UpdateVisitor();
  private readonly Computer computer = new()
  {
    IsCpuEnabled = true,
    IsGpuEnabled = true,
    IsMotherboardEnabled = false,
    IsMemoryEnabled = false,
    IsStorageEnabled = false,
    IsNetworkEnabled = false,
    IsControllerEnabled = false,
    IsBatteryEnabled = false,
    IsPsuEnabled = false,
  };
  private bool diagnosticsEnabled;
  private bool cpuDiagnosticsLogged;

  public HardwareTemperatureMonitor()
  {
    computer.Open();
  }

  public void SetDiagnosticsEnabled(bool enabled)
  {
    diagnosticsEnabled = enabled;
  }

  public void Refresh()
  {
    lock (syncRoot)
    {
      try
      {
        computer.Accept(updateVisitor);
      }
      catch
      {
        // ignored
      }
    }
  }

  public void WriteDiagnosticsSnapshot()
  {
    lock (syncRoot)
    {
      Refresh();
      Console.WriteLine("=== Диагностика LibreHardwareMonitor ===");
      DumpHardwareAndSensors(Console.WriteLine);
      Console.WriteLine("=== Конец диагностики LibreHardwareMonitor ===");
    }
  }

  public double? TryReadCpuTemperatureC()
  {
    lock (syncRoot)
    {
      var sensors = EnumerateSensors()
        .Where(sensor =>
          sensor.SensorType == SensorType.Temperature &&
          sensor.Value.HasValue &&
          IsCpuTemperatureSensor(sensor)
        )
        .ToArray();

      var temperature = PickTemperature(
        sensors,
        "Package",
        "Tctl",
        "Tdie",
        "CCD",
        "CPU",
        "Core"
      );

      if (!temperature.HasValue)
      {
        LogMissingSensorsOnce("CPU", ref cpuDiagnosticsLogged);
      }

      return temperature;
    }
  }

  public GpuPayload CollectGpuStatus()
  {
    lock (syncRoot)
    {
      var mainGpu = computer.Hardware
        .Where(h => h.HardwareType is HardwareType.GpuNvidia or HardwareType.GpuAmd or HardwareType.GpuIntel)
        .OrderBy(h => h.HardwareType == HardwareType.GpuNvidia ? 0 : h.HardwareType == HardwareType.GpuAmd ? 1 : 2)
        .FirstOrDefault();

      if (mainGpu == null)
      {
        return new GpuPayload
        {
          Name = "GPU",
          Vendor = string.Empty,
          DriverVersion = string.Empty,
          VideoProcessor = string.Empty,
          MemoryTotalBytes = 0,
          MemoryUsedBytes = 0,
          UsagePercent = 0,
          TemperatureC = null
        };
      }

      var name = mainGpu.Name ?? "GPU";
      var vendor = mainGpu.HardwareType == HardwareType.GpuNvidia ? "NVIDIA" :
                   mainGpu.HardwareType == HardwareType.GpuAmd ? "AMD" : "Intel";

      double? temperatureC = null;
      double usagePercent = 0;
      long memoryTotalBytes = 0;
      long memoryUsedBytes = 0;
      bool foundD3dDedicatedTotal = false;
      bool foundD3dDedicatedUsed = false;

      foreach (var sensor in mainGpu.Sensors)
      {
        if (sensor.Value.HasValue)
        {
          if (sensor.SensorType == SensorType.Temperature && sensor.Name.Contains("Core", StringComparison.OrdinalIgnoreCase))
          {
            temperatureC = Math.Round((double)sensor.Value.Value, 1);
          }
          else if (sensor.SensorType == SensorType.Load && sensor.Name.Equals("GPU Core", StringComparison.OrdinalIgnoreCase))
          {
            usagePercent = Math.Round((double)sensor.Value.Value, 1);
          }
          else if (sensor.SensorType == SensorType.SmallData || sensor.SensorType == SensorType.Data)
          {
            if (sensor.Name.Equals("D3D Dedicated Memory Total", StringComparison.OrdinalIgnoreCase))
            {
              memoryTotalBytes = (long)Math.Round(sensor.Value.Value * 1024 * 1024);
              foundD3dDedicatedTotal = true;
            }
            else if (sensor.Name.Equals("GPU Memory Total", StringComparison.OrdinalIgnoreCase) && !foundD3dDedicatedTotal)
            {
              memoryTotalBytes = (long)Math.Round(sensor.Value.Value * 1024 * 1024);
            }
            else if (sensor.Name.Equals("D3D Dedicated Memory Used", StringComparison.OrdinalIgnoreCase))
            {
              memoryUsedBytes = (long)Math.Round(sensor.Value.Value * 1024 * 1024);
              foundD3dDedicatedUsed = true;
            }
            else if (sensor.Name.Equals("GPU Memory Used", StringComparison.OrdinalIgnoreCase) && !foundD3dDedicatedUsed)
            {
              memoryUsedBytes = (long)Math.Round(sensor.Value.Value * 1024 * 1024);
            }
          }
        }
      }

      if (!temperatureC.HasValue)
      {
        var tempSensor = mainGpu.Sensors
          .FirstOrDefault(s => s.SensorType == SensorType.Temperature && s.Value.HasValue);
        if (tempSensor != null)
        {
          temperatureC = Math.Round((double)tempSensor.Value!.Value, 1);
        }
      }

      return new GpuPayload
      {
        Name = name,
        Vendor = vendor,
        DriverVersion = string.Empty,
        VideoProcessor = string.Empty,
        MemoryTotalBytes = memoryTotalBytes,
        MemoryUsedBytes = memoryUsedBytes,
        UsagePercent = usagePercent,
        TemperatureC = temperatureC
      };
    }
  }

  public void Dispose()
  {
    computer.Close();
  }


  private IEnumerable<ISensor> EnumerateSensors()
  {
    foreach (var hardware in computer.Hardware)
    {
      foreach (var sensor in hardware.Sensors)
      {
        yield return sensor;
      }

      foreach (var subHardware in hardware.SubHardware)
      {
        foreach (var sensor in subHardware.Sensors)
        {
          yield return sensor;
        }
      }
    }
  }

  private void LogMissingSensorsOnce(string target, ref bool flag)
  {
    if (!diagnosticsEnabled || flag)
    {
      return;
    }

    flag = true;

    Console.WriteLine($"LibreHardwareMonitor не нашёл температуру для {target}.");
    DumpHardwareAndSensors(Console.WriteLine);
  }

  private static string FormatSensorValue(float? value)
  {
    return value.HasValue ? value.Value.ToString("0.0") : "null";
  }

  private void DumpHardwareAndSensors(Action<string> writeLine)
  {
    foreach (var hardware in computer.Hardware)
    {
      writeLine($"LHM hardware: {hardware.HardwareType} | {hardware.Name}");

      foreach (var sensor in hardware.Sensors)
      {
        writeLine(
          $"LHM sensor: {hardware.HardwareType} | {sensor.SensorType} | {sensor.Name} | {FormatSensorValue(sensor.Value)}"
        );
      }

      foreach (var subHardware in hardware.SubHardware)
      {
        writeLine($"LHM subhardware: {subHardware.HardwareType} | {subHardware.Name}");

        foreach (var sensor in subHardware.Sensors)
        {
          writeLine(
            $"LHM sensor: {subHardware.HardwareType} | {sensor.SensorType} | {sensor.Name} | {FormatSensorValue(sensor.Value)}"
          );
        }
      }
    }
  }

  private static double? PickTemperature(IReadOnlyList<ISensor> sensors, params string[] priorities)
  {
    foreach (var priority in priorities)
    {
      var matched = sensors
        .Where(sensor => sensor.Name.Contains(priority, StringComparison.OrdinalIgnoreCase))
        .Select(sensor => sensor.Value)
        .Where(value => value.HasValue)
        .Select(value => (double)value!.Value)
        .ToArray();

      if (matched.Length > 0)
      {
        return Math.Round(matched.Max(), 1);
      }
    }

    var any = sensors
      .Select(sensor => sensor.Value)
      .Where(value => value.HasValue)
      .Select(value => (double)value!.Value)
      .ToArray();

    return any.Length > 0 ? Math.Round(any.Max(), 1) : null;
  }

  private static bool IsCpuTemperatureSensor(ISensor sensor)
  {
    if (sensor.Hardware.HardwareType == HardwareType.Cpu)
    {
      return true;
    }

    if (sensor.Hardware.HardwareType is not HardwareType.Motherboard and not HardwareType.SuperIO)
    {
      return false;
    }

    var name = sensor.Name;

    return
      name.Contains("CPU", StringComparison.OrdinalIgnoreCase) ||
      name.Contains("Package", StringComparison.OrdinalIgnoreCase) ||
      name.Contains("Tctl", StringComparison.OrdinalIgnoreCase) ||
      name.Contains("Tdie", StringComparison.OrdinalIgnoreCase) ||
      name.Contains("CCD", StringComparison.OrdinalIgnoreCase);
  }
}

internal sealed class UpdateVisitor : IVisitor
{
  public void VisitComputer(IComputer computer)
  {
    computer.Traverse(this);
  }

  public void VisitHardware(IHardware hardware)
  {
    hardware.Update();

    foreach (var subHardware in hardware.SubHardware)
    {
      subHardware.Accept(this);
    }
  }

  public void VisitSensor(ISensor sensor)
  {
  }

  public void VisitParameter(IParameter parameter)
  {
  }
}

internal sealed class NetworkSnapshotProvider
{
  private readonly bool logDiagnostics;
  private NetworkInterface? cachedAdapter;
  private DateTimeOffset nextLookupTime = DateTimeOffset.MinValue;
  private NetworkRawSnapshot previous;

  public NetworkSnapshotProvider(AgentSettings settings)
  {
    logDiagnostics = settings.LogNetworkDiagnostics;
    cachedAdapter = GetActiveInterface();
    previous = NetworkRawSnapshot.Read(cachedAdapter);
  }

  public void Initialize()
  {
    cachedAdapter = GetActiveInterface();
    previous = NetworkRawSnapshot.Read(cachedAdapter);
  }

  private NetworkInterface? GetActiveInterface()
  {
    var now = DateTimeOffset.UtcNow;
    if (cachedAdapter != null && now < nextLookupTime)
    {
      try
      {
        if (cachedAdapter.OperationalStatus == OperationalStatus.Up)
        {
          return cachedAdapter;
        }
      }
      catch
      {
        // ignored
      }
    }

    cachedAdapter = NetworkRawSnapshot.SelectNetworkInterface(logDiagnostics);
    nextLookupTime = now.AddSeconds(15);
    return cachedAdapter;
  }

  public NetworkPayload GetSnapshot()
  {
    var adapter = GetActiveInterface();
    var current = NetworkRawSnapshot.Read(adapter);

    if (!string.Equals(current.AdapterId, previous.AdapterId, StringComparison.Ordinal))
    {
      previous = current;

      return new NetworkPayload
      {
        Adapter = current.Adapter,
        Description = current.Description,
        RxBytesPerSecond = 0,
        TxBytesPerSecond = 0,
      };
    }

    var elapsedSeconds = Math.Max((current.Timestamp - previous.Timestamp).TotalSeconds, 0.001);
    var rxBytesPerSecond = Math.Max((current.ReceivedBytes - previous.ReceivedBytes) / elapsedSeconds, 0);
    var txBytesPerSecond = Math.Max((current.SentBytes - previous.SentBytes) / elapsedSeconds, 0);

    previous = current;

    return new NetworkPayload
    {
      Adapter = current.Adapter,
      Description = current.Description,
      RxBytesPerSecond = (long)Math.Round(rxBytesPerSecond),
      TxBytesPerSecond = (long)Math.Round(txBytesPerSecond),
    };
  }
}

internal readonly record struct NetworkRawSnapshot(
  string AdapterId,
  string Adapter,
  string Description,
  long ReceivedBytes,
  long SentBytes,
  DateTimeOffset Timestamp
)
{
  public static NetworkRawSnapshot Read(NetworkInterface? adapter)
  {
    if (adapter is null)
    {
      return new NetworkRawSnapshot(
        string.Empty,
        "Нет подключения",
        string.Empty,
        0,
        0,
        DateTimeOffset.UtcNow
      );
    }

    try
    {
      var statistics = adapter.GetIPStatistics();

      return new NetworkRawSnapshot(
        adapter.Id,
        adapter.Name,
        adapter.Description,
        statistics.BytesReceived,
        statistics.BytesSent,
        DateTimeOffset.UtcNow
      );
    }
    catch
    {
      return new NetworkRawSnapshot(
        adapter.Id,
        adapter.Name,
        adapter.Description,
        0,
        0,
        DateTimeOffset.UtcNow
      );
    }
  }

  internal static NetworkInterface? SelectNetworkInterface(bool logDiagnostics)
  {
    var candidates = NetworkInterface.GetAllNetworkInterfaces()
      .Where(networkInterface =>
      {
        if (networkInterface.OperationalStatus != OperationalStatus.Up)
        {
          return false;
        }

        if (networkInterface.NetworkInterfaceType != NetworkInterfaceType.Wireless80211)
        {
          return false;
        }

        if (networkInterface.NetworkInterfaceType is NetworkInterfaceType.Loopback or NetworkInterfaceType.Tunnel)
        {
          return false;
        }

        var name = networkInterface.Name;
        var description = networkInterface.Description;

        // Ignore common virtual adapters so background VM/container traffic does not show up as Wi-Fi.
        if (
          name.Contains("vEthernet", StringComparison.OrdinalIgnoreCase) ||
          name.Contains("WSL", StringComparison.OrdinalIgnoreCase) ||
          description.Contains("Hyper-V", StringComparison.OrdinalIgnoreCase) ||
          description.Contains("Virtual", StringComparison.OrdinalIgnoreCase) ||
          description.Contains("VPN", StringComparison.OrdinalIgnoreCase) ||
          description.Contains("TAP", StringComparison.OrdinalIgnoreCase)
        )
        {
          return false;
        }

        return true;
      })
      .ToArray();

    if (logDiagnostics)
    {
      Console.WriteLine("=== Диагностика сетевых интерфейсов ===");

      foreach (var networkInterface in candidates)
      {
        Console.WriteLine(
          $"NET candidate: {networkInterface.Name} | {networkInterface.NetworkInterfaceType} | {networkInterface.Description}"
        );
      }

      if (candidates.Length == 0)
      {
        Console.WriteLine("NET candidate: не найдено ни одного подходящего интерфейса.");
      }
    }

    if (candidates.Length == 0)
    {
      if (logDiagnostics)
      {
        Console.WriteLine("NET selected: Wi-Fi интерфейс не найден или отключён.");
        Console.WriteLine("=== Конец диагностики сетевых интерфейсов ===");
      }

      return null;
    }

    var selected = candidates
      .OrderBy(networkInterface => networkInterface.Name, StringComparer.OrdinalIgnoreCase)
      .FirstOrDefault();

    if (logDiagnostics && selected is not null)
    {
      Console.WriteLine(
        $"NET selected: {selected.Name} | {selected.NetworkInterfaceType} | {selected.Description}"
      );
      Console.WriteLine("=== Конец диагностики сетевых интерфейсов ===");
    }

    return selected;
  }
}

internal sealed class DiskSnapshotProvider
{
  private DateTimeOffset expiresAt = DateTimeOffset.MinValue;
  private IReadOnlyList<DiskPayload> cachedStatic = Array.Empty<DiskPayload>();

  public IReadOnlyList<DiskPayload> GetSnapshot(DiskActivitySampler activitySampler)
  {
    var now = DateTimeOffset.UtcNow;
    if (now >= expiresAt || cachedStatic.Count == 0)
    {
      cachedStatic = DriveInfo.GetDrives()
        .Where(drive => drive.DriveType == DriveType.Fixed && drive.IsReady)
        .Select(drive =>
        {
          var totalBytes = drive.TotalSize;
          var freeBytes = drive.AvailableFreeSpace;
          var usedBytes = Math.Max(totalBytes - freeBytes, 0);

          return new DiskPayload
          {
            FreeBytes = freeBytes,
            Label = drive.Name.TrimEnd('\\'),
            Name = drive.VolumeLabel,
            TotalBytes = totalBytes,
            UsedBytes = usedBytes,
            UsagePercent = 0
          };
        })
        .ToArray();

      expiresAt = now.AddSeconds(30);
    }

    var result = new List<DiskPayload>(cachedStatic.Count);
    foreach (var cachedDisk in cachedStatic)
    {
      var activityPercent = activitySampler.GetDiskActivity(cachedDisk.Label);
      result.Add(new DiskPayload
      {
        FreeBytes = cachedDisk.FreeBytes,
        Label = cachedDisk.Label,
        Name = cachedDisk.Name,
        TotalBytes = cachedDisk.TotalBytes,
        UsedBytes = cachedDisk.UsedBytes,
        UsagePercent = activityPercent
      });
    }

    return result;
  }
}

internal sealed class DiskActivitySampler : IDisposable
{
  private PdhQuery? query;
  private IntPtr diskTimeCounter;
  private IReadOnlyList<PdhNamedDouble> lastValues = Array.Empty<PdhNamedDouble>();

  public void Initialize()
  {
    try
    {
      query = new PdhQuery();
      diskTimeCounter = query.TryAddEnglishCounter(
        @"\LogicalDisk(*)\% Disk Time",
        @"\PhysicalDisk(*)\% Disk Time"
      );
      if (diskTimeCounter != IntPtr.Zero)
      {
        query.Collect();
      }
    }
    catch
    {
      Cleanup();
    }
  }

  public void Collect()
  {
    if (query is null || diskTimeCounter == IntPtr.Zero)
    {
      return;
    }

    try
    {
      query.Collect();
      lastValues = query.GetDoubleArray(diskTimeCounter);
    }
    catch
    {
      Cleanup();
    }
  }

  public double GetDiskActivity(string driveName)
  {
    var targetLetter = driveName.TrimEnd('\\').ToUpperInvariant();

    foreach (var val in lastValues)
    {
      if (val.Name.Equals("_Total", StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      // Для LogicalDisk имя инстанса будет "C:", "D:"
      // Для PhysicalDisk имя инстанса будет "0 C:", "1 D:", "0 C: D:"
      if (val.Name.Equals(targetLetter, StringComparison.OrdinalIgnoreCase) ||
          val.Name.Contains(targetLetter, StringComparison.OrdinalIgnoreCase))
      {
        return Math.Round(Math.Clamp(val.Value, 0, 100), 1);
      }
    }

    return 0;
  }

  private void Cleanup()
  {
    query?.Dispose();
    query = null;
    diskTimeCounter = IntPtr.Zero;
    lastValues = Array.Empty<PdhNamedDouble>();
  }

  public void Dispose()
  {
    Cleanup();
  }
}

internal sealed class PdhQuery : IDisposable
{
  private const uint PdhFmtDouble = 0x00000200;
  private const uint PdhFmtLarge = 0x00000400;
  private const uint PdhFmtNoCap100 = 0x00008000;
  private const uint PdhMoreData = 0x800007D2;
  private static readonly uint[] ValidStatuses = {0, 1};
  private readonly IntPtr handle;

  public PdhQuery()
  {
    var status = PdhNative.PdhOpenQuery(IntPtr.Zero, IntPtr.Zero, out handle);

    if (status != 0)
    {
      throw new InvalidOperationException($"PdhOpenQuery failed with 0x{status:x8}");
    }
  }

  public IntPtr TryAddEnglishCounter(params string[] paths)
  {
    foreach (var path in paths)
    {
      var status = PdhNative.PdhAddEnglishCounter(handle, path, IntPtr.Zero, out var counterHandle);

      if (status == 0)
      {
        return counterHandle;
      }
    }

    return IntPtr.Zero;
  }

  public void Collect()
  {
    _ = PdhNative.PdhCollectQueryData(handle);
  }

  public IReadOnlyList<PdhNamedDouble> GetDoubleArray(IntPtr counterHandle)
  {
    if (counterHandle == IntPtr.Zero)
    {
      return Array.Empty<PdhNamedDouble>();
    }

    uint bufferSize = 0;
    uint itemCount = 0;
    var status = PdhNative.PdhGetFormattedCounterArrayDouble(
      counterHandle,
      PdhFmtDouble | PdhFmtNoCap100,
      ref bufferSize,
      ref itemCount,
      IntPtr.Zero
    );

    if (status != 0 && status != PdhMoreData)
    {
      return Array.Empty<PdhNamedDouble>();
    }

    var buffer = Marshal.AllocHGlobal((int)bufferSize);

    try
    {
      status = PdhNative.PdhGetFormattedCounterArrayDouble(
        counterHandle,
        PdhFmtDouble | PdhFmtNoCap100,
        ref bufferSize,
        ref itemCount,
        buffer
      );

      if (status != 0)
      {
        return Array.Empty<PdhNamedDouble>();
      }

      var itemSize = Marshal.SizeOf<PDH_FMT_COUNTERVALUE_ITEM_DOUBLE>();
      var values = new List<PdhNamedDouble>((int)itemCount);

      for (var index = 0; index < itemCount; index++)
      {
        var itemPointer = IntPtr.Add(buffer, index * itemSize);
        var item = Marshal.PtrToStructure<PDH_FMT_COUNTERVALUE_ITEM_DOUBLE>(itemPointer);

        if (!ValidStatuses.Contains(item.FmtValue.CStatus))
        {
          continue;
        }

        values.Add(new PdhNamedDouble(
          Marshal.PtrToStringUni(item.Name) ?? string.Empty,
          item.FmtValue.Value
        ));
      }

      return values;
    }
    finally
    {
      Marshal.FreeHGlobal(buffer);
    }
  }

  public IReadOnlyList<PdhNamedLong> GetLongArray(IntPtr counterHandle)
  {
    if (counterHandle == IntPtr.Zero)
    {
      return Array.Empty<PdhNamedLong>();
    }

    uint bufferSize = 0;
    uint itemCount = 0;
    var status = PdhNative.PdhGetFormattedCounterArrayLarge(
      counterHandle,
      PdhFmtLarge,
      ref bufferSize,
      ref itemCount,
      IntPtr.Zero
    );

    if (status != 0 && status != PdhMoreData)
    {
      return Array.Empty<PdhNamedLong>();
    }

    var buffer = Marshal.AllocHGlobal((int)bufferSize);

    try
    {
      status = PdhNative.PdhGetFormattedCounterArrayLarge(
        counterHandle,
        PdhFmtLarge,
        ref bufferSize,
        ref itemCount,
        buffer
      );

      if (status != 0)
      {
        return Array.Empty<PdhNamedLong>();
      }

      var itemSize = Marshal.SizeOf<PDH_FMT_COUNTERVALUE_ITEM_LARGE>();
      var values = new List<PdhNamedLong>((int)itemCount);

      for (var index = 0; index < itemCount; index++)
      {
        var itemPointer = IntPtr.Add(buffer, index * itemSize);
        var item = Marshal.PtrToStructure<PDH_FMT_COUNTERVALUE_ITEM_LARGE>(itemPointer);

        if (!ValidStatuses.Contains(item.FmtValue.CStatus))
        {
          continue;
        }

        values.Add(new PdhNamedLong(
          Marshal.PtrToStringUni(item.Name) ?? string.Empty,
          item.FmtValue.Value
        ));
      }

      return values;
    }
    finally
    {
      Marshal.FreeHGlobal(buffer);
    }
  }

  public void Dispose()
  {
    if (handle != IntPtr.Zero)
    {
      _ = PdhNative.PdhCloseQuery(handle);
    }
  }
}

internal readonly record struct PdhNamedDouble(string Name, double Value);

internal readonly record struct PdhNamedLong(string Name, long Value);

internal static class PdhNative
{
  [DllImport("pdh.dll", CharSet = CharSet.Unicode)]
  public static extern uint PdhOpenQuery(IntPtr dataSource, IntPtr userData, out IntPtr query);

  [DllImport("pdh.dll", CharSet = CharSet.Unicode, EntryPoint = "PdhAddEnglishCounterW")]
  public static extern uint PdhAddEnglishCounter(
    IntPtr query,
    string fullCounterPath,
    IntPtr userData,
    out IntPtr counter
  );

  [DllImport("pdh.dll")]
  public static extern uint PdhCollectQueryData(IntPtr query);

  [DllImport("pdh.dll", CharSet = CharSet.Unicode, EntryPoint = "PdhGetFormattedCounterArrayW")]
  public static extern uint PdhGetFormattedCounterArrayDouble(
    IntPtr counter,
    uint format,
    ref uint bufferSize,
    ref uint itemCount,
    IntPtr itemBuffer
  );

  [DllImport("pdh.dll", CharSet = CharSet.Unicode, EntryPoint = "PdhGetFormattedCounterArrayW")]
  public static extern uint PdhGetFormattedCounterArrayLarge(
    IntPtr counter,
    uint format,
    ref uint bufferSize,
    ref uint itemCount,
    IntPtr itemBuffer
  );

  [DllImport("pdh.dll")]
  public static extern uint PdhCloseQuery(IntPtr query);
}

[StructLayout(LayoutKind.Sequential)]
internal struct PDH_FMT_COUNTERVALUE_DOUBLE
{
  public uint CStatus;
  public double Value;
}

[StructLayout(LayoutKind.Sequential)]
internal struct PDH_FMT_COUNTERVALUE_ITEM_DOUBLE
{
  public IntPtr Name;
  public PDH_FMT_COUNTERVALUE_DOUBLE FmtValue;
}

[StructLayout(LayoutKind.Sequential)]
internal struct PDH_FMT_COUNTERVALUE_LARGE
{
  public uint CStatus;
  public long Value;
}

[StructLayout(LayoutKind.Sequential)]
internal struct PDH_FMT_COUNTERVALUE_ITEM_LARGE
{
  public IntPtr Name;
  public PDH_FMT_COUNTERVALUE_LARGE FmtValue;
}

[StructLayout(LayoutKind.Sequential)]
internal struct FILETIME
{
  public uint dwLowDateTime;
  public uint dwHighDateTime;
}

internal static class Kernel32
{
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool GetSystemTimes(
    out FILETIME idleTime,
    out FILETIME kernelTime,
    out FILETIME userTime
  );

  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX buffer);

  [DllImport("kernel32.dll")]
  public static extern void QueryUnbiasedInterruptTime(out ulong lpUnbiasedInterruptTime);
}

internal readonly record struct GpuStaticInfo(string Name, string Vendor, long MemoryTotalBytes)
{
  public static GpuStaticInfo Load()
  {
    var displayDevice = DisplayDeviceInfo.TryGetPrimary();

    if (displayDevice is null)
    {
      return new GpuStaticInfo("GPU", string.Empty, 0);
    }

    return new GpuStaticInfo(
      displayDevice.Value.Name,
      displayDevice.Value.Vendor,
      displayDevice.Value.MemoryTotalBytes
    );
  }
}

internal readonly record struct DisplayDeviceInfo(string Name, string Vendor, long MemoryTotalBytes)
{
  public static DisplayDeviceInfo? TryGetPrimary()
  {
    var displayDevice = new DISPLAY_DEVICE
    {
      cb = Marshal.SizeOf<DISPLAY_DEVICE>(),
    };

    for (uint index = 0; User32.EnumDisplayDevices(null, index, ref displayDevice, 0); index++)
    {
      if ((displayDevice.StateFlags & DisplayDeviceStateFlags.AttachedToDesktop) == 0)
      {
        displayDevice.cb = Marshal.SizeOf<DISPLAY_DEVICE>();
        continue;
      }

      var name = string.IsNullOrWhiteSpace(displayDevice.DeviceString)
        ? "GPU"
        : displayDevice.DeviceString.Trim();
      var vendor = InferVendor(name);
      var memoryTotalBytes = TryReadAdapterMemory(displayDevice.DeviceKey);

      return new DisplayDeviceInfo(name, vendor, memoryTotalBytes);
    }

    return null;
  }

  private static long TryReadAdapterMemory(string deviceKey)
  {
    const string registryPrefix = @"\Registry\Machine\";

    if (!deviceKey.StartsWith(registryPrefix, StringComparison.OrdinalIgnoreCase))
    {
      return 0;
    }

    var subKeyPath = deviceKey[registryPrefix.Length..];

    using var registryKey = Registry.LocalMachine.OpenSubKey(subKeyPath);

    if (registryKey?.GetValue("HardwareInformation.qwMemorySize") is byte[] rawBytes &&
        rawBytes.Length >= sizeof(long))
    {
      return BitConverter.ToInt64(rawBytes, 0);
    }

    return 0;
  }

  private static string InferVendor(string name)
  {
    if (name.Contains("NVIDIA", StringComparison.OrdinalIgnoreCase))
    {
      return "NVIDIA";
    }

    if (name.Contains("AMD", StringComparison.OrdinalIgnoreCase) ||
        name.Contains("Radeon", StringComparison.OrdinalIgnoreCase))
    {
      return "AMD";
    }

    if (name.Contains("Intel", StringComparison.OrdinalIgnoreCase))
    {
      return "Intel";
    }

    return string.Empty;
  }
}

internal static class User32
{
  [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool EnumDisplayDevices(
    string? device,
    uint deviceNum,
    ref DISPLAY_DEVICE displayDevice,
    uint flags
  );
}

[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
internal struct DISPLAY_DEVICE
{
  public int cb;

  [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
  public string DeviceName;

  [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
  public string DeviceString;

  public DisplayDeviceStateFlags StateFlags;

  [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
  public string DeviceID;

  [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
  public string DeviceKey;
}

[Flags]
internal enum DisplayDeviceStateFlags : int
{
  AttachedToDesktop = 0x00000001,
}

[StructLayout(LayoutKind.Sequential)]
internal struct MEMORYSTATUSEX
{
  public int dwLength;
  public int dwMemoryLoad;
  public ulong ullTotalPhys;
  public ulong ullAvailPhys;
  public ulong ullTotalPageFile;
  public ulong ullAvailPageFile;
  public ulong ullTotalVirtual;
  public ulong ullAvailVirtual;
  public ulong ullAvailExtendedVirtual;
}

internal static class MemorySnapshot
{
  public static MemoryPayload Read()
  {
    var status = new MEMORYSTATUSEX
    {
      dwLength = Marshal.SizeOf<MEMORYSTATUSEX>(),
    };

    if (!Kernel32.GlobalMemoryStatusEx(ref status))
    {
      return new MemoryPayload();
    }

    var totalBytes = Math.Max((long)status.ullTotalPhys, 0);
    var availableBytes = Math.Max((long)status.ullAvailPhys, 0);
    var usedBytes = Math.Max(totalBytes - availableBytes, 0);

    return new MemoryPayload
    {
      AvailableBytes = availableBytes,
      CachedBytes = 0,
      CommitLimitBytes = Math.Max((long)status.ullTotalPageFile, 0),
      CommitUsedBytes = Math.Max((long)(status.ullTotalPageFile - status.ullAvailPageFile), 0),
      FreeBytes = availableBytes,
      TotalBytes = totalBytes,
      UsagePercent = totalBytes > 0 ? Math.Round(usedBytes * 100d / totalBytes, 1) : 0,
      UsedBytes = usedBytes,
    };
  }
}

internal static class SwapSnapshot
{
  public static SwapPayload Read(MemoryPayload memory)
  {
    var status = new MEMORYSTATUSEX
    {
      dwLength = Marshal.SizeOf<MEMORYSTATUSEX>(),
    };

    if (!Kernel32.GlobalMemoryStatusEx(ref status))
    {
      return new SwapPayload();
    }

    var totalPageFile = Math.Max((long)status.ullTotalPageFile - memory.TotalBytes, 0);
    var availPageFile = Math.Max((long)status.ullAvailPageFile - Math.Max(memory.TotalBytes - memory.UsedBytes, 0), 0);
    var usedBytes = Math.Max(totalPageFile - availPageFile, 0);

    return new SwapPayload
    {
      PeakUsedBytes = usedBytes,
      TotalBytes = totalPageFile,
      UsagePercent = totalPageFile > 0 ? Math.Round(usedBytes * 100d / totalPageFile, 1) : 0,
      UsedBytes = usedBytes,
    };
  }
}

internal sealed class SystemSnapshot
{
  [JsonPropertyName("architecture")]
  public required string Architecture { get; init; }

  [JsonPropertyName("build")]
  public required string Build { get; init; }

  [JsonPropertyName("buildNumber")]
  public required string BuildNumber { get; init; }

  [JsonPropertyName("caption")]
  public required string Caption { get; init; }

  [JsonPropertyName("version")]
  public required string Version { get; init; }

  public static SystemSnapshot Load()
  {
    using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
    var caption = key?.GetValue("ProductName")?.ToString() ?? "Windows";
    var buildNumber = key?.GetValue("CurrentBuildNumber")?.ToString() ?? string.Empty;
    var ubr = key?.GetValue("UBR")?.ToString() ?? string.Empty;
    var majorVersion = key?.GetValue("CurrentMajorVersionNumber")?.ToString();
    var minorVersion = key?.GetValue("CurrentMinorVersionNumber")?.ToString();
    var version = !string.IsNullOrWhiteSpace(majorVersion) && !string.IsNullOrWhiteSpace(minorVersion)
      ? $"{majorVersion}.{minorVersion}.{buildNumber}"
      : $"{Environment.OSVersion.Version.Major}.{Environment.OSVersion.Version.Minor}.{buildNumber}";

    return new SystemSnapshot
    {
      Architecture = Environment.Is64BitOperatingSystem ? "64-разрядная" : "32-разрядная",
      Build = string.Join(
        '.',
        new[] {buildNumber, ubr}.Where(value => !string.IsNullOrWhiteSpace(value))
      ),
      BuildNumber = buildNumber,
      Caption = caption,
      Version = version,
    };
  }
}

internal sealed class StatusPayload
{
  [JsonPropertyName("cpu")]
  public required CpuPayload Cpu { get; init; }

  [JsonPropertyName("disk")]
  public DiskPayload? Disk { get; init; }

  [JsonPropertyName("disks")]
  public required IReadOnlyList<DiskPayload> Disks { get; init; }

  [JsonPropertyName("gpu")]
  public required GpuPayload Gpu { get; init; }

  [JsonPropertyName("host")]
  public required string Host { get; init; }

  [JsonPropertyName("memory")]
  public required MemoryPayload Memory { get; init; }

  [JsonPropertyName("network")]
  public required NetworkPayload Network { get; init; }

  [JsonPropertyName("swap")]
  public required SwapPayload Swap { get; init; }

  [JsonPropertyName("system")]
  public required SystemSnapshot System { get; init; }

  [JsonPropertyName("timestamp")]
  public required string Timestamp { get; init; }

  [JsonPropertyName("uptimeSeconds")]
  public required long UptimeSeconds { get; init; }
}

internal sealed class CpuPayload
{
  [JsonPropertyName("cores")]
  public int Cores { get; init; }

  [JsonPropertyName("temperatureC")]
  public double? TemperatureC { get; init; }

  [JsonPropertyName("usagePercent")]
  public double UsagePercent { get; init; }
}

internal sealed class MemoryPayload
{
  [JsonPropertyName("availableBytes")]
  public long AvailableBytes { get; init; }

  [JsonPropertyName("cachedBytes")]
  public long CachedBytes { get; init; }

  [JsonPropertyName("commitLimitBytes")]
  public long CommitLimitBytes { get; init; }

  [JsonPropertyName("commitUsedBytes")]
  public long CommitUsedBytes { get; init; }

  [JsonPropertyName("freeBytes")]
  public long FreeBytes { get; init; }

  [JsonPropertyName("totalBytes")]
  public long TotalBytes { get; init; }

  [JsonPropertyName("usagePercent")]
  public double UsagePercent { get; init; }

  [JsonPropertyName("usedBytes")]
  public long UsedBytes { get; init; }
}

internal sealed class SwapPayload
{
  [JsonPropertyName("peakUsedBytes")]
  public long PeakUsedBytes { get; init; }

  [JsonPropertyName("totalBytes")]
  public long TotalBytes { get; init; }

  [JsonPropertyName("usagePercent")]
  public double UsagePercent { get; init; }

  [JsonPropertyName("usedBytes")]
  public long UsedBytes { get; init; }
}

internal sealed class DiskPayload
{
  [JsonPropertyName("freeBytes")]
  public long FreeBytes { get; init; }

  [JsonPropertyName("label")]
  public required string Label { get; init; }

  [JsonPropertyName("name")]
  public required string Name { get; init; }

  [JsonPropertyName("totalBytes")]
  public long TotalBytes { get; init; }

  [JsonPropertyName("usagePercent")]
  public double UsagePercent { get; init; }

  [JsonPropertyName("usedBytes")]
  public long UsedBytes { get; init; }
}

internal sealed class NetworkPayload
{
  [JsonPropertyName("adapter")]
  public required string Adapter { get; init; }

  [JsonPropertyName("description")]
  public required string Description { get; init; }

  [JsonPropertyName("rxBytesPerSecond")]
  public long RxBytesPerSecond { get; init; }

  [JsonPropertyName("txBytesPerSecond")]
  public long TxBytesPerSecond { get; init; }
}

internal sealed class GpuPayload
{
  [JsonPropertyName("driverVersion")]
  public required string DriverVersion { get; init; }

  [JsonPropertyName("memoryTotalBytes")]
  public long MemoryTotalBytes { get; init; }

  [JsonPropertyName("memoryUsedBytes")]
  public long MemoryUsedBytes { get; init; }

  [JsonPropertyName("name")]
  public required string Name { get; init; }

  [JsonPropertyName("temperatureC")]
  public double? TemperatureC { get; init; }

  [JsonPropertyName("usagePercent")]
  public double UsagePercent { get; init; }

  [JsonPropertyName("vendor")]
  public required string Vendor { get; init; }

  [JsonPropertyName("videoProcessor")]
  public required string VideoProcessor { get; init; }
}

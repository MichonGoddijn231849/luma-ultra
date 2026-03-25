using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using inair.api.pipeclient;

namespace LumaUltra.InairPatchSupport;

public static class DistanceCommandDebouncer
{
    private static readonly object Sync = new object();

    private static readonly TimeSpan Delay = TimeSpan.FromMilliseconds(90);

    private static float _pendingValue;

    private static int _generation;

    public static Task PushSetDistance(float value)
    {
        int generation;
        lock (Sync)
        {
            _pendingValue = value;
            generation = ++_generation;
        }

        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay(Delay).ConfigureAwait(false);
                float distanceToSend;
                lock (Sync)
                {
                    if (generation != _generation)
                    {
                        return;
                    }

                    distanceToSend = _pendingValue;
                }

                await SendDistanceAsync(distanceToSend).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                Log("Distance debounce failed: " + ex);
            }
        });

        return Task.CompletedTask;
    }

    private static async Task SendDistanceAsync(float value)
    {
        Type serverType = Type.GetType("inair.dotnet.pipeserver.InAirPipeServer, inair.api.pipeserver", throwOnError: true);
        object server = serverType.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static)?.GetValue(null)
            ?? throw new InvalidOperationException("Could not resolve InAirPipeServer.Instance.");

        MethodInfo pushCommand = serverType.GetMethod("PushCommand", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Could not resolve InAirPipeServer.PushCommand.");

        InAirPipeMessage message = new InAirPipeMessage(value.ToString(CultureInfo.InvariantCulture))
        {
            command = InAirPipeMessage.Command.SetDistance
        };

        Task task = (Task)pushCommand.Invoke(server, new object[] { message });
        if (task != null)
        {
            await task.ConfigureAwait(false);
        }
    }

    private static void Log(string message)
    {
        try
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string logDir = Path.Combine(localAppData, "INAIR", "logs");
            Directory.CreateDirectory(logDir);
            File.AppendAllText(Path.Combine(logDir, "luma-patch.log"), $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {message}{Environment.NewLine}");
        }
        catch
        {
        }
    }
}

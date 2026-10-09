namespace BookTrace.Api.Auth;

/// <summary>
/// 連續登入失敗太多次就暫時鎖住登入。這是單一使用者的書房，所以整站共用一個計數，記憶體用量固定。
/// </summary>
public sealed class LoginThrottle(TimeProvider timeProvider)
{
    public const int MaxFailures = 5;
    public static readonly TimeSpan LockDuration = TimeSpan.FromMinutes(5);

    private readonly object gate = new();
    private int failures;
    private DateTimeOffset lockedUntil;

    public bool IsLocked(out TimeSpan retryAfter)
    {
        lock (gate)
        {
            retryAfter = lockedUntil - timeProvider.GetUtcNow();
            if (retryAfter > TimeSpan.Zero)
            {
                return true;
            }

            retryAfter = TimeSpan.Zero;
            return false;
        }
    }

    public void RecordFailure()
    {
        lock (gate)
        {
            if (++failures >= MaxFailures)
            {
                failures = 0;
                lockedUntil = timeProvider.GetUtcNow() + LockDuration;
            }
        }
    }

    public void Reset()
    {
        lock (gate)
        {
            failures = 0;
        }
    }
}

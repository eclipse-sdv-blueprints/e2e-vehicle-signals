package org.eclipse.sdv.fleet.analysis;

public class InfluxStatsConfig {
  private static final long DEFAULT_INTERVAL_SECONDS = 30;
  private static final long DEFAULT_INITIAL_DELAY_SECONDS = 10;
  private final long intervalSeconds;
  private final long initialDelaySeconds;

  private InfluxStatsConfig(long intervalSeconds, long initialDelaySeconds) {
    this.intervalSeconds = intervalSeconds;
    this.initialDelaySeconds = initialDelaySeconds;
  }

  public static InfluxStatsConfig fromEnv() {
    String raw =
        System.getProperty(
            "INFLUXDB_STATS_INTERVAL_SECONDS",
            System.getenv("INFLUXDB_STATS_INTERVAL_SECONDS"));
    long interval = parseInterval(raw);
    String rawDelay =
        System.getProperty(
            "INFLUXDB_STATS_INITIAL_DELAY_SECONDS",
            System.getenv("INFLUXDB_STATS_INITIAL_DELAY_SECONDS"));
    long initialDelay = parseInitialDelay(rawDelay);
    return new InfluxStatsConfig(interval, initialDelay);
  }

  public long getIntervalSeconds() {
    return intervalSeconds;
  }

  public long getInitialDelaySeconds() {
    return initialDelaySeconds;
  }

  private static long parseInterval(String raw) {
    if (raw == null || raw.isBlank()) {
      return DEFAULT_INTERVAL_SECONDS;
    }
    try {
      long value = Long.parseLong(raw.trim());
      return value > 0 ? value : DEFAULT_INTERVAL_SECONDS;
    } catch (NumberFormatException ex) {
      return DEFAULT_INTERVAL_SECONDS;
    }
  }

  private static long parseInitialDelay(String raw) {
    if (raw == null || raw.isBlank()) {
      return DEFAULT_INITIAL_DELAY_SECONDS;
    }
    try {
      long value = Long.parseLong(raw.trim());
      return value >= 0 ? value : DEFAULT_INITIAL_DELAY_SECONDS;
    } catch (NumberFormatException ex) {
      return DEFAULT_INITIAL_DELAY_SECONDS;
    }
  }
}

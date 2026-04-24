package org.eclipse.sdv.fleet.analysis;

public class FleetAnalysisSummary {
  private int vehicleCount;
  private double averageSpeedKph;
  private double minBatterySoc;
  private double maxBatterySoc;
  private long brakingVehicles;

  public int getVehicleCount() {
    return vehicleCount;
  }

  public void setVehicleCount(int vehicleCount) {
    this.vehicleCount = vehicleCount;
  }

  public double getAverageSpeedKph() {
    return averageSpeedKph;
  }

  public void setAverageSpeedKph(double averageSpeedKph) {
    this.averageSpeedKph = averageSpeedKph;
  }

  public double getMinBatterySoc() {
    return minBatterySoc;
  }

  public void setMinBatterySoc(double minBatterySoc) {
    this.minBatterySoc = minBatterySoc;
  }

  public double getMaxBatterySoc() {
    return maxBatterySoc;
  }

  public void setMaxBatterySoc(double maxBatterySoc) {
    this.maxBatterySoc = maxBatterySoc;
  }

  public long getBrakingVehicles() {
    return brakingVehicles;
  }

  public void setBrakingVehicles(long brakingVehicles) {
    this.brakingVehicles = brakingVehicles;
  }
}

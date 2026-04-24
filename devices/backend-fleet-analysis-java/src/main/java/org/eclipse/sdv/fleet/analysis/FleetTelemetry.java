package org.eclipse.sdv.fleet.analysis;

import java.time.Instant;

public class FleetTelemetry {
  private String vehicleId;
  private double speedKph;
  private double batterySoc;
  private boolean brakeActive;
  private Instant updatedAt;

  public String getVehicleId() {
    return vehicleId;
  }

  public void setVehicleId(String vehicleId) {
    this.vehicleId = vehicleId;
  }

  public double getSpeedKph() {
    return speedKph;
  }

  public void setSpeedKph(double speedKph) {
    this.speedKph = speedKph;
  }

  public double getBatterySoc() {
    return batterySoc;
  }

  public void setBatterySoc(double batterySoc) {
    this.batterySoc = batterySoc;
  }

  public boolean isBrakeActive() {
    return brakeActive;
  }

  public void setBrakeActive(boolean brakeActive) {
    this.brakeActive = brakeActive;
  }

  public Instant getUpdatedAt() {
    return updatedAt;
  }

  public void setUpdatedAt(Instant updatedAt) {
    this.updatedAt = updatedAt;
  }
}

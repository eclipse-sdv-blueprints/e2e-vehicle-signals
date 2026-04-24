package org.eclipse.sdv.fleet.analysis;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import java.util.List;

@Path("/analysis")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class FleetAnalysisResource {

  @POST
  @Path("/summary")
  public FleetAnalysisSummary summarize(List<FleetTelemetry> telemetry) {
    FleetAnalysisSummary summary = new FleetAnalysisSummary();
    if (telemetry == null || telemetry.isEmpty()) {
      summary.setVehicleCount(0);
      summary.setAverageSpeedKph(0.0);
      summary.setMinBatterySoc(0.0);
      summary.setMaxBatterySoc(0.0);
      summary.setBrakingVehicles(0);
      return summary;
    }

    summary.setVehicleCount(telemetry.size());
    summary.setAverageSpeedKph(
        telemetry.stream().mapToDouble(FleetTelemetry::getSpeedKph).average().orElse(0.0));
    summary.setMinBatterySoc(
        telemetry.stream().mapToDouble(FleetTelemetry::getBatterySoc).min().orElse(0.0));
    summary.setMaxBatterySoc(
        telemetry.stream().mapToDouble(FleetTelemetry::getBatterySoc).max().orElse(0.0));
    summary.setBrakingVehicles(telemetry.stream().filter(FleetTelemetry::isBrakeActive).count());

    return summary;
  }
}

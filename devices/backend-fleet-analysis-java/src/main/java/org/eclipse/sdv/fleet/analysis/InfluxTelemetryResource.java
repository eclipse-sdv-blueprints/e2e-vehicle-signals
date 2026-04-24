package org.eclipse.sdv.fleet.analysis;

import jakarta.inject.Inject;
import jakarta.ws.rs.BadRequestException;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/telemetry")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class InfluxTelemetryResource {

  @Inject
  private InfluxDbWriter influxDbWriter;

  @POST
  @Path("/ingest")
  public InfluxWriteResult ingest(InfluxTelemetryPayload payload) {
    if (payload == null) {
      throw new BadRequestException("Payload is required.");
    }

    if (payload.getVin() == null || payload.getVin().isBlank()) {
      throw new BadRequestException("vin is required.");
    }

    if (payload.getTrigger() == null || payload.getTrigger().isBlank()) {
      throw new BadRequestException("trigger is required.");
    }

    if (payload.getCreatedDateTime() == null) {
      throw new BadRequestException("createdDateTime is required.");
    }

    boolean wroteHeader = false;
    boolean wroteSnapshot = false;

    if (payload.getHeader() != null) {
      influxDbWriter.writeHeader(
          payload.getVin(),
          payload.getTrigger(),
          payload.getCreatedDateTime(),
          payload.getHeader());
      wroteHeader = true;
    }

    if (payload.getSnapshot() != null) {
      influxDbWriter.writeSnapshot(
          payload.getVin(),
          payload.getTrigger(),
          payload.getCreatedDateTime(),
          payload.getSnapshot());
      wroteSnapshot = true;
    }

    if (!wroteHeader && !wroteSnapshot) {
      throw new BadRequestException("Provide header and/or snapshot data to write.");
    }

    return new InfluxWriteResult(wroteHeader, wroteSnapshot);
  }
}

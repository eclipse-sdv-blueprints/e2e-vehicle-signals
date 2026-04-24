package org.eclipse.sdv.fleet.analysis;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/analysis")
@Produces(MediaType.APPLICATION_JSON)
public class FleetStatsResource {

  @Inject
  private InfluxStatsService statsService;

  @GET
  @Path("/stats")
  public FleetStatsSummary getStats() {
    FleetStatsSummary stats = statsService.getLatestStats(true);
    return stats == null ? new FleetStatsSummary() : stats;
  }
}

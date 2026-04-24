package org.eclipse.sdv.fleet.analysis;

public class InfluxWriteResult {
  private boolean headerWritten;
  private boolean snapshotWritten;

  public InfluxWriteResult() {
  }

  public InfluxWriteResult(boolean headerWritten, boolean snapshotWritten) {
    this.headerWritten = headerWritten;
    this.snapshotWritten = snapshotWritten;
  }

  public boolean isHeaderWritten() {
    return headerWritten;
  }

  public void setHeaderWritten(boolean headerWritten) {
    this.headerWritten = headerWritten;
  }

  public boolean isSnapshotWritten() {
    return snapshotWritten;
  }

  public void setSnapshotWritten(boolean snapshotWritten) {
    this.snapshotWritten = snapshotWritten;
  }
}

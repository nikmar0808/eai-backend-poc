package com.utility.ingestion;

import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.api.dto.MeterReadingRequest;
import com.utility.ingestion.api.dto.TransformationResponse;

import java.time.OffsetDateTime;
import java.util.List;

/** Sample data shared by the tests. */
public final class TestData {

    private TestData() {
    }

    public static final String VALID_JSON = """
            {"meter_id":"MTR-POC2-001","grid_zone":"ZONE-A",
             "readings":[{"timestamp":"2026-10-09T00:00:00Z","kwh_value":12.5,"voltage":230.0}]}
            """;

    /** What python-validator answers for the valid request. */
    public static final String PYTHON_RESPONSE_JSON = """
            {"message":"ok",
             "metadata":{"processed_asset":"MTR-POC2-001","regional_zone":"ZONE-A","intervals_saved":1},
             "analytics_summary":{"cumulative_kwh":12.5,"average_load_per_interval":12.5}}
            """;

    public static MeterReadingRequest reading(Double kwhValue, Double voltage) {
        return new MeterReadingRequest(OffsetDateTime.parse("2026-10-09T00:00:00Z"), kwhValue, voltage);
    }

    public static BulkIngestionRequest request(String meterId, String gridZone, List<MeterReadingRequest> readings) {
        return new BulkIngestionRequest(meterId, gridZone, readings);
    }

    public static BulkIngestionRequest validRequest() {
        return request("MTR-POC2-001", "ZONE-A", List.of(reading(12.5, 230.0)));
    }

    public static TransformationResponse response() {
        return new TransformationResponse(
                "ok",
                new TransformationResponse.Metadata("MTR-POC2-001", "ZONE-A", 1),
                new TransformationResponse.AnalyticsSummary(12.5, 12.5));
    }
}

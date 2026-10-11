package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;

public record MeterReadingRequest(
        @JsonProperty("timestamp")
        @NotNull(message = "Timestamp cannot be null")
        OffsetDateTime timestamp,

        @JsonProperty("kwh_value")
        @NotNull(message = "KWH value cannot be null")
        @Positive(message = "KWH value must be greater than zero")
        Double kwhValue,

        @JsonProperty("voltage")
        @DecimalMin(value = "100.0", message = "Voltage must be at least 100")
        @DecimalMax(value = "300.0", message = "Voltage must be at most 300")
        Double voltage
) {
}

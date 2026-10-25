package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;

public record MeterReadingRequest(
        @JsonProperty("timestamp")
        @NotNull(message = "Timestamp cannot be null")
        @JsonDeserialize(using = StrictOffsetDateTimeDeserializer.class)     // strict: a string, a real offset (D29, D37)
        OffsetDateTime timestamp,

        @JsonProperty("kwh_value")
        @NotNull(message = "KWH value cannot be null")
        @Positive(message = "KWH value must be greater than zero")
        @DecimalMax(value = "1000000.0", message = "KWH value must be at most 1000000")
        Double kwhValue,

        @JsonProperty("voltage")
        @DecimalMin(value = "100.0", message = "Voltage must be at least 100")
        @DecimalMax(value = "300.0", message = "Voltage must be at most 300")
        Double voltage
) {
}

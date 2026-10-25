package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

public record BulkIngestionRequest(
        @JsonProperty("meter_id")
        @NotBlank(message = "Meter ID cannot be blank")
        @Size(min = 5, max = 20, message = "Meter ID must be between 5 and 20 characters")
        // No control characters (U+0000 to U+001F, U+007F): PostgreSQL text cannot store NUL (finding D39).
        @Pattern(regexp = "^[^\\x00-\\x1F\\x7F]+$", message = "Meter ID must not contain control characters")
        String meterId,

        @JsonProperty("grid_zone")
        @NotBlank(message = "Grid Zone cannot be blank")
        @Size(max = 50, message = "Grid Zone must be at most 50 characters")
        // At least one character that is neither whitespace nor a control character. A plain \S would not do: NUL is
        // not whitespace, so \S accepts it (D39).
        @Pattern(regexp = "^[^\\x00-\\x1F\\x7F]*[^\\s\\x00-\\x1F\\x7F][^\\x00-\\x1F\\x7F]*$",
                message = "Grid Zone must contain a visible character and no control characters")
        String gridZone,

        @NotEmpty(message = "Readings array cannot be empty")
        @Size(max = 1000, message = "At most 1000 readings per request")
        // Container-element constraints: @NotNull applies to EACH element, so [null] is refused (finding D36);
        // @Valid on the element type replaces the old @Valid on the list and validates each reading.
        List<@NotNull(message = "A reading must not be null") @Valid MeterReadingRequest> readings
) {
}

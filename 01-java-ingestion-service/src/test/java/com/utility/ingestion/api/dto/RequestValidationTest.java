package com.utility.ingestion.api.dto;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.MethodSource;

import java.time.OffsetDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static com.utility.ingestion.TestData.reading;
import static com.utility.ingestion.TestData.request;
import static com.utility.ingestion.TestData.validRequest;
import static org.assertj.core.api.Assertions.assertThat;

class RequestValidationTest {

    private static Validator validator;

    @BeforeAll
    static void createValidator() {
        validator = Validation.buildDefaultValidatorFactory().getValidator();
    }

    /** The set of violated property paths; a set, because a rule may be reported more than once for a record. */
    private static Set<String> violatedPaths(BulkIngestionRequest request) {
        return validator.validate(request).stream()
                .map(violation -> violation.getPropertyPath().toString())
                .collect(Collectors.toSet());
    }

    @Test
    void aValidRequestHasNoViolations() {
        assertThat(violatedPaths(validRequest())).isEmpty();
    }

    @ParameterizedTest(name = "meter id of {0} characters -> violation: {1}")
    @CsvSource({"4,true", "5,false", "20,false", "21,true"})
    void meterIdMustBeFiveToTwentyCharacters(int length, boolean violated) {
        Set<String> paths = violatedPaths(request("M".repeat(length), "ZONE-A", List.of(reading(12.5, 230.0))));
        assertThat(paths.contains("meterId")).isEqualTo(violated);
    }

    static Stream<Arguments> gridZones() {
        return Stream.of(
                Arguments.of(null, true, "null"),
                Arguments.of("", true, "empty"),
                Arguments.of(" ", true, "one space"),
                Arguments.of("   ", true, "spaces only"),
                Arguments.of("Z", false, "one character"),
                Arguments.of("Z".repeat(50), false, "50 characters"),
                Arguments.of("Z".repeat(51), true, "51 characters"));
    }

    @ParameterizedTest(name = "grid zone: {2} -> violation: {1}")
    @MethodSource("gridZones")
    void gridZoneMustBeNonBlankAndAtMostFiftyCharacters(String zone, boolean violated, String description) {
        Set<String> paths = violatedPaths(request("MTR-POC2-001", zone, List.of(reading(12.5, 230.0))));
        assertThat(paths.contains("gridZone")).isEqualTo(violated);
    }

    @ParameterizedTest(name = "{0} readings -> violation: {1}")
    @CsvSource({"0,true", "1,false", "1000,false", "1001,true"})
    void readingsMustContainOneToOneThousandItems(int count, boolean violated) {
        Set<String> paths = violatedPaths(
                request("MTR-POC2-001", "ZONE-A", Collections.nCopies(count, reading(12.5, 230.0))));
        assertThat(paths.contains("readings")).isEqualTo(violated);
    }

    @Test
    void aMissingReadingsListIsRejected() {
        assertThat(violatedPaths(request("MTR-POC2-001", "ZONE-A", null))).contains("readings");
    }

    @ParameterizedTest(name = "kwh_value {0} -> violation: {1}")
    @CsvSource(value = {"-1,true", "0,true", "0.001,false", "NIL,true"}, nullValues = "NIL")
    void kwhValueMustBeStrictlyPositive(Double kwh, boolean violated) {
        Set<String> paths = violatedPaths(request("MTR-POC2-001", "ZONE-A", List.of(reading(kwh, 230.0))));
        assertThat(paths.contains("readings[0].kwhValue")).isEqualTo(violated);
    }

    // Upper bound of the contract (maximum: 1000000). Inclusive: the bound itself is valid.
    @ParameterizedTest(name = "kwh_value {0} -> violation: {1}")
    @CsvSource({"1000000,false", "1000000.01,true"})
    void kwhValueHasAnUpperBound(Double kwh, boolean violated) {
        Set<String> paths = violatedPaths(request("MTR-POC2-001", "ZONE-A", List.of(reading(kwh, 230.0))));
        assertThat(paths.contains("readings[0].kwhValue")).isEqualTo(violated);
    }

    @ParameterizedTest(name = "voltage {0} -> violation: {1}")
    @CsvSource(value = {"NIL,false", "99.99,true", "100,false", "300,false", "300.01,true"}, nullValues = "NIL")
    void voltageIsOptionalButMustBeBetween100And300(Double voltage, boolean violated) {
        Set<String> paths = violatedPaths(request("MTR-POC2-001", "ZONE-A", List.of(reading(12.5, voltage))));
        assertThat(paths.contains("readings[0].voltage")).isEqualTo(violated);
    }

    @Test
    void aMissingTimestampIsRejected() {
        BulkIngestionRequest request = request("MTR-POC2-001", "ZONE-A",
                List.of(new MeterReadingRequest((OffsetDateTime) null, 12.5, null)));
        assertThat(violatedPaths(request)).contains("readings[0].timestamp");
    }

    @Test
    void everyViolationIsReportedTogetherNotJustTheFirst() {
        BulkIngestionRequest request = request("M1", "ZONE-A", List.of(reading(12.5, 50.0)));
        assertThat(violatedPaths(request)).containsExactlyInAnyOrder("meterId", "readings[0].voltage");
    }
}

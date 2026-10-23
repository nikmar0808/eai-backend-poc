package com.utility.ingestion.configuration;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;

@Configuration
public class JwtDecoderConfiguration {

    // JwtDecoder is the interface the resource-server filter calls: "give me the verified Jwt for this token text, or
    // throw". NimbusJwtDecoder is Spring's implementation on top of the Nimbus JOSE library.
    @Bean
    public JwtDecoder jwtDecoder(SecurityProperties properties) {
        // withJwkSetUri: verify signatures with the public keys published at this URL. Nothing is fetched here:
        // the keys are loaded when the first token arrives and then cached; an unknown key id (kid) triggers a
        // refresh, which is how Keycloak's key rotation reaches the gateway without a restart. RS256 is the default
        // algorithm and what Keycloak signs with.
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withJwkSetUri(properties.jwkSetUri()).build();

        // Replaces the default validators with ours: time + issuer + audience (the signature is checked before this).
        decoder.setJwtValidator(JwtValidatorFactory.create(properties.issuer(), properties.audience()));
        return decoder;
    }
}

"""Talks to the schema registry (Apicurio Registry 3, Core API v3). Standard library only, so it runs anywhere Python does.

  register URL               Registers every event schema of this repository, with its rules. Safe to run again:
                             the same content finds the existing version instead of making a new one.
  check URL BASE NEW         Would NEW be accepted as the next version after BASE, under the BACKWARD rule? Registers
                             BASE in a throw-away artifact, then asks the registry with dryRun=true. Exit 1 if not.

URL is the registry's base address, for example http://127.0.0.1:8085 (on this machine) or
http://schema-registry:8080 (inside Compose).
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "/apis/registry/v3"
# What is registered: (group, artifact id, schema file). The artifact id follows the "<topic>-value" convention that
# Kafka serializers use to find a topic's value schema.
SCHEMAS = [("default", "meter-readings-stored-value", "docs/api/events/readings-stored.schema.json")]
RULES = [("VALIDITY", "FULL"), ("COMPATIBILITY", "BACKWARD")]


def call(method: str, url: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode() or "{}"
            return response.status, json.loads(text)
    except urllib.error.HTTPError as error:
        text = error.read().decode()
        try:
            return error.code, json.loads(text)
        except json.JSONDecodeError:
            return error.code, text


def wait_until_up(base: str) -> None:
    for _ in range(60):
        try:
            status, _ = call("GET", f"{base}{API}/system/info")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit(f"registry at {base} did not answer within two minutes")


def version_body(text: str, version: str | None = None) -> dict:
    body: dict = {"content": {"content": text, "contentType": "application/json"}}
    if version:
        body["version"] = version
    return body


def add_rules(base: str, group: str, artifact: str, rules: list[tuple[str, str]]) -> None:
    for rule_type, config in rules:
        status, answer = call("POST", f"{base}{API}/groups/{group}/artifacts/{artifact}/rules",
                              {"ruleType": rule_type, "config": config})
        if status == 409:            # the rule is already there: set it again, in case its configuration changed
            status, answer = call("PUT", f"{base}{API}/groups/{group}/artifacts/{artifact}/rules/{rule_type}",
                                  {"ruleType": rule_type, "config": config})
        if status not in (200, 204):
            raise SystemExit(f"rule {rule_type} on {artifact}: HTTP {status} {answer}")
        print(f"  rule {rule_type} = {config}")


def register(base: str) -> int:
    wait_until_up(base)
    for group, artifact, path in SCHEMAS:
        text = Path(path).read_text(encoding="utf-8")
        status, answer = call("POST", f"{base}{API}/groups/{group}/artifacts?ifExists=FIND_OR_CREATE_VERSION",
                              {"artifactId": artifact, "artifactType": "JSON", "firstVersion": version_body(text)})
        if status != 200:
            print(f"{group}/{artifact}: HTTP {status} {answer}")
            return 1
        version = answer.get("version", {}).get("version") if isinstance(answer, dict) else None
        print(f"{group}/{artifact}: version {version}")
        add_rules(base, group, artifact, RULES)
    return 0


def check(base: str, old_path: str, new_path: str) -> int:
    wait_until_up(base)
    group, artifact = "compat-check", f"check-{int(time.time() * 1000)}"
    old_text, new_text = (Path(p).read_text(encoding="utf-8") for p in (old_path, new_path))
    status, answer = call("POST", f"{base}{API}/groups/{group}/artifacts",
                          {"artifactId": artifact, "artifactType": "JSON", "firstVersion": version_body(old_text, "1")})
    if status != 200:
        print(f"could not register the old schema: HTTP {status} {answer}")
        return 1
    add_rules(base, group, artifact, [("COMPATIBILITY", "BACKWARD")])
    status, answer = call("POST", f"{base}{API}/groups/{group}/artifacts/{artifact}/versions?dryRun=true",
                          version_body(new_text, "2"))
    if status == 200:
        print("compatible: consumers using the new schema can still read events written with the old one")
        return 0
    print(f"NOT compatible (HTTP {status}):")
    causes = answer.get("causes", []) if isinstance(answer, dict) else []
    for cause in causes:
        print(f"  {cause.get('context', '')}: {cause.get('description', '')}")
    if not causes:
        print(f"  {answer}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "register":
        sys.exit(register(sys.argv[2].rstrip("/")))
    if len(sys.argv) == 5 and sys.argv[1] == "check":
        sys.exit(check(sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4]))
    print(__doc__)
    sys.exit(2)

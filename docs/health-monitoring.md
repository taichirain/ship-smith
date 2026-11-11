# Project health monitoring

A project is healthy only when every configured HTTP probe and every expected
Compose service is healthy. `healthcheck_url` remains the primary release check;
`healthcheck_urls` adds up to ten monitoring probes using the same timeout and
expected HTTP status. Add the public landing page alongside the API readiness
endpoint. The project editor shows each probe and the failure reason.

The agent resolves services using the current Compose file and enabled profiles.
Inactive profile containers, orphans and one-off migration containers are excluded;
a missing expected service is unhealthy. A failed Docker query is unknown rather
than healthy. HTTP checks do not override a broken container.

`healthcheck_failure_threshold` defaults to two consecutive heartbeat failures.
The first failure is unknown/pending; reaching the threshold emits the existing
health_unhealthy event, and recovery resolves the panel alert and emits
health_recovered. Healthy samples reset the count. Deployments and intentional
project stops retain their existing unknown/stopped states. External delivery
still requires an enabled notification channel and project subscription.

Database migration: 0025 adds two columns, preserving all existing probes.
Upgrade the API and agents together. The old API can run with the added columns;
rollback need not drop columns or restore application data. Agent wheel downloads
must be rebuilt with the new code. Do not start the retired workers profile when
light-workers is active.

For Alpha Forge keep http://127.0.0.1:18290/ready and add
http://127.0.0.1:18290/ to healthcheck_urls. For Training keep its frontend check
and add http://127.0.0.1:18294/ready. Validate frontend failure with API still
healthy in an isolated Compose project; never stop live Alpha writers to test
monitoring.

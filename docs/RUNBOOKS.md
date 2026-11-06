# Runbooks

14 runbooks seed the knowledge repo. Each becomes `knowledge/runbooks/RB-xx.md` with front matter (id, title, category, platforms, versions, signals, source). Hosts, ports and names are generic; nothing comes from a real environment.

Every step is tagged: **[read]** is safe to run at any time; **[change]** changes state, so the engineer decides and keeps a rollback.

| ID | Runbook | Category | Based on |
| --- | --- | --- | --- |
| RB-01 | Integration Server node down or not responding | OUTAGE | Field experience |
| RB-02 | JDBC adapter cannot get a connection from its pool | POOL | IBM Community thread |
| RB-03 | IS internal DB pool login timeouts | DB | Field experience |
| RB-04 | Blocking database session holds locks | DB | Field experience |
| RB-05 | Audit or document-history tablespace full | DB | Field experience |
| RB-06 | Thread pile-up from per-call password hashing on Basic auth | AUTH | Field experience |
| RB-07 | Server thread pool exhausted or threads hung | POOL | IBM docs and IBM Community thread |
| RB-08 | Terracotta active swap or cache rejoin | CLUSTER | Field experience and IBM docs |
| RB-09 | Distributed cache configuration conflict | CLUSTER | Field experience |
| RB-10 | Universal Messaging session leak | MSG | Field experience |
| RB-11 | Host swap and memory pressure | RESOURCE | Field experience |
| RB-12 | SSL "PKIX path building failed" to a partner endpoint | CONN | IBM Community thread |
| RB-13 | Token or credential rejections after a node restart | AUTH | Field experience |
| RB-14 | Safe recovery order for a clustered IS restart | OUTAGE | Field experience |

## RB-01 Integration Server node down or not responding

**Signals:** ping fails or is very slow; load average far above the core count; Admin UI does not answer; clients get timeouts.

**Check** (in order; always finish step 3)

1. [read] Host: `uptime`, `free -m`, `vmstat 5 5` (si/so for swap, r for run queue), thread count and memory of the IS process.
2. [read] Threads: 2–3 thread dumps 30 s apart (`jstack <pid>`, or `kill -3 <pid>` which writes to wrapper.log). Group threads by top frame: auth hashing, `getConnection`, socket reads.
3. [read] Database: grep server.log for `Login has timed out`, `fail-fast`, `ORA-`, `0 available`; ask the DBA for blocking sessions. Go to RB-03, RB-04 or RB-05.
4. [read] Cluster: Terracotta status on both servers; rejoin errors in the IS log. Go to RB-08.
5. [read] Messaging: connection count to the UM port. Go to RB-10.
6. [read] Gateway and clients: server threads against the limit, new short sessions from the gateway, top APIs by calls.

**Fix:** follow the runbook for the strongest signal, then RB-14 for any restart.

**Verify:** ping returns 200, server threads well under the limit, error rate back to normal.

**Lesson:** in a real outage the DB signals were present but missed. Step 3 is never skipped.

## RB-02 JDBC adapter cannot get a connection from its pool

**Signals:** `ART.118.5053 Unable to get a connection to resource <pool>`; `ART.117.4012 Unable to run adapter service`.

**Check**

1. [read] Is the database up and reachable from the IS host?
2. [read] Did the DB user's password change, or is the account locked?
3. [read] Pool usage against max size and block timeout in the Admin UI; threads waiting in `getConnection` in a thread dump.
4. [read] What changed just before the first error: deploy, DB maintenance, network change?

**Fix**

1. [change] Fix the cause first: DB up, password updated in the connection, network restored.
2. [change] Disable and enable the adapter connection to reset the pool.
3. [change] Raise max pool size only if usage proves it, and only after checking the DB session limit.

**Verify:** the adapter service runs; no new ART.118.5053 for 15 minutes.

## RB-03 IS internal DB pool login timeouts

**Signals:** `Login has timed out`, `fail-fast`, `ISS.0128`, `threshold exceeded, 0 available` in server.log; audit queue warnings; many threads in `WmConnectionPool.getConnection` or Oracle network reads. Often hidden behind a general thread pile-up.

**Check**

1. [read] grep server.log for those strings; note first and last time and count.
2. [read] Test the internal pools (ISInternal, ISCoreAudit, DocumentHistory) in the Admin UI.
3. [read] DBA: sessions of the IS schema grouped by machine, login rate, listener log errors.
4. [read] Check whether one pool serves several functions; a shared pool means a shared failure.

**Fix**

1. [change] DBA clears dead sessions left by forced restarts.
2. [change] Restart the internal pools, or follow RB-14.
3. [change] Longer term: one pool per function, connection timeouts and validation, dead-connection detection on the DB side.

**Verify:** pool tests pass; no `Login has timed out` for 30 minutes.

## RB-04 Blocking database session holds locks

**Signals:** a backend service hangs; requests time out; threads wait in DB calls; the DB shows one session blocking others for many minutes.

**Check**

1. [read] DBA: blocking sessions and what they wait on (`v$session` rows with `blocking_session` set), with machine, program and duration.
2. [read] Match the blocking session's machine and program to an IS node and service.
3. [read] Thread dump on that node: does a live thread still own the transaction?

**Fix**

1. [change] If the owning thread is gone or the node was restarted, the DBA kills the blocking session.
2. [change] If a live service holds it, cancel that service thread in IS first; the DBA kills the session only if needed.

**Verify:** no blocking sessions; waiting requests complete.

**Note:** in a real outage one leftover audit session held a lock for 127 minutes across restarts.

## RB-05 Audit or document-history tablespace full

**Signals:** `ORA-01653: unable to extend table` (or `ORA-01654` for an index) in server.log; audit or document-history writes fail; services slow as audit queues fill.

**Check**

1. [read] DBA: used and free space in the tablespace, autoextend setting.
2. [read] Which tables grew, and is a purge job in place?

**Fix**

1. [change] DBA adds a data file or extends the tablespace.
2. [change] Purge old audit data per the retention policy.
3. [change] Longer term: reduce audit logging on busy services, schedule purges, add a free-space alert.

**Verify:** no new ORA-01653; the audit queue drains.

## RB-06 Thread pile-up from per-call password hashing on Basic auth

**Signals:** very high CPU; most HTTP handler threads in password key derivation (`PBKDF2KeyImpl.deriveKey` in thread dumps); calls arrive from the API gateway with Basic auth on every request.

**Check**

1. [read] Thread dumps: count threads in `deriveKey`; group HTTP handler threads by client IP.
2. [read] Gateway analytics: top APIs and callers by volume.
3. [read] IS Sessions page: many new 0-second sessions from the gateway.

**Fix**

1. [change] Short term: throttle the heaviest APIs at the gateway; cap the IS thread pool so the node stays responsive.
2. [change] Long term: replace per-call Basic auth between gateway and IS with mTLS or tokens.

**Verify:** threads in `deriveKey` near zero; CPU back to normal.

## RB-07 Server thread pool exhausted or threads hung

**Signals:** "no threads available" errors; requests queue; server threads at the limit while the host itself is not overloaded.

**Check**

1. [read] Statistics > System Threads in the Admin UI; use the diagnostic port if the main port does not answer.
2. [read] 2–3 thread dumps; find the shared blocking frame, or one thread holding a lock the others wait for.
3. [read] Was there a backend or DB outage just before? Pools may not have recovered.

**Fix**

1. [change] Cancel stuck threads tied to user services; kill a thread only if cancel fails.
2. [change] Restart internal or adapter pools after a backend outage; set pool minimum size to 0 so stale connections drop.
3. [change] Size the thread pool by testing; there is no universal formula.
4. [read] If nothing clears it, take a JVM dump for vendor support, then follow RB-14.

**Verify:** server threads back under the limit; no queued requests.

## RB-08 Terracotta active swap or cache rejoin

**Signals:** IS log shows `ISS.0033.0154E` or `0155E`, rejoin messages, or cache put timeouts; the active Terracotta server changed; a Terracotta host is swapping.

**Check**

1. [read] Status of both Terracotta servers (one active-coordinator, one passive-standby).
2. [read] Swap and memory on both Terracotta hosts.
3. [read] IS log: when did the rejoin start and end?

**Fix**

1. [read] If the disconnect happened after IS started, IS rejoins on its own; watch and wait.
2. [change] If Terracotta is swapping or stuck: stop the passive, then the active; start the intended active first, then the passive. Then restart IS nodes per RB-14.
3. [change] Longer term: size Terracotta heap and host memory so it never swaps.

**Verify:** one active and one passive; no new 0154E errors.

**Note:** if IS cannot reach the cache at startup, it follows its "Action on Startup Error" setting, and clustering does not work until the connection is fixed.

## RB-09 Distributed cache configuration conflict

**Signals:** one cache fails to start, or IS logs a configuration mismatch, for example a different `maxEntriesInCache` between nodes or against the cache already on the server array.

**Check**

1. [read] Compare that cache's settings on every IS node and on the server array.

**Fix**

1. [change] Make the setting the same everywhere, then restart the cache manager or the node per RB-14.

**Verify:** the cache starts on all nodes; no mismatch errors.

## RB-10 Universal Messaging session leak

**Signals:** connections from each IS node to the UM port grow over days; `channel object is obsolete` in logs; IS thread count grows with them.

**Check**

1. [read] `ss -tnp | grep -c '<um-host>]\?:<um-port>'` on each node. `ss` can print the address as `[::ffff:IP]:port`, so match both forms. Compare with the count right after startup.
2. [read] Run the count on a schedule and log it to see the trend.

**Fix**

1. [change] Short term: planned restart of the node with the highest count, per RB-14.
2. [change] Long term: find the client code or trigger that does not close sessions; raise a vendor case with the trend data.

**Verify:** the count stays flat over days.

## RB-11 Host swap and memory pressure

**Signals:** high si/so in vmstat; swap use climbing; long JVM pauses; everything slow.

**Check**

1. [read] `free -m`, `vmstat 5 5`, swap per process (`VmSwap` in `/proc/<pid>/status`).
2. [read] Does JVM heap plus everything else fit in RAM?

**Fix**

1. [change] Short term: planned restart of the swapped process per RB-14; free swap only when enough RAM is free.
2. [change] Long term: smaller heap or more RAM, low `vm.swappiness`, a swap alert.

**Verify:** si/so at zero under normal load.

**Note:** when swap is full, new SSH logins can hang; work from a session that is already open.

## RB-12 SSL "PKIX path building failed" to a partner endpoint

**Signals:** an outbound HTTPS call fails with `PKIX path building failed` or `unable to find valid certification path to requested target`, often right after the partner changed its certificate.

**Check**

1. [read] Get the partner's chain (`openssl s_client -connect <host>:443 -showcerts`); note the issuer and intermediates.
2. [read] Find the truststore that call uses (Security > Keystores and Certificates in the Admin UI; the JVM `cacerts` by default).
3. [read] Is the root or intermediate CA there and still valid?

**Fix**

1. [change] Back up the truststore, then import the missing root or intermediate into a separate truststore and link it in IS.
2. [change] Reload the keystore configuration or restart, per your change process.

**Verify:** the call succeeds. **Rollback:** restore the truststore backup.

## RB-13 Token or credential rejections after a node restart

**Signals:** after a restart, a partner gets 401, `Access is denied` or a token rejection on one node while the other node works.

**Check**

1. [read] Which node rejects? Compare its auth settings, keys and clock with the healthy node.
2. [read] Server log entries for the rejected calls: user, alias, reason.
3. [read] Was the token issued before the restart, and is token state shared between nodes?

**Fix**

1. [change] Align the settings; ask the partner to get a new token and resubmit.
2. [change] Longer term: token settings that survive a node restart.

**Verify:** no rejections for that partner for 30 minutes.

## RB-14 Safe recovery order for a clustered IS restart

Every step is [change]; the engineer decides each one.

1. Stop inbound traffic to the affected node: block or drain at the gateway or firewall.
2. Stop IS with a timeout; force-kill only if it does not stop; remove the stale PID file.
3. DBA clears leftover sessions from the stopped node (RB-04).
4. If Terracotta is swapped or unhealthy, restart it in order (RB-08).
5. Free swap in the background if needed (RB-11).
6. Start IS nodes one at a time; confirm the startup-complete message and a ping before the next.
7. Reopen traffic one node at a time while watching load, threads and errors.

**Verify:** all nodes healthy under normal traffic for 30 minutes.

**Rollback:** keep traffic blocked and escalate to the vendor if a node fails to start twice.

## Sources

- [Unable to get a connection to resource pool (IBM Community)](https://community.ibm.com/community/user/discussion/unable-to-get-a-connection-to-resource-pool-state-error): RB-02
- [Adapter couldn't recover DB connection, drained the thread pools (IBM Community)](https://community.ibm.com/community/user/discussion/adapter-couldnt-recover-db-connection-instead-it-drained-the-thread-pools-and-got-stuck): RB-07
- [Diagnosing Integration Server with thread dumps (webMethods 10.5 docs)](https://documentation.softwareag.com/webmethods/compendiums/v10-5/C_DevOps/devOps_compendium/to-diagnose_is_13.html): RB-07
- [When an IS in a stateful cluster cannot connect to the distributed cache (IS 10.15 docs)](https://documentation.softwareag.com/webmethods/integration_server/pie10-15/webhelp/pie-webhelp/pie-webhelp/to-installation_and_setup_10.html): RB-08
- [PKIX path building failed (IBM Community)](https://community.ibm.com/community/user/discussion/pkix-path-building-failed): RB-12
- Field experience from real outages, generalized and anonymized: RB-01, RB-03 to RB-06, RB-08 to RB-11, RB-13, RB-14

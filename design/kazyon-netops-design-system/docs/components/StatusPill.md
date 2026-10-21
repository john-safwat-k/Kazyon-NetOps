# StatusPill

The result of one diagnostic check from the dual-ping and traceroute harness.

- `label`: `IP1` (router 10.x.x.1), `IP2` (switch 10.x.x.2) or `4G` (hub detected in traceroute).
- `state`: `up` (good), `down` (critical), `hub` (info, reads "4G BACKUP": traceroute hit the 4G hub, local loop down), `skip` (IP2 is not pinged when IP1 is down).
- Dot + word, so state never relies on color alone.

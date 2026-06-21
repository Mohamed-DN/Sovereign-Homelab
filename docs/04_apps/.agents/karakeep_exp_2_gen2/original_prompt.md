# USER REQUEST
Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_exp_2_gen2
Task: We are in iteration 2 of rewriting the Karakeep runbook. The previous iteration failed Reviewer 2's checks.
Failure output: 
1. Env vars explanation used `KARAKEEP_NEXTAUTH_SECRET` instead of `NEXTAUTH_SECRET`. 
2. DR backed up `/var/lib/docker/volumes/...` instead of explicitly `/data` and `/meili_data`.

Analyze the `karakeep.md` and `stacks/karakeep/docker-compose.yml` to recommend a fix strategy that addresses these failures while keeping the file accurate to the compose file. 
Output: Write your fix strategy in `handoff.md` and notify me.

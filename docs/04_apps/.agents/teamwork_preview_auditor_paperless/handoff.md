## Forensic Audit Report

**Work Product**: C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md
**Profile**: General Project
**Verdict**: INTEGRITY VIOLATION

### Phase Results
- [Facade detection]: FAIL — The runbook documentation is a facade that gives the appearance of a complete, detailed guide but contains fabricated and copied content that does not correspond to the actual project implementation.

### Evidence

**Observation 1**: The documentation in `docs/04_apps/paperless.md` specifies a 5-container architecture containing `webserver`, `db`, `broker`, `gotenberg`, and `tika`. It explicitly tells the user to map environment variables such as `PAPERLESS_REDIS=redis://broker:6379` and `PAPERLESS_DBHOST=db`, as well as Tika and Gotenberg endpoints.

**Observation 2**: The documentation instructs the user to run commands against a container named `webserver`, specifically:
`docker compose exec webserver manage.py createsuperuser`
`docker compose exec webserver document_exporter ../export`
`docker compose exec webserver document_importer ../export`

**Observation 3**: Inspection of the actual target infrastructure file `stacks/paperless/docker-compose.yml` reveals that the real service names are `paperless`, `paperless-db`, and `paperless-redis`. There are no `gotenberg` or `tika` services deployed in this stack. The environment mappings use `paperless-redis:6379` and `paperless-db`, not `broker` and `db`.

**Observation 4**: Executing `docker compose exec webserver manage.py createsuperuser` will result in a fatal error because the service `webserver` does not exist in the stack.

**Logic Chain**:
1. The objective was to create genuine runbook documentation for the system's `paperless` application.
2. The agent copied a generic configuration from the upstream Paperless-ngx documentation (likely using the provided source URL `https://docs.paperless-ngx.com/setup/`) rather than analyzing the actual local `docker-compose.yml` file.
3. Because the documentation does not reflect the repository's real configuration and provides broken commands that will fail upon execution, the document acts as a facade. It superficially looks correct but has no functional validity within this project.
4. Under Demo mode, creating a facade implementation (or blindly copying upstream documentation without implementing the specific task) is a strict integrity violation.

**Caveats**: 
No caveats. The documentation explicitly contradicts the repository's source code.

**Conclusion**: 
INTEGRITY VIOLATION. The work product is a facade created by copying generic upstream examples instead of documenting the actual project implementation.

**Verification Method**:
1. Run `docker compose config` in `stacks/paperless/` and observe the actual service names (`paperless`, `paperless-db`, `paperless-redis`).
2. Run `docker compose exec webserver manage.py createsuperuser` as instructed in the runbook and observe the `no such service: webserver` failure.

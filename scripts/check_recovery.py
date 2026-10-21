"""Exercise missing-model failure and recovery in an isolated disposable container."""
import json
import subprocess
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def observe(port):
    for _ in range(40):
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
                health, ready = client.get("/health"), client.get("/ready")
                return {"health_status": health.status_code, "health": health.json(),
                        "ready_status": ready.status_code, "ready": ready.json()}
        except httpx.TransportError:
            time.sleep(0.25)
    raise RuntimeError("Disposable service did not start within the bounded wait")


def run():
    name = f"reclab-recovery-{uuid.uuid4().hex[:8]}"
    port = 8012
    created = False
    image = "career-reclab:0.1.0"
    try:
        docker("run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:8011", image)
        created = True
        missing = observe(port)
        docker("rm", "-f", name)
        created = False
        mount = f"type=bind,source={ROOT / 'artifacts/model.joblib'},target=/models/model.joblib,readonly"
        docker("run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:8011", "--mount", mount, image)
        created = True
        restored = observe(port)
        checks = {"missing_model_liveness_200": missing["health_status"] == 200,
                  "missing_model_readiness_503": missing["ready_status"] == 503,
                  "trusted_model_recovery_200": restored["ready_status"] == 200}
        result = {"checks": checks, "passed": all(checks.values()),
                  "missing_model": missing, "restored_model": restored,
                  "image_id": docker("image", "inspect", image, "--format", "{{.Id}}"),
                  "scope": "Isolated second container on port 8012; main demo unchanged. Recreate recovery, not zero downtime rollout."}
        destination = ROOT / "reports/operations/recovery_check.json"
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise RuntimeError("Recovery check failed")
    finally:
        if created:
            docker("rm", "-f", name)


if __name__ == "__main__":
    run()

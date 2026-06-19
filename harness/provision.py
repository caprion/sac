"""Provision Spot VMs for sac experiments. Thin wrapper around az CLI.

Usage:
    python harness/provision.py burst --name cf-spot-burst
    python harness/provision.py worker --name cf-spot-01 --size D4as_v5
    python harness/provision.py model --name cf-spot-model --size E8as_v5 --models-disk cf-models
    python harness/provision.py list
    python harness/provision.py deallocate --name cf-spot-burst

All VMs join the cloudfleet Tailscale mesh and are accessible via Tailscale SSH.
"""

import subprocess
import sys
import json
import argparse
import time
from pathlib import Path

RG = "cloudfleet-rg"
LOCATION = "centralindia"
IMAGE = "Canonical:ubuntu-24_04-lts:server:latest"
ADMIN_USER = "sumit"
SSH_KEY = "~/.ssh/id_ed25519.pub"
CLOUD_INIT_DIR = Path(__file__).parent.parent / "infra" / "cloud-init"

# Fleet Tailscale auth key — read from file or env to avoid committing
# Sumit: set TAILSCALE_AUTH_KEY env var or place in ~/.tailscale/sac-key
TAILSCALE_KEY_PATH = Path.home() / ".tailscale" / "sac-key"


def get_tailscale_key() -> str:
    """Get Tailscale auth key from env var or file."""
    import os
    key = os.environ.get("TAILSCALE_AUTH_KEY")
    if key:
        return key
    if TAILSCALE_KEY_PATH.exists():
        return TAILSCALE_KEY_PATH.read_text().strip()
    # Fallback: try to read from Azure Key Vault
    try:
        result = subprocess.run(
            ["az", "keyvault", "secret", "show", "--vault-name", "claw-agent",
             "--name", "TAILSCALE-AUTH-KEY", "--query", "value", "-o", "tsv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    print("ERROR: Tailscale auth key not found. Set TAILSCALE_AUTH_KEY env var.")
    print("  or place it in ~/.tailscale/sac-key")
    print("  or store in Key Vault as claw-agent/TAILSCALE-AUTH-KEY")
    sys.exit(1)


def build_cloud_init(hostname: str, role: str) -> str:
    """Build cloud-init YAML with hostname and tailscale key substituted."""
    template_path = CLOUD_INIT_DIR / f"spot-{role}.yml"
    if not template_path.exists():
        print(f"WARNING: No cloud-init template for role '{role}', using spot-worker.yml")
        template_path = CLOUD_INIT_DIR / "spot-worker.yml"

    content = template_path.read_text()
    key = get_tailscale_key()
    content = content.replace("SPOT_HOSTNAME", hostname)
    content = content.replace("TAILSCALE_AUTH_KEY", key)
    return content


def provision(name: str, size: str, role: str = "worker",
              models_disk: str = None, dry_run: bool = False) -> dict:
    """Provision a Spot VM."""
    cloud_init = build_cloud_init(name, role)
    cloud_init_path = Path(f"/tmp/sac-cloud-init-{name}.yml")
    cloud_init_path.write_text(cloud_init)

    cmd = [
        "az", "vm", "create",
        "--resource-group", RG,
        "--name", name,
        "--location", LOCATION,
        "--image", IMAGE,
        "--size", size,
        "--admin-username", ADMIN_USER,
        "--ssh-key-values", SSH_KEY,
        "--priority", "Spot",
        "--max-price", "-1",
        "--eviction-policy", "Delete",
        "--os-disk-size-gb", "30",
        "--public-ip-sku", "Standard",
        "--custom-data", str(cloud_init_path),
        "--tags", f"role=sac-{role}", "project=sac-experiments", "managed-by=harness",
    ]

    if models_disk:
        cmd += ["--attach-data-disks", models_disk]

    if dry_run:
        print("DRY RUN:")
        print(" ".join(cmd))
        return {"name": name, "status": "dry_run"}

    print(f"Provisioning {name} ({size}, Spot, {role})...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

    # Parse output for public IP and other details
    try:
        data = json.loads(result.stdout)
        public_ip = data.get("publicIpAddress", "none")
        private_ip = data.get("privateIpAddress", "none")
        print(f"  {name}: public IP {public_ip}, private IP {private_ip}")
        print(f"  Wait ~2 min for cloud-init. Then SSH: ssh {ADMIN_USER}@{public_ip}")
        print(f"  After Tailscale join: ssh {ADMIN_USER}@{name}")
        return {"name": name, "public_ip": public_ip, "private_ip": private_ip}
    except json.JSONDecodeError:
        print(result.stdout)
        return {"name": name, "status": "created"}


def deallocate(name: str) -> None:
    """Deallocate a Spot VM (stop compute, keep disk)."""
    print(f"Deallocating {name}...")
    subprocess.run(
        ["az", "vm", "deallocate", "--resource-group", RG, "--name", name],
        check=True
    )
    print(f"  {name} deallocated. Disk preserved. Restart with: az vm start --name {name}")


def delete(name: str) -> None:
    """Delete a Spot VM and its OS disk."""
    print(f"Deleting {name}...")
    subprocess.run(
        ["az", "vm", "delete", "--resource-group", RG, "--name", name, "--yes"],
        check=True
    )
    print(f"  {name} deleted (OS disk destroyed).")


def list_vms() -> None:
    """List all sac experiment VMs."""
    result = subprocess.run(
        ["az", "vm", "list", "--resource-group", RG,
         "--query", "[?tags.project=='sac-experiments'].{Name:name, Size:hardwareProfile.vmSize, Power:powerState, Priority:priority}"],
        capture_output=True, text=True
    )
    if result.stdout.strip() and result.stdout.strip() != "[]":
        print(result.stdout)
    else:
        print("No sac experiment VMs found.")


def main():
    parser = argparse.ArgumentParser(description="Provision Spot VMs for sac experiments")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("worker", help="Pool worker (D4as_v5, 4vCPU 16GB)")
    p.add_argument("--name", required=True)
    p.add_argument("--size", default="Standard_D4as_v5")
    p.add_argument("--dry-run", action="store_true")

    b = sub.add_parser("burst", help="Burst worker (D8as_v5, 8vCPU 32GB)")
    b.add_argument("--name", required=True)
    b.add_argument("--size", default="Standard_D8as_v5")
    b.add_argument("--dry-run", action="store_true")

    m = sub.add_parser("model", help="Model host (E8as_v5, 8vCPU 64GB)")
    m.add_argument("--name", required=True)
    m.add_argument("--size", default="Standard_E8as_v5")
    m.add_argument("--models-disk")
    m.add_argument("--dry-run", action="store_true")

    sub.add_parser("list", help="List sac experiment VMs")

    d = sub.add_parser("deallocate", help="Deallocate a Spot VM")
    d.add_argument("--name", required=True)

    dl = sub.add_parser("delete", help="Delete a Spot VM")
    dl.add_argument("--name", required=True)

    args = parser.parse_args()

    if args.command == "list":
        list_vms()
    elif args.command == "deallocate":
        deallocate(args.name)
    elif args.command == "delete":
        delete(args.name)
    elif args.command in ("worker", "burst", "model"):
        role = "model-host" if args.command == "model" else "worker"
        models_disk = getattr(args, "models_disk", None)
        provision(args.name, args.size, role, models_disk, getattr(args, "dry_run", False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

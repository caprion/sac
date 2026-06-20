"""VM lifecycle for cf-sac. Start, deallocate, status, SSH.

Usage:
    python harness/vm.py start        # Start cf-sac, wait for ready
    python harness/vm.py deallocate   # Stop compute, preserve disk
    python harness/vm.py status       # Show VM state, IP, cost
    python harness/vm.py ssh          # SSH into VM
    python harness/vm.py run --script benchmark.py --args "--exp exp1"
"""

import subprocess
import sys
import json
import time
import argparse
from pathlib import Path

RG = "cloudfleet-rg"
VM_NAME = "cf-sac"
SSH_USER = "sumit"
TAILSCALE_IP_FILE = Path.home() / ".cache" / "sac" / "cf-sac-ip"


def _az(args, timeout=60):
    """Run az CLI command, return parsed JSON or die."""
    result = subprocess.run(
        ["az"] + args, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return result.stdout.strip()


def status():
    """Show VM status, IPs, and estimated cost."""
    vm = _az(["vm", "show", "-g", RG, "-n", VM_NAME,
              "--query", "{Name:name, Power:powerState, Size:hardwareProfile.vmSize, Location:location}"])
    power = vm.get("powerState", "unknown")

    # Get IPs
    ips = _az(["vm", "list-ip-addresses", "-g", RG, "-n", VM_NAME,
               "--query", "[virtualMachine.network.publicIpAddresses[0].ipAddress, virtualMachine.network.privateIpAddresses[0]]"])
    public_ip = ips[0] if ips and ips[0] else "none"
    private_ip = ips[1] if ips and len(ips) > 1 else "none"

    # Get Tailscale IP from cache if available
    tailscale_ip = TAILSCALE_IP_FILE.read_text().strip() if TAILSCALE_IP_FILE.exists() else "unknown"

    # Cost estimate
    size = vm.get("size", "unknown")
    hourly = _size_to_cost(size)

    print(f"VM:      {VM_NAME}")
    print(f"Power:   {power}")
    print(f"Size:    {size} ({hourly}/hr)")
    print(f"Public:  {public_ip}")
    print(f"Private: {private_ip}")
    print(f"Tailscale: {tailscale_ip}")
    if power == "VM deallocated":
        print(f"Cost:    $0 compute, ~$5/mo disk")
    else:
        print(f"Cost:    {hourly}/hr compute + ~$5/mo disk")


def start():
    """Start cf-sac and wait for it to be ready."""
    print(f"Starting {VM_NAME}...")
    _az(["vm", "start", "-g", RG, "-n", VM_NAME], timeout=120)

    # Wait for running state
    for i in range(20):
        time.sleep(5)
        power = _az(["vm", "show", "-g", RG, "-n", VM_NAME, "--query", "powerState"])
        if power == "VM running":
            break
        print(f"  waiting... ({power})")

    # Get IPs — note Tailscale IP may change after VM restart
    print("Getting IP addresses...")
    for i in range(10):
        time.sleep(3)
        ips = _az(["vm", "list-ip-addresses", "-g", RG, "-n", VM_NAME,
                   "--query", "[virtualMachine.network.publicIpAddresses[0].ipAddress]"])
        public_ip = ips[0] if ips else None
        if public_ip:
            break

    if public_ip:
        print(f"Public IP: {public_ip}")
    print(f"SSH:  ssh {SSH_USER}@{public_ip or VM_NAME}")
    print(f"      (Tailscale SSH: ssh {SSH_USER}@{VM_NAME})")
    print(f"Cost: $0.444/hr (compute) + ~$5/mo (disk)")
    print(f"Don't forget: az vm deallocate -g {RG} -n {VM_NAME}")


def deallocate():
    """Deallocate cf-sac — stop compute, keep disk."""
    print(f"Deallocating {VM_NAME}...")
    _az(["vm", "deallocate", "-g", RG, "-n", VM_NAME], timeout=120)
    print("Done. Compute: $0. Disk: ~$5/mo.")
    print(f"Restart with: python harness/vm.py start")


def ssh():
    """SSH into cf-sac via Tailscale (preferred) or public IP."""
    # Try Tailscale first
    tailscale_ip = TAILSCALE_IP_FILE.read_text().strip() if TAILSCALE_IP_FILE.exists() else None
    if tailscale_ip:
        cmd = f"ssh {SSH_USER}@{tailscale_ip}"
    else:
        ips = _az(["vm", "list-ip-addresses", "-g", RG, "-n", VM_NAME,
                   "--query", "[virtualMachine.network.publicIpAddresses[0].ipAddress]"])
        public_ip = ips[0] if ips else None
        if not public_ip:
            print("ERROR: No IP found. Is the VM running?")
            sys.exit(1)
        cmd = f"ssh {SSH_USER}@{public_ip}"
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


def run(script, args):
    """Start VM, run a script via SSH, deallocate. One-shot experiment run."""
    # Check if already running
    power = _az(["vm", "show", "-g", RG, "-n", VM_NAME, "--query", "powerState"])
    was_running = (power == "VM running")

    if not was_running:
        start()

    # Run the script via SSH
    tailscale_ip = TAILSCALE_IP_FILE.read_text().strip() if TAILSCALE_IP_FILE.exists() else None
    if args:
        remote_cmd = f"cd /opt/sac && source .venv/bin/activate && python {script} {args}"
    else:
        remote_cmd = f"cd /opt/sac && source .venv/bin/activate && python {script}"

    print(f"Running: {remote_cmd}")
    subprocess.run(f'ssh {SSH_USER}@{tailscale_ip} "{remote_cmd}"', shell=True)

    if not was_running:
        deallocate()


def _size_to_cost(size):
    costs = {
        "Standard_D16as_v5": "$0.444",
        "Standard_D8as_v5": "$0.222",
        "Standard_D4as_v5": "$0.111",
        "Standard_D2as_v5": "$0.056",
        "Standard_E8as_v5": "$0.286",
        "Standard_E4as_v5": "$0.143",
    }
    return costs.get(size, "$?.???")


def main():
    parser = argparse.ArgumentParser(description="cf-sac VM lifecycle")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start cf-sac")
    sub.add_parser("deallocate", help="Deallocate cf-sac (stop compute, keep disk)")
    sub.add_parser("status", help="Show VM status, IP, cost")
    sub.add_parser("ssh", help="SSH into cf-sac")

    r = sub.add_parser("run", help="Start, run script, deallocate")
    r.add_argument("--script", required=True, help="Path to script on VM")
    r.add_argument("--args", default="", help="Arguments to pass to script")

    args = parser.parse_args()

    if args.command == "start":
        start()
    elif args.command == "deallocate":
        deallocate()
    elif args.command == "status":
        status()
    elif args.command == "ssh":
        ssh()
    elif args.command == "run":
        run(args.script, args.args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

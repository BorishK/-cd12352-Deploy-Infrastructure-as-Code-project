#!/usr/bin/env python3
"""
deploy.py — Udagram CloudFormation deploy script
Usage:
  python deploy.py network      # deploy network stack only
  python deploy.py app          # deploy application stack only
  python deploy.py all          # deploy network then app (recommended for first run)

  Optionally override the AWS profile:
  python deploy.py all --profile udacity
"""

import boto3
import json
import sys
from pathlib import Path
from botocore.exceptions import ClientError
from botocore.session import Session

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

REGION           = "us-east-1"
AWS_PROFILE      = "udacity"          # Udacity Vocareum lab credentials
NETWORK_STACK    = "udagram-network"
APP_STACK        = "udagram-app"
NETWORK_TEMPLATE = Path(__file__).parent / "network.yml"
APP_TEMPLATE     = Path(__file__).parent / "udagram.yml"
NETWORK_PARAMS   = Path(__file__).parent / "network-parameters.json"
APP_PARAMS       = Path(__file__).parent / "udagram-parameters.json"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

# Allow profile override via --profile flag: python deploy.py all --profile myprofile
if "--profile" in sys.argv:
    idx = sys.argv.index("--profile")
    AWS_PROFILE = sys.argv[idx + 1]
    sys.argv.pop(idx)
    sys.argv.pop(idx)

session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
cf = session.client("cloudformation")

print(f"  Using AWS profile : {AWS_PROFILE}")
print(f"  Region            : {REGION}")


def load_template(path: Path) -> str:
    return path.read_text()


def load_params(path: Path) -> list:
    return json.loads(path.read_text())


def stack_exists(stack_name: str) -> bool:
    try:
        cf.describe_stacks(StackName=stack_name)
        return True
    except ClientError as e:
        if "does not exist" in str(e):
            return False
        raise


def deploy_stack(stack_name: str, template_path: Path, params_path: Path):
    """Create or update a CloudFormation stack and wait for completion."""
    template_body = load_template(template_path)
    parameters    = load_params(params_path)
    capabilities  = ["CAPABILITY_NAMED_IAM"]

    exists = stack_exists(stack_name)
    action = "update_stack" if exists else "create_stack"
    verb   = "Updating" if exists else "Creating"

    print(f"\n{'='*60}")
    print(f"  {verb} stack: {stack_name}")
    print(f"{'='*60}")

    try:
        kwargs = dict(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=capabilities,
        )
        getattr(cf, action)(**kwargs)
    except ClientError as e:
        if "No updates are to be performed" in str(e):
            print("  ✓ Stack is already up-to-date — nothing to do.")
            return
        raise

    wait_for_stack(stack_name, "update" if exists else "create")
    print_outputs(stack_name)


def wait_for_stack(stack_name: str, operation: str):
    """Poll until the stack reaches a terminal state."""
    waiter_name = (
        "stack_update_complete" if operation == "update" else "stack_create_complete"
    )
    print(f"\n  Waiting for stack {operation} to complete ", end="", flush=True)
    waiter = cf.get_waiter(waiter_name)
    try:
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 15, "MaxAttempts": 80},
        )
        print(" ✓")
    except Exception:
        print(" ✗")
        print_stack_events(stack_name)
        raise


def print_outputs(stack_name: str):
    response = cf.describe_stacks(StackName=stack_name)
    outputs  = response["Stacks"][0].get("Outputs", [])
    if not outputs:
        return
    print(f"\n  Stack outputs for '{stack_name}':")
    for o in outputs:
        print(f"    {o['OutputKey']:30s}  {o['OutputValue']}")


def print_stack_events(stack_name: str):
    """Print the last 10 stack events to help diagnose failures."""
    events = cf.describe_stack_events(StackName=stack_name)["StackEvents"]
    print(f"\n  Last events for '{stack_name}':")
    for ev in events[:10]:
        status = ev.get("ResourceStatus", "")
        reason = ev.get("ResourceStatusReason", "")
        rid    = ev.get("LogicalResourceId", "")
        print(f"    [{status}] {rid} — {reason}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if target in ("network", "all"):
        deploy_stack(NETWORK_STACK, NETWORK_TEMPLATE, NETWORK_PARAMS)

    if target in ("app", "all"):
        deploy_stack(APP_STACK, APP_TEMPLATE, APP_PARAMS)

    print("\n  ✓ Done! Check outputs above for your Load Balancer URL.\n")


if __name__ == "__main__":
    main()

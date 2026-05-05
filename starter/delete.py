#!/usr/bin/env python3
"""
delete.py — Udagram CloudFormation teardown script

IMPORTANT: Empties the S3 bucket before deleting the app stack,
since CloudFormation cannot delete a non-empty bucket.

Usage:
  python delete.py app          # delete application stack only
  python delete.py network      # delete network stack only (run AFTER app)
  python delete.py all          # delete app then network (recommended)

  Optionally override the AWS profile:
  python delete.py all --profile udacity
"""

import boto3
import sys
from botocore.exceptions import ClientError

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

REGION        = "us-east-1"
AWS_PROFILE   = "udacity"          # Udacity Vocareum lab credentials
NETWORK_STACK = "udagram-network"
APP_STACK     = "udagram-app"
ENV_NAME      = "udagram"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

# Allow profile override via --profile flag: python delete.py all --profile myprofile
if "--profile" in sys.argv:
    idx = sys.argv.index("--profile")
    AWS_PROFILE = sys.argv[idx + 1]
    sys.argv.pop(idx)
    sys.argv.pop(idx)

session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
cf  = session.client("cloudformation")
s3  = session.resource("s3")

print(f"  Using AWS profile : {AWS_PROFILE}")
print(f"  Region            : {REGION}")


def stack_exists(stack_name: str) -> bool:
    try:
        cf.describe_stacks(StackName=stack_name)
        return True
    except ClientError as e:
        if "does not exist" in str(e):
            return False
        raise


def get_stack_output(stack_name: str, key: str) -> str | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        for o in response["Stacks"][0].get("Outputs", []):
            if o["OutputKey"] == key:
                return o["OutputValue"]
    except ClientError:
        pass
    return None


def empty_s3_bucket(bucket_name: str):
    """Delete all objects and versions from the bucket before stack deletion."""
    print(f"\n  Emptying S3 bucket: {bucket_name}")
    try:
        bucket = s3.Bucket(bucket_name)
        # Delete all object versions (handles versioned buckets too)
        bucket.object_versions.all().delete()
        # Delete any remaining objects (non-versioned)
        bucket.objects.all().delete()
        print(f"  ✓ Bucket emptied.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            print(f"  Bucket {bucket_name} not found — skipping.")
        else:
            raise


def delete_stack(stack_name: str):
    """Delete a CloudFormation stack and wait for completion."""
    if not stack_exists(stack_name):
        print(f"\n  Stack '{stack_name}' does not exist — skipping.")
        return

    print(f"\n{'='*60}")
    print(f"  Deleting stack: {stack_name}")
    print(f"{'='*60}")

    cf.delete_stack(StackName=stack_name)

    print(f"\n  Waiting for deletion to complete ", end="", flush=True)
    waiter = cf.get_waiter("stack_delete_complete")
    try:
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 15, "MaxAttempts": 80},
        )
        print(" ✓")
        print(f"  Stack '{stack_name}' deleted successfully.")
    except Exception:
        print(" ✗")
        print_stack_events(stack_name)
        raise


def print_stack_events(stack_name: str):
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

    confirm = input(
        f"\n  ⚠  This will DELETE the '{target}' stack(s) and all their resources.\n"
        f"  Type 'yes' to confirm: "
    ).strip().lower()

    if confirm != "yes":
        print("  Aborted.")
        sys.exit(0)

    if target in ("app", "all"):
        # Must empty S3 before stack deletion
        bucket_name = get_stack_output(APP_STACK, "S3BucketName")
        if bucket_name:
            empty_s3_bucket(bucket_name)
        delete_stack(APP_STACK)

    if target in ("network", "all"):
        delete_stack(NETWORK_STACK)

    print("\n  ✓ Teardown complete. Remember to verify in the AWS Console.\n")


if __name__ == "__main__":
    main()

# Udagram — Deploy a High-Availability Web App using CloudFormation

A complete AWS Infrastructure-as-Code (IaC) project deploying a highly available web application across two Availability Zones using CloudFormation, Python (boto3), EC2 Auto Scaling, an Application Load Balancer, S3, and CloudFront.

---

## Architecture Overview

```
Internet / Users
      │
 CloudFront (CDN)
      │
Internet Gateway
      │
 ┌────────────────────────── VPC 10.0.0.0/16 ──────────────────────────┐
 │                                                                      │
 │  Public us-east-1a          Public us-east-1b                        │
 │  ┌──────────────────┐       ┌──────────────────┐                     │
 │  │ NAT Gateway      │       │ NAT Gateway      │                     │
 │  │ Bastion Host     │       │                  │                     │
 │  └──────────────────┘       └──────────────────┘                     │
 │                                                                      │
 │            Application Load Balancer (port 80)                       │
 │                     /              \                                 │
 │  Private us-east-1a                Private us-east-1b               │
 │  ┌──────────────────┐       ┌──────────────────┐                     │
 │  │ EC2 t2.micro ×2  │       │ EC2 t2.micro ×2  │                     │
 │  │ Ubuntu 22/nginx  │       │ Ubuntu 22/nginx  │                     │
 │  └──────────────────┘       └──────────────────┘                     │
 │                     \              /                                 │
 │                      S3 Bucket (static content)                      │
 └──────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- AWS CLI configured (`aws configure`) with a user that has CloudFormation/EC2/S3/IAM permissions
- Python 3.8+ with boto3 installed (`pip install boto3`)
- AWS account in `us-east-1`

---

## Project Files

| File | Description |
|---|---|
| `network.yml` | CloudFormation template — VPC, subnets, gateways, route tables |
| `network-parameters.json` | Parameters for the network stack |
| `udagram.yml` | CloudFormation template — EC2, ALB, ASG, S3, IAM, CloudFront, Bastion |
| `udagram-parameters.json` | Parameters for the application stack |
| `deploy.py` | Python script to create/update stacks |
| `delete.py` | Python script to tear down stacks (empties S3 first) |
| `index.html` | Sample static page to upload to S3 |
| `diagram.png` | Infrastructure architecture diagram |

---

## Deployment Instructions

### Step 1 — Deploy the network stack

```bash
python deploy.py network
```

Wait for the stack to reach `CREATE_COMPLETE` (~3–4 minutes).

### Step 2 — Deploy the application stack

```bash
python deploy.py app
```

Wait for the stack to reach `CREATE_COMPLETE` (~8–12 minutes — NAT Gateways and ALB take time).

### Step 3 — Upload static content to S3

Once the app stack is deployed, get the bucket name from the stack output and upload your static page:

```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name udagram-app \
  --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
  --output text \
  --region us-east-1)

# Upload index.html
aws s3 cp index.html s3://$BUCKET/index.html
```

### Step 4 — Verify the deployment

Get the Load Balancer URL from the stack output:

```bash
aws cloudformation describe-stacks \
  --stack-name udagram-app \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
  --output text \
  --region us-east-1
```

Open the URL in your browser — you should see **"It works! Udagram, Udacity"**.

> **Note:** The UserData script on EC2 instances takes 2–4 minutes to complete after the ASG is created. If you see a 502/504, wait a few minutes and refresh.

---

## Deploy Everything in One Command

```bash
python deploy.py all
```

This deploys the network stack first, then the application stack, and prints all outputs.

---

## Teardown Instructions

⚠️ **Always delete stacks when done to avoid charges.**

```bash
python delete.py all
```

This script will:
1. Prompt for confirmation
2. Empty the S3 bucket (required before CloudFormation can delete it)
3. Delete the application stack
4. Delete the network stack

To delete stacks individually:

```bash
python delete.py app       # application stack only
python delete.py network   # network stack only (run AFTER app)
```

---

## Accessing Servers via Bastion Host

The Bastion Host is in the public subnet. To SSH into private EC2 instances:

```bash
# 1. SSH to the Bastion
BASTION_IP=$(aws cloudformation describe-stacks \
  --stack-name udagram-app \
  --query "Stacks[0].Outputs[?OutputKey=='BastionPublicIP'].OutputValue" \
  --output text --region us-east-1)

ssh -A ubuntu@$BASTION_IP

# 2. From the Bastion, SSH into a private instance
ssh ubuntu@<private-ec2-ip>
```

> **Tip:** Use `ssh -A` (agent forwarding) so your key is available on the Bastion for the second hop.

---

## Debugging Tips

- UserData logs: `/var/log/cloud-init-output.log` on EC2 instances
- If the ALB shows unhealthy targets, check nginx is running: `systemctl status nginx`
- Check S3 content was pulled: `cat /var/www/html/index.html`
- To trigger an ASG instance refresh after template changes:
  ```bash
  aws autoscaling start-instance-refresh \
    --auto-scaling-group-name udagram-asg \
    --region us-east-1
  ```

---

## Evidence of Working Deployment

**Option 1 — Working URL:**  
`http://<ALB-DNS-Name>` → displays "It works! Udagram, Udacity"

**Option 2 — Screenshots (if stack was deleted before submission):**
- Screenshot of CloudFormation stack outputs (both stacks) showing deployment timestamp
- Screenshot of the web page accessed via Load Balancer URL
- Screenshot of S3 bucket containing `index.html`

---

## Cost Estimate

Resources that incur charges while running:

| Resource | Approx. cost |
|---|---|
| 4× t2.micro EC2 | ~$0.046/hr total |
| 2× NAT Gateways | ~$0.09/hr + data |
| Application Load Balancer | ~$0.025/hr |
| 1× t2.micro Bastion | ~$0.0116/hr |

**Always run `python delete.py all` when finished.**

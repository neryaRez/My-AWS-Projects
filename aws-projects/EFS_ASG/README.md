# 📦 EFS + Auto Scaling Group (ASG) Testing Framework on AWS

This project builds and verifies an advanced AWS infrastructure using **CDK**, integrating:

* Amazon EC2 instances (via Auto Scaling Group)
* Amazon EFS (Elastic File System) with shared file access
* Dynamic scale-out/scale-in based on CPU usage
* Full integration tests to verify EFS mount consistency across all instances

---

## 🏗️ Architecture Overview

```
            ┌──────────────────┐
            │    Amazon S3     │ ◄──── Uploads EC2 mount info
            └──────────────────┘
                    ▲
                    │
            ┌───────┴────────┐
            │    EC2 (xN)    │ ◄─── Auto Scaling Group (2-4 instances)
            └───────┬────────┘
                    │ mounts
                    ▼
            ┌──────────────────┐
            │      Amazon EFS  │ ◄── Shared across all EC2s
            └──────────────────┘
```

* **CDK Deploys:**

  * VPC with public subnets
  * EFS with 2 mount targets
  * Auto Scaling Group (min=2, max=4)
  * EC2s mount EFS and write files with their instance IDs
  * `stress` tool is downloaded & optionally triggered to test CPU scaling

---

## 🔧 Components

### 1. `EfStack` (CDK)

* Creates:

  * VPC
  * Public Subnets
  * Security Group (allow SSH, HTTP, HTTPS, NFS)
  * EFS file system
  * Manual Mount Targets (to avoid circular dependencies)
  * Outputs key values via `export_name` for cross-stack use

### 2. `AutoScalingGroupStack` (CDK)

* Imports values from `EfStack`
* Launches EC2s via Launch Template:

  * Installs tools (EFS/NFS/SSM/stress)
  * Mounts EFS with TLS first, fallback to NFS
  * Writes unique file per instance to `/mnt/efs`
  * Uploads mount & `ls -la` info to S3 bucket
  * Applies CPU-based scale-out/in policy

### 3. `integration_test.py` (Python)

* Adjusts ASG warmup settings to 0s for fast test cycles
* Clears previous S3 files
* Forces ASG to `DesiredCapacity=4`
* Waits for scale-out with real CPU stress check
* Verifies:

  * EFS consistency across all instances
  * Shared file visibility (`ls -la /mnt/efs`)
  * Each instance creates a `.txt` file with its ID
  * Uploads instance info to S3 for validation
* Then reduces capacity and verifies scale-in

---

## ✅ What Does This Prove?

| Feature                      | Verified? | How                                      |
| ---------------------------- | --------- | ---------------------------------------- |
| Auto Scaling Group           | ✅         | Real CPU-based scale-out/in via `stress` |
| EFS Shared Mount             | ✅         | All EC2s see same files in `/mnt/efs`    |
| UserData script works        | ✅         | Instances mount, write, and upload logs  |
| S3 as validation backend     | ✅         | Instance results are collected there     |
| Threaded integration testing | ✅         | Fast with `ThreadPoolExecutor`           |

---

## 🚀 Deploying This Project

### 1. Synthesize and Deploy CDK:

```bash
cd efs-autoscaling/EFS
source .venv/bin/activate
cdk deploy EfStack
cdk deploy AutoScalingGroupStack
```

Make sure your `cdk.json` app points to `app.py` that imports both stacks.

### 2. Run Integration Tests:

```bash
python3 integration_test.py
```

* It will automatically scale the ASG up/down
* It will test EFS consistency
* All logs are printed to console

---

## 🧪 Test Breakdown (integration\_test.py)

| Step                   | Description                                   |
| ---------------------- | --------------------------------------------- |
| `update_asg_timings()` | Set warmup = 0s for faster tests              |
| `clear_old_files()`    | Clean old S3 logs                             |
| `wait_for_scale_out()` | Wait for DesiredCapacity=4 with stress checks |
| `compare_files()`      | Check `/mnt/efs` files match across EC2s      |
| `upload_info()`        | Mount info + EFS contents uploaded to S3      |
| `wait_for_scale_in()`  | Stress is stopped and instances removed       |

---

## 📷 Visual Proof

* 📸 Screenshot 1: Auto Scaling Group activity log showing 4 scale-outs based on CPU alarm
* 📸 Screenshot 2: Four EC2 instances showing identical `/mnt/efs` contents (via SSH `ls -la`)

---

## 📌 Notes & Best Practices

* `UserData` script uses fallback logic (TLS → NFS)
* No manual SSH required — SSM is included via IAM
* S3 used as a verification sink
* EFS lifecycle rule: transition to IA after 7 days
* Cooldown reset to 300s after test completes

---

## 👨‍💻 Author

**Nerya Reznikov**
Cloud DevOps | AWS Infrastructure Automation | Python Integrator

---

## 📂 Outputs from CDK

* `EfsStack-VPCId`
* `EfsStack-Subnet1`
* `EfsStack-Subnet2`
* `EfsStack-EfsId`
* `EfsStack-EfsDns`
* `EfsStack-SecurityGroupId`

These are imported into the ASG stack using `cdk.Fn.import_value()`.

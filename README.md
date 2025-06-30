# ☁️ Nerya Reznikovich's AWS Cloud Projects Portfolio

Welcome to a curated showcase of my hands-on AWS cloud projects. Each project reflects real-world architectural patterns, automation practices, and integration of modern AWS services. All infrastructure is deployed with **CloudFormation** or **AWS CDK**, and each project includes custom validation, monitoring, and automation layers.

---

## 📁 Projects Summary

### 1. 🛠️ Two-VPC Communication with EC2 & Peering

**Goal**: Connect two isolated VPCs with EC2 instances via **VPC Peering**

* **VPC1**: With internet access via IGW
* **VPC2**: No internet, but can communicate with VPC1 via peering
* **EC2 Instances**: One in each VPC, with ICMP (ping) enabled
* **SSM Access**: Instances are connected via Systems Manager

🔐 Emphasis on private communication without bastion hosts.

➡️ [][See Full Readme](https://github.com/neryaRez/My-AWS-Projects/tree/main/aws-projects/Cat%20Cloud%20Serverless%20App#readme)(#)

---

### 2. 🔒 Private EC2 with SSM via VPC Endpoints

**Goal**: Launch an EC2 instance in a **fully private subnet**, without internet or NAT

* **Interface Endpoints**: For `ssm`, `ssmmessages`, `ec2messages`
* **Gateway Endpoint**: For `s3`
* **IAM Role**: Grants S3 + SSM access
* **Result**: Fully manageable EC2 via SSM, without public exposure

💡 Perfect pattern for secure, air-gapped environments.

➡️ [See Full README](#)

---

### 3. 😺 Cat Cloud – Image Processing & Notification System

**Goal**: A Python desktop app + serverless backend for image upload & notification

* **Frontend**: TkinterDnD2 + ttkbootstrap GUI
* **Transformations**: Flip, Mirror, Grayscale
* **Upload**: Processed images sent to S3 via boto3

**Backend Workflow**:

* S3 triggers Lambda 1 → Sends message to SQS
* Lambda 2 → Reads SQS → Publishes to SNS
* SNS sends email with image link

🔔 Smart automation of event-based workflows with image-based triggers.

➡️ [See Full README](#)

---

### 4. 📈 EFS + Auto Scaling Group + Integration Tests

**Goal**: Launch EC2 fleet with EFS mounted, test consistency & scale dynamically

* **EFS**: Shared storage mounted with fallback TLS/NFS
* **ASG**: Scales from 2 → 4 instances on CPU stress
* **UserData**: Writes unique file to EFS per instance
* **Integration Script**:

  * Verifies scale-out works
  * All EC2s mount EFS & see same files
  * Results uploaded to S3 for comparison

🧪 Threaded, automated, verifiable testing of real scaling behavior.

➡️ [See Full README](#)

---

## 📦 Technologies Used

| Domain         | Tools & Services                                        |
| -------------- | ------------------------------------------------------- |
| Infrastructure | AWS CDK, CloudFormation, EC2, S3, EFS, SSM, Lambda, ASG |
| Automation     | boto3, Python3, ThreadPoolExecutor, Shell via SSM       |
| Notifications  | SNS, SQS                                                |
| UI             | Python TkinterDnD2, ttkbootstrap, Pillow (PIL)          |
| Security       | IAM Roles, VPC Endpoints, Private Subnets, EFS SG Rules |

---

## 🧠 What This Portfolio Demonstrates

* ✅ Multi-VPC design with routing and security
* ✅ Secure EC2 deployments with SSM & no public IP
* ✅ Serverless pipelines using S3 + Lambda + SQS + SNS
* ✅ Real Auto Scaling and EFS integration under stress
* ✅ Validation logic that proves behavior with logs, screenshots, and uploads

---

## 👨‍💻 Author

**Nerya Reznikov**
Cloud Infrastructure | DevOps | Python Automation | AWS Architecture

If you're hiring, collaborating, or want to learn more about these projects — feel free to reach out!

---

## 📌 Repository Tips

* Each project lives in its own folder
* Each folder includes a dedicated `README.md`
* CloudFormation templates and/or CDK apps included
* Python validation scripts (where applicable) are documented

---

Thank you for checking out my AWS portfolio ☁️🔥

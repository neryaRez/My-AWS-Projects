# 🛠️ AWS Two-VPC Peering & EC2 Communication Project

This project creates two separate VPCs, each with a single subnet and EC2 instance. It establishes full communication between them via VPC Peering and allows internet access and SSM management for testing and operations.

---

## 📐 Architecture Overview

- **VPC1**: `10.0.0.0/16` with a public subnet and internet access.
- **VPC2**: `20.0.0.0/16` with a private subnet (no internet).
- **VPC Peering**: Allows internal communication between the two VPCs.
- **EC2 Instances**: One in each subnet.
- **SSM Access**: Both instances are connected via AWS Systems Manager.

---

## 📋 Features

✅ Two isolated VPCs  
✅ VPC Peering with correct routing  
✅ ICMP (ping) allowed between EC2s  
✅ SSM role and instance profile for remote management  
✅ Internet access to VPC1 only

---

## 🧱 Resources Created

| Resource                 | Description                             |
|--------------------------|-----------------------------------------|
| `VPC1`, `VPC2`           | Two VPCs with distinct CIDRs            |
| `Subnet1`, `Subnet2`     | One subnet per VPC                      |
| `InternetGateway1`       | Internet access for VPC1               |
| `VPCPeeringConnection`   | Connects VPC1 and VPC2                  |
| `RouteTable1`, `RouteTable2` | Custom routing for each subnet       |
| `SecurityGroup1`, `SecurityGroup2` | Ping permission between VPCs |
| `EC2SSMRole1`, `EC2SSMInstanceProfile1` | Enables SSM              |
| `EC2Instance1`, `EC2Instance2` | EC2 machines in each VPC          |

---

## 🔌 Connectivity & Routing

- `EC2Instance1` in **VPC1** has:
  - Internet access via IGW.
  - Can ping EC2Instance2 via Peering.
  - Can be managed via SSM.

- `EC2Instance2` in **VPC2** has:
  - No internet access.
  - Can ping EC2Instance1 via Peering.
  - Can be managed via SSM thanks to the IAM role.

---

## 🚀 How to Deploy

1. Save the template to a file (e.g., `vpc-peering.yaml`)
2. Deploy it using AWS CLI:

   ```bash
   aws cloudformation create-stack \
     --stack-name VPCPeeringStack \
     --template-body file://vpc-peering.yaml \
     --capabilities CAPABILITY_NAMED_IAM

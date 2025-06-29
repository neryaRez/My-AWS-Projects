# 🛡️ Private EC2 Instance with SSM Access via VPC Endpoints Only

This AWS CloudFormation project provisions a secure EC2 instance within a **private subnet**, completely isolated from the internet. The instance is remotely managed **exclusively via AWS Systems Manager (SSM)** using **VPC Interface Endpoints**, without any NAT Gateway or Internet Gateway.

---

## 🧭 Architecture Overview

- **VPC CIDR**: 10.0.0.0/16
- **Subnet**: 10.0.1.0/24 (Private only)
- **No Internet Gateway or NAT Gateway**
- **SSM Access via Interface VPC Endpoints**
- **S3 Access via Gateway Endpoint**
- **EC2 instance with IAM role allowing S3 and SSM**

---

## 🔧 Key Resources

| Resource                     | Purpose                                             |
|------------------------------|-----------------------------------------------------|
| `NVPC`                       | Main VPC                                            |
| `NPrivateSubnet`            | Private subnet for the EC2 instance                 |
| `PrivateRouteTable`         | Route table for subnet                              |
| `VPCEndpointSecurityGroup`  | Allows HTTPS (443) to/from endpoints                |
| `SSMVPCEndpoint`            | Interface endpoint for Systems Manager              |
| `SSMMessagesVPCEndpoint`    | Required for SSM messaging                          |
| `EC2MessagesVPCEndpoint`    | Required for SSM messaging                          |
| `S3VPCEndpoint`             | Gateway endpoint to access S3 internally            |
| `S3SSMAccessRole`           | IAM role with permissions for SSM and S3            |
| `S3SSMInstanceProfile`      | Instance profile for EC2                            |
| `NEC2Instance`              | Private EC2 instance (no internet access)           |

---

## 🔒 Security Model

- No public IP is assigned.
- No Internet Gateway or NAT Gateway is used.
- All communication with AWS services (SSM, S3) occurs through **private VPC endpoints**.
- The EC2's security group allows:
  - Inbound HTTPS (443) from within the VPC.
  - Outbound HTTPS to any destination.

---

## 🚀 Deployment

1. Save the template as `private-ec2-vpce.yaml`.
2. Deploy using AWS CLI:

   ```bash
   aws cloudformation create-stack \
     --stack-name PrivateEC2ViaSSM \
     --template-body file://private-ec2-vpce.yaml \
     --capabilities CAPABILITY_NAMED_IAM

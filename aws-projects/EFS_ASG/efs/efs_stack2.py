import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_autoscaling as autoscaling,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

class EfStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # 1. VPC
        vpc = ec2.Vpc(self, "MyVPC",
            max_azs=2,
            nat_gateways=0,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            subnet_configuration=[ec2.SubnetConfiguration(
                name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
            )]
        )

        # 2. EFS
        file_system = efs.FileSystem(self, "MyEFS",
            vpc=vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encrypted=False,
        )

        efs_sg = file_system.connections.security_groups[0]
        efs_sg.add_ingress_rule(peer=ec2.Peer.ipv4(vpc.vpc_cidr_block), connection=ec2.Port.tcp(2049), description="Allow NFS from VPC CIDR")
        efs_sg.add_ingress_rule(peer=ec2.Peer.ipv4(vpc.vpc_cidr_block), connection=ec2.Port.tcp(22), description="Allow SSH from VPC CIDR")
        efs_sg.add_ingress_rule(peer=ec2.Peer.ipv4(vpc.vpc_cidr_block), connection=ec2.Port.tcp(80), description="Allow HTTP from VPC CIDR")

        # Add resource policy
        file_system.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=[
                    "elasticfilesystem:ClientMount",
                    "elasticfilesystem:ClientWrite",
                    "elasticfilesystem:ClientRootAccess"
                ],
                conditions={
                    "Bool": {
                        "elasticfilesystem:AccessedViaMountTarget": "true"
                    }
                },
                resources=[file_system.file_system_arn]
            )
        )

        # 4. Outputs with export names
        CfnOutput(self, "VPCId", value=vpc.vpc_id, export_name="EfsStack-VPCId")
        CfnOutput(self, "Subnet1", value=vpc.public_subnets[0].subnet_id, export_name="EfsStack-Subnet1")
        CfnOutput(self, "Subnet2", value=vpc.public_subnets[1].subnet_id, export_name="EfsStack-Subnet2")
        CfnOutput(self, "EfsId", value=file_system.file_system_id, export_name="EfsStack-EfsId")
        CfnOutput(self, "EfsDns", value=f"{file_system.file_system_id}.efs.{self.region}.amazonaws.com", export_name="EfsStack-EfsDns")
        CfnOutput(self, "SecurityGroupId", value=efs_sg.security_group_id, export_name="EfsStack-SecurityGroupId")

class AutoScalingGroupStack(Stack):

     def __init__(self, scope: Construct, construct_id: str, *,
                 vpc_id: str, subnet1_id: str, subnet2_id: str,
                 efs_id: str, efs_dns: str, sg_id: str,
                 **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_vpc_attributes(self, "VPC",
        vpc_id=vpc_id,
         availability_zones=["eu-north-1a", "eu-north-1b"],
         public_subnet_ids=[subnet1_id, subnet2_id]
        )

        sg = ec2.SecurityGroup.from_security_group_id(self, "SG", security_group_id=sg_id)

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            f"EFS_ID=\"{efs_id}\"",
            f"REGION=\"{self.region}\"",
            "yum update -y",
            "yum install -y nfs-utils amazon-efs-utils gcc make autoconf automake unzip curl",
            "mkdir -p /mnt/efs",
            f"for i in {{1..60}}; do nslookup \"$EFS_ID.efs.$REGION.amazonaws.com\" && break || sleep 10; done",
            "if mount -t efs -o tls ${EFS_ID}:/ /mnt/efs; then",
            "echo 'Mounted with TLS successfully' >> /var/log/efs-mount.log",
            "elif mount -t nfs4 -o nfsvers=4.1 ${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs; then",
            "echo 'Mounted without TLS (fallback to NFS)' >> /var/log/efs-mount.log",
            "else",
            "echo 'Mount failed' >> /var/log/efs-mount.log",
            "exit 1",
            "fi",
            "ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)",
            "echo \"Hello from $ID\" > /mnt/efs/$ID.txt",
            "chmod 777 /mnt/efs",
            "chmod 777 /mnt/efs/$ID.txt",
            "cd /home/ec2-user",
            "curl -LO https://github.com/resurrecting-open-source-projects/stress/archive/refs/heads/master.zip",
            "unzip master.zip",
            "cd stress-master",
            "./autogen.sh || true",
            "./configure || true",
            "make || true",
            "make install || true"
        )

        role = iam.Role(self, "ASGInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonElasticFileSystemClientFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )

        lt = ec2.LaunchTemplate(self, "ASGLaunchTemplate",
        instance_type=ec2.InstanceType("t3.micro"),
        machine_image=ec2.AmazonLinuxImage(
        generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        ),
        key_name="Nery-Pair",
        security_group=sg,
        role=role,
        user_data=user_data
        )

        asg = autoscaling.AutoScalingGroup(self, "MyASG",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[
            ec2.Subnet.from_subnet_id(self, "Subnet1", subnet1_id),
            ec2.Subnet.from_subnet_id(self, "Subnet2", subnet2_id)
        ]),
            min_capacity=2,
            max_capacity=4,
            launch_template=lt
        )

        efs_sg = ec2.SecurityGroup.from_security_group_id(self, "ImportedEfsSG",
        security_group_id=cdk.Fn.import_value("EfsStack-SecurityGroupId")
        )

        asg_sg = ec2.SecurityGroup(self, "ASGSecurityGroup",
            vpc=vpc,
            description="Allow NFS access to EFS",
            allow_all_outbound=True
        )
        asg_sg.add_ingress_rule(efs_sg, ec2.Port.tcp(2049), "Allow NFS access from EFS SG")
        asg_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH access from anywhere")
        asg_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP access from anywhere")
        asg_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS access from anywhere")
        asg.add_security_group(asg_sg)

        efs_sg.add_ingress_rule(peer=asg_sg,
            connection=ec2.Port.tcp(2049),
            description="Allow NFS access from ASG SG"
        )

        asg.scale_on_cpu_utilization("ScaleOnCPU",
            target_utilization_percent=60
        )

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_iam as iam,
    CfnOutput
)
from aws_cdk import aws_autoscaling as autoscaling
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

        # 2. Security Group
        sg = ec2.SecurityGroup(self, "InstanceSG",
            vpc=vpc,
            description="Allow HTTP, SSH, HTTPS access",
            allow_all_outbound=True
        )
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # 3. EFS (Manual Mount Targets to avoid circular dependency)
        file_system = efs.CfnFileSystem(self, "MyEFS",
            performance_mode="generalPurpose",
            encrypted=False,
            lifecycle_policies=[{"transitionToIa": "AFTER_7_DAYS"}]
        )
        
        efs.CfnMountTarget(self, "EfsMountTarget1",
            file_system_id=file_system.ref,
            subnet_id=vpc.public_subnets[0].subnet_id,
            security_groups=[sg.security_group_id]
        )

        efs.CfnMountTarget(self, "EfsMountTarget2",
            file_system_id=file_system.ref,
            subnet_id=vpc.public_subnets[1].subnet_id,
            security_groups=[sg.security_group_id]
        )

        # 4. Outputs with export names
        CfnOutput(self, "VPCId", value=vpc.vpc_id, export_name="EfsStack-VPCId")
        CfnOutput(self, "Subnet1", value=vpc.public_subnets[0].subnet_id, export_name="EfsStack-Subnet1")
        CfnOutput(self, "Subnet2", value=vpc.public_subnets[1].subnet_id, export_name="EfsStack-Subnet2")
        CfnOutput(self, "EfsId", value=file_system.ref, export_name="EfsStack-EfsId")
        CfnOutput(self, "EfsDns", value=f"{file_system.ref}.efs.{self.region}.amazonaws.com", export_name="EfsStack-EfsDns")
        CfnOutput(self, "SecurityGroupId", value=sg.security_group_id, export_name="EfsStack-SecurityGroupId")

class AutoScalingGroupStack(Stack):

     def __init__(self, scope: Construct, construct_id: str, *,
                 vpc_id: str, subnet1_id: str, subnet2_id: str,
                 efs_id: str, efs_dns: str, sg_id: str,
                 **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_vpc_attributes(self, "VPC",
        vpc_id=vpc_id,
         availability_zones=[cdk.Fn.select(0, cdk.Fn.get_azs()),
                             cdk.Fn.select(1, cdk.Fn.get_azs())],
         public_subnet_ids=[subnet1_id, subnet2_id]
        )

        sg = ec2.SecurityGroup.from_security_group_id(self, "SG", security_group_id=sg_id)

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            f"EFS_ID=\"{efs_id}\"",
            f"REGION=\"{self.region}\"",
            "yum update -y",
            "yum install -y nfs-utils amazon-efs-utils gcc make autoconf automake unzip curl",
            "yum install -y awscli",

            "mkdir -p /mnt/efs",

            f"for i in {{1..60}}; do nslookup \"$EFS_ID.efs.$REGION.amazonaws.com\" && break || sleep 10; done",
            #Try TLS mount first
            "if mount -t efs -o tls ${EFS_ID}:/ /mnt/efs; then",
            "echo 'Mounted with TLS successfully' >> /var/log/efs-mount.log",
            "echo '${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs efs defaults,_netdev,tls 0 0' >> /etc/fstab",
            "mount -a || echo 'fstab mount failed' >> /var/log/efs-mount.log",

            #Fallback to NFS if TLS mount fails
            "elif mount -t nfs4 -o nfsvers=4.1 ${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs; then",
            "echo 'Mounted without TLS (fallback to NFS)' >> /var/log/efs-mount.log",
            "echo '${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs nfs4 defaults,_netdev 0 0' >> /etc/fstab",
            "mount -a || echo 'fstab mount failed' >> /var/log/efs-mount.log",
            
            # If both mounts fail, log the error
            "else",
            "echo 'Mount failed' >> /var/log/efs-mount.log",
            "exit 1",
            "fi",

            "ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)",
            "echo \"Hello from $ID\" > /mnt/efs/$ID.txt",
            "date >> /mnt/efs/$ID.txt",
            "sh -c 'mount | grep efs >> /mnt/efs/$ID.txt'",
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

                # Role & Instance Profile
        role = iam.Role(self, "ASGInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonElasticFileSystemClientFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("Amazons3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
            ]
        )

        lt = ec2.LaunchTemplate(self, "ASGLaunchTemplate",
        instance_type=ec2.InstanceType("t3.micro"),
        machine_image=ec2.AmazonLinuxImage(
        generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        ),
        key_name="your-key-pair-name",  # Replace with your key pair name
        security_group=sg,
        role=role,
        user_data=user_data
        )


        # Auto Scaling Group
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

        # CPU Scaling Policy (sensitive to stress test)
        asg.scale_on_cpu_utilization("ScaleOnCPU",
            target_utilization_percent=60
        )

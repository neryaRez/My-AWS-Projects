#!/usr/bin/env python3
import aws_cdk as cdk
from efs.efs_asg_stacks import AutoScalingGroupStack
from efs.efs_asg_stacks import EfStack

app = cdk.App()
efs_stack = EfStack(app, "EfStack")
asg_stack = AutoScalingGroupStack(app, "AutoScalingGroupStack",
    # Importing values from EfsStack outputs
    # These values are expected to be exported from the EfsStack
    vpc_id=cdk.Fn.import_value("EfsStack-VPCId"),
    subnet1_id=cdk.Fn.import_value("EfsStack-Subnet1"),
    subnet2_id=cdk.Fn.import_value("EfsStack-Subnet2"),
    efs_id=cdk.Fn.import_value("EfsStack-EfsId"),
    efs_dns=cdk.Fn.import_value("EfsStack-EfsDns"),
    sg_id=cdk.Fn.import_value("EfsStack-SecurityGroupId")
)
app.synth()


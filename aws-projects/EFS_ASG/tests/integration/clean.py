import boto3
import time
asg_client = boto3.client('autoscaling')
ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')
efs = boto3.client('efs')

ASG_NAME = "AutoScalingGroupStack-MyASG63588E97-y0tq7fAJ8My7"
def get_instance_ids():
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:aws:autoscaling:groupName", "Values": [ASG_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    return [inst["InstanceId"] for res in resp["Reservations"] for inst in res["Instances"]]

def stop_stress():
    instance_ids = get_instance_ids()
    for iid in instance_ids:
        try:
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["pkill stress"]}
            )
            print(f"🛑 stress stopped on {iid}")
        except Exception as e:
            print(f"⚠️ error stopping stress on {iid}: {e}")


def clear_nfs_files():
    instance_ids = get_instance_ids()
    for iid in instance_ids:
        try:
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["rm -rf /mnt/efs/*"]}
            )
            print(f"🗑️ NFS files cleared on {iid}")
        except Exception as e:
            print(f"⚠️ error clearing NFS files on {iid}: {e}")
            
# def change_asg_warmup_and_cooldown(asg_name, seconds):
#     try:
#         # עדכון ה־warmup של ה־ASG
#         asg_client.update_auto_scaling_group(
#             AutoScalingGroupName=asg_name,
#             DefaultInstanceWarmup=seconds
#         )

#         # עדכון רק לפוליסות מסוג SimpleScaling
#         policies = asg_client.describe_policies(AutoScalingGroupName=asg_name)["ScalingPolicies"]
#         for policy in policies:
#             if policy.get("PolicyType") == "SimpleScaling":
#                 asg_client.put_scaling_policy(
#                     AutoScalingGroupName=asg_name,
#                     PolicyName=policy["PolicyName"],
#                     PolicyType="SimpleScaling",
#                     AdjustmentType=policy["AdjustmentType"],
#                     ScalingAdjustment=policy["ScalingAdjustment"],
#                     Cooldown=seconds
#                 )

#         print(f"⏱️ Warmup and cooldown updated to {seconds} seconds")

#     except Exception as e:
#         print(f"⚠️ Failed to update ASG warmup or cooldown: {e}")

# change_asg_warmup_and_cooldown(ASG_NAME,300)  # Restore the ASG warmup and cooldown to the default values
# def set_asg_test_speed(asg_name, seconds):
#     try:
#         # 1. עדכון warmup של ה-ASG
#         asg_client.update_auto_scaling_group(
#             AutoScalingGroupName=asg_name,
#             DefaultInstanceWarmup=seconds
#         )
#         print(f"⚙️ DefaultInstanceWarmup set to {seconds}")

#         # 2. עדכון cooldown או estimated warmup לפי סוג הפוליסה
#         policies = asg_client.describe_policies(AutoScalingGroupName=asg_name)["ScalingPolicies"]
#         for policy in policies:
#             if policy["PolicyType"] == "TargetTrackingScaling":
#                 asg_client.put_scaling_policy(
#                     AutoScalingGroupName=asg_name,
#                     PolicyName=policy["PolicyName"],
#                     PolicyType="TargetTrackingScaling",
#                     TargetTrackingConfiguration=policy["TargetTrackingConfiguration"],
#                     EstimatedInstanceWarmup=seconds
#                 )
#                 print(f"📈 TargetTracking '{policy['PolicyName']}' EstimatedInstanceWarmup set to {seconds}")

#             elif policy["PolicyType"] == "SimpleScaling":
#                 asg_client.put_scaling_policy(
#                     AutoScalingGroupName=asg_name,
#                     PolicyName=policy["PolicyName"],
#                     PolicyType="SimpleScaling",
#                     AdjustmentType=policy["AdjustmentType"],
#                     ScalingAdjustment=policy["ScalingAdjustment"],
#                     Cooldown=seconds
#                 )
#                 print(f"📉 SimpleScaling '{policy['PolicyName']}' Cooldown set to {seconds}")

#         print(f"✅ ASG warmup and cooldown updated to {seconds} seconds for all relevant policies.")

#     except Exception as e:
#         print(f"⚠️ Failed to update ASG warmup/cooldown: {e}")



# set_asg_test_speed(ASG_NAME, 0)  # Set the ASG warmup and cooldown to 0 seconds for testing        


# def set_asg_speed(asg_client, asg_name, seconds):
#     try:
#         # 1. עדכון warmup הכללי של ה-ASG
#         asg_client.update_auto_scaling_group(
#             AutoScalingGroupName=asg_name,
#             DefaultInstanceWarmup=seconds
#         )
#         print(f"⚙️ DefaultInstanceWarmup set to {seconds}")

#         # 2. עדכון cooldown או estimated warmup לפי סוג הפוליסה
#         policies = asg_client.describe_policies(AutoScalingGroupName=asg_name)["ScalingPolicies"]
#         for policy in policies:
#             if policy["PolicyType"] == "TargetTrackingScaling":
#                 asg_client.put_scaling_policy(
#                     AutoScalingGroupName=asg_name,
#                     PolicyName=policy["PolicyName"],
#                     PolicyType="TargetTrackingScaling",
#                     TargetTrackingConfiguration=policy["TargetTrackingConfiguration"],
#                     EstimatedInstanceWarmup=seconds
#                 )
#                 print(f"📈 TargetTracking '{policy['PolicyName']}' EstimatedInstanceWarmup set to {seconds}")

#             elif policy["PolicyType"] == "SimpleScaling":
#                 asg_client.put_scaling_policy(
#                     AutoScalingGroupName=asg_name,
#                     PolicyName=policy["PolicyName"],
#                     PolicyType="SimpleScaling",
#                     AdjustmentType=policy["AdjustmentType"],
#                     ScalingAdjustment=policy["ScalingAdjustment"],
#                     Cooldown=seconds
#                 )
#                 print(f"📉 SimpleScaling '{policy['PolicyName']}' Cooldown set to {seconds}")

#         print(f"✅ ASG warmup + cooldown fully updated to {seconds}s for all policy types")

#     except Exception as e:
#         print(f"❌ Failed to update ASG timing settings: {e}")
# # set_asg_speed(asg_client, ASG_NAME, 0)  # Restore the ASG warmup and cooldown to the default values



def update_asg_timings(asg_name, seconds):
    try:
        # 1. עדכון ה־DefaultInstanceWarmup של ה־ASG
        asg_client.update_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            DefaultInstanceWarmup=seconds
        )
        print(f"⚙️ DefaultInstanceWarmup set to {seconds} seconds")

        # 2. עדכון EstimatedInstanceWarmup בפוליסות TargetTracking
        policies = asg_client.describe_policies(AutoScalingGroupName=asg_name)["ScalingPolicies"]
        for policy in policies:
            if policy["PolicyType"] == "TargetTrackingScaling":
                config = policy["TargetTrackingConfiguration"]

                # בונים מחדש את הפוליסה עם EstimatedInstanceWarmup חדש
                asg_client.put_scaling_policy(
                    AutoScalingGroupName=asg_name,
                    PolicyName=policy["PolicyName"],
                    PolicyType="TargetTrackingScaling",
                    TargetTrackingConfiguration=config,
                    EstimatedInstanceWarmup=seconds
                )
                print(f"📈 TargetTracking '{policy['PolicyName']}' EstimatedInstanceWarmup set to {seconds} seconds")

        print(f"✅ ASG warmup + policies updated to {seconds} seconds")
        
    except Exception as e:
        print(f"❌ Error updating ASG timings: {e}")




update_asg_timings(ASG_NAME, 300)  # Set the ASG warmup and cooldown to 0 seconds for testing
policies = asg_client.describe_policies(AutoScalingGroupName=ASG_NAME)["ScalingPolicies"]
for p in policies:
    print(f"{p['PolicyName']} - {p['PolicyType']}")

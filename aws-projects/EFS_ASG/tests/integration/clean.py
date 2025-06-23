import boto3

asg_client = boto3.client('autoscaling')
ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')

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

stop_stress()

import boto3
import time
from datetime import datetime, timedelta, timezone
s3 = boto3.client("s3")
ec2 = boto3.client("ec2")
ssm = boto3.client("ssm")
efs = boto3.client("efs")
asg = boto3.client('autoscaling')


BUCKET = "asg-efs-checking"
PREFIX = "efs-check"
ASG_NAME = "AutoScalingGroupStack-MyASG63588E97-y0tq7fAJ8My7"
EXPECTED = 4
MIN_EXPECTED = 2
WAIT_INTERVAL = 10
MAX_SCALE_WAIT =  600  # Maximum wait time for scale-out in seconds
COOLDOWN_WAIT = 600  # Cooldown period for scale-in in seconds

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def clear_old_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    for obj in response.get("Contents", []):
        s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    log("🧹  Old files cleared from S3 bucket.")

def get_instance_ids():
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:aws:autoscaling:groupName", "Values": [ASG_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    return [inst["InstanceId"] for res in resp["Reservations"] for inst in res["Instances"]]

def start_stress_on_instance(instance_id):
        try:
            ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["stress --cpu 2 --timeout 600 &"]},
            )
            log(f"🔥 stress started on {instance_id}")
        except Exception as e:
            log(f"⚠️  Error starting stress on {instance_id}: {e}")

def checking_applying_stress(instance_ids):
    success = []
    for iid in instance_ids:
        time.sleep(5)  # Avoid throttling by adding a small delay
        try:
            resp = ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["pgrep stress"]},
            )
            cmd_id = resp["Command"]["CommandId"]
            time.sleep(5)  # Wait for command to execute
            # Check the command invocation to see if stress is running
            out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=iid)
            if out["StandardOutputContent"].strip() != "":
                success.append(iid)
            else:
                log(f"❌ stress is not running on {iid}")
                start_stress_on_instance(iid)
        
        except ssm.exceptions.InvalidInstanceId as e:
            log(f"⚠️ error has been occured on {iid}: {e}")
    
    return success

def wait_for_scale_out(expected_count):
    waited = 0
    while waited < MAX_SCALE_WAIT:
        
        ids = get_instance_ids() # counts the current amount of instances
        
        if len(ids) >= expected_count:
            return ids
        
        checking_applying_stress(ids)  # Make sure stress is running, and if not, start it.
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL
        
        #loging debug info every 1 minute
        if waited % 60 == 0:
            log(f"waited {waited} seconds, still waiting for {expected_count} instances. Current count: {len(ids)} ")
    
    log("❌ not enough instances after waiting for scale-out.")
    return []

def cleanup_efs(instance_ids):
    for iid in instance_ids:
        ssm.send_command(
            InstanceIds=[iid],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": ["rm -f /mnt/efs/*"]}
        )
        log(f"🧹 cleaned up /mnt/efs on {iid}")

def write_to_efs(instance_ids):
    for iid in instance_ids:
        time.sleep(5)  # Avoid throttling by adding a small delay

        try:
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [f"echo 'This is a test file from instance $HOSTNAME' > /mnt/efs/testfile_{iid}.txt"]}
            )
            time.sleep(5)
            # Wait for the command to complete
            # Upload the test file to S3 for verification
            log(f"📄 test file written to EFS on {iid}.")
        except Exception as e:
            log(f"⚠️ error has been occured on {iid}: {e}")

def collect_mount_info(instance_ids):
    cleanup_efs(instance_ids)  # Ensure the EFS is clean before collecting info
    write_to_efs(instance_ids)  # Write a test file to EFS
    for iid in instance_ids:
        time.sleep(5)  # Avoid throttling by adding a small delay
        try:
            filename = f"/tmp/{iid}-efs-check.txt"
            cmd = (
                f"(mount | grep efs && echo && ls -la /mnt/efs) > {filename} && "
                f"aws s3 cp {filename} s3://{BUCKET}/{PREFIX}/{iid}.txt"
            )
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [cmd]}
            )
            time.sleep(10)  
            # Wait for the command to complete
            log(f"📂 mount info collected and uploaded for {iid}.")
        except Exception as e:
            log(f"⚠️ error has been occured on {iid}: {e}")

def count_uploaded_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    return len([obj for obj in response.get("Contents", []) if obj["Key"].endswith(".txt")])

def get_s3_file(key):
    resp = s3.get_object(Bucket=BUCKET, Key=key)
    return resp["Body"].read().decode("utf-8")

def compare_mount_outputs(instance_ids):
    def extract_filenames(text):
        lines = text.strip().splitlines()
        lines = [line for line in lines if "nfs4" not in line and not line.strip().endswith("..")]

        filenames = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) > 0 and "testfile_" in line:
                filenames.append(parts[-1])
        return sorted(filenames)

    base_files = extract_filenames(get_s3_file(f"{PREFIX}/{instance_ids[0]}.txt"))

    for iid in instance_ids[1:]:
        other_files = extract_filenames(get_s3_file(f"{PREFIX}/{iid}.txt"))
        if other_files != base_files:
            log(f"❌ File list mismatch on {iid} vs {instance_ids[0]}")
            log(f"Base: {base_files}")
            log(f"{iid}: {other_files}")
            return False

    return True

def stop_stress(instance_ids):
    for iid in instance_ids:
        try:
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["pkill stress"]}
            )
            log(f"🛑 stress stopped on {iid}")
        except Exception as e:
            log(f"⚠️ error stopping stress on {iid}: {e}")

def check_scale_in(min_expected):
    waited = 0
    while waited < COOLDOWN_WAIT:
        ids = get_instance_ids()
        
        if len(ids) <= min_expected:
            log("✅ scale-in  check passed, instances scaled down to minimum expected.")
            return True
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL

        # Log debug info every 1 minute
        if waited % 60 == 0:
            log(f"waited {waited} seconds, still waiting for scale-in. Current count: {len(ids)} ")
    log("❌ cooldown period exceeded, instances did not scale down to minimum expected.")
    return False

# === MAIN FLOW ===

log("🚀 Test starts")
clear_old_files()

ids = get_instance_ids()
if not ids:
    log("❌ There are no running instances in the ASG")
    exit(1)
log(f"There are now  {len(ids)} instances in the ASG.")

time.sleep(10)

log("Checking if stress is running on instances, and if not apllys it...")
log("⏳ waiting for scale out...")

final_ids = wait_for_scale_out(EXPECTED)

if len(final_ids) < EXPECTED:
    log(f"❌ only {len(final_ids)} instances scaled out, expected {EXPECTED}.")
    exit(1)

log("✅ Enough instances scaled out, checks the connection to EFS...")

log("📥 apllying commands of mount and ls -la on the EFS.")
log("collect_mount_info started...")
collect_mount_info(final_ids)
log("collect_mount_info finished, waiting for S3 to update...")
log("⏳waiting 30 seconds.")
time.sleep(30)

log("📊 checks the files who have been uploaded to s3..")
uploaded_count = count_uploaded_files()
if uploaded_count < len(final_ids):
    log(f"❌ only {uploaded_count} files uploaded, expected {len(final_ids)}.")
    exit(1)

if compare_mount_outputs(final_ids):
    log("✅ EFS mount is shared across all instances.")
    log(" 📂 All instances have the same mount and ls -la output.")

else:
    log("❌ EFS mount outputs are not the same across instances.")
    log("Exiting test with failure.")
    exit(1)

print("The actual data of the mount info is: ")
print("========================================")
print(get_s3_file(f"{PREFIX}/{final_ids[0]}.txt"))
print("========================================")

log("🛑 stopping stress to allow scale-in.")
stop_stress(final_ids)

log("🧘 waits five minutes to cool down.")
time.sleep(COOLDOWN_WAIT)

check_scale_in(MIN_EXPECTED)

# Log the activity of the ASG in the terminal

print("The activity log of the ASG (last 5 minutes):")
print("========================================")

activity_history = asg.describe_scaling_activities(AutoScalingGroupName=ASG_NAME)

now = datetime.now(timezone.utc)
cutoff_time = now - timedelta(minutes=5)

recent_activities = [activity for activity in activity_history['Activities'] if activity['StartTime'] >= cutoff_time]

if not recent_activities:
    print("No scaling activities in the last 5 minutes.")
else:
    for activity in recent_activities:
        print(f"Activity ID: {activity['ActivityId']}")
        print(f"Description: {activity['Description']}")
        print(f"Cause: {activity['Cause']}")
        print(f"Start Time: {activity['StartTime']}")
        print(f"End Time: {activity.get('EndTime', 'N/A')}")
        print(f"Status Code: {activity['StatusCode']}")
        print("========================================")
log("🎉 All the tests passed successfully!")

# This script is designed to test the integration of an Auto Scaling Group (ASG) with an Amazon EFS file system.
# It checks if the ASG scales out to the expected number of instances, verifies that all instances have the EFS mounted correctly,
# and ensures that the ASG scales back down to a  minimum number of instances after a cooldown period.
# This script also collects mount information from each instance and uploads it to an S3 bucket for verification.
# It uses AWS SDK for Python (Boto3) to interact with AWS services like EC2, S3, SSM, and EFS.
# Make sure to have the necessary AWS credentials configured in your environment to run this script.
# The script also logs the activity of the ASG, providing insights into the scaling activities that occurred during the test.
# Note: Make sure to replace 'your-bucket-name', 'your-asg-name', and 'fs-xxxxxxx' with actual values.
#       Also, ensure that the necessary IAM permissions are set for the script to run successfully.

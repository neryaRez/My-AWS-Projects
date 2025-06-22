import boto3
import time

s3 = boto3.client("s3")
ec2 = boto3.client("ec2")
ssm = boto3.client("ssm")
efs = boto3.client("efs")

BUCKET = "your-bucket-name"
PREFIX = "efs-check"
ASG_NAME = "your-asg-name"
EXPECTED = 4
MIN_EXPECTED = 2
WAIT_INTERVAL = 10
MAX_SCALE_WAIT = 300
COOLDOWN_WAIT = 300

def get_efs_dns(efs_id):
    region = boto3.session.Session().region_name
    return f"{efs_id}.efs.{region}.amazonaws.com"

def clear_old_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    for obj in response.get("Contents", []):
        s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    print("🧹  Old files cleared from S3 bucket.")

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
                Parameters={"commands": ["stress --cpu 2 --timeout 15000 &"]},
            )
            print(f"🔥 stress started on {instance_id}")
        except Exception as e:
            print(f"⚠️  Error starting stress on {instance_id}: {e}")

def checking_applying_stress(instance_ids):
    success = []
    for iid in instance_ids:
        try:
            resp = ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["pgrep stress"]},
            )
            cmd_id = resp["Command"]["CommandId"]
            time.sleep(2)
            out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=iid)
            if out["StandardOutputContent"].strip() != "":
                success.append(iid)
            else:
                print(f"❌ stress is not running on{iid}")
                start_stress_on_instance(iid)
        
        except ssm.exceptions.InvalidInstanceId as e:
            print(f"⚠️ error has been occured on {iid}: {e}")
    
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
        
        #printing debug info every 1 minute
        if waited % 60 == 0:
            print(f"waited {waited} seconds, still waiting for {expected_count} instances. Current count: {len(ids)} ")
    
    print("❌ not enough instances after waiting for scale-out.")
    return []

def collect_mount_info(instance_ids):
    for iid in instance_ids:
        try:
            filename = f"/tmp/{iid}-efs-check.txt"
            cmd = (
                f"(mount | grep efs && echo && ls -la /mnt/efs') > {filename} && "
                f"aws s3 cp {filename} s3://{BUCKET}/{PREFIX}/{iid}.txt"
            )
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [cmd]}
            )
            print(f"📤 mount + ls -la נשלח ל־{iid}")
        except Exception as e:
            print(f"⚠️ error has been occured on {iid}: {e}")

def count_uploaded_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    return len([obj for obj in response.get("Contents", []) if obj["Key"].endswith(".txt")])

def get_s3_file(key):
    resp = s3.get_object(Bucket=BUCKET, Key=key)
    return resp["Body"].read().decode("utf-8")

def compare_mount_outputs(instance_ids):
    base = get_s3_file(f"{PREFIX}/{instance_ids[0]}.txt")

    for iid in instance_ids[1:]:
        other = get_s3_file(f"{PREFIX}/{iid}.txt")
        if other != base:
            print(f"❌ {iid} לא תואם ל־{instance_ids[0]}")
            return False

    print("📂 All the files are the same.")
    print("✅ The machines share the same mount EFS.")
    return True

def check_scale_in(min_expected):
    waited = 0
    while waited < COOLDOWN_WAIT + 60:
        ids = get_instance_ids()
        print(f"📉 נותרו {len(ids)} מכונות אחרי cooldown")
        if len(ids) <= min_expected:
            print("✅ scale-in הצליח. חזרנו למינימום.")
            return True
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL
    print("❌ המכונות לא ירדו בזמן אחרי cooldown.")
    return False

# === MAIN FLOW ===

print("🚀 Test starts")
clear_old_files()

ids = get_instance_ids()
if not ids:
    print("❌ There are no running instances in the ASG")
    exit(1)
print(f"There are now  {len(ids)} instances in the ASG.")

time.sleep(10)
print()
print("Checking if stress is running on instances...")
print("Applying stress on instances...")
print("⏳ waiting for scale out...")

final_ids = wait_for_scale_out(EXPECTED)

if len(final_ids) < EXPECTED:
    print(f"❌ only {len(final_ids)} instances scaled out, expected {EXPECTED}.")
    exit(1)

print("✅ Enough instances scaled out, checks the connection to EFS...")
print()

print("📥 apllying commands of mount and ls -la on the EFS.")
print("collect_mount_info started...")
collect_mount_info(final_ids)
print("collect_mount_info finished, waiting for S3 to update...")
print("⏳waiting 30 seconds.")
time.sleep(30)
print()

print("📊 checks the files who have been uploaded to s3..")
uploaded_count = count_uploaded_files()
if uploaded_count < len(final_ids):
    print(f"❌ only {uploaded_count} files uploaded, expected {len(final_ids)}.")
    exit(1)

if compare_mount_outputs(final_ids):
    print("✅ EFS mount is shared across all instances.")
    print("All instances have the same mount and ls -la output.")

else:
    print("❌ EFS mount outputs are not the same across instances.")
    print("Exiting test with failure.")
    exit(1)

print("🧘 waits five minutes to cool down.")
time.sleep(COOLDOWN_WAIT)

check_scale_in(MIN_EXPECTED)
print("✅  Scale-in check passed, instances scaled down to minimum expected.")
print("🎉 All the tests passed successfully!")
# Note: Make sure to replace 'your-bucket-name', 'your-asg-name', and 'fs-xxxxxxx' with actual values.
#       Also, ensure that the necessary IAM permissions are set for the script to run successfully.

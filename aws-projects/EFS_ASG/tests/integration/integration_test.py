import boto3
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

s3 = boto3.client("s3")
ec2 = boto3.client("ec2")
ssm = boto3.client("ssm")
asg = boto3.client("autoscaling")

BUCKET = "asg-efs-checking"
PREFIX = "efs-check"
ASG_NAME = "AutoScalingGroupStack-MyASG63588E97-y0tq7fAJ8My7"
EXPECTED = 4
MIN_EXPECTED = 2
WAIT_INTERVAL = 10
TEST_MODE = True


def log(msg):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}")


def update_asg_timings(asg_name, seconds):
    asg.update_auto_scaling_group(AutoScalingGroupName=asg_name, DefaultInstanceWarmup=seconds)
    for policy in asg.describe_policies(AutoScalingGroupName=asg_name)["ScalingPolicies"]:
        if policy["PolicyType"] == "TargetTrackingScaling":
            asg.put_scaling_policy(
                AutoScalingGroupName=asg_name,
                PolicyName=policy["PolicyName"],
                PolicyType="TargetTrackingScaling",
                TargetTrackingConfiguration=policy["TargetTrackingConfiguration"],
                EstimatedInstanceWarmup=seconds
            )
    log(f"✅ ASG warmup + policies updated to {seconds}s")


def clear_old_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    for obj in response.get("Contents", []):
        s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    log("🧹 Old files cleared from S3")


def get_instance_ids():
    resp = ec2.describe_instances(Filters=[
        {"Name": "tag:aws:autoscaling:groupName", "Values": [ASG_NAME]},
        {"Name": "instance-state-name", "Values": ["running"]}
    ])
    return [i["InstanceId"] for r in resp["Reservations"] for i in r["Instances"]]


def start_stress(instance_id):
    try:
        ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": ["stress --cpu 2 --timeout 600 &"]})
        log(f"🔥 stress started on {instance_id}")
    except Exception as e:
        log(f"❌ Error starting stress on {instance_id}: {e}")


def check_and_apply_stress(instance_ids):
    def run(iid):
        try:
            resp = ssm.send_command(InstanceIds=[iid], DocumentName="AWS-RunShellScript",
                                    Parameters={"commands": ["pgrep stress"]})
            cmd_id = resp["Command"]["CommandId"]
            time.sleep(2)
            out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=iid)
            if not out["StandardOutputContent"].strip():
                log(f"❌ stress not running on {iid}, starting it.")
                start_stress(iid)
        except Exception as e:
            log(f"❌ stress check error on {iid}: {e}")

    with ThreadPoolExecutor() as executor:
        executor.map(run, instance_ids)


def wait_for_scale_out(expected_count):
    start = time.time()
    last_minute = -1
    while True:
        ids = get_instance_ids()
        elapsed = time.time() - start
        current_minute = int(elapsed // 60)

        if len(ids) >= expected_count:
            log(f"✅ Scale-out reached: {len(ids)}")
            return ids

        if current_minute != last_minute:
            log(f"⏳ {int(elapsed)}s elapsed, instances: {len(ids)}")
            last_minute = current_minute

        check_and_apply_stress(ids)
        time.sleep(WAIT_INTERVAL)


def write_efs(instance_id):
    try:
        ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": [f"echo 'This is from $HOSTNAME' > /mnt/efs/testfile_{instance_id}.txt"]})
        log(f"📄 Wrote file to EFS on {instance_id}")
    except Exception as e:
        log(f"❌ Error writing file on {instance_id}: {e}")


def upload_info(instance_id):
    try:
        cmd = (
            f"(mount | grep efs && echo && ls -la /mnt/efs) > /tmp/{instance_id}.txt && "
            f"aws s3 cp /tmp/{instance_id}.txt s3://{BUCKET}/{PREFIX}/{instance_id}.txt"
        )
        ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": [cmd]})
        log(f"📤 Uploaded info from {instance_id}")
    except Exception as e:
        log(f"❌ Upload error from {instance_id}: {e}")


def count_s3_files():
    res = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    return len([o for o in res.get("Contents", []) if o["Key"].endswith(".txt")])


def get_s3_file(key):
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()


def extract_files(text):
    return sorted([line.split()[-1] for line in text.splitlines() if "testfile_" in line])


def compare_files(instance_ids):
    base = extract_files(get_s3_file(f"{PREFIX}/{instance_ids[0]}.txt"))
    for iid in instance_ids[1:]:
        other = extract_files(get_s3_file(f"{PREFIX}/{iid}.txt"))
        if other != base:
            log(f"❌ Mismatch: {iid} vs base")
            return False
    return True


def stop_stress(instance_id):
    try:
        ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": ["pkill stress"]})
        log(f"🛑 stress stopped on {instance_id}")
    except Exception as e:
        log(f"❌ Error stopping stress on {instance_id}: {e}")


def wait_for_scale_in(min_expected):
    start = time.time()
    last_minute = -1
    while True:
        ids = get_instance_ids()
        elapsed = time.time() - start
        minute = int(elapsed // 60)

        if len(ids) <= min_expected:
            log(f"✅ Scale-in reached: {len(ids)}")
            return True

        if minute != last_minute:
            log(f"⏳ {int(elapsed)}s elapsed, instances: {len(ids)}")
            last_minute = minute

        with ThreadPoolExecutor() as ex:
            ex.map(stop_stress, ids)

        time.sleep(WAIT_INTERVAL)


# === MAIN ===
update_asg_timings(ASG_NAME, 0)
clear_old_files()

if TEST_MODE:
    log("🧪 Forcing DesiredCapacity for test...")
    asg.update_auto_scaling_group(AutoScalingGroupName=ASG_NAME, DesiredCapacity=EXPECTED)

log("⏳ Waiting for scale-out...")
final_ids = wait_for_scale_out(EXPECTED)

if TEST_MODE:
    log(f"✅ Scale-out reached: {len(final_ids)}")
    log("🕒 Waiting 5s for final EFS/UserData readiness...")
    time.sleep(5)

if not TEST_MODE:
    log("🔥 Triggering real stress to test ASG response...")
    with ThreadPoolExecutor() as executor:
        executor.map(start_stress, final_ids)

log("📁 Writing files to EFS")
with ThreadPoolExecutor() as ex:
    ex.map(write_efs, final_ids)

log("📤 Uploading mount info to S3")
with ThreadPoolExecutor() as ex:
    ex.map(upload_info, final_ids)

log("⏳ Waiting 10s before checking S3...")
time.sleep(10)

if count_s3_files() < len(final_ids):
    log("❌ Not all files uploaded")
    exit(1)

if compare_files(final_ids):
    log("✅ All EFS views match")
else:
    log("❌ EFS views mismatch")
    exit(1)

print(get_s3_file(f"{PREFIX}/{final_ids[0]}.txt"))

if TEST_MODE:
    log("🧪 Forcing DesiredCapacity down for test...")
    asg.update_auto_scaling_group(AutoScalingGroupName=ASG_NAME, DesiredCapacity=MIN_EXPECTED)

log("🧘 Stopping stress and waiting for scale-in...")
wait_for_scale_in(MIN_EXPECTED)

update_asg_timings(ASG_NAME, 300)
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

log("🎉 All tests passed!")

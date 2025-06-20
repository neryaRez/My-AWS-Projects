import boto3
import time

s3 = boto3.client("s3")
ec2 = boto3.client("ec2")
ssm = boto3.client("ssm")
efs = boto3.client("efs")

BUCKET = "your-bucket-name"
PREFIX = "efs-check"
ASG_NAME = "your-asg-name"
EFS_ID = "fs-xxxxxxx"  # <-- עדכן כאן
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
    print("🧹 קבצים ישנים נמחקו מתיקיית S3.")

def get_instance_ids():
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:aws:autoscaling:groupName", "Values": [ASG_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    return [inst["InstanceId"] for res in resp["Reservations"] for inst in res["Instances"]]

def start_stress_on_instances(instance_ids):
    for iid in instance_ids:
        try:
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["stress --cpu 2 --timeout 15000 &"]},
            )
            print(f"🔥 סטרס הופעל על {iid}")
        except Exception as e:
            print(f"⚠️ שגיאה בהרצת סטרס על {iid}: {e}")

def check_stress_running(instance_ids):
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
        except Exception as e:
            print(f"⚠️ שגיאה ב־{iid}: {e}")
    return success

def wait_for_scale_out(expected_count):
    waited = 0
    while waited < MAX_SCALE_WAIT:
        ids = get_instance_ids()
        print(f"🖥️ {len(ids)}/{expected_count} מכונות פעילות")
        if len(ids) >= expected_count:
            return ids
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL
    print("❌ לא הגיעו מספיק מכונות בזמן.")
    return []

def collect_mount_info(instance_ids, expected_dns):
    for iid in instance_ids:
        try:
            filename = f"/tmp/{iid}-efs-check.txt"
            cmd = (
                f"(mount | grep efs && echo && ls -la /mnt/efs && echo && echo 'Expected: {expected_dns}') > {filename} && "
                f"aws s3 cp {filename} s3://{BUCKET}/{PREFIX}/{iid}.txt"
            )
            ssm.send_command(
                InstanceIds=[iid],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [cmd]}
            )
            print(f"📤 mount + ls -la נשלח ל־{iid}")
        except Exception as e:
            print(f"⚠️ שגיאה ב־{iid}: {e}")

def count_uploaded_files():
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
    return len([obj for obj in response.get("Contents", []) if obj["Key"].endswith(".txt")])

def get_s3_file(key):
    resp = s3.get_object(Bucket=BUCKET, Key=key)
    return resp["Body"].read().decode("utf-8")

def compare_mount_outputs(instance_ids, expected_dns):
    base = get_s3_file(f"{PREFIX}/{instance_ids[0]}.txt")

    if expected_dns not in base:
        print(f"❌ {instance_ids[0]} לא מכיל את ה־EFS DNS {expected_dns}")
        return False

    for iid in instance_ids[1:]:
        other = get_s3_file(f"{PREFIX}/{iid}.txt")
        if other != base:
            print(f"❌ {iid} לא תואם ל־{instance_ids[0]}")
            return False
        if expected_dns not in other:
            print(f"❌ {iid} לא מכיל את ה־EFS DNS {expected_dns}")
            return False

    print("✅ כל ה־mounts תואמים וכוללים את ה־EFS DNS.")
    print("📂 כל הקבצים תואמים.")
    print(f"🔗 EFS DNS: {expected_dns}")
    print("✅ כל המכונות רואות את אותו mount EFS.")
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

print("🚀 התחלת טסט: סטרס + סקיילינג + EFS + mount + ניקוי")
clear_old_files()

ids = get_instance_ids()
if not ids:
    print("❌ אין מכונות פעילות בכלל.")
    exit(1)

print("🔥 מריץ פקודת סטרס בפועל על המכונות הקיימות")
start_stress_on_instances(ids)

time.sleep(10)  # זמן התחלה לפקודות stress

running = check_stress_running(ids)
if len(running) < len(ids):
    print("❌ סטרס לא רץ על כל המכונות. עוצר.")
    exit(1)
print(f"✅ סטרס רץ על {len(running)} מכונות.")

print("⏳ ממתין ל־scale-out...")
final_ids = wait_for_scale_out(EXPECTED)
if not final_ids:
    print("❌ לא כל המכונות עלו בזמן. עוצר.")
    exit(1)

if len(final_ids) < EXPECTED:
    print(f"❌ רק {len(final_ids)} מתוך {EXPECTED} עלו בפועל. עוצר.")
    exit(1)

expected_dns = get_efs_dns(EFS_ID)
print("📥 שולח פקודת mount + ls -la לכל המכונות")
collect_mount_info(final_ids, expected_dns)

print("⏳ ממתין 30 שניות ש־S3 יתעדכן...")
time.sleep(30)

print("📊 בודק מספר קבצים שהועלו ל-S3...")
uploaded_count = count_uploaded_files()
if uploaded_count < len(final_ids):
    print(f"❌ רק {uploaded_count} קבצים ב־S3 מתוך {len(final_ids)} מכונות – משהו נכשל.")
    exit(1)

print(f"🔍 בודק שכל mount זהה וכולל את ה־DNS: {expected_dns}")
if compare_mount_outputs(final_ids, expected_dns):
    print("✅ הצלחה: כל המכונות רואות את אותו mount EFS.")
else:
    print("❌ כישלון: mount לא אחיד או לא מתאים.")
    exit(1)

print("🧘 ממתין 5 דקות לקול-דאון...")
time.sleep(COOLDOWN_WAIT)

check_scale_in(MIN_EXPECTED)
print("✅ טסט הסתיים בהצלחה! כל המכונות חזרו למינימום אחרי הקול-דאון.")
print("🎉 כל הבדיקות עברו בהצלחה!")
# Note: Make sure to replace 'your-bucket-name', 'your-asg-name', and 'fs-xxxxxxx' with actual values.
#       Also, ensure that the necessary IAM permissions are set for the script to run successfully.

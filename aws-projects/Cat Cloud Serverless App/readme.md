## 🐱 Cat Cloud - Image Processing & Notification System

This project combines a Python desktop application with an AWS cloud architecture to allow users to upload cat pictures, apply transformations (flip, mirror, grayscale), and receive email notifications when a new image is uploaded. The system is fully serverless, secure, and scalable.

---

### ✨ Overview

**Client (Tkinter App):**

* Built with Python `TkinterDnD2` + `ttkbootstrap`
* Allows drag-and-drop or browse-based image selection
* Applies local image operations (flip, mirror, grayscale)
* Uploads the transformed image to a structured S3 bucket path (e.g., `grayscale/cat.jpeg`)

**Cloud (AWS Infrastructure):**

* Triggered by S3 events upon upload of `.jpeg` files
* Lambda 1 sends S3 object info to SQS
* Lambda 2 reads from SQS and publishes to SNS
* SNS sends email notifications with a view link to the image

---

### 🌌 Architecture Summary

```
[Tkinter App] → [S3 Bucket] → [Lambda 1: S3 to SQS] → [SQS Queue] → [Lambda 2: SQS to SNS] → [SNS Topic] → [Email]
```

---

### 🚀 Components

#### AWS CloudFormation Resources

* **S3 Bucket**: `cats-nerya-reznikov-<account>-<region>`
* **Lambda 1 (S3ToSQSFunction)**:

  * Triggered on `.jpeg` file creation
  * Sends bucket/key info to SQS
* **SQS Queue**: `CatImageQueue-Nerya_Reznikov`
* **Lambda 2 (SQSToSNSFunction)**:

  * Reads SQS messages
  * Constructs image URL
  * Sends to SNS topic
* **SNS Topic**: `CatPicturesTopic`
* **Email Subscription**: `neryarez@gmail.com`
* **Custom Resource Lambda**: Sets up S3 event notification via `PutBucketNotificationConfiguration`

---

### ⚖️ Security & Permissions

* Lambda IAM Role allows:

  * `sns:Publish`, `sqs:*`, `s3:GetObject`, and `logs:*`
* S3 bucket triggers Lambda securely via permission resource
* SQS is only writable by SNS topic (queue policy)

---

### 📆 Deployment Instructions

1. Deploy the CloudFormation stack:

```bash
aws cloudformation create-stack \
  --stack-name CatCloud \
  --template-body file://cat-cloud.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

2. Confirm SNS email subscription to start receiving notifications.
3. Run the `Cat Cloud` Tkinter app locally.

---

### 🚜 Image Upload Flow

1. User drops or browses for an image
2. Selects an operation (flip, mirror, grayscale)
3. Image is transformed locally and saved
4. Processed image is uploaded to the corresponding S3 folder
5. S3 triggers Lambda 1, which sends metadata to SQS
6. Lambda 2 picks up the message and notifies SNS
7. Email is sent with a direct link to the uploaded image

---

### 📅 Example Email Output

```
Subject: New Cat Uploaded!
Message:
New cat image has been uploaded!

View it here:
https://cats-nerya-reznikov-<account>.s3.amazonaws.com/grayscale/cat.jpeg
```

---

### 📃 Outputs

* `BucketName`: Name of the S3 bucket
* `QueueName`: SQS queue name
* `TopicARN`: SNS topic
* `Lambda1`: S3ToSQSFunction name
* `Lambda2`: SQSToSNSFunction name

---

### 🌟 Author

Created by **Nerya Reznikov**
Cloud DevOps Developer | Python Automation | AWS Projects

---

### 📊 Notes

* Image type filtered: only `.jpeg` files trigger the flow
* Lambda functions are inline (ZipFile) for easy stack deployment
* Add more subscribers to the SNS topic as needed

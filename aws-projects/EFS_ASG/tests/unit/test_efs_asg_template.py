import aws_cdk as core
import aws_cdk.assertions as assertions

from efs_asg.efs_asg_stacks import EfsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in efs/efs_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = EfsStack(app, "efs")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })

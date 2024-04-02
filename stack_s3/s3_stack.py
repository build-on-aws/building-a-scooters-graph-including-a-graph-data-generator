from aws_cdk import (
    Stack,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class S3Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, input_metadata, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket creation
        self.bucket = s3.Bucket(self, "scooters.demo",
                    # Let CDK to delete the bucket if this is empty:
                    removal_policy=RemovalPolicy.DESTROY)

        # Return bucket auto-generated name
        CfnOutput(self, "output-s3-bucket", value=self.bucket.bucket_arn, export_name="s3-bucket-arn")

from aws_cdk import (
    aws_lambda as _lambda,
    aws_lambda_python_alpha as _alambda,
    aws_s3 as s3,
    Stack, Fn, CfnOutput, Duration, Aws,
)
from constructs import Construct

class ScootersDataStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, input_metadata, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # AWS-maintained Lambda layer. More at: aws-sdk-pandas.readthedocs.io/en/stable/layers.html
        sdk_lambda_layer_arn = f"arn:aws:lambda:{Aws.REGION}:336392948345:layer:AWSSDKPandas-Python39:3"
        
        # Create function, using SDK for Pandas (formerly AWS DataWrangler), as a Lambda layer (aws-managed)
        lambda_fn = _alambda.PythonFunction(
            self,
            "lambda_fn",
            entry="./stack_lambda_datagen/",
            runtime=_lambda.Runtime.PYTHON_3_9,
            index="lambda_function.py",
            handler="lambda_handler",
            layers=[
                _alambda.PythonLayerVersion.from_layer_version_arn(
                    self,
                    'layer-sdk-for-pandas',
                    sdk_lambda_layer_arn
                    )
                ],
            timeout=Duration.seconds(600),
            memory_size=2048
        )

        # Fetch S3 bucket
        s3_bucket = s3.Bucket.from_bucket_attributes(self, "S3Bucket", bucket_arn=Fn.import_value("s3-bucket-arn"))

        # Grant Lambda to read and write on new bucket:
        s3_bucket.grant_read_write(lambda_fn)

        # Add OS default vars
        input_lambda_bucket = '{}'.format(s3_bucket.bucket_name)
        lambda_fn.add_environment(key='s3_bucket_name', value=input_lambda_bucket)
        lambda_fn.add_environment(key='s3_prefix', value=input_metadata['s3_prefix_scooters_data_loc'])
        lambda_fn.add_environment(key='datagen_num_of_vehicles', value=input_metadata['lambda_datagen_num_vehicles'])
        lambda_fn.add_environment(key='datagen_num_of_parts_per_vehicle', value=input_metadata['lambda_datagen_num_parts'])

        """
        @ Output begin
        """

        # Output: 
        CfnOutput(self, "output-datagen-Fn-name", value=lambda_fn.function_name)

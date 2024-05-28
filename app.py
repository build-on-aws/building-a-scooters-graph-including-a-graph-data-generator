import os
import aws_cdk as cdk
from aws_cdk import Environment, Tags
from stack_params_config.stack_ssm_config import SsmParametersStack
from stack_lambda_datagen.lambda_datagen_stack import ScootersDataStack
from stack_s3.s3_stack import S3Stack
from stack_vpc_neptune.vpc_neptune_stack import VpcNeptuneStack


# AWS Settings
app = cdk.App()
env_aws_settings = Environment(account=os.environ['CDK_DEFAULT_ACCOUNT'], region=os.environ['CDK_DEFAULT_REGION'])

# Add environment to deploy (see cdk.json file). CLI: cdk deploy --context <<env-production>> 
env_context_params = app.node.try_get_context("env-production")

# Optional, so you can store above's parameters in AWS Systems Manager SSM instead
stack_ssm = SsmParametersStack(app, "ScootersSsmParametersStack",
                              input_metadata=env_context_params, 
                              env=env_aws_settings
                              )

# Amazon S3 bucket for Graph data
stack_s3 = S3Stack(app, "ScootersS3Stack", 
                   input_metadata=env_context_params, 
                   env=env_aws_settings
                   )

# AWS Lambda stack to create the Graph data generator
stack_lambda_datagen = ScootersDataStack(app, "ScootersDataStack",
                                         input_metadata=env_context_params, 
                                         env=env_aws_settings
                                         )

# Amazon Neptune cluster and VPC stack
stack_vpc_neptune = VpcNeptuneStack(app, "ScootersNeptuneStack",
                              input_metadata=env_context_params,
                              env=env_aws_settings
                              )

# Stack dependencies
stack_lambda_datagen.add_dependency(stack_s3)
stack_vpc_neptune.add_dependency(stack_s3)

# Tagging all stacks:
Tags.of(stack_s3).add("project", "scooters-demo/stack-s3")
Tags.of(stack_lambda_datagen).add("project", "scooters-demo/stack-lambda-datagen")
Tags.of(stack_vpc_neptune).add("project", "scooters-demo/stack-vpc-neptune")


app.synth()
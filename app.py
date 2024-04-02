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

# Choose environment to deploy; see cdk.json file. CLI: cdk deploy --context <<env-production>> 
env_context_params = app.node.try_get_context("env-production")

# SSM Parameters. Here, you can save above's DICT, instead of hard-coding.
ssm_stack = SsmParametersStack(app, "ScootersSsmParametersStack",
                              input_metadata=env_context_params, 
                              env=env_aws_settings
                              )

# S3 stack to create bucket
stack_s3 = S3Stack(app, "ScootersS3Stack", 
                   input_metadata=env_context_params, 
                   env=env_aws_settings
                   )

# Lambda stack to create Graph data generator
stack_lambda_datagen = ScootersDataStack(app, "ScootersDataStack",
                                         input_metadata=env_context_params, 
                                         env=env_aws_settings
                                         )

# Neptune cluster stack;
stack_vpc_neptune = VpcNeptuneStack(app, "ScootersNeptuneStack",
                              input_metadata=env_context_params,
                              env=env_aws_settings
                              )

# Stack dependencies (i.e. both, dataGen and Neptune cluster, need the S3 bucket to grant RW privs)
stack_lambda_datagen.add_dependency(stack_s3)
stack_vpc_neptune.add_dependency(stack_s3)

# Tagging all stacks:
Tags.of(stack_s3).add("project", "scooters-demo/stack-s3")
Tags.of(stack_lambda_datagen).add("project", "scooters-demo/stack-lambda-datagen")
Tags.of(stack_vpc_neptune).add("project", "scooters-demo/stack-vpc-neptune")


app.synth()
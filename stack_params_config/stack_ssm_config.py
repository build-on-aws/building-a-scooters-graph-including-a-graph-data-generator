from random import choices
from string import ascii_lowercase, digits 
from constructs import Construct
from aws_cdk import (
    Aws,
    Stack,
    aws_ssm as ssm,
)

class SsmParametersStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, input_metadata, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # i.e. Neptune requires the notebook name to begin with "aws-neptune", so we can't leave CDK Logical IDs.
        # - optional: you can add a random suffix as CDK does to string_value, to avoid names dups errors when deploying N times this stack
        ssm.StringParameter(self, 'myNotebookSsmParameter',
            parameter_name='buildOnAWSScootersNotebook',
            description='Notebook name for Neptune workbench',
            string_value='aws-neptune-buildOnAWSScootersNotebook'
        )

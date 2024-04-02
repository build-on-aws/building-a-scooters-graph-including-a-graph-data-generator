import ast
from constructs import Construct
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Tags,
    Fn,
    Aws,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_neptune_alpha as neptune,
    aws_s3 as s3,
    aws_iam as iam,
    aws_sagemaker as sagemaker,
    aws_lambda_python_alpha as _alambda,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
)

class VpcNeptuneStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, input_metadata, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        """
        @ VPC creation or Get existing VPC:
        """

        # VPC creation or using existing one from options:
        if input_metadata['vpc_neptune']:
            # Using existing VPC
            vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=input_metadata['vpc_neptune'])
        else:
            # Create VPC if none provided, including private subnet.
            vpc = ec2.Vpc(self, "VPC",
                               max_azs=2,
                               ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16")
                               )

        # VPC Security Group:
        sg_neptune = ec2.SecurityGroup(
            self,
            id="sg_neptune",
            vpc=vpc,
            security_group_name="sg_neptune"
        )

        # Security Group (SG) inbound rules:
        # - Granting all TCP communication (self-reference in/rule), among the resources added to this SG.
        sg_neptune.add_ingress_rule(peer=sg_neptune,
                                    connection=ec2.Port.all_tcp(),
                                    description="self-reference rule, to allow all TCP within same group only")

        """
        @ Neptune cluster creation:
        """

        # Neptune IAM role to attach (i.e. grant S3 privileges)
        iam_neptune_role = iam.Role(self, "scooters-neptune-role",
                assumed_by=iam.ServicePrincipal("rds.amazonaws.com"))
        
        # Fetch S3 bucket
        s3_bucket = s3.Bucket.from_bucket_attributes(self, "S3Bucket", bucket_arn=Fn.import_value("s3-bucket-arn"))

        # Grant Lambda to read and write on new bucket:
        s3_bucket.grant_read_write(iam_neptune_role)

        # Neptune cluster creation. Sample for provisioned (non-serverless) clusters:  
        #    --> instance_type=neptune.InstanceType.T3_MEDIUM, instances=1, removal_policy=RemovalPolicy.DESTROY,
        db_cluster = neptune.DatabaseCluster(self, "neptune-db", 
                                             vpc=vpc,
                                             instance_type=neptune.InstanceType.SERVERLESS,
                                             serverless_scaling_configuration=neptune.ServerlessScalingConfiguration(
                                                min_capacity=1,
                                                max_capacity=5
                                                ),
                                             security_groups=[sg_neptune],
                                             associated_roles=[iam_neptune_role],
                                             removal_policy=RemovalPolicy.DESTROY
                                            )
        
        # Fetch network config, from the deployed Neptune cluster
        neptune_security_group = db_cluster.connections.security_groups[0]
        neptune_security_group_id = neptune_security_group.security_group_id
        neptune_subnet = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT).subnets[0]
        neptune_subnet_id = neptune_subnet.subnet_id

        """
        @ Jupyter Notebook creation:
        """

        # Create an IAM policy for the Notebook
        notebook_role_policy_doc = iam.PolicyDocument()
        
        # Add Amazon S3 read/write permissions, to load CSV data
        notebook_role_policy_doc.add_statements(iam.PolicyStatement(**{
            "effect": iam.Effect.ALLOW,
            "resources": ["arn:aws:s3:::aws-neptune-notebook", "arn:aws:s3:::aws-neptune-notebook/*"],
            "actions": ["s3:GetObject", "s3:ListBucket"]
            })
        )

        # Add Amazon Bedrock permissions, to use natural language to query our Graph
        # - Important: you still need to grant model access. See https://go.aws/48ZEVx1
        notebook_role_policy_doc.add_statements(iam.PolicyStatement(**{
            "effect": iam.Effect.ALLOW,
            "resources": ["*"],
            "actions": ["bedrock:ListFoundationModels","bedrock:InvokeModel"]
            })
        )

        # Create a role and add the policy to it
        # - Optional: role_name='AWSNeptuneNotebookRole-CDK'
        notebook_role = iam.Role(self, 'Neptune-CDK-Notebook-Role',
            assumed_by=iam.ServicePrincipal('sagemaker.amazonaws.com'),
            inline_policies={
                'AWSNeptuneNotebook-CDK': notebook_role_policy_doc
            }
        )

        # Retrieve local config, with the Neptune lifecycle script
        with open("stack_vpc_neptune/neptune_lifecycle.sh","r") as f:
                notebook_lifecycle_script = f.read()

        # Replace host and region in lifecycle script
        notebook_lifecycle_script = notebook_lifecycle_script.replace('replace_cluster_endpoint_hostname',db_cluster.cluster_endpoint.hostname)
        notebook_lifecycle_script = notebook_lifecycle_script.replace('replace_aws_region',Aws.REGION)

        # Create SageMaker Lifecycle, for the notebook
        notebook_lifecycle_config = sagemaker.CfnNotebookInstanceLifecycleConfig(self, 'NeptuneWorkbenchLifeCycleConfig',
            notebook_instance_lifecycle_config_name='aws-neptune-lifecycle',
            on_start=[sagemaker.CfnNotebookInstanceLifecycleConfig.NotebookInstanceLifecycleHookProperty(
            content=Fn.base64(notebook_lifecycle_script)
            )]
        )

        # Create Notebook instance, using AWS SageMaker. 
        # - It's not a good practice to use physical names.
        # - However, notebook_instance_name prefix has to be "aws-neptune-*", to show on AWS Neptune console (not only on SageMaker). 
        #   You can change the string after the prefix.
        notebook = sagemaker.CfnNotebookInstance(self, 'CDKNeptuneWorkbench',
            instance_type='ml.t3.medium',
            role_arn=notebook_role.role_arn,
            lifecycle_config_name=notebook_lifecycle_config.notebook_instance_lifecycle_config_name,
            notebook_instance_name='aws-neptune-buildOnAWSScootersNotebook',
            root_access='Disabled',
            security_group_ids=[neptune_security_group_id],
            subnet_id=neptune_subnet_id,
            direct_internet_access='Enabled',
        )

        # Add tags required by Neptune Workbench:
        Tags.of(notebook).add('aws-neptune-cluster-id', db_cluster.cluster_identifier)
        Tags.of(notebook).add('aws-neptune-resource-id', db_cluster.cluster_resource_identifier)

        """
        @ Lambda fn creation - DB Queries:
        """

        # Create DB Query function
        lambda_fn = _alambda.PythonFunction(
            self,
            "lambda_fn",
            entry="./stack_vpc_neptune/",
            vpc=vpc,
            security_groups=[sg_neptune],
            runtime=_lambda.Runtime.PYTHON_3_9,
            index="lambda_function.py",
            handler="lambda_handler",
            timeout=Duration.seconds(600),
            memory_size=2048
        )

        # Grant Lambda to access Amazon Bedrock
        lambda_fn.add_to_role_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=["*"],
                actions=["bedrock:ListFoundationModels","bedrock:InvokeModel"]
            )
        )

        """
        @ API Gateway creation:
        """

        # List of IPs to whitelist
        approved_ip_list = []

        # Validate if user entered IP address(es) to whitelist
        if 'api_gtw_ip_addr_whitelist_list' in input_metadata and input_metadata['api_gtw_ip_addr_whitelist_list']: 
            ips = input_metadata['api_gtw_ip_addr_whitelist_list']
            ips_to_whitelist = ast.literal_eval(ips)

            for i in ips_to_whitelist:
                approved_ip_list.append(i)

        # Create new API Gateway Resource Policy, allowing only the approved IP addresses or CIDR ranges
        api_resource_policy = iam.PolicyDocument(
             statements=[
                  iam.PolicyStatement(
                       actions=['execute-api:Invoke'],
                       principals=[iam.AnyPrincipal()],
                       resources=['execute-api:/*/*/*']
                  ),
                  iam.PolicyStatement(
                       effect=iam.Effect.DENY,
                       principals=[iam.AnyPrincipal()],
                       resources=['execute-api:/*/*/*'],
                       conditions={
                            "NotIpAddress": {
                                 "aws:SourceIp": approved_ip_list
                                 }
                            }
                  )
                  ]
        )

        # API gateway creation
        api = apigateway.RestApi(self, "api-query-db",
                                 rest_api_name='queryNeptuneV1',
                                 policy=api_resource_policy,
                                 description='This service allows to query the Scooters graph in Neptune')

        """
        @ API REST Methods:
        """

        # API gateway integration with Lambda
        api_get_scooters = apigateway.LambdaIntegration(lambda_fn,
                                                        request_templates={"application/json": '{ "statusCode": "200" }'}
                                                        )
        # Add GET method, to query Scooters by asset code id:
        rest_get_scooter = api.root.add_resource('getScooter')
        rest_get_scooter.add_method("GET", api_get_scooters,
                            request_parameters={
                                 "method.request.querystring.scooter_asset_code": True,
                                 "method.request.querystring.neptune_endpoint": True
                                 })
        
        # Add GET method, to run open Gremlin queries:
        rest_run_query = api.root.add_resource('runQuery')
        rest_run_query.add_method("GET", api_get_scooters,
                            request_parameters={
                                 "method.request.querystring.gremlin_query": True,
                                 "method.request.querystring.neptune_endpoint": True
                                 })
        
        # Add GET method, to submit a question to the LLM via Bedrock 
        rest_ask_graph = api.root.add_resource('askGraph')
        rest_ask_graph.add_method("GET", api_get_scooters,
                            request_parameters={
                                 "method.request.querystring.llm_query": True,
                                 "method.request.querystring.neptune_endpoint": True
                                 })               
                                 
        """
        @ Output begin
        """

        # Output: 
        CfnOutput(self, "output-s3-bucket", value=s3_bucket.bucket_name)

        # Output: 
        CfnOutput(self, "output-neptune-iam-role", value=iam_neptune_role.role_arn)

        # Output: 
        CfnOutput(self, "output-neptune-endpoint", value=db_cluster.cluster_endpoint.hostname)

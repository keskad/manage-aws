from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamo_db,
    aws_s3 as s3,
    aws_iam as iam,
    CfnOutput, Duration,
)
from constructs import Construct


class KubeCICDStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.configure_iam(
            bucket=self.create_states_bucket(),
            table=self.create_locks_table()
        )

    def configure_iam(self, bucket, table):
        """Terraform role for secure access within GitHub Actions via OIDC"""

        gh_provider = iam.OpenIdConnectProvider(
            self,
            id="GitHubProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
        )

        gh_oidc_principal = iam.OpenIdConnectPrincipal(gh_provider).with_conditions({
            "StringLike": {
                "token.actions.githubusercontent.com:sub": "repo:kube-cicd/.manage:*"
            },
            "StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
        })

        tf_policy = iam.ManagedPolicy(
            self,
            managed_policy_name="kubecicd-terraform-state-lock",
            id="TerraformBackendPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                        "s3:GetObjectVersion",
                        "s3:DeleteObjectVersion",
                    ],
                    resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
                ),
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:DescribeTable",
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:DeleteItem",
                    ],
                    resources=[table.table_arn],
                ),
            ],
        )
        gh_assume_role = iam.Role(
            self,
            id="KubeCICDActionsAssumeRole",
            role_name="kube-cicd-assume-role",
            assumed_by=gh_oidc_principal,
            description="Assume role for kube-cicd organization on GitHub",
            max_session_duration=Duration.hours(2),
        )
        stm = iam.PolicyStatement(
            sid="AllowAssumeOnlySelectedRolesForKubeCICDGH",
            actions=["sts:AssumeRole"],
        )

        tf_role = iam.Role(
            self,
            id="KubeCICDActionsRole",
            role_name="kube-cicd-actions-role",
            description="Role for Terraform with access to S3 state and DynamoDB locks",
            max_session_duration=Duration.hours(2),
            assumed_by=iam.ArnPrincipal(
                f"{gh_assume_role.role_arn}"
            ),
        )

        tf_role.add_managed_policy(tf_policy)
        gh_assume_role.add_to_policy(stm)
        stm.add_resources(tf_role.role_arn)
        CfnOutput(self, "AssumeRoleArn", value=gh_assume_role.role_arn)
        CfnOutput(self, "ActionsRoleArn", value=tf_role.role_arn)

    def create_locks_table(self) -> dynamo_db.Table:
        """DynamoDB table for locks with LockID partition key"""
        table = dynamo_db.Table(self, id="TFLockTables",
                                table_name="TFLockTables",
                                removal_policy=RemovalPolicy.RETAIN,
                                billing_mode=dynamo_db.BillingMode.PAY_PER_REQUEST,
                                partition_key=dynamo_db.Attribute(
                                    name="LockID", type=dynamo_db.AttributeType.STRING
                            ))

        CfnOutput(self, "LockTableName", value=table.table_name)
        return table

    def create_states_bucket(self) -> s3.Bucket:
        """Creates an S3 bucket for Terraform state files"""
        bucket = s3.Bucket(self, id="TFStates",
                           block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           bucket_name="damiank-tfstates",
                           encryption=s3.BucketEncryption.S3_MANAGED,
                           removal_policy=RemovalPolicy.RETAIN,
                           auto_delete_objects=False,
                           enforce_ssl=True,
                           versioned=True)

        # add a policy to deny non-tls connections
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureTransport",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        CfnOutput(self, "StateBucketName", value=bucket.bucket_name)
        return bucket

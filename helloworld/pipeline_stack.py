from aws_cdk import (
    core as cdk,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_codebuild as codebuild,
    pipelines as pipelines
)

from helloworld.application_stack import HelloWorldStage
from helloworld.buildspec import build_spec as linked_build_spec

class PipelineStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECR
        ecr_repo = ecr.Repository(self, "ECRRepo",
            repository_name="helloworldlambdacontainer"
        )
        ecr_repo.add_lifecycle_rule(max_image_count=10)

        # Github Source
        git_hub = pipelines.CodePipelineSource.git_hub(
                    "stuartgraham/HelloWorldCDKPipeline",
                    "lambdacontainer",
                    authentication=cdk.SecretValue.secrets_manager("github-token")
                )

        # Pipeline
        ## Synth
        pipeline = pipelines.CodePipeline(self, "Pipeline",
            synth = pipelines.ShellStep("Synth",
                input = git_hub,
                commands=[
                    "pip install -r requirements.txt", "npm install -g aws-cdk", "cdk synth"
                ]
            ),
            pipeline_name="HelloWorldPipeline"
        )

        ## Container build
        build_spec = codebuild.BuildSpec.from_object(linked_build_spec)
        build_role = iam.Role(self, "CodeBuildRole", 
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser")
            ]
        )
        build_role.add_to_policy(iam.PolicyStatement(
                resources=["*"],
                actions=["ssm:PutParameter"]
        ))

        # Change to this when ARM support is added to build environment
        # https://github.com/aws/aws-cdk/pull/16635
        # build_environment = codebuild.BuildEnvironment(
        #     build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM,
        #     compute_type=codebuild.ComputeType.SMALL,
        #     privileged=True
        #     )

        build_environment = codebuild.BuildEnvironment(
            build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
            compute_type=codebuild.ComputeType.SMALL,
            privileged=True
            )

        container_build = pipelines.CodeBuildStep("ContainerBuild",
            build_environment = build_environment,
            input = git_hub,
            partial_build_spec=build_spec,
            commands=[],
            role=build_role,
            env={
                "AWS_ACCOUNT_ID": self.account,
                "REPO_NAME":  f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repo.repository_name}"
            }
        )

        # App deploy
        hello_world_app = HelloWorldStage(self, "HelloWorldApp", ecr_repo=ecr_repo)
        pipeline.add_stage(hello_world_app, pre=[container_build])

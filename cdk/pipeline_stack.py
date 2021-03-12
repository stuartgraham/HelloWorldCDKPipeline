from os import path
from aws_cdk import (
    core,
    aws_ecr as ecr,
    aws_codebuild as codebuild
)
from .buildspec import buildspec as buildspec

class PipelineStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        this_dir = path.dirname(__file__)

        # ECR
        ecr_repo = ecr.Repository(self, "HelloWorldRepo")

        # Codebuild
        codebuild.GitHubSourceCredentials(self, "CodeBuildGitHubCreds",
            access_token=core.SecretValue.secrets_manager("github-token")
        )
        
        github_source = codebuild.Source.git_hub(
            owner="stuartgraham",
            repo="HelloWorldCodePipeline",
            webhook=True,
            webhook_triggers_batch_build=False,
            webhook_filters=[
                codebuild.FilterGroup.in_event_of(codebuild.EventAction.PUSH)
            ]
        )

        codebuild.Project(self, "HelloWorldBuildProject", 
            source=github_source, 
            build_spec=codebuild.BuildSpec.from_object(buildspec),
            environment=codebuild.BuildEnvironment(build_image=codebuild.LinuxBuildImage.STANDARD_4_0,
                privileged=True),        
            environment_variables= {
            'TEST': {'value': 'test'},
            #'PACKAGE_BUCKET': {'value': artifactsBucket.bucket_name},
            #'AWS_ACCOUNT_ID': {'value': self.account},
            'IMAGE_REPO_NAME': {'value': f'{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repo}'},
            #'IMAGE_TAG': {'value': tag}, 
            }            
            )



from os import path
import yaml

from aws_cdk import (
    core,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_iam as _iam
)

class PipelineStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        this_dir = path.dirname(__file__)
        with open(path.join(this_dir, 'buildspec.yaml')) as f:
            buildspec = yaml.load(f, Loader=yaml.FullLoader)

        # ECR
        ecr_repo = ecr.Repository(self, "HelloWorldRepo",
            repository_name='helloworld'
        )

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

        helloworld_codebuild_project = codebuild.Project(self, "HelloWorldBuildProject", 
            source=github_source, 
            build_spec=codebuild.BuildSpec.from_object(buildspec),
            environment=codebuild.BuildEnvironment(build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True),        
            environment_variables= {
            'AWS_ACCOUNT_ID': {'value': self.account},
            'REPO_NAME': {'value': f'{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repo.repository_name}'}
            }            
            )

        helloworld_codebuild_project.role.add_managed_policy(
                _iam.ManagedPolicy.from_aws_managed_policy_name('AmazonEC2ContainerRegistryPowerUser'))




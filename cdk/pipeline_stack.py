from aws_cdk import (
    core,
    aws_ecr as ecr,
    aws_codebuild as codebuild
)

class PipelineStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        codebuild.Project(self, "HelloWorldBuildProject", source=github_source)
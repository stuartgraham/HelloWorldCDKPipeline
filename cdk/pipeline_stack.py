from os import path
import yaml

from aws_cdk import (
    core,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_codebuild as codebuild,
    aws_codedeploy as codedeploy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elb,
    aws_elasticloadbalancingv2_targets as elb_targets
)

class PipelineStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        this_dir = path.dirname(__file__)
        with open(path.join(this_dir, "buildspec.yaml")) as f:
            buildspec = yaml.load(f, Loader=yaml.FullLoader)
        
        # ECR
        ecr_repo = ecr.Repository(self, "HelloWorldRepo",
            repository_name="helloworld"
        )
        ecr_repo.add_lifecycle_rule(max_image_count=10)

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
            "AWS_ACCOUNT_ID": {"value": self.account},
            "REPO_NAME": {"value": f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repo.repository_name}"}
            }            
            )

        helloworld_codebuild_project.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"))

        # Codedeploy
        hello_world_application = codedeploy.EcsApplication(self, "HelloWorldApplication",
            application_name="HelloWorld"
        )

        hello_world_codedeloy_role  = iam.Role(self, "HelloWorldCodeDeployRole",
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"))

        hello_world_codedeloy_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeDeployRoleForECS")
        )


        # VPC
        target_vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_name="Main VPC")

        # ALB
        helloworld_alb = elb.ApplicationLoadBalancer(self, "HelloWorldALB",
            vpc=target_vpc,
            internet_facing=True
        )

        helloworld_listener_1 = helloworld_alb.add_listener("HelloWorldListener1",
            port=80,
            open=True
        )

        helloworld_listener_2 = helloworld_alb.add_listener("HelloWorldListener2",
            port=8080,
            open=True
        )

        helloworld_tg1 = elb.ApplicationTargetGroup(self, "HelloWorldTG1",
            target_type=elb.TargetType.IP,
            port=5000,
            protocol=elb.ApplicationProtocol("HTTP"),
            vpc=target_vpc
        )

        helloworld_tg2 = elb.ApplicationTargetGroup(self, "HelloWorldTG2",
            target_type=elb.TargetType.IP,
            port=5000,
            protocol=elb.ApplicationProtocol("HTTP"),
            vpc=target_vpc
        )

        helloworld_listener_1.add_target_groups("HelloWorldAddTG1",
            target_groups=[helloworld_tg1]
        )

        helloworld_listener_2.add_target_groups("HelloWorldAddTG2",
            target_groups=[helloworld_tg2]
        )



        # ECS
        hello_world_ecs_cluster = ecs.Cluster(self, "HelloWorldEcsCluster",
            cluster_name="HelloWorldCluster",
            capacity_providers=["FARGATE", "FARGATE_SPOT"],
            vpc=target_vpc
        )

        # ECS Task
        hello_world_ecs_exec_role  = iam.Role(self, "FargateContainerExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))

        hello_world_ecs_task_role  = iam.Role(self, "FargateContainerTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))
        
        hello_world_task_def = ecs.FargateTaskDefinition(self, "HelloWorldTaskDef",
            memory_limit_mib=512,
            cpu=256,
            execution_role=hello_world_ecs_exec_role, 
            task_role=hello_world_ecs_task_role
        )

        hello_world_container = hello_world_task_def.add_container("HelloWorld",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo)
        )

        hello_world_security_group = ec2.SecurityGroup(
            self, "HelloWorldContainerSG",
            vpc=target_vpc,
            allow_all_outbound=True
        )
        hello_world_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(5000)
        )

        fargate_capacity_provider_strategy = ecs.CapacityProviderStrategy(
            capacity_provider="FARGATE",
            base=1,
            weight=0
        )
        fargate_spot_capacity_provider_strategy = ecs.CapacityProviderStrategy(
            capacity_provider="FARGATE_SPOT",
            base=0,
            weight=100
        )


        hello_world_ecs_service = ecs.FargateService(self, "HelloWorldService",
            cluster=hello_world_ecs_cluster,
            task_definition=hello_world_task_def,
            desired_count=5,
            assign_public_ip=False,
            security_groups=[hello_world_security_group],
            capacity_provider_strategies=[
                fargate_spot_capacity_provider_strategy,
                fargate_capacity_provider_strategy
            ]
        )




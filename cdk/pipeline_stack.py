from os import path
import yaml

from aws_cdk import (
    core,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_codebuild as codebuild,
    aws_codedeploy as codedeploy,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
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

        # Codepipeline
        pipeline = codepipeline.Pipeline(self, "HelloWorldPipeline",
            pipeline_name="HelloWorldPipeline",
        )

        github_source_artifact = codepipeline.Artifact()
        source_action = codepipeline_actions.GitHubSourceAction(
            action_name="GitHub_Source",
            owner="stuartgraham",
            repo="HelloWorldCodePipeline",
            oauth_token=core.SecretValue.secrets_manager("github-token"),
            output=github_source_artifact,
            branch="main"
        )
        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action]
        )

        codebuild_project = codebuild.PipelineProject(self, "HelloWorldBuildProject", 
            build_spec=codebuild.BuildSpec.from_object(buildspec),
            environment=codebuild.BuildEnvironment(build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True),        
            environment_variables= {
            "AWS_ACCOUNT_ID": {"value": self.account},
            "REPO_NAME": {"value": f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repo.repository_name}"}
            }            
            )

        codebuild_project.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"))

        build_action = codepipeline_actions.CodeBuildAction(
            action_name="CodeBuild",
            project=codebuild_project,
            input=github_source_artifact,
            outputs=[codepipeline.Artifact()],
            execute_batch_build=True
        )

        pipeline.add_stage(
            stage_name="Build",
            actions=[build_action]
        )

        # Codedeploy
        application = codedeploy.EcsApplication(self, "HelloWorldApplication",
            application_name="HelloWorld"
        )

        codedeloy_role  = iam.Role(self, "HelloWorldCodeDeployRole",
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"))

        codedeloy_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeDeployRoleForECS")
        )


        # VPC
        target_vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_name="Main VPC")

        # ALB
        alb = elb.ApplicationLoadBalancer(self, "HelloWorldALB",
            vpc=target_vpc,
            internet_facing=True
        )

        listener_1 = alb.add_listener("HelloWorldListener1",
            port=80,
            open=True
        )

        listener_2 = alb.add_listener("HelloWorldListener2",
            port=8080,
            open=True
        )

        tg1 = elb.ApplicationTargetGroup(self, "HelloWorldTG1",
            target_type=elb.TargetType.IP,
            port=5000,
            protocol=elb.ApplicationProtocol("HTTP"),
            vpc=target_vpc
        )

        tg2 = elb.ApplicationTargetGroup(self, "HelloWorldTG2",
            target_type=elb.TargetType.IP,
            port=5000,
            protocol=elb.ApplicationProtocol("HTTP"),
            vpc=target_vpc
        )

        listener_1.add_target_groups("HelloWorldAddTG1",
            target_groups=[tg1]
        )

        listener_2.add_target_groups("HelloWorldAddTG2",
            target_groups=[tg2]
        )



        # ECS
        ecs_cluster = ecs.Cluster(self, "HelloWorldEcsCluster",
            cluster_name="HelloWorldCluster",
            capacity_providers=["FARGATE", "FARGATE_SPOT"],
            vpc=target_vpc
        )

        # ECS Task
        ecs_exec_role  = iam.Role(self, "FargateContainerExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))

        ecs_task_role  = iam.Role(self, "FargateContainerTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))
        
        task_def = ecs.FargateTaskDefinition(self, "HelloWorldTaskDef",
            memory_limit_mib=512,
            cpu=256,
            execution_role=ecs_exec_role, 
            task_role=ecs_task_role
        )

        container = task_def.add_container("HelloWorld",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo)
        )

        port_mapping = ecs.PortMapping(container_port=5000, host_port=5000)
        container.add_port_mappings(port_mapping)

        security_group = ec2.SecurityGroup(
            self, "HelloWorldContainerSG",
            vpc=target_vpc,
            allow_all_outbound=True
        )
        security_group.add_ingress_rule(
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

        code_deploy_deployment_controller = ecs.DeploymentController(
            type=ecs.DeploymentControllerType.CODE_DEPLOY
        )

        ecs_service = ecs.FargateService(self, "HelloWorldService",
            cluster=ecs_cluster,
            task_definition=task_def,
            desired_count=5,
            assign_public_ip=False,
            security_groups=[security_group],
            capacity_provider_strategies=[
                fargate_spot_capacity_provider_strategy,
                fargate_capacity_provider_strategy
            ],
            deployment_controller=code_deploy_deployment_controller
        )
        ecs_service.attach_to_application_target_group(tg1)




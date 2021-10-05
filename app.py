#!/usr/bin/env python3
from aws_cdk import core
from helloworld.pipeline_stack import PipelineStack

app = core.App()
aws_env = core.Environment(account="811799881965", region="eu-west-1")

PipelineStack(app, "HelloWorldPipeline", 
    env=aws_env
    )

app.synth()

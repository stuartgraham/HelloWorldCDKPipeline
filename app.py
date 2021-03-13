#!/usr/bin/env python3

from aws_cdk import core

from cdk.pipeline_stack import PipelineStack

aws_env = core.Environment(account="811799881965", region="eu-west-1")

app = core.App()
PipelineStack(app, "HelloWorld", env=aws_env)

app.synth()

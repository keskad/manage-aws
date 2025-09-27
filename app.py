#!/usr/bin/env python3
import os
import aws_cdk as cdk
from manage_aws.kube_cicd_stack import KubeCICDStack

app = cdk.App()

KubeCICDStack(app,
              "KubeCICDStack",
              env=cdk.Environment(
                  account=app.node.try_get_context("account"),
                  region="eu-central-1",
              ),
              )

app.synth()

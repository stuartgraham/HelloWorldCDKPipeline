build_spec = {
    "version": "0.2",
    "phases": {
        "install": {
            "commands": [
                "echo Install phase started",
                "cd container",
                "echo $REPO_NAME"
            ]
        },
        "pre_build": {
            "commands": [
                "echo Logging in to Amazon ECR",
                "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
            ]
        },
        "build": {
            "commands": [
                "echo Starting build number $CODEBUILD_BUILD_NUMBER",
                "echo Building image",
                "BUILD_PREFIX=1.0.",
                "TAG_NAME=$BUILD_PREFIX$CODEBUILD_BUILD_NUMBER",
                "LATEST_IMAGE_TAG=$TAG_NAME",
                "echo $LATEST_IMAGE_TAG",
                "aws ssm put-parameter --name \"/HelloWorldLambdaContainer/LatestImage\" --type \"String\" --value $LATEST_IMAGE_TAG --overwrite",
                "echo $TAG_NAME",
                "docker build --no-cache -t $REPO_NAME:$TAG_NAME .",
                "docker tag $REPO_NAME:$TAG_NAME $REPO_NAME:latest"
            ]
        },
        "post_build": {
            "commands": [
                "echo Pushing Docker images",
                "docker push $REPO_NAME:$TAG_NAME",
                "docker push $REPO_NAME:latest",
                "echo Build complete"
            ]
        }
    }
}
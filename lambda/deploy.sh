#!/bin/bash
# Lambda 배포 스크립트 — ffmpeg Layer + gif_processor 함수
#
# 사전 조건:
#   - AWS CLI 설치 및 자격증명 설정 (aws configure)
#   - lambda/build_layer.sh 먼저 실행해서 ffmpeg-layer.zip 생성
#
# 실행: bash lambda/deploy.sh [--layer-only | --function-only]
#   옵션 없음: Layer + 함수 둘 다 배포
#   --layer-only: Layer만 배포
#   --function-only: 함수만 배포 (Layer ARN 필요)

set -e

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
FUNCTION_NAME="gifgloo-gif-processor"
LAYER_NAME="gifgloo-ffmpeg"
LAYER_ZIP="lambda/layer/ffmpeg-layer.zip"
FUNCTION_DIR="lambda/gif_processor"
FUNCTION_ZIP="/tmp/gifgloo-gif-processor.zip"
RUNTIME="python3.12"
MEMORY=512    # MB
TIMEOUT=300   # 초 (5분)

MODE="${1:-all}"

deploy_layer() {
    echo "▶ ffmpeg Layer 배포 중..."

    if [ ! -f "$LAYER_ZIP" ]; then
        echo "❌ $LAYER_ZIP 없음 — 먼저 bash lambda/build_layer.sh 실행"
        exit 1
    fi

    LAYER_ARN=$(aws lambda publish-layer-version \
        --layer-name "$LAYER_NAME" \
        --description "ffmpeg static binary for GIF processing" \
        --zip-file "fileb://$LAYER_ZIP" \
        --compatible-runtimes python3.12 \
        --compatible-architectures x86_64 \
        --region "$AWS_REGION" \
        --query "LayerVersionArn" \
        --output text)

    echo "✓ Layer 배포 완료"
    echo "  ARN: $LAYER_ARN"
    echo "$LAYER_ARN" > lambda/.layer_arn
}

deploy_function() {
    echo "▶ gif_processor 함수 패키징 중..."
    cd "$FUNCTION_DIR"
    zip -r "$FUNCTION_ZIP" handler.py
    cd -

    # Layer ARN 읽기
    if [ ! -f "lambda/.layer_arn" ]; then
        echo "❌ lambda/.layer_arn 없음 — 먼저 Layer 배포 필요"
        exit 1
    fi
    LAYER_ARN=$(cat lambda/.layer_arn)

    # 함수 존재 여부 확인
    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" > /dev/null 2>&1; then
        echo "▶ 기존 함수 업데이트 중..."
        aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file "fileb://$FUNCTION_ZIP" \
            --region "$AWS_REGION" > /dev/null

        aws lambda update-function-configuration \
            --function-name "$FUNCTION_NAME" \
            --layers "$LAYER_ARN" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY" \
            --region "$AWS_REGION" > /dev/null
    else
        echo "▶ 새 함수 생성 중..."

        # IAM Role ARN 필요
        if [ -z "$LAMBDA_ROLE_ARN" ]; then
            echo "❌ LAMBDA_ROLE_ARN 환경변수 필요"
            echo "   export LAMBDA_ROLE_ARN=arn:aws:iam::<account-id>:role/<role-name>"
            exit 1
        fi

        aws lambda create-function \
            --function-name "$FUNCTION_NAME" \
            --runtime "$RUNTIME" \
            --handler "handler.handler" \
            --zip-file "fileb://$FUNCTION_ZIP" \
            --role "$LAMBDA_ROLE_ARN" \
            --layers "$LAYER_ARN" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY" \
            --architectures x86_64 \
            --region "$AWS_REGION" > /dev/null
    fi

    echo "✓ 함수 배포 완료: $FUNCTION_NAME"
    echo "  Region: $AWS_REGION"
}

case "$MODE" in
    --layer-only)    deploy_layer ;;
    --function-only) deploy_function ;;
    *)               deploy_layer && deploy_function ;;
esac

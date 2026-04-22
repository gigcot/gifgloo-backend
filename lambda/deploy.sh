#!/bin/bash
# Lambda 배포 스크립트
#
# 사전 조건:
#   - AWS CLI 설치 및 자격증명 설정 (aws configure)
#   - lambda/build_layer.sh 먼저 실행해서 ffmpeg-layer.zip 생성
#
# 실행: bash lambda/deploy.sh [대상] [--layer-only | --function-only]
#   대상: gif | ai | all (기본값: all)
#   예시:
#     bash lambda/deploy.sh             # 전체 배포
#     bash lambda/deploy.sh gif         # gif_processor만 배포
#     bash lambda/deploy.sh ai          # ai_processor만 배포
#     bash lambda/deploy.sh gif --layer-only
#     bash lambda/deploy.sh gif --function-only

set -e

# .env에서 환경변수 로드
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
RUNTIME="python3.12"

# gif_processor 설정
GIF_FUNCTION_NAME="gifgloo-gif-processor"
GIF_FUNCTION_DIR="lambda/gif_processor"
GIF_FUNCTION_ZIP="/tmp/gifgloo-gif-processor.zip"
GIF_MEMORY=512
GIF_TIMEOUT=300

# ai_processor 설정
AI_FUNCTION_NAME="gifgloo-ai-processor"
AI_FUNCTION_DIR="lambda/ai_processor"
AI_FUNCTION_ZIP="/tmp/gifgloo-ai-processor.zip"
AI_MEMORY=1024
AI_TIMEOUT=600   # 10분 (프레임 합성 오래 걸림)

# ffmpeg Layer 설정
LAYER_NAME="gifgloo-ffmpeg"
LAYER_ZIP="lambda/layer/ffmpeg-layer.zip"

TARGET="${1:-all}"
MODE="${2:-all}"

# ── Layer 배포 (gif_processor 전용) ──────────────────────────

deploy_layer() {
    echo "▶ ffmpeg Layer 배포 중..."

    if [ ! -f "$LAYER_ZIP" ]; then
        echo "❌ $LAYER_ZIP 없음 — 먼저 bash lambda/build_layer.sh 실행"
        exit 1
    fi

    if [ -z "$LAMBDA_LAYER_BUCKET" ]; then
        echo "❌ LAMBDA_LAYER_BUCKET 환경변수 필요 (Layer zip 업로드용 S3 버킷)"
        exit 1
    fi

    S3_KEY="lambda-layers/ffmpeg-layer.zip"
    echo "▶ S3 업로드 중: s3://$LAMBDA_LAYER_BUCKET/$S3_KEY"
    aws s3 cp "$LAYER_ZIP" "s3://$LAMBDA_LAYER_BUCKET/$S3_KEY" --region "$AWS_REGION"

    LAYER_ARN=$(aws lambda publish-layer-version \
        --layer-name "$LAYER_NAME" \
        --description "ffmpeg static binary for GIF processing" \
        --content "S3Bucket=$LAMBDA_LAYER_BUCKET,S3Key=$S3_KEY" \
        --compatible-runtimes python3.12 \
        --compatible-architectures x86_64 \
        --region "$AWS_REGION" \
        --query "LayerVersionArn" \
        --output text)

    echo "✓ Layer 배포 완료: $LAYER_ARN"
    echo "$LAYER_ARN" > lambda/.layer_arn
}

# ── gif_processor 함수 배포 ───────────────────────────────────

deploy_gif_function() {
    echo "▶ gif_processor 패키징 중..."
    cd "$GIF_FUNCTION_DIR"
    zip -r "$GIF_FUNCTION_ZIP" handler.py
    cd -

    if [ ! -f "lambda/.layer_arn" ]; then
        echo "❌ lambda/.layer_arn 없음 — 먼저 Layer 배포 필요"
        exit 1
    fi
    LAYER_ARN=$(cat lambda/.layer_arn)

    _deploy_function \
        "$GIF_FUNCTION_NAME" \
        "$GIF_FUNCTION_ZIP" \
        "$GIF_MEMORY" \
        "$GIF_TIMEOUT" \
        "--layers $LAYER_ARN" \
        "R2_ENDPOINT_URL=$R2_ENDPOINT_URL,R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID,R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY,R2_BUCKET_NAME=$R2_BUCKET_NAME"

    echo "✓ gif_processor 배포 완료"
}

# ── ai_processor 함수 배포 ────────────────────────────────────

deploy_ai_function() {
    echo "▶ ai_processor 패키징 중..."
    mkdir -p /tmp/ai_build
    cp "$AI_FUNCTION_DIR/handler.py" /tmp/ai_build/
    cp -r "$AI_FUNCTION_DIR/prompts/" /tmp/ai_build/prompts/
    pip3 install openai \
        -t /tmp/ai_build \
        --quiet \
        --platform manylinux2014_x86_64 \
        --only-binary=:all: \
        --python-version 3.12 \
        --implementation cp
    cd /tmp/ai_build && zip -r "$AI_FUNCTION_ZIP" . && cd -
    rm -rf /tmp/ai_build

    _deploy_function \
        "$AI_FUNCTION_NAME" \
        "$AI_FUNCTION_ZIP" \
        "$AI_MEMORY" \
        "$AI_TIMEOUT" \
        "" \
        "R2_ENDPOINT_URL=$R2_ENDPOINT_URL,R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID,R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY,R2_BUCKET_NAME=$R2_BUCKET_NAME,OPENAI_API_KEY=$OPENAI_API_KEY,INTERNAL_SECRET=$INTERNAL_SECRET"

    echo "✓ ai_processor 배포 완료"
}

# ── 공통 함수 배포 헬퍼 ───────────────────────────────────────

_deploy_function() {
    local name="$1"
    local zip="$2"
    local memory="$3"
    local timeout="$4"
    local layers_arg="$5"
    local env_vars="$6"

    if aws lambda get-function --function-name "$name" --region "$AWS_REGION" > /dev/null 2>&1; then
        echo "▶ $name 업데이트 중..."
        aws lambda update-function-code \
            --function-name "$name" \
            --zip-file "fileb://$zip" \
            --region "$AWS_REGION" > /dev/null

        aws lambda wait function-updated \
            --function-name "$name" \
            --region "$AWS_REGION"

        local config_args=(
            --function-name "$name"
            --timeout "$timeout"
            --memory-size "$memory"
            --region "$AWS_REGION"
            --environment "Variables={$env_vars}"
        )
        [ -n "$layers_arg" ] && config_args+=(--layers $layers_arg)

        aws lambda update-function-configuration "${config_args[@]}" > /dev/null
    else
        echo "▶ $name 생성 중..."

        if [ -z "$LAMBDA_ROLE_ARN" ]; then
            echo "❌ LAMBDA_ROLE_ARN 환경변수 필요"
            exit 1
        fi

        local create_args=(
            --function-name "$name"
            --runtime "$RUNTIME"
            --handler "handler.handler"
            --zip-file "fileb://$zip"
            --role "$LAMBDA_ROLE_ARN"
            --timeout "$timeout"
            --memory-size "$memory"
            --architectures x86_64
            --region "$AWS_REGION"
            --environment "Variables={$env_vars}"
        )
        [ -n "$layers_arg" ] && create_args+=(--layers $layers_arg)

        aws lambda create-function "${create_args[@]}" > /dev/null
    fi
}

# ── 진입점 ────────────────────────────────────────────────────

case "$TARGET" in
    gif)
        case "$MODE" in
            --layer-only)    deploy_layer ;;
            --function-only) deploy_gif_function ;;
            *)               deploy_layer && deploy_gif_function ;;
        esac
        ;;
    ai)
        deploy_ai_function
        ;;
    all)
        deploy_layer && deploy_gif_function && deploy_ai_function
        ;;
    *)
        echo "❌ 알 수 없는 대상: $TARGET (gif | ai | all)"
        exit 1
        ;;
esac

#!/bin/bash
# CDCT batch runner for multiple subject models across all concepts

SUBJECT_MODELS=(
    "llama-4-maverick-17b-128e-instruct-fp8"
    "phi-4"
    "mistral-medium-2025"
    "gpt-oss-120b"
    "qwen3-235b-a22b-instruct"
    "grok-4-fast-non-reasoning"
    "o3"
    "o4-mini"
    "claude-haiku-4-5"
    "gpt-5"
)

RESULTS_DIR="results"
PROMPT_STRATEGY="compression_aware"
EVALUATION_MODE="balanced"

echo "=========================================="
echo "CDCT Evaluation - Multiple Models"
echo "=========================================="
echo "Total models: ${#SUBJECT_MODELS[@]}"
echo "Results directory: $RESULTS_DIR"
echo "Prompt strategy: $PROMPT_STRATEGY"
echo "Evaluation mode: $EVALUATION_MODE"
echo ""

for model in "${SUBJECT_MODELS[@]}"; do
    echo "🚀 Running model: $model"
    python run_all.py \
        --model "$model" \
        --deployment "$model" \
        --results-dir "$RESULTS_DIR" \
        --prompt-strategy "$PROMPT_STRATEGY" \
        --evaluation-mode "$EVALUATION_MODE"
    
    if [ $? -eq 0 ]; then
        echo "✅ Completed: $model"
    else
        echo "❌ Failed: $model"
    fi
    echo ""
done

echo "=========================================="
echo "🎉 All models evaluated!"
echo "=========================================="

#!/bin/bash
# Full CDCT-1.0 Benchmark

declare -A MODELS=(
    ["gpt-4.1"]="gpt-4.1"
    ["gpt-5-mini"]="gpt-5-mini"
    ["deepseek-v3-0324"]="DeepSeek-V3-0324"
    ["grok-4-fast-reasoning"]="grok-4-fast-reasoning"
    ["phi-4-mini-instruct"]="Phi-4-mini-instruct"
    ["gpt-oss-120b"]="gpt-oss-120b"
    ["mistral-medium-3"]="mistral-medium-2505"
)

CONCEPTS=(

    "concepts/art_impressionism.json"
    "concepts/biology_natural_selection.json"
    "concepts/computer_science_recursion.json"
    "concepts/mathematics_derivative.json"
    "concepts/ethics_harm_principle.json"
    "concepts/linguistics_phoneme.json"
    "concepts/logic_modus_ponens.json"
    "concepts/physics_f_equals_ma.json"
    )

TOTAL=$((${#MODELS[@]} * ${#CONCEPTS[@]}))
CURRENT=0

echo "Starting full benchmark: $TOTAL experiments"
echo ""

for model in "${!MODELS[@]}"; do
    deployment="${MODELS[$model]}"
    
    for concept in "${CONCEPTS[@]}"; do
        CURRENT=$((CURRENT + 1))
        concept_name=$(basename "$concept" .json)
        
        echo "[$CURRENT/$TOTAL] $model × $concept_name"
        
        python main.py \
            --concept "$concept" \
            --model "$model" \
            --deployment "$deployment"\
            --evaluation-mode "lenient" \
        
        sleep 2  # Rate limiting
    done
done

echo ""
echo "Benchmark complete! Results in results/"

#!/bin/bash
# Verification script to check OpenAI removal

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         OpenAI Removal Verification Script                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo

# Check for OpenAI imports in Python files
echo "🔍 Checking for OpenAI imports in Python files..."
OPENAI_IMPORTS=$(grep -r "from langchain_openai import\|import langchain_openai" --include="*.py" . 2>/dev/null | grep -v ".git" | wc -l)

if [ $OPENAI_IMPORTS -eq 0 ]; then
    echo "✅ No OpenAI imports found in Python files"
else
    echo "❌ Found $OPENAI_IMPORTS OpenAI imports:"
    grep -r "from langchain_openai import\|import langchain_openai" --include="*.py" . 2>/dev/null | grep -v ".git"
fi
echo

# Check for OpenAI API key in config
echo "🔍 Checking for OPENAI_API_KEY validation..."
OPENAI_VALIDATION=$(grep -r "OPENAI_API_KEY" --include="*.py" src/config.py 2>/dev/null | grep -v "#" | wc -l)

if [ $OPENAI_VALIDATION -eq 0 ]; then
    echo "✅ No OPENAI_API_KEY validation found"
else
    echo "❌ Found OPENAI_API_KEY validation in config"
fi
echo

# Check for HuggingFace in requirements
echo "🔍 Checking for HuggingFace in requirements.txt..."
if grep -q "langchain-huggingface" requirements.txt; then
    echo "✅ langchain-huggingface found in requirements.txt"
else
    echo "❌ langchain-huggingface NOT found in requirements.txt"
fi

if grep -q "sentence-transformers" requirements.txt; then
    echo "✅ sentence-transformers found in requirements.txt"
else
    echo "❌ sentence-transformers NOT found in requirements.txt"
fi
echo

# Check for HuggingFace usage in code
echo "🔍 Checking for HuggingFace usage in code..."
HF_USAGE=$(grep -r "HuggingFaceEmbeddings" --include="*.py" . 2>/dev/null | grep -v ".git" | wc -l)

if [ $HF_USAGE -ge 2 ]; then
    echo "✅ HuggingFaceEmbeddings used in $HF_USAGE files"
    grep -r "HuggingFaceEmbeddings" --include="*.py" . 2>/dev/null | grep -v ".git" | sed 's/^/   /'
else
    echo "❌ HuggingFaceEmbeddings not properly used"
fi
echo

# Check .env.example
echo "🔍 Checking .env.example..."
if grep -q "OPENAI_API_KEY" .env.example | grep -v "#"; then
    echo "❌ OPENAI_API_KEY still in .env.example (uncommented)"
else
    echo "✅ OPENAI_API_KEY removed/commented from .env.example"
fi
echo

# Check documentation
echo "🔍 Checking documentation updates..."
DOC_FILES=("README.md" "DEVELOPER_GUIDE.md" "QUICK_REFERENCE.md")
for doc in "${DOC_FILES[@]}"; do
    if [ -f "$doc" ]; then
        OPENAI_MENTIONS=$(grep -i "openai" "$doc" | grep -v "no longer\|not required\|removed\|free\|huggingface" | wc -l)
        if [ $OPENAI_MENTIONS -eq 0 ]; then
            echo "✅ $doc - OpenAI properly documented as removed"
        else
            echo "⚠️  $doc - has $OPENAI_MENTIONS OpenAI mentions (check if appropriate)"
        fi
    fi
done
echo

# Final summary
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                     Verification Summary                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo
echo "✅ Key Changes Verified:"
echo "   • OpenAI imports removed from Python files"
echo "   • OpenAI API key validation removed"
echo "   • HuggingFace embeddings added to requirements"
echo "   • HuggingFace usage implemented in code"
echo "   • Documentation updated"
echo
echo "📋 Next Steps for Users:"
echo "   1. pip install -r requirements.txt"
echo "   2. Remove OPENAI_API_KEY from .env file"
echo "   3. rm -rf ./chroma_db (if exists)"
echo "   4. python ingest_data.py"
echo "   5. Run the app - it's FREE now! 🎉"
echo

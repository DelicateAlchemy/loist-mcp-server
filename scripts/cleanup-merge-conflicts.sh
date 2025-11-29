#!/bin/bash

# Script to clean up merge conflict markers in project files
# Based on Perplexity research recommendations

echo "🧹 Cleaning up merge conflict markers..."

# Find all project files with merge conflicts (excluding .venv and __pycache__)
conflict_files=$(grep -r -l '<<<<<<<\|======\|>>>>>>>' . --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=.git)

if [ -z "$conflict_files" ]; then
    echo "✅ No merge conflict markers found in project files"
    exit 0
fi

echo "📋 Found merge conflicts in the following files:"
echo "$conflict_files"
echo ""

# Clean up each file
for file in $conflict_files; do
    echo "🔧 Cleaning up: $file"
    
    # Create backup
    cp "$file" "$file.backup"
    
    # Remove merge conflict markers and empty lines between them
    sed -i '' '/^<<<<<<< /d; /^=======$/d; /^>>>>>>> /d' "$file"
    
    # Remove multiple consecutive empty lines at end of file
    sed -i '' -e :a -e '/^\s*$/N;ba' -e 's/\n*$//' "$file"
    
    echo "✅ Cleaned: $file"
done

echo ""
echo "🎉 Merge conflict cleanup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Review the changes with: git diff"
echo "2. Test the code to ensure it still works"
echo "3. Stage the cleaned files: git add ."
echo "4. Commit the cleanup: git commit -m 'Clean up merge conflict markers'"
echo ""
echo "⚠️  Backup files created with .backup extension"




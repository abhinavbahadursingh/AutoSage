import os, sys
sys.path.insert(0, r'D:\autoSage\backend')

# Search for dataset_name references in Python files
for root, dirs, files in os.walk('D:\autoSage\backend'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r') as fh:
                    content = fh.read()
                    count = content.lower().count('dataset_name')
                    if count > 0:
                        print(f'{path}: {count} occurrences')
            except:
                pass
"
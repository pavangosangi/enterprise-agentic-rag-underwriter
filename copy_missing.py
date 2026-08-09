import shutil
import os

def migrate_folders():
    src_base = r"d:\genai"
    dest_base = r"d:\genai-public"
    
    folders_to_copy = ["vite-app", "eval_mcp", "utility", "data", "groundtruth"]
    
    # Ignore patterns to keep the new workspace clean
    ignore_func = shutil.ignore_patterns(
        "node_modules", 
        "__pycache__", 
        ".deepeval", 
        "*.pyc"
    )
    
    for folder in folders_to_copy:
        src = os.path.join(src_base, folder)
        dest = os.path.join(dest_base, folder)
        
        if os.path.exists(src):
            if os.path.exists(dest):
                print(f"Skipping {folder}, already exists in {dest_base}")
            else:
                print(f"Copying {folder}...")
                shutil.copytree(src, dest, ignore=ignore_func)
                print(f"Successfully copied {folder} without caches/modules.")
        else:
            print(f"Source folder {src} does not exist.")

if __name__ == "__main__":
    migrate_folders()

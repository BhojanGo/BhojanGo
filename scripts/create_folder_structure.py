import os
from pathlib import Path

# Configuration
START_DIR = Path(".")  # Current directory
OUTPUT_PATH = Path("docs/folder_structure.md")

DEFAULT_EXCLUDE_FOLDERS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", ".hypothesis", ".ipynb_checkpoints", "venv", ".venv",
    "env", ".env", ".eggs", "node_modules", "dist", "build", ".next",
    ".nuxt", ".svelte-kit", ".parcel-cache", ".turbo", ".vite", ".cache",
    ".angular", "storybook-static", '_archive', '.kimchi', '.husky', '.turbo', '.venv',
    '.git.disabled', 'latest_files',
    #'chat_downloads', 'logs'
}

def generate_tree(dir_path: Path, prefix: str = "") -> list:
    """Recursively generates a tree structure as a list of strings."""
    tree_lines = []
    
    try:
        # Fetch and sort contents (directories first, then files)
        contents = sorted(
            list(dir_path.iterdir()), 
            key=lambda p: (not p.is_dir(), p.name.lower())
        )
    except PermissionError:
        return []

    # Filter out excluded folders
    contents = [
        path for path in contents 
        if not (path.is_dir() and path.name in DEFAULT_EXCLUDE_FOLDERS)
    ]

    pointers = ["├── "] * (len(contents) - 1) + ["└── "] if contents else []

    for pointer, path in zip(pointers, contents):
        if path.is_dir():
            tree_lines.append(f"{prefix}{pointer}{path.name}/")
            # If it's the last item, change the prefix indentation shape
            extension = "    " if pointer == "└── " else "│   "
            tree_lines.extend(generate_tree(path, prefix + extension))
        else:
            tree_lines.append(f"{prefix}{pointer}{path.name}")
            
    return tree_lines

def main():
    print("Generating project tree...")
    
    # Generate tree lines
    root_name = START_DIR.resolve().name
    tree_output = [f"{root_name}/"] + generate_tree(START_DIR)
    
    # Wrap in markdown code blocks
    markdown_content = "# Project Folder Structure\n\n```text\n" + "\n".join(tree_output) + "\n```\n"
    
    # Ensure the docs directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"Success! Tree structure saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
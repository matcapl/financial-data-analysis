#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path
from difflib import get_close_matches

FIELDS_YAML = Path("config/fields.yaml")

def load_fields():
    with open(FIELDS_YAML) as f:
        data = yaml.safe_load(f)
    return data

def save_fields(data):
    with open(FIELDS_YAML, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

def prompt(prompt_text):
    resp = input(prompt_text).strip().lower()
    return resp in ("y", "yes")

def main():
    data = load_fields()
    fields = data.get("fields", {})
    print("Available fields:")
    for name in fields:
        print("  -", name)
    field = input("\nEnter the field key to update (e.g. line_item): ").strip()
    if field not in fields:
        # suggest similar
        close = get_close_matches(field, fields.keys(), n=1)
        if close:
            use = prompt(f"Field '{field}' not found. Did you mean '{close[0]}'? [y/N]: ")
            if use:
                field = close[0]
            else:
                print("Aborting.")
                sys.exit(1)
        else:
            print(f"No matching field for '{field}'. Aborting.")
            sys.exit(1)

    aliases = fields[field].setdefault("synonyms", [])
    new_alias = input(f"Enter the new alias to add to '{field}': ").strip()
    if new_alias in aliases:
        print(f"Alias '{new_alias}' already exists for '{field}'. Nothing to do.")
        sys.exit(0)

    print(f"\nCurrent aliases for '{field}': {aliases}")
    confirm = prompt(f"Add '{new_alias}' to '{field}'? [y/N]: ")
    if not confirm:
        print("Aborted by user.")
        sys.exit(0)

    aliases.append(new_alias)
    # Optionally keep sorted
    fields[field]["synonyms"] = sorted(set(aliases), key=str.lower)
    save_fields(data)
    print(f"✅ Added alias '{new_alias}' to field '{field}' in {FIELDS_YAML}.")

if __name__ == "__main__":
    main()

"""Quick test to debug enum conversion."""

from src.shared.models import SourceType

# Simulate what update_profile does
updates = {
    "preferred_sources": [SourceType.ARXIV, SourceType.YOUTUBE]
}

print("Original updates:", updates)
print("Type of first element:", type(updates["preferred_sources"][0]))

if "preferred_sources" in updates:
    converted_sources = []
    for source in updates["preferred_sources"]:
        print(f"Processing source: {source}, type: {type(source)}")
        if isinstance(source, SourceType):
            # Use .value to get lowercase string like "arxiv"
            print(f"  -> Converting to value: {source.value}")
            converted_sources.append(source.value)
        elif isinstance(source, str):
            # If it's already a string, ensure it's lowercase
            print(f"  -> Converting string to lowercase: {source.lower()}")
            converted_sources.append(source.lower())
        else:
            print(f"  -> Keeping as-is")
            converted_sources.append(source)
    updates["preferred_sources"] = converted_sources

print("Converted updates:", updates)
print("Type of first element after conversion:", type(updates["preferred_sources"][0]))

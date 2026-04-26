import json
import sys
from feyn_parser import FeynExtractor
from feyn_notation import FeynNotator

def run_feynmap(project_dir):
    extractor = FeynExtractor(project_dir)
    graph_data = extractor.scan()

    # Feature Pathfinding (Simulated for MVP)
    # This represents the 'Physics' of a Bounty Submission
    bounty_trace = [
        ("PROPAGATOR", "POST /api/bounty/"),
        ("VERTEX", "BountyCreateView"),
        ("TRANSFORM", "BountySerializer"),
        ("PARTICLE", "BountyModel"),
        ("VIRTUAL", "WalletUpdateSignal")
    ]

    notation = FeynNotator.generate_string(bounty_trace)

    print("="*40)
    print(" FEYNMAP MVP OUTPUT ")
    print("="*40)
    # Save the full graph for the AI agent's detailed queries
    with open("feyn_graph.json", "w") as f:
        json.dump(graph_data, f, indent=4)
    print("\n[SUCCESS] Graph data saved to feyn_graph.json")

    try:
        print(f"\n[FEYNMAN NOTATION]\n{notation}")
    except UnicodeEncodeError:
        print(f"\n[FEYNMAN NOTATION] (Unicode display error in console, but graph saved)")
    
    print(f"\n[UNIFIED SCHEMA NODES FOUND]\n{len(graph_data['nodes'])} items detected.")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    run_feynmap(path)
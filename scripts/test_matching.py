import sys
import os
import json
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.matching_agent import run_matching

# User Provided Example Data subset for quick testing
example_data = [
    {
      "medication_name": "SOLUC. DEXTROSA",
      "presentation": "5% env. x 500 ml. B. BR",
      "amount": 3.0,
      "cost_per_unit": 19023.7,
      "total_cost": 57071.1,
      "source_page": 1
    },
    {
      "medication_name": "Spongostan",
      "presentation": "Unknown",
      "amount": 1.0,
      "cost_per_unit": 37000.0,
      "total_cost": 37000.0,
      "source_page": 1
    },
    {
      "medication_name": "PARACETAMOL sol. Freeflex iny.",
      "presentation": "x 100 ml. KA",
      "amount": 1.0,
      "cost_per_unit": 30817.26,
      "total_cost": 30817.26,
      "source_page": 1
    },
    {
      "medication_name": "DICLOFENAC",
      "presentation": "75 mg/3 ml. a. x 100 DENVER",
      "amount": 1.0,
      "cost_per_unit": 10270.1,
      "total_cost": 10270.1,
      "source_page": 1
    },
    {
      "medication_name": "RANITIDINA",
      "presentation": "50 mg/ 5 ml iny. a. x 100 DENVE",
      "amount": 1.0,
      "cost_per_unit": 11477.12,
      "total_cost": 11477.12,
      "source_page": 1
    }
]

async def main():
    print("Starting matching agent execution...")
    graph_path = "agents/resources/data_grafo_structured.md"
    
    if not os.path.exists(graph_path):
        print(f"Error: {graph_path} not found. Running creator first...")
        return

    try:
        result = await run_matching(example_data, graph_path=graph_path)
        
        if result:
            print("\n=== Matching Result ===")
            print(json.dumps(result, indent=2))
            
            output_path = "tests/test_matching_result.json"
            with open(output_path, "w", encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\nSaved result to {output_path}")
        else:
            print("\nFailed to get typed result state back.")
            
    except Exception as e:
        print(f"Exception encountered: {e}")

if __name__ == "__main__":
    asyncio.run(main())

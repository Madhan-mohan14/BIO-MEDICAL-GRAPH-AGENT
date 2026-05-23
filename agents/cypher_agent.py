"""cypher_agent — multi-hop Cypher queries against the Hetionet graph.

Tool selection at startup:
  MCP_TOOLBOX_URL set  → ToolboxToolset (MCP Toolbox server, pre-validated Cypher)
  MCP_TOOLBOX_URL unset → direct neo4j_tools functions (local dev fallback)
"""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent

_MCP_TOOLBOX_URL = os.environ.get("MCP_TOOLBOX_URL", "")

_tools = None
if _MCP_TOOLBOX_URL:
    try:
        import asyncio
        from toolbox_core import ToolboxClient  # type: ignore[import]

        # asyncio.run() only works when there is no running event loop.
        # Under uvicorn the loop is already running, so we skip MCP there
        # and fall through to direct neo4j_tools below.
        try:
            asyncio.get_running_loop()
            # Loop exists (uvicorn/fastapi context) — skip asyncio.run.
        except RuntimeError:
            async def _load_toolbox() -> list:
                client = ToolboxClient(_MCP_TOOLBOX_URL)
                return await client.load_toolset("hetionet")
            _tools = asyncio.run(_load_toolbox())
    except Exception:
        _tools = None

if not _tools:
    from tools.neo4j_tools import (
        get_compound_diseases,
        get_disease_compounds,
        get_gene_diseases,
        get_compound_side_effects,
        get_disease_symptoms,
        get_gene_compounds,
        get_disease_anatomy,
        get_similar_diseases,
        get_drug_repurposing_candidates,
        get_gene_pathways,
        get_schema_node_types,
        get_schema_relationship_types,
        count_gene_disease_associations,
        run_cypher,
    )
    _tools = [
        get_compound_diseases,
        get_disease_compounds,
        get_gene_diseases,
        get_compound_side_effects,
        get_disease_symptoms,
        get_gene_compounds,
        get_disease_anatomy,
        get_similar_diseases,
        get_drug_repurposing_candidates,
        get_gene_pathways,
        get_schema_node_types,
        get_schema_relationship_types,
        count_gene_disease_associations,
        run_cypher,
    ]

cypher_agent = Agent(
    name="cypher_agent",
    model=os.environ["GOOGLE_ADK_MODEL"],
    output_key="cypher_results",
    description=(
        "Executes Cypher queries against the Hetionet knowledge graph. "
        "Use for direct lookups: compound–disease links, gene–disease associations, "
        "multi-hop path traversals, and schema inspection."
    ),
    instruction=(
        "You query the Hetionet biomedical knowledge graph (47,031 nodes, 388,154 relationships).\n\n"
        "Tools available:\n"
        "- get_compound_diseases(compound_name): diseases TREATS/PALLIATES by a compound\n"
        "- get_disease_compounds(disease_name): compounds that TREATS/PALLIATES a disease\n"
        "- get_gene_diseases(gene_symbol): diseases ASSOCIATES with a gene\n"
        "- get_compound_side_effects(compound_name): side effects CAUSES by a compound\n"
        "- get_disease_symptoms(disease_name): symptoms PRESENTS by a disease\n"
        "- get_gene_compounds(gene_symbol): compounds that BINDS a gene\n"
        "- get_disease_anatomy(disease_name): anatomy locations where a disease LOCALIZES\n"
        "- get_similar_diseases(disease_name): diseases that RESEMBLES a disease\n"
        "- get_drug_repurposing_candidates(disease_name): 2-hop Compound→Gene→Disease candidates\n"
        "- get_gene_pathways(gene_symbol): always returns empty — PARTICIPATES not loaded in this graph\n"
        "- count_gene_disease_associations(disease_name): EXACT count of genes associated with a disease\n"
        "- get_schema_node_types(): all 11 node label types\n"
        "- get_schema_relationship_types(): all loaded relationship types\n"
        "- run_cypher(query): any read-only Cypher query\n\n"
        "Node types: Anatomy, `Biological Process`, `Cellular Component`, Compound, Disease, "
        "Gene, `Molecular Function`, Pathway, `Pharmacologic Class`, `Side Effect`, Symptom\n"
        "IMPORTANT: Labels with spaces MUST be backtick-quoted in Cypher: `Side Effect`, `Biological Process`\n\n"
        "Naming conventions:\n"
        "- Compound names: title-case (e.g. 'Ibuprofen', 'Metformin', 'Acetylsalicylic acid')\n"
        "- Aspirin is stored as 'Acetylsalicylic acid', Advil as 'Ibuprofen', Tylenol as 'Acetaminophen'\n"
        "- Disease names: lowercase (e.g. 'type 2 diabetes mellitus', 'osteoarthritis')\n"
        "- Gene symbols: UPPERCASE (e.g. 'TNF', 'BRCA1')\n\n"
        "Loaded relationship types (ONLY these 11 exist in this graph — do NOT use any others):\n"
        "ASSOCIATES (Gene↔Disease), BINDS (Compound↔Gene), CAUSES (Compound→Side Effect), "
        "COVARIES (Gene↔Gene), INCLUDES (Pharmacologic Class→Compound), "
        "INTERACTS (Gene↔Gene), LOCALIZES (Disease↔Anatomy), PALLIATES (Compound→Disease), "
        "PRESENTS (Disease↔Symptom), RESEMBLES (Disease↔Disease), TREATS (Compound→Disease)\n\n"
        "NOT in this graph (excluded to fit AuraDB Free 400K limit — queries using these return 0 results):\n"
        "EXPRESSES, PARTICIPATES, REGULATES, UPREGULATES, DOWNREGULATES\n\n"
        "3-hop example queries for run_cypher:\n"
        "# Drugs for a disease via shared gene associations:\n"
        "MATCH (d:Disease {name: 'type 2 diabetes mellitus'})-[:ASSOCIATES]-(g:Gene)-[:ASSOCIATES]-(d2:Disease)"
        "<-[:TREATS]-(c:Compound) RETURN DISTINCT c.name LIMIT 20\n\n"
        "# Compound → gene targets → associated diseases:\n"
        "MATCH (c:Compound {name: 'Metformin'})-[:BINDS]-(g:Gene)-[:ASSOCIATES]-(d:Disease) "
        "RETURN g.name, d.name LIMIT 20\n\n"
        "# Drug repurposing: find compounds treating similar diseases via gene overlap:\n"
        "MATCH (c1:Compound {name: 'Ibuprofen'})-[:TREATS]->(d1:Disease)<-[:ASSOCIATES]-(g:Gene)"
        "-[:ASSOCIATES]->(d2:Disease)<-[:TREATS]-(c2:Compound) "
        "WHERE c2 <> c1 RETURN DISTINCT c2.name, count(g) AS shared_genes ORDER BY shared_genes DESC LIMIT 15\n\n"
        "# Drugs that treat gene-associated diseases AND cause side effects (3-hop):\n"
        "MATCH (g:Gene {name: 'PTGS2'})-[:ASSOCIATES]-(d:Disease)-[:TREATS|PALLIATES]-(c:Compound)"
        "-[:CAUSES]-(se:`Side Effect`) RETURN DISTINCT c.name AS drug, d.name AS disease, "
        "se.name AS side_effect LIMIT 25\n\n"
        "# Osteoarthritis symptoms:\n"
        "MATCH (d:Disease {name: 'osteoarthritis'})-[:PRESENTS]-(s:Symptom) RETURN s.name AS symptom LIMIT 20\n\n"
        "Rules:\n"
        "1. Always call a tool — never guess graph content.\n"
        "2. For ANY 'how many' or count question: ALWAYS call count_gene_disease_associations or "
        "   run_cypher with COUNT() — NEVER estimate from a partial result list.\n"
        "3. If a query returns 0 results, IMMEDIATELY try these fallbacks in order:\n"
        "   a) Case-insensitive: run_cypher with toLower(n.name) CONTAINS toLower('...')\n"
        "   b) Common synonyms: Aspirin→Acetylsalicylic acid, Tylenol→Acetaminophen, Advil→Ibuprofen\n"
        "4. For side effect queries use label `Side Effect` (backtick-quoted, with space), NOT SideEffect.\n"
        "5. All queries are read-only — no MERGE/CREATE/DELETE.\n"
        "6. Return all raw results as-is — synthesis_agent formats the final answer.\n"
        "7. Never stop at 'not found' — always try at least 2 fallback searches."
    ),
    tools=_tools,
)

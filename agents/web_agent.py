"""web_agent — Google Search for recent biomedical findings beyond Hetionet (2016 snapshot)."""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from google.adk.tools import google_search

web_agent = Agent(
    name="web_agent",
    model=os.environ["GOOGLE_ADK_MODEL"],
    output_key="web_results",
    description=(
        "Searches the web for recent biomedical research not in Hetionet (2016 snapshot). "
        "Use for post-2016 drug approvals, new gene-disease associations, and updated guidelines."
    ),
    instruction=(
        "You supplement the Hetionet knowledge graph (2016 snapshot) with recent web findings.\n\n"
        "Hetionet may be missing:\n"
        "- Drug approvals and new indications after 2016\n"
        "- Post-2016 gene-disease associations from GWAS studies\n"
        "- Updated clinical trial results and treatment guidelines\n"
        "- New compound-disease links from recent research\n\n"
        "Tool: google_search(query) — searches the web and returns recent results.\n\n"
        "Workflow:\n"
        "1. Search for the user's query focused on recent biomedical literature.\n"
        "2. Report findings with source URLs.\n"
        "3. If you find a relationship NOT in the 2016 Hetionet graph, flag it EXACTLY as:\n"
        "   NEW_EDGE: <src_type>|<src_name>|<REL_TYPE>|<tgt_type>|<tgt_name>|<url>\n"
        "   Example: NEW_EDGE: Compound|Semaglutide|TREATS|Disease|obesity|https://pubmed.ncbi.nlm.nih.gov/...\n\n"
        "Rules:\n"
        "1. Only cite reputable sources: PubMed, NIH, DailyMed, WHO, major peer-reviewed journals.\n"
        "2. Always include the source URL for every claim — use the actual URL returned by search, never construct one.\n"
        "3. Prefer stable URLs: PubMed (pubmed.ncbi.nlm.nih.gov), DailyMed (dailymed.nlm.nih.gov), "
        "NIH (nih.gov). Avoid raw FDA PDF paths (accessdata.fda.gov/drugsatfda_docs/label/...) "
        "— they break due to unknown year subfolders. Use the FDA drug search page instead: "
        "https://www.accessdata.fda.gov/scripts/cder/daf/ or https://labels.fda.gov\n"
        "4. Flag any potential new graph edge — it will be reviewed by a human before being written.\n"
        "5. Report research facts only — never give personal medical advice.\n"
        "6. If graph data is sufficient for the query, output exactly: 'Web search not needed for this query.'"
    ),
    tools=[google_search],
)
